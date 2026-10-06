# NyxOS: Team Plan

AI-native, CLI-only Linux distro. Base: Ubuntu Server 24.04 LTS (minimal). Two people: Maanas and Utpal. Each runs their own Claude Code agent(s).

## 1. Repo

Fresh repo `OS-PROJECT`, not a fork. We only add our layer on Ubuntu (build config, our packages, our daemon). Forking would pull in thousands of upstream files we never touch.

## 2. Work split

### Maanas: AI brain (`shell/`, `ai/`)
- `nyx` CLI: user types natural language, gets a proposed shell command.
- NL to command via Claude API (cloud). Local model later (llama.cpp).
- Safety gate: show command + explanation, require confirm. Block destructive patterns.
- Nushell integration.
- On failed command, offer diagnosis.

### Utpal: OS plumbing (`image/`, `pkg/`, `daemon/`)
- ISO build with live-build: Ubuntu base, nushell preinstalled, boots to shell. No desktop.
- Package layer: `pkg/` lists + `nyx-pkg` wrapper around apt.
- `nyxd` daemon (Rust): tails journalctl, detects anomalies, emits events over Unix socket.
- systemd unit for `nyxd`.

### Shared
- `tests/`: QEMU smoke tests.
- `docs/contracts/`: interfaces.

## 3. Agent rules

1. Each agent edits only its owner folders.
2. Cross-boundary code needs a contract PR first.
3. One task, one branch, one PR. Small diffs.
4. Run local checks before PR; paste output in PR.
5. Agents never merge. Humans review.
6. Shared context lives in `docs/`, not chat.

## 4. Contracts

| Contract | Writer | Reader | Shape |
|---|---|---|---|
| `command-proposal.json` | Maanas | Maanas | `{ intent, command, explanation, risk, requires_confirm }` |
| `nyxd-event.json` | Utpal | Maanas | `{ ts, source, severity, message, suggested_action? }` |
| `nyxd.sock` | Utpal | Maanas | newline-delimited JSON, `/run/nyxd.sock` |
| `pkg-request.json` | Maanas | Utpal | `{ action, packages[] }` |

## 5. Milestones

| # | Milestone | Owner | Done when |
|---|---|---|---|
| M0 | Repo + CODEOWNERS + contracts v0 | Both | On `main`, both can branch |
| M1 | Ubuntu minimal ISO boots to shell | Utpal | Boots in QEMU, `nu` launches |
| M2 | `nyx "list big files"` returns correct command | Maanas | Proposal shown, confirm, runs on yes |
| M3 | Safety gate blocks `rm -rf /` | Maanas | Refused, non-zero exit |
| M4 | `nyx "install htop"` installs via apt | Both | Works in VM |
| M5 | `nyxd` surfaces injected error | Utpal | `logger -p err "test"` shows alert in `nyx` |
| M6 | Offline local model fallback | Maanas | M2 query works with network off |
| M7 | Boots on real hardware | Both | Smoke test passes |

## 6. Ground rules

- No secrets in git. `.env` gitignored.
- Keep it simple. No abstraction until second use.
- Destructive disk ops only in VM.
