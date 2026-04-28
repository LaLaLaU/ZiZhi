from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from zizhi.case_postprocess import build_consolidated_corpus, postprocess_case_run


DEFAULT_CHUNKS_PATH = ROOT / ".cache" / "zizhi_tagging_chunks.jsonl"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Postprocess case runs with role normalization, sorting, and conservative dedupe/merge.")
    parser.add_argument("--chunks", type=Path, default=DEFAULT_CHUNKS_PATH, help="Path to tagging chunks JSON/JSONL.")
    parser.add_argument("--run-dir", action="append", type=Path, required=True, help="Run directory to process. Repeat for multiple runs.")
    parser.add_argument("--output-run-dir", type=Path, default=None, help="Optional output directory for a consolidated corpus.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_dirs = [path.resolve() for path in args.run_dir]
    if args.output_run_dir is None and len(run_dirs) == 1:
        summary = postprocess_case_run(run_dirs[0], args.chunks.resolve())
    else:
        output_run_dir = args.output_run_dir.resolve() if args.output_run_dir is not None else run_dirs[0]
        summary = build_consolidated_corpus(run_dirs, output_run_dir, args.chunks.resolve())
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
