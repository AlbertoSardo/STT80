import argparse
import os


SUPPORTED_AUDIO_EXTENSIONS = (".m4a", ".wav", ".mp3", ".flac", ".ogg", ".opus")


def scan_dataset(dataset_dir):
    audio_by_stem = {}
    text_by_stem = {}

    for name in sorted(os.listdir(dataset_dir)):
        path = os.path.join(dataset_dir, name)
        if not os.path.isfile(path):
            continue
        stem, ext = os.path.splitext(name)
        ext = ext.lower()
        if ext in SUPPORTED_AUDIO_EXTENSIONS:
            audio_by_stem[stem] = path
        elif ext == ".txt":
            text_by_stem[stem] = path

    audio_stems = set(audio_by_stem.keys())
    text_stems = set(text_by_stem.keys())

    paired = sorted(audio_stems & text_stems)
    missing_text = sorted(audio_stems - text_stems)
    missing_audio = sorted(text_stems - audio_stems)

    empty_text = []
    for stem in paired:
        txt_path = text_by_stem[stem]
        try:
            with open(txt_path, "r", encoding="utf-8") as handle:
                content = handle.read().strip()
            if not content:
                empty_text.append(stem)
        except Exception:
            empty_text.append(stem)

    return {
        "paired": paired,
        "missing_text": missing_text,
        "missing_audio": missing_audio,
        "empty_text": sorted(empty_text),
        "audio_by_stem": audio_by_stem,
        "text_by_stem": text_by_stem,
    }


def print_report(report, dataset_dir):
    print("\n=== STT80 DATASET CHECK ===\n")
    print(f"Dataset dir: {dataset_dir}")
    print(f"Valid pairs: {len(report['paired'])}")
    print(f"Audio without .txt: {len(report['missing_text'])}")
    print(f".txt without audio: {len(report['missing_audio'])}")
    print(f"Empty/invalid .txt: {len(report['empty_text'])}\n")

    if report["paired"]:
        print("Paired examples:")
        for stem in report["paired"]:
            audio_name = os.path.basename(report["audio_by_stem"][stem])
            text_name = os.path.basename(report["text_by_stem"][stem])
            print(f"- {stem}: {audio_name} + {text_name}")
        print("")

    if report["missing_text"]:
        print("Missing reference .txt for:")
        for stem in report["missing_text"]:
            audio_name = os.path.basename(report["audio_by_stem"][stem])
            print(f"- {audio_name}")
        print("")

    if report["missing_audio"]:
        print("Missing audio for .txt:")
        for stem in report["missing_audio"]:
            text_name = os.path.basename(report["text_by_stem"][stem])
            print(f"- {text_name}")
        print("")

    if report["empty_text"]:
        print("Empty/invalid transcript files:")
        for stem in report["empty_text"]:
            text_name = os.path.basename(report["text_by_stem"][stem])
            print(f"- {text_name}")
        print("")


def parse_args():
    parser = argparse.ArgumentParser(description="Validate local benchmark dataset pairs.")
    parser.add_argument("--dataset-dir", required=True, help="Folder containing audio + .txt reference pairs.")
    return parser.parse_args()


def main():
    args = parse_args()
    dataset_dir = os.path.abspath(args.dataset_dir)

    if not os.path.isdir(dataset_dir):
        raise SystemExit(f"Dataset dir not found: {dataset_dir}")

    report = scan_dataset(dataset_dir)
    print_report(report, dataset_dir)

    if not report["paired"]:
        raise SystemExit("No valid audio/.txt pairs found.")

    if report["missing_text"] or report["missing_audio"] or report["empty_text"]:
        raise SystemExit("Dataset has issues. Fix the items above before running benchmark.")

    print("Dataset is ready for benchmark.py")


if __name__ == "__main__":
    main()
