# STT80

![macOS](https://img.shields.io/badge/macOS-12%2B-0A84FF)
![Python](https://img.shields.io/badge/Python-3.9%2B-3776AB)
![License](https://img.shields.io/badge/License-MIT-34C759)

STT80 is a local macOS transcription app built with **PyObjC** + **whisper.cpp**.

- Drag and drop audio files (`.m4a`, `.wav`, `.mp3`, `.flac`, `.ogg`, `.opus`, `.aac`, `.mp4`, `.m4b`)
- Any language supported by Whisper (`auto` detect or explicit code like `en`, `es`, `it`, `fr`)
- Estimated two-speaker turn split
- Midnight blue liquid-glass UI

## Backends

STT80 can run with two local backends:

- `whisper-cpp-python` (preferred for non-quantized models during source runs)
- `whisper-cli` (required for quantized models like `medium-q5`)

Backend selection behavior:

- `medium-q5` always uses `whisper-cli`
- non-quantized models try `whisper-cpp-python`, then fallback to `whisper-cli`
- standalone app bundles prefer `whisper-cli` by design

## Language Selection

STT80 supports multilingual transcription.

- In the app header, set `LANG` to `auto` (recommended) or to a language code (for example: `en`, `es`, `it`, `fr`, `de`, `pt`, `ja`, `zh`).
- You can set the default with environment variable `STT80_LANGUAGE`.

Examples:

```bash
STT80_LANGUAGE=auto ./run.sh
STT80_LANGUAGE=es ./run.sh
```

## Requirements

- macOS
- Python 3.9+
- `ffmpeg` (`brew install ffmpeg`)
- CMake + Xcode Command Line Tools (for `whisper-cli` local build)

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
CMAKE_ARGS="-DCMAKE_POLICY_VERSION_MINIMUM=3.5" pip install -r requirements.txt
```

Build local `whisper-cli` (required for `medium-q5`):

```bash
./setup_whisper_cli.sh
```

Download models (example):

```bash
./download_models.sh small medium-q5
```

## Run

```bash
./run.sh
```

## Model Locations

STT80 searches models in this order:

1. `STT80_MODEL_DIR` (if set)
2. `./models`
3. project root (`./`)
4. current working directory and `./models` from there
5. `~/Library/Application Support/STT80/models`

Supported model files:

- `ggml-tiny.bin`
- `ggml-base.bin`
- `ggml-small.bin`
- `ggml-medium-q5_0.bin`
- `ggml-medium.bin`

## Build Standalone macOS App

Create a redistributable `.app` bundle with py2app:

```bash
./make_standalone.sh
```

Output:

- `dist/STT80.app`

Optional: include local model files in the bundle (large output):

```bash
INCLUDE_MODELS=1 ./make_standalone.sh
```

Package a release zip + checksum:

```bash
./package_release.sh v0.1.0
```

Outputs:

- `release/STT80-macos-universal-v0.1.0.zip`
- `release/STT80-macos-universal-v0.1.0.zip.sha256`

## Benchmark Transcription Quality

Dataset format:

- `clip01.m4a` + `clip01.txt`
- `clip02.m4a` + `clip02.txt`

Validate dataset first:

```bash
source venv/bin/activate
python prepare_dataset.py --dataset-dir ./dataset
```

Run benchmark:

```bash
python benchmark.py --dataset-dir ./dataset --models tiny,base,small,medium-q5,medium --language auto --output-json ./benchmark-report.json
```

Metrics:

- WER (word error rate)
- CER (character error rate)
- total runtime per model
