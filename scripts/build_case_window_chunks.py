from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


DEFAULT_INPUT_PATH = ROOT / ".cache" / "zizhi_tagging_chunks.json"
DEFAULT_OUTPUT_PATH = ROOT / ".cache" / "case_experiments" / "window_chunks.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build longer case-extraction chunks from existing short chunks.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT_PATH, help="Existing tagging chunks JSON/JSONL.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH, help="Output experiment chunk JSON.")
    parser.add_argument("--volumes", nargs="+", type=int, required=True, help="Volume numbers to include.")
    parser.add_argument(
        "--window-chars",
        nargs="+",
        default=["5000", "10000", "volume"],
        help="Target window sizes. Use integers or 'volume'.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    source_rows = load_rows(resolve_json_family_path(args.input))
    selected = [row for row in source_rows if int(row.get("volume_no") or 0) in set(args.volumes)]

    rows: list[dict[str, Any]] = []
    for window in args.window_chars:
        if window == "volume":
            rows.extend(build_volume_windows(selected))
        else:
            rows.extend(build_sized_windows(selected, int(window)))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    summary = {
        "source_chunks": len(selected),
        "experiment_chunks": len(rows),
        "volumes": args.volumes,
        "window_chars": args.window_chars,
        "output": str(args.output),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def build_sized_windows(source_rows: list[dict[str, Any]], target_chars: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    grouped = group_by_volume(source_rows)
    for volume_no, volume_rows in grouped.items():
        buffer: list[dict[str, Any]] = []
        for row in volume_rows:
            if buffer and char_count(buffer) + row_char_count(row) > target_chars:
                rows.append(make_window_chunk(volume_no, f"w{target_chars}", len(rows) + 1, buffer))
                buffer = []
            buffer.append(row)
        if buffer:
            rows.append(make_window_chunk(volume_no, f"w{target_chars}", len(rows) + 1, buffer))
    return rows


def build_volume_windows(source_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for volume_no, volume_rows in group_by_volume(source_rows).items():
        rows.append(make_window_chunk(volume_no, "whole", len(rows) + 1, volume_rows))
    return rows


def make_window_chunk(volume_no: int, mode: str, index: int, source_rows: list[dict[str, Any]]) -> dict[str, Any]:
    first = source_rows[0]
    source_chunk_ids = [str(row.get("chunk_id", "")).strip() for row in source_rows if str(row.get("chunk_id", "")).strip()]
    section_keys: list[str] = []
    commentary_ids: list[str] = []
    text_parts: list[str] = []
    for row in source_rows:
        section_keys.extend(str(key) for key in row.get("section_keys", []) if str(key).strip())
        commentary_ids.extend(str(key) for key in row.get("commentary_ids", []) if str(key).strip())
        text = str(row.get("white_text", "")).strip()
        if text:
            text_parts.append(text)

    return {
        "chunk_id": f"casewin-v{volume_no:03d}-{mode}-c{index:04d}",
        "source_chunk_ids": source_chunk_ids,
        "section_keys": dedupe_preserve_order(section_keys),
        "volume_no": volume_no,
        "volume_title": first.get("volume_title", ""),
        "chapter_title": first.get("chapter_title", ""),
        "year_title": "",
        "white_text": "\n".join(text_parts),
        "white_char_count": sum(len(part) for part in text_parts),
        "section_count": len(dedupe_preserve_order(section_keys)),
        "commentary_ids": dedupe_preserve_order(commentary_ids),
        "commentary_count": len(dedupe_preserve_order(commentary_ids)),
        "chunk_version": f"case-window-{mode}",
    }


def group_by_volume(rows: list[dict[str, Any]]) -> dict[int, list[dict[str, Any]]]:
    grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        volume_no = int(row.get("volume_no") or 0)
        if volume_no:
            grouped[volume_no].append(row)
    return dict(sorted(grouped.items()))


def char_count(rows: list[dict[str, Any]]) -> int:
    return sum(row_char_count(row) for row in rows)


def row_char_count(row: dict[str, Any]) -> int:
    return int(row.get("white_char_count") or len(str(row.get("white_text", ""))))


def dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def load_rows(path: Path) -> list[dict[str, Any]]:
    if path.suffix == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        return [row for row in data if isinstance(row, dict)] if isinstance(data, list) else []
    with path.open("r", encoding="utf-8") as file:
        return [json.loads(line) for line in file if line.strip()]


def resolve_json_family_path(path: Path) -> Path:
    if path.exists():
        return path
    if path.suffix == ".jsonl" and path.with_suffix(".json").exists():
        return path.with_suffix(".json")
    if path.suffix == ".json" and path.with_suffix(".jsonl").exists():
        return path.with_suffix(".jsonl")
    raise SystemExit(f"Input file not found: {path}")


if __name__ == "__main__":
    main()
