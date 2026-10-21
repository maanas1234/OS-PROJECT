#!/bin/sh
set -eu

IMAGE_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_DIR=$(CDPATH= cd -- "$IMAGE_DIR/.." && pwd)
WORK_DIR="$IMAGE_DIR/.build-work"

if [ "$(id -u)" -ne 0 ]; then
    echo "build.sh must run as root (live-build creates a chroot)" >&2
    exit 1
fi
if ! command -v lb >/dev/null 2>&1; then
    echo "live-build is required; install it with apt install live-build" >&2
    exit 1
fi
if ! command -v mkfs.msdos >/dev/null 2>&1; then
    MKFS_FAT=$(command -v mkfs.fat || true)
    if [ -z "$MKFS_FAT" ]; then
        echo "dosfstools is required on the build host (mkfs.fat was not found)" >&2
        exit 1
    fi
    COMPAT_BIN="$WORK_DIR/host-compat"
    mkdir -p "$COMPAT_BIN"
    ln -sf "$MKFS_FAT" "$COMPAT_BIN/mkfs.msdos"
    PATH="$COMPAT_BIN:$PATH"
    export PATH
fi

mkdir -p "$WORK_DIR"

# Keep the pinned Nushell release outside config so live-build cleanup does not
# remove it. The checksum is the SHA-256 digest published by the GitHub release.
NU_VERSION=0.116.1
NU_SHA256=d6d8ace4be491ed8abba4026e73b60c0470b4671d7039307e7d772282ef863da
DOWNLOAD_DIR="$WORK_DIR/downloads"
NU_ARCHIVE="$DOWNLOAD_DIR/nu-$NU_VERSION-x86_64-unknown-linux-gnu.tar.gz"
mkdir -p "$DOWNLOAD_DIR"
if [ ! -f "$NU_ARCHIVE" ] || [ "$(sha256sum "$NU_ARCHIVE" | cut -d ' ' -f 1)" != "$NU_SHA256" ]; then
    rm -f "$NU_ARCHIVE"
    curl --fail --location --retry 3 --continue-at - \
        "https://github.com/nushell/nushell/releases/download/$NU_VERSION/nu-$NU_VERSION-x86_64-unknown-linux-gnu.tar.gz" \
        -o "$NU_ARCHIVE.part"
    if [ "$(sha256sum "$NU_ARCHIVE.part" | cut -d ' ' -f 1)" != "$NU_SHA256" ]; then
        rm -f "$NU_ARCHIVE.part"
        echo "Nushell release checksum verification failed" >&2
        exit 1
    fi
    mv "$NU_ARCHIVE.part" "$NU_ARCHIVE"
fi

# Keep live-build's package and bootstrap caches between runs, but discard
# generated chroot/output state so updated project files are always applied.
if [ -d "$WORK_DIR/config" ]; then
    (
        cd "$WORK_DIR"
        lb clean --stage --chroot --binary
    )
fi
rm -rf "$WORK_DIR/config"

cp -a "$IMAGE_DIR/config" "$WORK_DIR/config"
mkdir -p "$WORK_DIR/config/includes.chroot/usr/local/src/nyxd"
mkdir -p "$WORK_DIR/config/includes.chroot/usr/local/bin"
NU_EXTRACT_DIR=$(mktemp -d "$WORK_DIR/nu.XXXXXX")
tar -xzf "$NU_ARCHIVE" -C "$NU_EXTRACT_DIR"
NU_BINARY=$(find "$NU_EXTRACT_DIR" -type f -name nu -print -quit)
if [ -z "$NU_BINARY" ]; then
    echo "Nushell archive did not contain the nu executable" >&2
    exit 1
fi
install -m 0755 "$NU_BINARY" "$WORK_DIR/config/includes.chroot/usr/local/bin/nu"
rm -rf "$NU_EXTRACT_DIR"
# nyx AI shell helper (stdlib-only Python) and its Nushell glue
mkdir -p "$WORK_DIR/config/includes.chroot/usr/local/lib/nyx"
mkdir -p "$WORK_DIR/config/includes.chroot/usr/local/share/nushell/vendor/autoload"
cp -a "$REPO_DIR/ai/nyx" "$WORK_DIR/config/includes.chroot/usr/local/lib/nyx/nyx"
find "$WORK_DIR/config/includes.chroot/usr/local/lib/nyx" -name __pycache__ -type d -prune -exec rm -rf {} +
cp "$REPO_DIR/shell/nyx.nu" "$WORK_DIR/config/includes.chroot/usr/local/share/nushell/vendor/autoload/nyx.nu"
# Optional offline model: NYX_BUNDLE_MODEL=1 sudo ./image/build.sh
if [ "${NYX_BUNDLE_MODEL:-0}" = "1" ]; then
    sh "$IMAGE_DIR/bundle-model.sh" "$WORK_DIR/config" "$DOWNLOAD_DIR"
fi
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
