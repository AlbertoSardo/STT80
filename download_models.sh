#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

MODEL_DIR="${1:-}"
if [ "$MODEL_DIR" = "--dir" ]; then
  if [ $# -lt 2 ]; then
    echo "Usage: ./download_models.sh [--dir path] [tiny|base|small|medium-q5|medium ...]"
    exit 1
  fi
  TARGET_DIR="$2"
  shift 2
else
  TARGET_DIR="models"
fi

mkdir -p "$TARGET_DIR"

if [ $# -eq 0 ]; then
  set -- small medium-q5
fi

download_one() {
  local key="$1"
  local filename=""

  case "$key" in
    tiny) filename="ggml-tiny.bin" ;;
    base) filename="ggml-base.bin" ;;
    small) filename="ggml-small.bin" ;;
    medium-q5) filename="ggml-medium-q5_0.bin" ;;
    medium) filename="ggml-medium.bin" ;;
    *)
      echo "Unknown model key: $key"
      echo "Allowed: tiny, base, small, medium-q5, medium"
      exit 1
      ;;
  esac

  local url="https://huggingface.co/ggerganov/whisper.cpp/resolve/main/$filename"
  local out="$TARGET_DIR/$filename"

  echo "Downloading $key -> $out"
  curl -L "$url" -o "$out"
}

for model in "$@"; do
  download_one "$model"
done

echo "Done. Models downloaded in: $TARGET_DIR"
