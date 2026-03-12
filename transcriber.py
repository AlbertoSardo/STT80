import importlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile


def runtime_base_dir():
    if getattr(sys, "frozen", False):
        executable_dir = os.path.dirname(os.path.abspath(sys.executable))
        resources_dir = os.path.abspath(os.path.join(executable_dir, "..", "Resources"))
        if os.path.isdir(resources_dir):
            return resources_dir
    return os.path.dirname(os.path.abspath(__file__))


def model_search_dirs():
    dirs = []

    env_dir = os.environ.get("STT80_MODEL_DIR", "").strip()
    if env_dir:
        dirs.append(os.path.abspath(os.path.expanduser(env_dir)))

    base_dir = runtime_base_dir()
    dirs.append(os.path.join(base_dir, "models"))
    dirs.append(base_dir)

    cwd = os.path.abspath(os.getcwd())
    dirs.append(os.path.join(cwd, "models"))
    dirs.append(cwd)

    app_support_models = os.path.expanduser("~/Library/Application Support/STT80/models")
    dirs.append(os.path.abspath(app_support_models))

    unique = []
    for path in dirs:
        if path not in unique:
            unique.append(path)
    return unique


def resolve_model_path(model_reference):
    if not model_reference:
        return None

    candidate = os.path.expanduser(str(model_reference))
    if os.path.isabs(candidate) or os.sep in candidate:
        absolute = os.path.abspath(candidate)
        if os.path.exists(absolute):
            return absolute
        return None

    for directory in model_search_dirs():
        file_path = os.path.join(directory, candidate)
        if os.path.exists(file_path):
            return os.path.abspath(file_path)

    return None


