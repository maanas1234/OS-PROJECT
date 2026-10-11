"""command-proposal contract (docs/contracts/command-proposal.json)."""
import json
import re
from dataclasses import dataclass, asdict

from .safety import assess

FIELDS = {"intent", "command", "explanation", "risk", "requires_confirm"}


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


def from_model_reply(intent: str, text: str) -> Proposal:
    """Parse reply, then run the safety gate. Gate overrides model on risk and confirm."""
    data = extract_json(text)
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
