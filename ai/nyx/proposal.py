"""command-proposal contract (docs/contracts/command-proposal.json)."""
import json
import re
from dataclasses import dataclass, asdict

from .safety import assess

FIELDS = {"intent", "command", "explanation", "risk", "requires_confirm"}

# Same rule as pkg/nyx-pkg. Keep in sync.
PACKAGE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9+.-]*$")


class ProposalError(ValueError):
    pass


@dataclass
class Proposal:
    intent: str
    command: str
    explanation: str
    risk: str
    requires_confirm: bool

    def to_json(self):
        return json.dumps(asdict(self))


def extract_json(text: str) -> dict:
    """Pull the first JSON object out of a model reply."""
    start = text.find("{")
    if start == -1:
        raise ProposalError("no JSON object in model reply")
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start : i + 1])
                except json.JSONDecodeError as e:
                    raise ProposalError(f"bad JSON from model: {e}")
    raise ProposalError("unterminated JSON object in model reply")


def pkg_command(request) -> str:
    """pkg-request contract -> `nyx-pkg ...` command line. Validates names; no shell metacharacters survive."""
    if not isinstance(request, dict):
        raise ProposalError("pkg_request must be an object")
    action, packages = request.get("action"), request.get("packages")
    if action not in ("install", "remove", "search"):
        raise ProposalError("pkg_request action must be install, remove, or search")
    if not isinstance(packages, list) or not packages:
        raise ProposalError("pkg_request packages must be a non-empty list")
    if not all(isinstance(p, str) and PACKAGE_RE.fullmatch(p) for p in packages):
        raise ProposalError("pkg_request has an invalid package name")
    return " ".join(["nyx-pkg", action, *packages])


def from_model_reply(intent: str, text: str) -> Proposal:
    """Parse reply, then run the safety gate. Gate overrides model on risk and confirm."""
    data = extract_json(text)
    if "pkg_request" in data:
        data["command"] = pkg_command(data["pkg_request"])
    command = data.get("command")
    if not isinstance(command, str) or not command.strip():
        raise ProposalError("model reply has no command")
    claimed = data.get("risk") if data.get("risk") in ("low", "med", "high") else "low"
    verdict = assess(command, claimed)
    explanation = str(data.get("explanation", "")).strip()
    if verdict.reasons:
        explanation = f"{explanation} [{verdict.reason}]".strip()
    return Proposal(
        intent=intent,
        command=command.strip(),
        explanation=explanation,
        risk=verdict.risk,
        requires_confirm=True,  # always. v1 never runs without a yes.
    )
