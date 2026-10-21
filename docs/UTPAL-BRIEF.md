# Utpal: Your Part of NyxOS

Hi Utpal. This is your slice of the project. Read this, then [PLAN.md](PLAN.md).

## One-line summary

You own the **OS**: bootable Ubuntu image, package layer, and the background daemon. Maanas owns the **AI shell** that talks to the user.

## What you own (folders)

| Folder | You build |
|---|---|
| `image/` | Ubuntu ISO via `live-build`. Boots to a shell. Nushell preinstalled. No desktop. |
| `pkg/` | Package lists and `nyx-pkg`, a wrapper around `apt`. |
| `daemon/` | `nyxd` in Rust. Reads `journalctl`, detects errors, sends events to a Unix socket. |

You do NOT touch `shell/` or `ai/`. That is Maanas.

## What Maanas owns

`shell/` (the `nyx` CLI) and `ai/` (natural language to command, safety gate). Maanas will call your `nyx-pkg` and read your `nyxd` events through the contracts below.

## Your milestones

| # | What | Done when |
|---|---|---|
| **M1** | Ubuntu minimal ISO boots to shell | Boots in QEMU, `nu` launches |
| **M4** | `nyx-pkg install <pkg>` works | `nyx-pkg install htop` installs in the VM |
| **M5** | `nyxd` surfaces errors | `logger -p err "test"` produces an event on the socket |
| **M7** | Real hardware | Boots on one real machine |

M0 (repo, contracts) is shared and happens first. Start M1 right after M0 merges.

## Contracts you must follow

Defined in `docs/contracts/`. Do not change shapes without a PR both of us approve.

1. **`nyxd-event.json`** (you write, Maanas reads)
   `{ ts, source, severity, message, suggested_action? }`
2. **`nyxd.sock`** (you serve)
   Unix socket at `/run/nyxd.sock`, newline-delimited JSON, one event per line.
3. **`pkg-request.json`** (Maanas writes, you read)
   `{ action: "install" | "remove" | "search", packages: [] }`

## Decisions I need from you (reply in PR or chat)

1. **Ubuntu version:** 24.04 LTS (my recommendation) or 22.04?
2. **Build tool:** `live-build` (scripted, repeatable) or Cubic (GUI, quicker to try)? I suggest `live-build`.
3. **Test VM:** can you set up QEMU/KVM on your machine for the smoke tests? Image work depends on it.
4. **Your GitHub username** so I can set `CODEOWNERS`.

## How we work

1. Clone: `git clone https://github.com/maanas1234/OS-PROJECT.git`
2. Branch: `git checkout -b utpal/<task>`
3. Work only in your folders.
4. Run your local checks (`shellcheck` for image/pkg, `cargo test` for daemon).
5. Push branch, open PR to `main`. Tag Maanas as reviewer.
6. Never merge your own PR. Never push to `main`.
7. Never commit API keys or passwords.

Commit messages: `feat:`, `fix:`, `docs:`, `chore:`.

## Working with your Claude agent

Start your Claude Code session inside your clone. Tell it:

> Read docs/PLAN.md and docs/UTPAL-BRIEF.md first. You own image/, pkg/, daemon/ only. Do not edit shell/ or ai/. For any contract change, stop and ask me.

## Questions?

Ask Maanas. Better to ask before coding than to rewrite later.

---

## Update 2026-10-21: what Maanas added inside your folders

Your files are unchanged except `image/build.sh` (one block that stages `nyx` + Nushell glue, and an optional model block) and `image/config/package-lists/nyxos.list.chroot` (+`libgomp1`, needed by the optional offline model). Everything else is new files:

| File | Purpose |
|---|---|
| `image/config/includes.chroot/usr/local/bin/nyx` | 2-line wrapper for the Python CLI |
| `image/config/includes.chroot/etc/nyx/nyx.conf` | commented settings template (API key, local model) |
| `image/config/includes.chroot/lib/systemd/system/nyx-alertlog.service` | logs `nyxd` events to `/run/nyx/alerts.jsonl` |
| `image/config/includes.chroot/lib/systemd/system/nyx-llm.service` | offline model server; does nothing unless the model is bundled |
| `image/config/hooks/normal/110-nyx.hook.chroot` | sets modes, enables the two services, checks `nyx` starts |
| `image/bundle-model.sh` | optional: `NYX_BUNDLE_MODEL=1 sudo ./image/build.sh` bakes in llama.cpp + a 1.5B model |
| `shell/nyx.nu` | Nushell glue (copied by build.sh to the vendor autoload dir) |

Please review these like any PR. Your `nyxd.service` is untouched; `nyx-alertlog` runs as `root:adm` so it can read your socket.

**Testing the ISO:** `python3 tests/boot_smoke.py image/build/nyxos-amd64.iso` (needs `qemu-system-x86_64` and `xorriso`).
