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
