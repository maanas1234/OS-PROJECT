"""Safety gate. Never trusts the model's own risk claim.

Verdict.blocked  -> refuse, never run.
Verdict.risk     -> low | med | high, used for the confirm prompt.
"""
import re
import shlex
from dataclasses import dataclass

RISK_ORDER = {"low": 0, "med": 1, "high": 2}

# Always refuse. Pattern is matched against the whole command string.
BLOCKED = [
    (r"\brm\s+(-\w*\s+)*-\w*[rR]\w*\s+(-\w+\s+)*(--no-preserve-root\s+)?(/|/\*|~|~/|\$HOME)(\s|$)", "recursive delete of / or home"),
    (r"\brm\b.*--no-preserve-root", "rm --no-preserve-root"),
    (r"\bmkfs(\.\w+)?\b", "formats a filesystem"),
    (r"\bdd\b[^|;&]*\bof=/dev/", "dd writes to a device"),
    (r">\s*/dev/(sd|nvme|vd|hd|mmcblk)\w*", "redirect to raw disk"),
    (r":\(\)\s*\{.*\};\s*:", "fork bomb"),
    (r"\bchmod\s+(-\w+\s+)*-\w*R\w*\s+\d*7\d*\s+/(\s|$)", "recursive chmod on /"),
    (r"\bchown\s+(-\w+\s+)*-\w*R\w*\s+\S+\s+/(\s|$)", "recursive chown on /"),
    (r"\b(wipefs|shred)\b[^|;&]*\s/dev/", "wipes a device"),
]

# Allowed, but force a high-risk confirm.
HIGH = [
    (r"\b(curl|wget)\b[^|;&]*\|\s*(sudo\s+)?(ba|z|da)?sh\b", "pipes download into a shell"),
    (r"\brm\b[^|;&]*\s-\w*[rR]", "recursive delete"),
    (r"\b(fdisk|parted|cfdisk|sfdisk)\b", "partition tool"),
    (r"\b(userdel|deluser|passwd)\b", "changes user accounts"),
    (r"\biptables\b|\bufw\b\s+(disable|reset)", "changes firewall"),
]

MED = [
    (r"\bsudo\b", "runs as root"),
    (r"\b(shutdown|reboot|poweroff|halt)\b", "stops the machine"),
    (r"\bsystemctl\s+(stop|disable|mask|restart)\b", "changes a service"),
    (r"\b(apt|apt-get|dpkg)\s+(-\w+\s+)*(install|remove|purge|upgrade|dist-upgrade)\b", "changes packages"),
    (r"\bkill(all)?\b|\bpkill\b", "kills processes"),
    (r"\bmv\b|\brm\b|\bchmod\b|\bchown\b", "modifies files"),
    (r">>?\s*\S", "writes to a file"),
]


@dataclass
class Verdict:
    risk: str
    blocked: bool
    reasons: list

    @property
    def reason(self):
        return "; ".join(self.reasons)


def _hit(patterns, command):
    return [why for pat, why in patterns if re.search(pat, command)]


def assess(command: str, claimed_risk: str = "low") -> Verdict:
    """Classify a command. Final risk = max(gate risk, model's claimed risk)."""
    command = command.strip()
    if not command:
        return Verdict("low", True, ["empty command"])
    try:
        shlex.split(command)
    except ValueError:
        return Verdict("high", True, ["unparseable quoting"])

    blocked = _hit(BLOCKED, command)
    if blocked:
        return Verdict("high", True, blocked)

    high = _hit(HIGH, command)
    if high:
        risk, reasons = "high", high
    else:
        med = _hit(MED, command)
        risk, reasons = ("med", med) if med else ("low", [])

    if claimed_risk in RISK_ORDER and RISK_ORDER[claimed_risk] > RISK_ORDER[risk]:
        risk = claimed_risk
        reasons = reasons + ["model flagged higher risk"]
    return Verdict(risk, False, reasons)
