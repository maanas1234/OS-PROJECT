# OS-PROJECT (NyxOS)

AI-native, CLI-only Linux distro. Base: Ubuntu Server (minimal LTS). No desktop.

Team: **Maanas** (AI brain) and **Utpal** (OS plumbing).

- Full plan: [docs/PLAN.md](docs/PLAN.md)
- Work split for Utpal: [docs/UTPAL-BRIEF.md](docs/UTPAL-BRIEF.md)
- Shared interfaces: [docs/contracts/](docs/contracts/)

## Layout

| Folder | What | Owner |
|---|---|---|
| `image/` | Ubuntu ISO build (live-build) | Utpal |
| `pkg/` | Package lists, `nyx-pkg` apt wrapper | Utpal |
| `daemon/` | `nyxd` log-watcher daemon (Rust) | Utpal |
| `shell/` | `nyx` CLI + nushell integration (Rust) | Maanas |
| `ai/` | NL to command, model router, safety gate (Python prototype) | Maanas |
| `tests/` | QEMU smoke tests | Shared |
| `docs/contracts/` | Interfaces between halves | Shared (both approve) |

## Rules

- `main` is protected. Work on a branch, open a PR, other person reviews.
- Edit only your own folders. Cross-folder need: note it in the PR.
- Contract changes: separate PR, both approve before code depends on it.
- No secrets in git. API keys go in `.env` (gitignored).
