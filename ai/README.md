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
nyx "install htop"                           # becomes: nyx-pkg install htop (confirm first)
nyx why -- ls /nope                          # run; on failure, explain
nyx alerts                                   # stream nyxd errors from /run/nyxd.sock
PYTHONPATH=. python -m pytest                # tests (no network needed)
```

Exit codes: 0 ok, 1 cancelled, 2 translate error, 3 refused by safety gate.

## Backends

`NYX_BACKEND=auto` (default): Claude if `ANTHROPIC_API_KEY` set, falls back to a local model when the cloud is unreachable.
`cloud` or `local` force one. Local = any OpenAI-compatible server: `llama-server` (default `http://127.0.0.1:8080/v1`) or Ollama (`NYX_LOCAL_URL=http://127.0.0.1:11434/v1`, `NYX_LOCAL_MODEL=<tag>`, optional `NYX_LOCAL_KEY` for servers that need a bearer token).
Local output goes through the same safety gate.

## Modules

| File | Job |
|---|---|
| `nyx/safety.py` | Blocklist (never run), high/med/low risk. Overrides model's risk claim. |
| `nyx/proposal.py` | Parse model reply into `command-proposal` contract. `requires_confirm` is always true. |
| `nyx/translate.py` | Claude API call (stdlib only). Model via `NYX_MODEL`, default `claude-sonnet-5-5`. |
| `nyx/alerts.py` | Reads `nyxd-event` JSON from the daemon socket (`NYXD_SOCKET_PATH`). |
| `nyx/cli.py` | Prompt, confirm, run. `why` and `alerts` subcommands. |

## Verified

Unit tests (55) on Windows and Ubuntu 24.04. On Ubuntu: `nyx "get me htop"` through a fake local LLM ran the real `nyx-pkg` and installed htop (M4). `nyx alerts` printed errors from Utpal's real `nyxd` (built on Ubuntu 24.04, fake `journalctl`) and dropped info-level lines (M5).

## Not done yet

- Ship a local model on the ISO (weights + `llama-server` service); the backend code is ready.
- Live Claude API call untested (no key on dev box).
- Nushell glue in `shell/`.
