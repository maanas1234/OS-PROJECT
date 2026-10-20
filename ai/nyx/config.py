"""Settings file so an API key survives reboots on the ISO.

Files (later wins, real environment variables always win over both):
  /etc/nyx/nyx.conf
  ~/.config/nyx/nyx.conf
Format: KEY=value per line, '#' comments. Only the keys below are read.
"""
import os

KEYS = (
    "ANTHROPIC_API_KEY",
    "NYX_BACKEND",
    "NYX_MODEL",
    "NYX_LOCAL_URL",
    "NYX_LOCAL_MODEL",
    "NYX_LOCAL_KEY",
    "NYXD_SOCKET_PATH",
)
SECRET = ("ANTHROPIC_API_KEY", "NYX_LOCAL_KEY")


def paths() -> list:
    return ["/etc/nyx/nyx.conf", os.path.join(os.path.expanduser("~"), ".config", "nyx", "nyx.conf")]


def parse(text: str) -> dict:
    values = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip("\"'")
        if key in KEYS and value:
            values[key] = value
    return values


def load(files=None, environ=None) -> dict:
    """Merge config files into environ (never overriding what is already set). Returns what was applied."""
    environ = os.environ if environ is None else environ
    merged = {}
    for path in files if files is not None else paths():
        try:
            with open(path, encoding="utf-8") as f:
                merged.update(parse(f.read()))
        except OSError:
            continue
    applied = {k: v for k, v in merged.items() if k not in environ}
    environ.update(applied)
    return applied


def mask(key: str, value: str) -> str:
    if key in SECRET:
        return value[:4] + "..." + value[-2:] if len(value) > 8 else "***"
    return value


def describe(environ=None) -> str:
    """Human summary of the effective settings and which backend order will be used."""
    environ = os.environ if environ is None else environ
    lines = [f"{k}={mask(k, environ[k])}" for k in KEYS if environ.get(k)]
    mode = environ.get("NYX_BACKEND", "auto")
    if mode == "auto":
        order = "cloud, then local" if environ.get("ANTHROPIC_API_KEY") else "local only (no ANTHROPIC_API_KEY)"
    else:
        order = mode
    lines.append(f"backend order: {order}")
    lines.append("config files: " + ", ".join(paths()))
    return "\n".join(lines)
