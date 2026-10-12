"""Natural language -> Proposal.

Backends: Claude API (cloud) and an OpenAI-compatible local server (llama.cpp
`llama-server`, Ollama). NYX_BACKEND = auto (default) | cloud | local.
auto: cloud if ANTHROPIC_API_KEY is set, falls back to local when cloud is unreachable.
"""
import json
import os
import platform
import urllib.error
import urllib.request

from .proposal import Proposal, ProposalError, from_model_reply

API_URL = "https://api.anthropic.com/v1/messages"
DEFAULT_MODEL = "claude-sonnet-5-5"
DEFAULT_LOCAL_URL = "http://127.0.0.1:8080/v1"  # llama-server; Ollama is http://127.0.0.1:11434/v1

SYSTEM = """You translate a user's intent into ONE shell command for Ubuntu Linux (bash/nushell host, GNU coreutils).
Reply with ONLY a JSON object, no prose, no code fences:
{"command": "du -ah . | sort -rh | head -20", "explanation": "Lists the 20 biggest files.", "risk": "low"}
Rules:
- Prefer read-only commands. Never add sudo unless the task needs root.
- To install, remove, or search packages, do NOT write apt commands. Reply instead with:
  {"pkg_request": {"action": "install", "packages": ["htop"]}, "explanation": "Installs htop.", "risk": "med"}
  action must be exactly one of: install, remove, search. Use exact Ubuntu package names. For search, packages holds the search terms.
- If the intent is impossible or unsafe to express as a command, reply with {"command": "echo 'cannot do that safely'", "explanation": "Why it is unsafe.", "risk": "low"}.
- risk: low = read-only, med = changes files/services/packages, high = destructive or irreversible."""


class TranslateError(RuntimeError):
    pass


def _context() -> str:
    return f"cwd={os.getcwd()} os={platform.system()} {platform.release()}"


def _user_message(intent: str) -> str:
    return f"Context: {_context()}\nIntent: {intent}"


def _post(url: str, headers: dict, body: dict, timeout: int, who: str) -> dict:
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(), headers={"content-type": "application/json", **headers}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        raise TranslateError(f"{who} HTTP {e.code}: {e.read().decode(errors='replace')[:200]}")
    except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
        raise TranslateError(f"cannot reach {who}: {e}")


def call_claude(intent: str, api_key: str, model: str = DEFAULT_MODEL, timeout: int = 30) -> str:
    payload = _post(
        API_URL,
        {"x-api-key": api_key, "anthropic-version": "2023-06-01"},
        {"model": model, "max_tokens": 400, "system": SYSTEM, "messages": [{"role": "user", "content": _user_message(intent)}]},
        timeout,
        "Claude API",
    )
    return "".join(b.get("text", "") for b in payload.get("content", []) if b.get("type") == "text")


def call_local(intent: str, base_url: str, model: str = "local", timeout: int = 120, api_key: str = None) -> str:
    payload = _post(
        base_url.rstrip("/") + "/chat/completions",
        {"authorization": f"Bearer {api_key}"} if api_key else {},
        {
            "model": model,
            "max_tokens": 1500,
            "temperature": 0,
            "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": _user_message(intent)}],
        },
        timeout,
        "local model",
    )
    try:
        return payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        raise TranslateError("local model returned an unexpected response shape")


def _backends() -> list:
    """Ordered list of (name, callable) to try."""
    mode = os.environ.get("NYX_BACKEND", "auto")
    key = os.environ.get("ANTHROPIC_API_KEY")
    cloud = ("cloud", lambda text: call_claude(text, key, os.environ.get("NYX_MODEL", DEFAULT_MODEL)))
    local = (
        "local",
        lambda text: call_local(
            text, os.environ.get("NYX_LOCAL_URL", DEFAULT_LOCAL_URL), os.environ.get("NYX_LOCAL_MODEL", "local"),
            api_key=os.environ.get("NYX_LOCAL_KEY"),
        ),
    )
    if mode == "local":
        return [local]
    if mode == "cloud":
        if not key:
            raise TranslateError("NYX_BACKEND=cloud but ANTHROPIC_API_KEY not set")
        return [cloud]
    return [cloud, local] if key else [local]


def translate(intent: str, backend=None) -> Proposal:
    """backend: callable(intent) -> raw model text (tests). Default: configured backends with fallback."""
    if backend is not None:
        return from_model_reply(intent, backend(intent))
    errors = []
    for name, call in _backends():
        try:
            try:
                return from_model_reply(intent, call(intent))
            except ProposalError:  # model rambled or broke format: one retry
                return from_model_reply(intent, call(intent))
        except (TranslateError, ProposalError) as e:  # unreachable / bad reply: try next backend
            errors.append(f"{name}: {e}")
    raise TranslateError("; ".join(errors))
