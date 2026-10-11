# ai/ (Owner: Maanas)

`nyx` CLI core: natural language to command, safety gate, failure diagnosis.

Milestones: M2, M3, M6.

## Use

```bash
cd ai
pip install -e .[dev]
export ANTHROPIC_API_KEY=...        # never commit
nyx --dry-run "list files using most disk"   # show only
nyx "list processes using most memory"       # show, confirm, run
nyx why -- ls /nope                          # run; on failure, explain
PYTHONPATH=. python -m pytest                # tests (no network needed)
```

Exit codes: 0 ok, 1 cancelled, 2 translate error, 3 refused by safety gate.

## Modules

| File | Job |
|---|---|
| `nyx/safety.py` | Blocklist (never run), high/med/low risk. Overrides model's risk claim. |
| `nyx/proposal.py` | Parse model reply into `command-proposal` contract. `requires_confirm` is always true. |
| `nyx/translate.py` | Claude API call (stdlib only). Model via `NYX_MODEL`, default `claude-sonnet-5-5`. |
| `nyx/cli.py` | Prompt, confirm, run. `why` subcommand. |

## Not done yet

- M6 local model backend (plug into `translate(backend=...)`).
- `nyx-pkg` hand-off (M4) and `nyxd` alerts reader (M5): need Utpal's pieces.
- Live Claude API call untested (no key on dev box); tests use a fake backend.