class Transcriber:
    def __init__(self, model_path=None):
        requested_model = str(model_path or "ggml-base.bin")
        resolved_model = resolve_model_path(requested_model)

        if not resolved_model:
            searched = "\n".join(f"- {path}" for path in model_search_dirs())
            raise FileNotFoundError(
                f"Whisper.cpp model not found: {requested_model}\n\n"
                f"Searched in:\n{searched}\n\n"
                "Download a ggml model (e.g. ggml-base.bin) and place it in one of those folders."
            )

        self.model_path = resolved_model
        self.cpu_threads = max(1, min(8, os.cpu_count() or 4))
        self.model = None
        self.backend = ""
        self.whisper_cli_path = ""

        model_name = os.path.basename(self.model_path).lower()
        prefer_cli = getattr(sys, "frozen", False) or os.environ.get("STT80_FORCE_CLI", "0") == "1"

        if prefer_cli:
            try:
                self._init_cli_backend()
                return
            except Exception as exc:
                if "-q" in model_name:
                    raise RuntimeError(f"Failed to initialize whisper-cli backend: {exc}") from exc

        if "-q" in model_name:
            self._init_cli_backend()
            return

        try:
            self._init_python_backend()
        except Exception:
            self._init_cli_backend()

    @property
    def backend_label(self):
        if self.backend == "cli":
            return "whisper-cli"
        return "whisper-cpp-python"

    def _init_python_backend(self):
        self._configure_whisper_cpp_lib_path()
        try:
            module = importlib.import_module("whisper_cpp_python")
            Whisper = getattr(module, "Whisper")
        except Exception as exc:
            raise RuntimeError(
                "Missing dependency 'whisper-cpp-python'. Install it with: pip install whisper-cpp-python"
            ) from exc

        self.model = Whisper(model_path=self.model_path, n_threads=self.cpu_threads)
        self.backend = "python"

    def _init_cli_backend(self):
        self.whisper_cli_path = self._resolve_whisper_cli_path()
        if not self.whisper_cli_path:
            raise RuntimeError(
                "Quantized model requested but whisper-cli was not found. "
                "Build whisper.cpp locally (./setup_whisper_cli.sh) or install whisper-cli in PATH."
            )
        self.backend = "cli"

    def _resolve_whisper_cli_path(self):
        env_path = os.environ.get("WHISPER_CLI_PATH", "").strip()
        if env_path and os.path.exists(env_path):
            return os.path.abspath(env_path)

        candidate_paths = [
            os.path.join(runtime_base_dir(), "vendor", "whisper.cpp", "build", "bin", "whisper-cli"),
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor", "whisper.cpp", "build", "bin", "whisper-cli"),
            os.path.join(os.path.abspath(os.getcwd()), "vendor", "whisper.cpp", "build", "bin", "whisper-cli"),
        ]
        for candidate in candidate_paths:
            if os.path.exists(candidate):
                return candidate

        return shutil.which("whisper-cli") or ""

    def _configure_whisper_cpp_lib_path(self):
        if os.environ.get("WHISPER_CPP_LIB"):
            return

        spec = importlib.util.find_spec("whisper_cpp_python")
        if spec and spec.submodule_search_locations:
            base_path = list(spec.submodule_search_locations)[0]
            dylib_path = os.path.join(base_path, "libwhisper.dylib")
            if os.path.exists(dylib_path):
                os.environ["WHISPER_CPP_LIB"] = dylib_path

    def convert_to_wav(self, input_file, output_file):
        command = [
            "ffmpeg",
            "-i",
            input_file,
            "-ar",
            "16000",
            "-ac",
            "1",
            "-c:a",
            "pcm_s16le",
            "-y",
            output_file,
        ]
        subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def _normalize_result(self, result):
        if isinstance(result, dict):
            return result
        if hasattr(result, "__dict__"):
            return result.__dict__
        return {"text": str(result), "segments": []}

    def _normalize_cli_transcription_text(self, text):
        if not text:
            return ""
        compact = re.sub(r"\s+", " ", text).strip()
        compact = re.sub(r"\s+([,.;:!?])", r"\1", compact)
        return compact

    def _format_time(self, seconds):
        total = int(seconds or 0)
        minutes = total // 60
        rem = total % 60
        return f"{minutes:02d}:{rem:02d}"

    def _dialogue_from_segments(self, segments):
        if not segments:
            return ""

        current_speaker = 1
        last_end = None
        last_text = ""
        lines = []

        for segment in segments:
            text = str(segment.get("text", "")).strip()
            if not text:
                continue

            start = float(segment.get("start", 0.0) or 0.0)
            end = float(segment.get("end", start) or start)
            pause = None if last_end is None else max(0.0, start - last_end)

            should_flip = False
            if pause is not None and pause > 0.9:
                should_flip = True
            elif pause is not None and pause > 0.35 and last_text.endswith(("?", "!", "...")):
                should_flip = True

            if should_flip:
                current_speaker = 2 if current_speaker == 1 else 1

            stamp = self._format_time(start)
            lines.append(f"[{stamp}] SPEAKER {current_speaker}: {text}")

            last_end = end
            last_text = text

        return "\n".join(lines)

    def transcribe(self, file_path):
        try:
            full_text, segments = self._transcribe_core(file_path)
            dialogue = self._dialogue_from_segments(segments)

            if dialogue:
                return f"TRANSCRIPT\n\n{full_text}\n\nESTIMATED TURNS (2 SPEAKERS)\n\n{dialogue}"
            return f"TRANSCRIPT\n\n{full_text}"
        except FileNotFoundError as exc:
            return f"Error: {exc}"
        except subprocess.CalledProcessError:
            return "Error: audio conversion failed. Make sure ffmpeg is installed and available in PATH."
        except Exception as exc:
            return f"Error during transcription: {exc}"

    def transcribe_text(self, file_path):
        full_text, _segments = self._transcribe_core(file_path)
        return full_text

    def _transcribe_with_python(self, wav_path):
        if self.model is None:
            raise RuntimeError("Python Whisper backend is not initialized")

        with open(wav_path, "rb") as audio_handle:
            result = self.model.transcribe(
                audio_handle,
                language="it",
                response_format="verbose_json",
                temperature=0.0,
            )

        data = self._normalize_result(result)
        full_text = str(data.get("text", "")).strip()
        segments = data.get("segments", []) or []
        return full_text, segments

    def _transcribe_with_cli(self, wav_path):
        with tempfile.TemporaryDirectory(prefix="stt80-whisper-") as temp_dir:
            output_base = os.path.join(temp_dir, "result")
            command = [
                self.whisper_cli_path,
                "-m",
                self.model_path,
                "-l",
                "it",
                "-f",
                wav_path,
                "-ojf",
                "-of",
                output_base,
                "-np",
                "-tp",
                "0.0",
                "-t",
                str(self.cpu_threads),
            ]
            subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            json_path = f"{output_base}.json"
            if not os.path.exists(json_path):
                raise RuntimeError("whisper-cli did not produce JSON output")

            with open(json_path, "r", encoding="utf-8") as file_handle:
                payload = json.load(file_handle)

        chunks = payload.get("transcription", []) or []
        segments = []
        full_parts = []

        for chunk in chunks:
            text = str(chunk.get("text", "")).strip()
            if not text:
                continue

            offsets = chunk.get("offsets", {}) or {}
            start_ms = float(offsets.get("from", 0.0) or 0.0)
            end_ms = float(offsets.get("to", start_ms) or start_ms)

            full_parts.append(text)
            segments.append(
                {
                    "start": start_ms / 1000.0,
                    "end": end_ms / 1000.0,
                    "text": text,
                }
            )

        full_text = self._normalize_cli_transcription_text(" ".join(full_parts))
        return full_text, segments

    def _transcribe_core(self, file_path):
        wav_path = f"{file_path}.temp-16k.wav"
        try:
            self.convert_to_wav(file_path, wav_path)
            if self.backend == "cli":
                return self._transcribe_with_cli(wav_path)
            return self._transcribe_with_python(wav_path)
        finally:
            if os.path.exists(wav_path):
                os.remove(wav_path)


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        transcriber = Transcriber()
        print(transcriber.transcribe(sys.argv[1]))
