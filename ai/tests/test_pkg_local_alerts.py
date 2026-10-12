import json
import os
import socket
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from nyx import translate as tr
from nyx.alerts import AlertsError, format_event, parse_event, stream_events
from nyx.cli import run_intent
from nyx.proposal import ProposalError, from_model_reply
from nyx.safety import assess


# ---- M4: package intents -> nyx-pkg ----

def pkg_reply(action, packages, risk="med"):
    return json.dumps({"pkg_request": {"action": action, "packages": packages}, "explanation": "e", "risk": risk})


def test_pkg_request_becomes_nyx_pkg_command():
    p = from_model_reply("get htop", pkg_reply("install", ["htop"]))
    assert p.command == "nyx-pkg install htop"
    assert p.risk == "med" and p.requires_confirm


def test_pkg_search_is_low_risk():
    assert from_model_reply("x", pkg_reply("search", ["video", "editor"], risk="low")).risk == "low"


@pytest.mark.parametrize(
    "bad",
    [
        pkg_reply("install", ["htop; rm -rf /"]),
        pkg_reply("install", ["$(reboot)"]),
        pkg_reply("install", ["-y"]),
        pkg_reply("install", []),
        pkg_reply("upgrade", ["htop"]),
        json.dumps({"pkg_request": "htop"}),
    ],
)
def test_bad_pkg_requests_rejected(bad):
    with pytest.raises(ProposalError):
        from_model_reply("x", bad)


def test_install_flows_through_confirm_then_runner():
    ran = []
    code = run_intent(
        "install htop", False, backend=lambda i: pkg_reply("install", ["htop"]),
        runner=lambda c, shell: ran.append(c) or 0, ask=lambda p: True,
    )
    assert code == 0 and ran == ["nyx-pkg install htop"]


def test_gate_marks_nyx_pkg_install_med():
    assert assess("nyx-pkg install htop").risk == "med"
    assert assess("nyx-pkg search htop").risk == "low"


# ---- M6: local backend + fallback ----

class FakeLLM(BaseHTTPRequestHandler):
    reply = '{"command": "ps aux --sort=-%mem | head", "explanation": "top memory", "risk": "low"}'

    def do_POST(self):
        self.rfile.read(int(self.headers["content-length"]))
        body = json.dumps({"choices": [{"message": {"content": self.reply}}]}).encode()
        self.send_response(200)
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


@pytest.fixture
def local_server():
    srv = HTTPServer(("127.0.0.1", 0), FakeLLM)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_port}/v1"
    srv.shutdown()


def test_local_backend_only(monkeypatch, local_server):
    monkeypatch.setenv("NYX_BACKEND", "local")
    monkeypatch.setenv("NYX_LOCAL_URL", local_server)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert tr.translate("most memory").command.startswith("ps aux")


def test_auto_without_key_uses_local(monkeypatch, local_server):
    monkeypatch.delenv("NYX_BACKEND", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("NYX_LOCAL_URL", local_server)
    assert tr.translate("x").command.startswith("ps aux")


def test_auto_falls_back_to_local_when_cloud_down(monkeypatch, local_server):
    monkeypatch.delenv("NYX_BACKEND", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    monkeypatch.setenv("NYX_LOCAL_URL", local_server)
    monkeypatch.setattr(tr, "API_URL", "http://127.0.0.1:1/v1/messages")  # nothing listens: airplane mode
    assert tr.translate("x").command.startswith("ps aux")


def test_both_down_reports_both(monkeypatch):
    monkeypatch.delenv("NYX_BACKEND", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    monkeypatch.setenv("NYX_LOCAL_URL", "http://127.0.0.1:1/v1")
    monkeypatch.setattr(tr, "API_URL", "http://127.0.0.1:1/v1/messages")
    with pytest.raises(tr.TranslateError) as e:
        tr.translate("x")
    assert "cloud:" in str(e.value) and "local:" in str(e.value)


def test_local_model_cannot_bypass_gate(monkeypatch, local_server):
    monkeypatch.setenv("NYX_BACKEND", "local")
    monkeypatch.setenv("NYX_LOCAL_URL", local_server)
    monkeypatch.setattr(FakeLLM, "reply", '{"command": "rm -rf /", "risk": "low"}')
    assert run_intent("x", False, runner=lambda *a, **k: pytest.fail("ran"), ask=lambda p: True) == 3


# ---- M5: alerts reader ----

EVENT = {"ts": "2026-10-12T10:00:00+00:00", "source": "ssh.service", "severity": "error", "message": "boom"}


def test_parse_event_accepts_contract_and_rejects_junk():
    assert parse_event(json.dumps(EVENT)) == EVENT
    assert parse_event("not json") is None
    assert parse_event(json.dumps({**EVENT, "severity": "fatal"})) is None
    assert parse_event(json.dumps({"ts": "x"})) is None


def test_format_event():
    assert format_event(EVENT) == "[ERROR] ssh.service: boom"
    assert "suggested: restart" in format_event({**EVENT, "suggested_action": "restart"})


def test_missing_socket(tmp_path):
    if not hasattr(socket, "AF_UNIX"):
        pytest.skip("no AF_UNIX")
    with pytest.raises(AlertsError, match="not running"):
        list(stream_events(str(tmp_path / "nope.sock")))


@pytest.mark.skipif(not hasattr(socket, "AF_UNIX"), reason="no AF_UNIX")
def test_stream_events_from_fake_daemon(tmp_path):
    path = str(tmp_path / "nyxd.sock")
    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    srv.bind(path)
    srv.listen(1)

    def serve():
        conn, _ = srv.accept()
        conn.sendall(b"garbage\n" + json.dumps(EVENT).encode() + b"\n")
        conn.close()

    threading.Thread(target=serve, daemon=True).start()
    assert list(stream_events(path)) == [EVENT]
    srv.close()
