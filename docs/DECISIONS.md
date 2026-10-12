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
