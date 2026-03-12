# STT80 Release Checklist

Use this checklist before publishing a new GitHub release.

## 1) Clean Build

- Ensure dependencies are installed:

```bash
python3 -m venv venv
source venv/bin/activate
CMAKE_ARGS="-DCMAKE_POLICY_VERSION_MINIMUM=3.5" pip install -r requirements.txt -r requirements-dev.txt
```

- Build local backend binaries and app bundle:

```bash
./setup_whisper_cli.sh
INCLUDE_MODELS=0 ./make_standalone.sh
```

## 2) Smoke Test

- Launch the source app:

```bash
./run.sh
```

- Confirm:
  - UI opens
  - model switching works
  - `medium-q5` loads (backend should show `whisper-cli`)
  - drag/drop transcription works

## 3) Package Artifacts

- Create release zip + checksum:

```bash
./package_release.sh v0.1.0
```

- Expected outputs:
  - `release/STT80-macos-universal-v0.1.0.zip`
  - `release/STT80-macos-universal-v0.1.0.zip.sha256`

## 4) GitHub Release

- Create git tag (example):

```bash
git tag v0.1.0
git push origin v0.1.0
```

- Create GitHub release and upload:
  - zip artifact
  - checksum file

## 5) Release Notes Template

- Added/changed features
- Backend notes (`whisper-cpp-python` + `whisper-cli`)
- Supported models (`tiny`, `base`, `small`, `medium-q5`, `medium`)
- Known limitations (local-only build, no embedded models by default)
