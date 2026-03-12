#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENDOR_DIR="$ROOT_DIR/vendor"
REPO_DIR="$VENDOR_DIR/whisper.cpp"
BUILD_DIR="$REPO_DIR/build"

mkdir -p "$VENDOR_DIR"

if [ ! -d "$REPO_DIR" ]; then
  git clone https://github.com/ggerganov/whisper.cpp "$REPO_DIR"
else
  git -C "$REPO_DIR" pull --ff-only
fi

cmake -S "$REPO_DIR" -B "$BUILD_DIR" -DWHISPER_BUILD_TESTS=OFF -DWHISPER_BUILD_EXAMPLES=ON
cmake --build "$BUILD_DIR" --config Release -j

echo "whisper-cli ready: $BUILD_DIR/bin/whisper-cli"
