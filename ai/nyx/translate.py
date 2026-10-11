"""Natural language -> Proposal. Cloud backend (Claude API). Local backend lands in M6."""
import json
import os
import platform
import urllib.error
import urllib.request

from .proposal import Proposal, from_model_reply

API_URL = "https://api.anthropic.com/v1/messages"
DEFAULT_MODEL = "claude-sonnet-5-5"

SYSTEM = """You translate a user's intent into ONE shell command for Ubuntu Linux (bash/nushell host, GNU coreutils).
Reply with ONLY a JSON object, no prose, no code fences:
{"command": "<single command or pipeline>", "explanation": "<one short sentence>", "risk": "low|med|high"}
Rules:
- Prefer read-only commands. Never add sudo unless the task needs root.
- If the intent is impossible or unsafe to express as a command, reply with {"command": "echo 'cannot do that safely'", "explanation": "<why>", "risk": "low"}.
- risk: low = read-only, med = changes files/services/packages, high = destructive or irreversible."""


class TranslateError(RuntimeError):
    pass


def _context() -> str:
    return f"cwd={os.getcwd()} os={platform.system()} {platform.release()}"


def call_claude(intent: str, api_key: str, model: str = DEFAULT_MODEL, timeout: int = 30) -> str:
    body = json.dumps(
        {
            "model": model,
            "max_tokens": 400,
            "system": SYSTEM,
            "messages": [{"role": "user", "content": f"Context: {_context()}\nIntent: {intent}"}],
        }
    ).encode()
    req = urllib.request.Request(
        API_URL,
        data=body,
        headers={
            "content-type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.load(resp)
    except urllib.error.HTTPError as e:
        raise TranslateError(f"Claude API HTTP {e.code}: {e.read().decode(errors='replace')[:200]}")
    except (urllib.error.URLError, TimeoutError) as e:
        raise TranslateError(f"cannot reach Claude API: {e}")
    return "".join(b.get("text", "") for b in payload.get("content", []) if b.get("type") == "text")


def translate(intent: str, backend=None) -> Proposal:
    """backend: callable(intent) -> raw model text. Default = Claude API using ANTHROPIC_API_KEY."""
    if backend is None:
        key = os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise TranslateError("ANTHROPIC_API_KEY not set (offline local model arrives in M6)")
        model = os.environ.get("NYX_MODEL", DEFAULT_MODEL)
        backend = lambda text: call_claude(text, key, model)
    return from_model_reply(intent, backend(intent))
