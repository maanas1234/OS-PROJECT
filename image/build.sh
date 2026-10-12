#!/bin/sh
set -eu

IMAGE_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_DIR=$(CDPATH= cd -- "$IMAGE_DIR/.." && pwd)

if [ "$(id -u)" -ne 0 ]; then
    echo "build.sh must run as root (live-build creates a chroot)" >&2
    exit 1
fi
if ! command -v lb >/dev/null 2>&1; then
    echo "live-build is required; install it with apt install live-build" >&2
    exit 1
fi

WORK_DIR=$(mktemp -d "${TMPDIR:-/tmp}/nyxos-build.XXXXXX")
cleanup() {
    rm -rf "$WORK_DIR"
}
trap cleanup EXIT
trap 'exit 1' HUP INT TERM

cp -a "$IMAGE_DIR/config" "$WORK_DIR/config"
mkdir -p "$WORK_DIR/config/includes.chroot/usr/local/src/nyxd"
mkdir -p "$WORK_DIR/config/includes.chroot/usr/local/bin"
cp "$REPO_DIR/pkg/nyx-pkg" "$WORK_DIR/config/includes.chroot/usr/local/bin/nyx-pkg"
cp "$REPO_DIR/daemon/Cargo.toml" "$WORK_DIR/config/includes.chroot/usr/local/src/nyxd/"
cp -a "$REPO_DIR/daemon/src" "$WORK_DIR/config/includes.chroot/usr/local/src/nyxd/"

(
    cd "$WORK_DIR"
    "$IMAGE_DIR/auto/config"
    lb build
)

ISO=$(find "$WORK_DIR" -maxdepth 1 -type f -name '*.iso' -print -quit)
if [ -z "$ISO" ]; then
    echo "live-build completed without producing an ISO" >&2
    exit 1
fi
mkdir -p "$IMAGE_DIR/build"
cp "$ISO" "$IMAGE_DIR/build/nyxos-amd64.iso"
echo "Built $IMAGE_DIR/build/nyxos-amd64.iso"
