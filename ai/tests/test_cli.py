import json

import pytest

from nyx.cli import run_intent
from nyx.proposal import ProposalError, from_model_reply, extract_json


def fake(command, risk="low", explanation="because"):
    reply = json.dumps({"command": command, "explanation": explanation, "risk": risk})
    return lambda intent: reply


def test_m2_proposal_shape_and_run_on_yes():
    ran = []
    code = run_intent(
        "list big files",
        dry_run=False,
        backend=fake("du -ah . | sort -rh | head -20"),
        runner=lambda c, shell: ran.append(c) or 0,
        ask=lambda p: True,
    )
    assert code == 0
    assert ran == ["du -ah . | sort -rh | head -20"]


def test_no_run_on_no():
    ran = []
    code = run_intent("x", False, backend=fake("ls"), runner=lambda c, shell: ran.append(c) or 0, ask=lambda p: False)
    assert code == 1 and ran == []


def test_dry_run_never_runs_or_asks():
    def boom(*a, **k):
        raise AssertionError("must not be called")

    assert run_intent("x", True, backend=fake("ls"), runner=boom, ask=boom) == 0


def test_m3_rm_rf_root_refused_even_if_model_says_low_and_user_would_say_yes():
    ran = []
    code = run_intent(
        "wipe everything",
        dry_run=False,
        backend=fake("rm -rf /", risk="low"),
        runner=lambda c, shell: ran.append(c) or 0,
        ask=lambda p: True,
    )
    assert code == 3
    assert ran == []


def test_gate_overrides_model_risk_and_confirm_always_true():
    p = from_model_reply("x", json.dumps({"command": "rm -rf ./build", "risk": "low", "explanation": "e"}))
    assert p.risk == "high"
    assert p.requires_confirm is True


def test_extract_json_tolerates_prose_and_fences():
    assert extract_json('Sure!\n```json\n{"command": "ls"}\n```')["command"] == "ls"


@pytest.mark.parametrize("bad", ["no json here", '{"command": ""}', '{"explanation": "x"}', '{"command": "ls"'])
def test_bad_replies_raise(bad):
    with pytest.raises(ProposalError):
        from_model_reply("x", bad)


def test_proposal_matches_contract_fields():
    p = from_model_reply("x", json.dumps({"command": "ls", "explanation": "e", "risk": "low"}))
    contract = json.load(open("../docs/contracts/command-proposal.json"))
    assert set(json.loads(p.to_json())) == set(contract["required"]) == set(contract["properties"])
