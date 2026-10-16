"""Compare saved video predictions against explicit reviewed location IDs."""
import argparse
import hashlib
import json
from pathlib import Path
from app.ml.benchmark_evaluation import evaluate_videos


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path)
    parser.add_argument("predictions", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    raw = args.predictions.read_bytes()
    report = evaluate_videos(json.loads(args.dataset.read_text()), json.loads(raw))
    report["predictions_sha256"] = hashlib.sha256(raw).hexdigest()
    rendered = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if args.output:
        args.output.write_text(rendered)
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()
