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

## Status (2026-10-21)

The ISO builds and boots: `tests/boot_smoke.py` passes 9/9 in QEMU (boot, Nushell, `nyx`, `nyxd`, DHCP, alert pipeline,
real-model English to command, package intent to `nyx-pkg`).

**Try it:**
```sh
sudo ./image/build.sh                    # or NYX_BUNDLE_MODEL=1 for the offline model; see tests/README.md for Docker
python3 tests/boot_smoke.py image/build/nyxos-amd64.iso
```
On the booted system (autologin `ubuntu`, Nushell):
```
ask list the biggest files        # or: nyx "list the biggest files"
ask install htop                  # becomes: nyx-pkg install htop (confirm first)
nyx alerts                        # live nyxd errors; new ones also show at your next prompt
sudo vi /etc/nyx/nyx.conf         # put ANTHROPIC_API_KEY here; without it nyx uses the local model if present
```

**Not verified:** real hardware (M7), UEFI/isolinux bootloader screens, live Anthropic API call, the offline-model ISO
booted end to end (model and server verified separately in a container).
