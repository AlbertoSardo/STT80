import argparse
import json
import os
import re
import time

from transcriber import Transcriber, model_search_dirs, normalize_language, resolve_model_path


MODEL_FILES = {
    "tiny": "ggml-tiny.bin",
    "base": "ggml-base.bin",
    "small": "ggml-small.bin",
    "medium-q5": "ggml-medium-q5_0.bin",
    "medium": "ggml-medium.bin",
}

SUPPORTED_AUDIO_EXTENSIONS = (".m4a", ".wav", ".mp3", ".flac", ".ogg", ".opus")


def normalize_text(text):
    normalized = text.lower()
    normalized = re.sub(r"[^\w\s]", " ", normalized, flags=re.UNICODE)
    normalized = re.sub(r"\s+", " ", normalized, flags=re.UNICODE).strip()
    return normalized


def levenshtein_distance(seq_a, seq_b):
    if len(seq_a) < len(seq_b):
        seq_a, seq_b = seq_b, seq_a
    previous = list(range(len(seq_b) + 1))
    for i, item_a in enumerate(seq_a, start=1):
        current = [i]
        for j, item_b in enumerate(seq_b, start=1):
            substitution = previous[j - 1] + (0 if item_a == item_b else 1)
            insertion = current[j - 1] + 1
            deletion = previous[j] + 1
            current.append(min(substitution, insertion, deletion))
        previous = current
    return previous[-1]


def wer(reference, hypothesis):
    ref_tokens = normalize_text(reference).split()
    hyp_tokens = normalize_text(hypothesis).split()
    if not ref_tokens:
        return 0.0 if not hyp_tokens else 1.0
    distance = levenshtein_distance(ref_tokens, hyp_tokens)
    return distance / len(ref_tokens)


def cer(reference, hypothesis):
    ref_chars = list(normalize_text(reference).replace(" ", ""))
    hyp_chars = list(normalize_text(hypothesis).replace(" ", ""))
    if not ref_chars:
        return 0.0 if not hyp_chars else 1.0
    distance = levenshtein_distance(ref_chars, hyp_chars)
    return distance / len(ref_chars)


def collect_dataset(dataset_dir):
    items = []
    for filename in sorted(os.listdir(dataset_dir)):
        path = os.path.join(dataset_dir, filename)
        if not os.path.isfile(path):
            continue
        if not filename.lower().endswith(SUPPORTED_AUDIO_EXTENSIONS):
            continue
        stem, _ext = os.path.splitext(filename)
        reference_path = os.path.join(dataset_dir, f"{stem}.txt")
        if not os.path.exists(reference_path):
            continue
        with open(reference_path, "r", encoding="utf-8") as ref_file:
            reference_text = ref_file.read().strip()
        items.append({
            "id": stem,
            "audio_path": path,
            "reference": reference_text,
        })
    return items


def benchmark_model(model_key, dataset_items, language):
    model_file = MODEL_FILES[model_key]
    model_path = resolve_model_path(model_file)
    if not model_path:
        searched = ", ".join(model_search_dirs())
        return {
            "model": model_key,
            "model_path": "",
            "error": f"Missing model file: {model_file} (searched in: {searched})",
            "files": [],
        }

    try:
        transcriber = Transcriber(model_path=model_path, language=language)
    except Exception as exc:
        return {
            "model": model_key,
            "model_path": model_path,
            "error": f"Model load failed: {exc}",
            "files": [],
        }
    rows = []
    start_all = time.perf_counter()

    for item in dataset_items:
        file_start = time.perf_counter()
        output = transcriber.transcribe_text(item["audio_path"])
        elapsed = time.perf_counter() - file_start
        row = {
            "id": item["id"],
            "audio_path": item["audio_path"],
            "reference": item["reference"],
            "hypothesis": output,
            "wer": wer(item["reference"], output),
            "cer": cer(item["reference"], output),
            "seconds": elapsed,
        }
        rows.append(row)

    total_seconds = time.perf_counter() - start_all
    avg_wer = sum(r["wer"] for r in rows) / len(rows) if rows else None
    avg_cer = sum(r["cer"] for r in rows) / len(rows) if rows else None

    return {
        "model": model_key,
        "model_path": model_path,
        "avg_wer": avg_wer,
        "avg_cer": avg_cer,
        "total_seconds": total_seconds,
        "files": rows,
    }


def print_report(report):
    print("\n=== STT80 BENCHMARK REPORT ===\n")
    print(f"Dataset files: {report['dataset_count']}")
    print(f"Dataset dir:   {report['dataset_dir']}\n")
    print(f"Language:      {report['language']}\n")

    valid_runs = [r for r in report["models"] if "error" not in r]
    valid_runs.sort(key=lambda r: r["avg_wer"])

    for run in report["models"]:
        if "error" in run:
            print(f"- {run['model']}: ERROR - {run['error']}")
            continue
        print(
            f"- {run['model']}: avg WER={run['avg_wer']:.3f} | avg CER={run['avg_cer']:.3f} | total={run['total_seconds']:.1f}s"
        )

    if valid_runs:
        best = valid_runs[0]
        print(f"\nBest model on this dataset: {best['model']} (lowest WER)")


def parse_args():
    parser = argparse.ArgumentParser(description="Benchmark whisper.cpp models on local labeled audio files.")
    parser.add_argument(
        "--dataset-dir",
        required=True,
        help="Folder with audio files and matching .txt references (same basename).",
    )
    parser.add_argument(
        "--models",
        default="tiny,base,small,medium-q5,medium",
        help="Comma-separated model keys: tiny,base,small,medium-q5,medium",
    )
    parser.add_argument(
        "--output-json",
        default="",
        help="Optional path to save full JSON report.",
    )
    parser.add_argument(
        "--language",
        default=os.environ.get("STT80_LANGUAGE", "auto"),
        help="Language code for transcription (e.g. en, it, es) or 'auto'.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    dataset_dir = os.path.abspath(args.dataset_dir)
    language = normalize_language(args.language)

    if not os.path.isdir(dataset_dir):
        raise SystemExit(f"Dataset dir not found: {dataset_dir}")

    dataset_items = collect_dataset(dataset_dir)
    if not dataset_items:
        raise SystemExit(
            "No benchmark pairs found. Add files like 'clip01.m4a' + 'clip01.txt' in dataset dir."
        )

    models = [m.strip() for m in args.models.split(",") if m.strip()]
    invalid = [m for m in models if m not in MODEL_FILES]
    if invalid:
        raise SystemExit(f"Invalid model keys: {invalid}. Use: {list(MODEL_FILES.keys())}")

    report = {
        "dataset_dir": dataset_dir,
        "dataset_count": len(dataset_items),
        "language": language,
        "models": [],
    }

    for model_key in models:
        print(f"Running model '{model_key}'...")
        result = benchmark_model(model_key, dataset_items, language)
        report["models"].append(result)

    print_report(report)

    if args.output_json:
        output_path = os.path.abspath(args.output_json)
        with open(output_path, "w", encoding="utf-8") as out_file:
            json.dump(report, out_file, ensure_ascii=False, indent=2)
        print(f"\nSaved JSON report: {output_path}")


if __name__ == "__main__":
    main()
