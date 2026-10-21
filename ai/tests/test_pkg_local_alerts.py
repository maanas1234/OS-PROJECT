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


def test_bad_first_reply_is_retried(monkeypatch):
    replies = iter(["I think we should\n/Safety/Risk:** read-only", '{"command": "df -h", "explanation": "e", "risk": "low"}'])
    monkeypatch.setattr(tr, "_backends", lambda: [("local", lambda text: next(replies))])
    assert tr.translate("disk free").command == "df -h"


def test_local_key_sent_as_bearer(monkeypatch):
    seen = {}
    monkeypatch.setattr(tr, "_post", lambda url, headers, body, timeout, who: seen.update(h=headers) or {"choices": [{"message": {"content": "{}"}}]})
    tr.call_local("x", "http://h/v1", "auto", api_key="k")
    assert seen["h"] == {"authorization": "Bearer k"}


# ---- config file ----

from nyx import config


def test_config_parse_ignores_unknown_and_comments():
    text = '# c\nANTHROPIC_API_KEY="sk-abc"\nEVIL=1\nNYX_BACKEND = local\n\nbad line\nNYX_MODEL=\n'
    assert config.parse(text) == {"ANTHROPIC_API_KEY": "sk-abc", "NYX_BACKEND": "local"}


def test_config_env_wins_and_later_file_wins(tmp_path):
    a, b = tmp_path / "a.conf", tmp_path / "b.conf"
    a.write_text("NYX_BACKEND=cloud\nNYX_MODEL=m1\n")
    b.write_text("NYX_MODEL=m2\nNYX_LOCAL_URL=http://x/v1\n")
    env = {"NYX_LOCAL_URL": "http://from-env/v1"}
    config.load([str(a), str(b), str(tmp_path / "missing.conf")], env)
    assert env == {"NYX_BACKEND": "cloud", "NYX_MODEL": "m2", "NYX_LOCAL_URL": "http://from-env/v1"}


def test_describe_masks_secrets():
    out = config.describe({"ANTHROPIC_API_KEY": "sk-ant-secretvalue", "NYX_BACKEND": "auto"})
    assert "secretvalue" not in out and "sk-a...ue" in out and "cloud, then local" in out
    assert "local only" in config.describe({})


# ---- proactive alert log + notify ----

from nyx import alerts as alerts_mod


def _write_log(path, n):
    with open(path, "w") as f:
        for i in range(n):
            f.write(json.dumps({**EVENT, "message": f"m{i}"}) + "\n")


def test_new_events_only_shows_unseen(tmp_path):
    log, off = str(tmp_path / "a.jsonl"), str(tmp_path / "c" / "off")
    _write_log(log, 2)
    assert [e["message"] for e in alerts_mod.new_events(log, off)] == ["m0", "m1"]
    assert alerts_mod.new_events(log, off) == []
    _write_log(log, 3)
    assert [e["message"] for e in alerts_mod.new_events(log, off)] == ["m2"]


def test_new_events_handles_reset_log_and_missing_file(tmp_path):
    log, off = str(tmp_path / "a.jsonl"), str(tmp_path / "off")
    _write_log(log, 5)
    alerts_mod.new_events(log, off)
    _write_log(log, 1)  # rebooted: log shorter than offset
    assert len(alerts_mod.new_events(log, off)) == 1
    assert alerts_mod.new_events(str(tmp_path / "nope"), off) == []


@pytest.mark.skipif(not hasattr(socket, "AF_UNIX"), reason="no AF_UNIX")
def test_follow_to_log_reconnects_and_appends(tmp_path):
    sock, log = str(tmp_path / "nyxd.sock"), str(tmp_path / "run" / "alerts.jsonl")
    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    srv.bind(sock)
    srv.listen(2)

    def serve():
        for n in range(2):  # daemon "restarts" once
            conn, _ = srv.accept()
            conn.sendall(json.dumps({**EVENT, "message": f"boot{n}"}).encode() + b"\n")
            conn.close()

    threading.Thread(target=serve, daemon=True).start()
    alerts_mod.follow_to_log(sock, log, retry_seconds=0, sleep=lambda s: None, max_rounds=2)
    assert [e["message"] for e in alerts_mod.read_log(log)] == ["boot0", "boot1"]
    srv.close()


# ---- apt commands from small models are routed through nyx-pkg ----

@pytest.mark.parametrize(
    "cmd,expected",
    [
        ("apt install htop", "nyx-pkg install htop"),
        ("sudo apt-get -y install htop curl", "nyx-pkg install htop curl"),
        ("sudo apt remove nginx", "nyx-pkg remove nginx"),
        ("apt purge -y nginx", "nyx-pkg remove nginx"),
    ],
)
def test_apt_commands_become_nyx_pkg(cmd, expected):
    p = from_model_reply("x", json.dumps({"command": cmd, "explanation": "e", "risk": "low"}))
    assert p.command == expected and p.risk == "med"


@pytest.mark.parametrize("cmd", ["apt update", "apt install htop && rm -rf x", "apt install $(whoami)", "apt list --installed"])
def test_other_apt_commands_untouched(cmd):
    p = from_model_reply("x", json.dumps({"command": cmd, "explanation": "e", "risk": "low"}))
    assert p.command == cmd
