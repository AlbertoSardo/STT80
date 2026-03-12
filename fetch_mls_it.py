import argparse
import os


def parse_args():
    parser = argparse.ArgumentParser(description="Download Italian benchmark pairs from Multilingual LibriSpeech.")
    parser.add_argument("--output-dir", required=True, help="Directory where audio/txt pairs are saved.")
    parser.add_argument("--split", default="test", help="Dataset split (test, train, validation).")
    parser.add_argument("--count", type=int, default=8, help="Number of samples to export.")
    return parser.parse_args()


def get_audio_bytes_and_ext(audio_obj):
    raw_bytes = audio_obj.get("bytes")
    path = str(audio_obj.get("path") or "")
    ext = os.path.splitext(path)[1].lower() or ".flac"
    return raw_bytes, ext


def main():
    args = parse_args()

    try:
        from datasets import Audio, load_dataset
    except ImportError as exc:
        raise SystemExit("Missing dependency 'datasets'. Install with: pip install datasets") from exc

    output_dir = os.path.abspath(args.output_dir)
    os.makedirs(output_dir, exist_ok=True)

    print("Loading Multilingual LibriSpeech Italian split (streaming)...")
    ds = load_dataset("facebook/multilingual_librispeech", "italian", split=args.split, streaming=True)
    ds = ds.cast_column("audio", Audio(decode=False))

    exported = 0
    for row in ds:
        transcript = str(row.get("transcript") or "").strip()
        audio_obj = row.get("audio") or {}
        audio_bytes, ext = get_audio_bytes_and_ext(audio_obj)

        if not transcript or not audio_bytes:
            continue

        stem = f"mls_it_{exported + 1:04d}"
        audio_path = os.path.join(output_dir, f"{stem}{ext}")
        text_path = os.path.join(output_dir, f"{stem}.txt")

        with open(audio_path, "wb") as audio_file:
            audio_file.write(audio_bytes)
        with open(text_path, "w", encoding="utf-8") as text_file:
            text_file.write(transcript)

        exported += 1
        print(f"Exported {stem}{ext}")

        if exported >= args.count:
            break

    print(f"Done. Exported {exported} samples to: {output_dir}")


if __name__ == "__main__":
    main()
