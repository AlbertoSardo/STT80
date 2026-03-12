#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

if [ ! -d "venv" ]; then
  python3 -m venv venv
fi

source "venv/bin/activate"

python -m pip install --upgrade pip
CMAKE_ARGS="-DCMAKE_POLICY_VERSION_MINIMUM=3.5" python -m pip install -r requirements.txt -r requirements-dev.txt

./setup_whisper_cli.sh

rm -rf build dist
python setup.py py2app

echo "Done. Standalone app available at: dist/STT80.app"
if [ "${INCLUDE_MODELS:-0}" != "1" ]; then
  echo "Note: model files are not embedded by default."
  echo "Use INCLUDE_MODELS=1 ./make_standalone.sh to include local models in the app bundle."
fi
