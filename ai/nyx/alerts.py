"""Read nyxd events (docs/contracts/nyxd-event.json) from the daemon's Unix socket."""
import json
import os
import socket

DEFAULT_SOCKET = "/run/nyxd.sock"
REQUIRED = {"ts", "source", "severity", "message"}
SEVERITIES = {"info", "warning", "error", "critical"}


class AlertsError(RuntimeError):
    pass


def socket_path() -> str:
    return os.environ.get("NYXD_SOCKET_PATH", DEFAULT_SOCKET)


def parse_event(line: str):
    """Return the event dict, or None if the line is not a valid nyxd-event."""
    try:
        event = json.loads(line)
    except json.JSONDecodeError:
        return None
    if not isinstance(event, dict) or not REQUIRED <= set(event) or event["severity"] not in SEVERITIES:
        return None
    return event


def format_event(event: dict) -> str:
    text = f"[{event['severity'].upper()}] {event['source']}: {event['message']}"
    if event.get("suggested_action"):
        text += f"\n    suggested: {event['suggested_action']}"
    return text


def stream_events(path: str = None):
    """Yield valid events until the daemon closes the socket."""
    if not hasattr(socket, "AF_UNIX"):
        raise AlertsError("Unix sockets not supported on this platform")
    path = path or socket_path()
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        sock.connect(path)
    except FileNotFoundError:
        raise AlertsError(f"nyxd not running (no socket at {path})")
    except PermissionError:
        raise AlertsError(f"permission denied on {path} (socket is group-restricted; try sudo)")
    except OSError as e:
        raise AlertsError(f"cannot connect to {path}: {e}")
    with sock, sock.makefile("r", encoding="utf-8", errors="replace") as lines:
        for line in lines:
            event = parse_event(line)
            if event:
                yield event


DEFAULT_LOG = "/run/nyx/alerts.jsonl"


def log_path() -> str:
    return os.environ.get("NYX_ALERT_LOG", DEFAULT_LOG)


def follow_to_log(sock_path: str = None, log_file: str = None, retry_seconds: float = 2.0, sleep=None, max_rounds=None):
    """Service loop: append every nyxd event to a JSONL file; reconnect if the daemon is not up yet or restarts."""
    import time

    sleep = sleep or time.sleep
    log_file = log_file or log_path()
    os.makedirs(os.path.dirname(log_file) or ".", exist_ok=True)
    rounds = 0
    while max_rounds is None or rounds < max_rounds:
        rounds += 1
        try:
            for event in stream_events(sock_path):
                with open(log_file, "a", encoding="utf-8") as f:
                    f.write(json.dumps(event) + "\n")
        except AlertsError:
            pass
        sleep(retry_seconds)


def read_log(log_file: str = None) -> list:
    try:
        with open(log_file or log_path(), encoding="utf-8") as f:
            return [e for e in map(parse_event, f) if e]
    except OSError:
        return []


def offset_file() -> str:
    base = os.environ.get("XDG_CACHE_HOME") or os.path.join(os.path.expanduser("~"), ".cache")
    return os.path.join(base, "nyx", "alerts.offset")


def new_events(log_file: str = None, offset_path: str = None, advance: bool = True) -> list:
    """Events appended since the last call (per user). First call returns everything."""
    events = read_log(log_file)
    offset_path = offset_path or offset_file()
    try:
        with open(offset_path, encoding="utf-8") as f:
            seen = int(f.read().strip() or 0)
    except (OSError, ValueError):
        seen = 0
    if seen > len(events):  # log was rotated or reset at boot
        seen = 0
    fresh = events[seen:]
    if advance and fresh:
        os.makedirs(os.path.dirname(offset_path), exist_ok=True)
        with open(offset_path, "w", encoding="utf-8") as f:
            f.write(str(len(events)))
    return fresh
