# Contracts

Interfaces between Maanas (`shell/`, `ai/`) and Utpal (`image/`, `pkg/`, `daemon/`).

Changing a contract needs a PR approved by both. Code depends on contracts only after they merge.

| File | Writer | Reader | Shape |
|---|---|---|---|
| `nyxd-event.json` | Utpal (`daemon/`) | Maanas (`shell/`) | `{ ts, source, severity, message, suggested_action? }` |
| `pkg-request.json` | Maanas (`ai/`) | Utpal (`pkg/`) | `{ action, packages[] }` |
| `command-proposal.json` | Maanas (`ai/`) | Maanas (`shell/`) | `{ intent, command, explanation, risk, requires_confirm }` |

Transport: `nyxd` serves newline-delimited JSON on `/run/nyxd.sock`.
