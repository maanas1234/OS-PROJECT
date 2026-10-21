#!/bin/sh
# Optional: bake an offline model into the image so `nyx` works with no internet (M6).
# Called by build.sh when NYX_BUNDLE_MODEL=1:  bundle-model.sh <live-build config dir> <downloads dir>
# Adds ~1.2 GB to the ISO. Both downloads are pinned and SHA-256 verified.
set -eu

CONFIG_DIR=$1
DOWNLOAD_DIR=$2

LLAMA_TAG=b11756
LLAMA_SHA256=9def57d9e9b0149979a9ceba40896a4e2bf88c94734069a5567d2f487ceab551
LLAMA_ARCHIVE="$DOWNLOAD_DIR/llama-$LLAMA_TAG-bin-ubuntu-x64.tar.gz"
LLAMA_URL="https://github.com/ggml-org/llama.cpp/releases/download/$LLAMA_TAG/llama-$LLAMA_TAG-bin-ubuntu-x64.tar.gz"

# Qwen2.5-1.5B-Instruct, Q4_K_M, pinned to a repo commit.
MODEL_SHA256=6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e
MODEL_FILE="$DOWNLOAD_DIR/qwen2.5-1.5b-instruct-q4_k_m.gguf"
MODEL_URL="https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/91cad51170dc346986eccefdc2dd33a9da36ead9/qwen2.5-1.5b-instruct-q4_k_m.gguf"

fetch() { # url file sha256
    if [ -f "$2" ] && [ "$(sha256sum "$2" | cut -d ' ' -f 1)" = "$3" ]; then
        return 0
    fi
    rm -f "$2"
    curl --fail --location --retry 8 --retry-all-errors --retry-delay 3 --continue-at - "$1" -o "$2.part"
    if [ "$(sha256sum "$2.part" | cut -d ' ' -f 1)" != "$3" ]; then
        rm -f "$2.part"
        echo "checksum mismatch for $1" >&2
        exit 1
    fi
    mv "$2.part" "$2"
}

mkdir -p "$DOWNLOAD_DIR"
fetch "$LLAMA_URL" "$LLAMA_ARCHIVE" "$LLAMA_SHA256"
fetch "$MODEL_URL" "$MODEL_FILE" "$MODEL_SHA256"

LLAMA_DEST="$CONFIG_DIR/includes.chroot/usr/local/lib/llama"
MODEL_DEST="$CONFIG_DIR/includes.chroot/usr/local/share/nyx"
mkdir -p "$LLAMA_DEST" "$MODEL_DEST"
tar -xzf "$LLAMA_ARCHIVE" -C "$LLAMA_DEST" --strip-components=1
if [ ! -x "$LLAMA_DEST/llama-server" ]; then
    echo "llama-server missing from $LLAMA_ARCHIVE" >&2
    exit 1
fi
cp "$MODEL_FILE" "$MODEL_DEST/model.gguf"
echo "Bundled llama.cpp $LLAMA_TAG and $(basename "$MODEL_FILE")"
