import argparse
import os


def parse_args():
    parser = argparse.ArgumentParser(description="Download a small Italian benchmark set from Common Voice.")
    parser.add_argument("--output-dir", required=True, help="Directory where wav/txt pairs will be saved.")
    parser.add_argument("--split", default="test", help="Dataset split (test, validation, train).")
    parser.add_argument("--count", type=int, default=10, help="Number of samples to export.")
    return parser.parse_args()


def main():
    args = parse_args()

    try:
        from datasets import load_dataset
    except ImportError as exc:
        raise SystemExit("Missing dependency 'datasets'. Install with: pip install datasets") from exc

    try:
        import soundfile as sf
    except ImportError as exc:
        raise SystemExit("Missing dependency 'soundfile'. Install with: pip install soundfile") from exc

    output_dir = os.path.abspath(args.output_dir)
    os.makedirs(output_dir, exist_ok=True)

    print("Loading Common Voice Italian split...")
    ds = load_dataset("mozilla-foundation/common_voice_17_0", "it", split=args.split)

    exported = 0
    index = 0
    while exported < args.count and index < len(ds):
        row = ds[index]
        index += 1

        sentence = str(row.get("sentence") or "").strip()
        audio = row.get("audio") or {}
        audio_array = audio.get("array")
        sample_rate = int(audio.get("sampling_rate") or 0)

        if not sentence or audio_array is None or sample_rate <= 0:
            continue

        stem = f"cv_it_{exported + 1:04d}"
        wav_path = os.path.join(output_dir, f"{stem}.wav")
        txt_path = os.path.join(output_dir, f"{stem}.txt")

        sf.write(wav_path, audio_array, sample_rate)
        with open(txt_path, "w", encoding="utf-8") as txt_file:
            txt_file.write(sentence)

        exported += 1
        print(f"Exported {stem}")

    print(f"Done. Exported {exported} samples to: {output_dir}")


if __name__ == "__main__":
    main()
