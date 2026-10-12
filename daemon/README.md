# daemon/ (Owner: Utpal)

`nyxd` is a Rust daemon that follows `journalctl` JSON output at error severity
and above. It streams contract-shaped, newline-delimited JSON events to clients
connected to `/run/nyxd.sock`. Set `NYXD_SOCKET_PATH` to use a different socket
path during development. The daemon refuses to replace an existing non-socket
path.

Build with `cargo build --release` from this directory. Running against the
system journal and binding `/run/nyxd.sock` normally requires root privileges.

Milestone: M5.
