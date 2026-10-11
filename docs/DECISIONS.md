# Decisions (append only)

## 2026-10-11 Maanas: `nyx` core in Python, not Rust
PLAN.md said Rust for `shell/`. Changed: core lives in `ai/` as stdlib-only Python.
Why: Ubuntu Server ships Python, no build step on the ISO, testable on any dev box today, zero dependencies.
`shell/` now holds only nushell glue. Rust stays an option if startup time or binary size hurts. Utpal's `daemon/` stays Rust; no impact on the contracts.

## 2026-10-11 Maanas: safety gate overrides the model
Gate computes risk itself; model's claim can only raise it. `requires_confirm` always true in v1. Blocklist commands are refused even if the user types yes.
