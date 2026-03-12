#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

if [ ! -d "dist/STT80.app" ]; then
  echo "dist/STT80.app not found. Building standalone app first..."
  INCLUDE_MODELS="${INCLUDE_MODELS:-0}" ./make_standalone.sh
fi

mkdir -p release

VERSION="${1:-$(date +%Y%m%d)}"
ZIP_NAME="STT80-macos-universal-${VERSION}.zip"
ZIP_PATH="release/${ZIP_NAME}"
SHA_PATH="${ZIP_PATH}.sha256"

rm -f "$ZIP_PATH" "$SHA_PATH"

ditto -c -k --keepParent "dist/STT80.app" "$ZIP_PATH"
shasum -a 256 "$ZIP_PATH" > "$SHA_PATH"

echo "Release package created: $ZIP_PATH"
echo "Checksum file created:   $SHA_PATH"
