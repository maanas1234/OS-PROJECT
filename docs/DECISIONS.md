# Decisions (append only)

## 2026-10-11 Maanas: `nyx` core in Python, not Rust
PLAN.md said Rust for `shell/`. Changed: core lives in `ai/` as stdlib-only Python.
Why: Ubuntu Server ships Python, no build step on the ISO, testable on any dev box today, zero dependencies.
`shell/` now holds only nushell glue. Rust stays an option if startup time or binary size hurts. Utpal's `daemon/` stays Rust; no impact on the contracts.

## 2026-10-11 Maanas: safety gate overrides the model
Gate computes risk itself; model's claim can only raise it. `requires_confirm` always true in v1. Blocklist commands are refused even if the user types yes.

## 2026-10-12 Maanas: package intents reuse the normal command path
Model returns a `pkg-request` (docs/contracts) instead of apt text; `nyx` validates names with the same regex as `pkg/nyx-pkg` and renders `nyx-pkg <action> <pkgs>`. Same safety gate and confirm as any command. `nyx-pkg install/remove` rated MED.

## 2026-10-12 Maanas: local model = OpenAI-compatible HTTP
Works with `llama-server` and Ollama, no Python deps. Cloud-first, local fallback on network failure (M6). Gate applies to both.

## 2026-10-12 Maanas: added .gitattributes (eol=lf)
Windows checkouts rewrote `pkg/nyx-pkg` to CRLF and broke its shebang (`python3\r`). Shared root file; Utpal's folders untouched.

## 2026-10-21 Maanas: nyx installed in the ISO without pip
`build.sh` copies `ai/nyx` to `/usr/local/lib/nyx/nyx`; `/usr/local/bin/nyx` is a 2-line wrapper that sets `PYTHONPATH`. No pip, no network at image build time, nothing to purge. A `110-nyx` hook runs `nyx config` at build time so a broken CLI fails the build instead of first boot.

## 2026-10-21 Maanas: proactive alerts via a log file, not by pushing into terminals
`nyx-alertlog.service` appends `nyxd` events to `/run/nyx/alerts.jsonl` (world-readable, reconnects if `nyxd` restarts). `nyx notify` prints only unseen events (per-user offset in `~/.cache/nyx`). The Nushell `pre_prompt` hook calls it, so alerts appear at the next prompt without interrupting typing and without needing the `adm` group.

## 2026-10-21 Maanas: offline model is opt-in at image build time
`NYX_BUNDLE_MODEL=1 sudo ./image/build.sh` adds llama.cpp `b11756` + Qwen2.5-1.5B-Instruct Q4_K_M (~1.2 GB, both pinned and SHA-256 verified). `nyx-llm.service` has `ConditionPathExists` on the model file, so default images are unchanged and the service is a no-op. `nyx` already falls back to `http://127.0.0.1:8080/v1`.

## 2026-10-21 Maanas: config file for settings
`/etc/nyx/nyx.conf` and `~/.config/nyx/nyx.conf` (KEY=value). Real environment variables win. Only known keys are read. `nyx config` shows the effective settings with secrets masked.

## 2026-10-21 Maanas: three boot bugs found by actually booting the ISO
Booting in QEMU (`tests/boot_smoke.py`) found that the ISO could not boot or log in as built:
1. Casper looks for `/casper/filesystem.squashfs`; live-build wrote `/live/`. Fixed with `live-media-path=live` in `--bootappend-live`.
2. live-build's default live user is `user`/`live`, hostname `debian`; our autologin files say `ubuntu`. Fixed with `username=ubuntu hostname=nyxos`.
3. A serial console runs `serial-getty@ttyS0`, not `getty@ttyS0`. Added a serial-getty autologin drop-in (the old file is harmless and left alone).
Also added: DHCP via systemd-networkd (+`systemd-resolved` package, resolv.conf tmpfiles rule), because the image had no network config at all; `nyx-pkg` runs `apt-get update` when apt lists are missing (live images ship none).
Ubuntu's own `live-build` package is the ancient `3.0~a57`; `--debian-installer none` needs upstream live-build (Utpal's Arch host has it). `tests/builder.Dockerfile` installs the upstream one.

## 2026-10-21 Maanas: apt commands from small models are rerouted
The bundled 1.5B model answers "install htop" with `apt install htop`. `nyx` rewrites plain `apt/apt-get install|remove|purge <names>` into `nyx-pkg ...`; anything fancier (`&&`, `$()`, `update`) is left alone and still goes through the safety gate.
