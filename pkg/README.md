# pkg/ (Owner: Utpal)

`nyx-pkg` is a small Python CLI for `install`, `remove`, and `search`. It accepts
direct command-line arguments or the shared `pkg-request.json` contract through
`--request FILE` (`-` reads standard input). Install and remove use `apt-get`
and run through `sudo` when needed; search uses `apt-cache`.

Package names and search terms are restricted to letters, digits, `+`, `.`, and
`-`, and commands are passed as argument arrays rather than through a shell.
The starter image package list is `packages.list`.

Example: `./pkg/nyx-pkg install htop`

Milestone: M4.
