import os

from setuptools import setup


APP = ["main.py"]

MODEL_FILES = [
    "ggml-tiny.bin",
    "ggml-base.bin",
    "ggml-small.bin",
    "ggml-medium-q5_0.bin",
    "ggml-medium.bin",
]


def build_resources():
    resources = []

    whisper_cli = os.path.join("vendor", "whisper.cpp", "build", "bin", "whisper-cli")
    if os.path.exists(whisper_cli):
        resources.append(whisper_cli)

    include_models = os.environ.get("INCLUDE_MODELS", "0") == "1"
    if include_models:
        for model in MODEL_FILES:
            if os.path.exists(model):
                resources.append(model)

    return resources


OPTIONS = {
    "argv_emulation": False,
    "packages": ["objc", "AppKit", "Foundation"],
    "includes": ["transcriber", "imp"],
    "resources": build_resources(),
    "plist": {
        "CFBundleName": "STT80",
        "CFBundleDisplayName": "STT80",
        "CFBundleIdentifier": "com.stt80.app",
        "CFBundleShortVersionString": "0.1.0",
        "CFBundleVersion": "1",
        "LSMinimumSystemVersion": "12.0",
        "NSHighResolutionCapable": True,
    },
}


setup(
    app=APP,
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
)
