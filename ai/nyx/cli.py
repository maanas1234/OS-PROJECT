"""nyx CLI.  nyx "list big files"  |  nyx --dry-run "..."  |  nyx why -- <cmd>  |  nyx alerts [--history]  |  nyx notify  |  nyx config"""
import argparse
import subprocess
import sys

from . import config
from . import alerts
from .alerts import AlertsError, format_event, stream_events
from .safety import assess
from .translate import TranslateError, translate

RISK_LABEL = {"low": "LOW", "med": "MEDIUM", "high": "HIGH"}


def confirm(proposal) -> bool:
    if proposal.risk == "high":
        return input("HIGH risk. Type 'yes' to run: ").strip() == "yes"
    return input("Run it? [y/N]: ").strip().lower() in ("y", "yes")


def show(proposal):
    print(f"\n  $ {proposal.command}\n")
    print(f"  {proposal.explanation}")
    print(f"  risk: {RISK_LABEL[proposal.risk]}\n")


def run_intent(intent: str, dry_run: bool, backend=None, runner=subprocess.call, ask=confirm) -> int:
    try:
        proposal = translate(intent, backend)
    except Exception as e:  # TranslateError or ProposalError
        print(f"nyx: {e}", file=sys.stderr)
        return 2
    verdict = assess(proposal.command, proposal.risk)
    show(proposal)
    if verdict.blocked:
        print(f"nyx: refused. {verdict.reason}", file=sys.stderr)
        return 3
    if dry_run:
        return 0
    if not ask(proposal):
        print("nyx: cancelled")
        return 1
    return runner(proposal.command, shell=True)


def run_why(cmd: list, backend=None) -> int:
    """Run a command; if it fails, ask the model what went wrong."""
    result = subprocess.run(cmd, capture_output=True, text=True)
    sys.stdout.write(result.stdout)
    sys.stderr.write(result.stderr)
    if result.returncode == 0:
        return 0
    question = (
        f"Command `{' '.join(cmd)}` exited {result.returncode} with stderr:\n{result.stderr[-1500:]}\n"
        "Explain the cause in one or two sentences and give a fix command."
    )
    try:
        proposal = translate(question, backend)
    except Exception as e:
        print(f"nyx: {e}", file=sys.stderr)
        return result.returncode
    print("\nnyx diagnosis:")
    show(proposal)
    return result.returncode


def run_alerts() -> int:
    """Print nyxd events as they arrive. Ctrl-C to stop."""
    try:
        for event in stream_events():
            print(format_event(event), flush=True)
    except AlertsError as e:
        print(f"nyx: {e}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 0
    print("nyx: nyxd closed the connection", file=sys.stderr)
    return 1


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    config.load()
    if argv == ["notify"]:  # called from the shell prompt hook: print only unseen alerts, silently otherwise
        for event in alerts.new_events():
            print(format_event(event))
        return 0
    if argv == ["alerts", "--history"]:
        for event in alerts.read_log():
            print(format_event(event))
        return 0
    if argv == ["alerts", "--log"]:  # service mode (systemd): never returns
        alerts.follow_to_log()
        return 0
    if argv == ["config"]:
        print(config.describe())
        return 0
    if argv and argv[0] == "why":
        cmd = [a for a in argv[1:] if a != "--"]
        if not cmd:
            print("usage: nyx why -- <command>", file=sys.stderr)
            return 2
        return run_why(cmd)
    if argv == ["alerts"]:
        return run_alerts()
    p = argparse.ArgumentParser(prog="nyx", description="AI-first shell helper")
    p.add_argument("intent", nargs="+", help="what you want, in plain English")
    p.add_argument("--dry-run", action="store_true", help="show the command, do not run")
    args = p.parse_args(argv)
    return run_intent(" ".join(args.intent), args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
