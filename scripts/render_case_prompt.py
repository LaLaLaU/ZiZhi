from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from zizhi.case_profile_prompt import build_case_extraction_messages


DEFAULT_CHUNKS_PATH = ROOT / ".cache" / "zizhi_tagging_chunks.jsonl"


def main() -> None:
    parser = argparse.ArgumentParser(description="Render case extraction prompts for one chunk.")
    parser.add_argument("--chunks", type=Path, default=DEFAULT_CHUNKS_PATH, help="Path to tagging chunks JSON/JSONL.")
    parser.add_argument("--chunk-id", help="Exact chunk_id to render.")
    parser.add_argument("--index", type=int, help="0-based row index in tagging chunks JSONL.")
    parser.add_argument("--version", default="v1", choices=["v1"], help="Prompt version.")
    parser.add_argument("--max-cases", type=int, default=3, help="Maximum cases to request in the rendered prompt.")
    parser.add_argument(
        "--format",
        default="combined",
        choices=["combined", "system", "user", "json"],
        help="Output format.",
    )
    args = parser.parse_args()

    chunk_row = _load_row(args.chunks, chunk_id=args.chunk_id, index=args.index)
    payload = _build_payload(chunk_row)
    messages = build_case_extraction_messages(payload, version=args.version, max_cases=args.max_cases)

    if args.format == "system":
        print(messages["system_prompt"])
        return
    if args.format == "user":
        print(messages["user_prompt"])
        return
    if args.format == "json":
        print(json.dumps({"payload": payload, **messages}, ensure_ascii=False, indent=2))
        return

    print("===== SYSTEM PROMPT =====")
    print(messages["system_prompt"])
    print()
    print("===== USER PROMPT =====")
    print(messages["user_prompt"])


def _load_row(path: Path, chunk_id: str | None, index: int | None) -> dict[str, Any]:
    if chunk_id is None and index is None:
        raise SystemExit("Please provide either --chunk-id or --index.")
    path = _resolve_chunks_path(path)
    for row_index, row in enumerate(_load_rows(path)):
        row_chunk_id = str(row.get("chunk_id", ""))
        if chunk_id is not None and row_chunk_id == chunk_id:
            return row
        if index is not None and row_index == index:
            return row

    if chunk_id is not None:
        raise SystemExit(f"chunk_id not found: {chunk_id}")
    raise SystemExit(f"index out of range: {index}")


def _resolve_chunks_path(path: Path) -> Path:
    if path.exists():
        return path
    if path.suffix == ".jsonl":
        json_path = path.with_suffix(".json")
        if json_path.exists():
            return json_path
    if path.suffix == ".json":
        jsonl_path = path.with_suffix(".jsonl")
        if jsonl_path.exists():
            return jsonl_path
    raise SystemExit(f"Input file not found: {path}")


def _load_rows(path: Path) -> list[dict[str, Any]]:
    if path.suffix == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        return [row for row in data if isinstance(row, dict)] if isinstance(data, list) else []

    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as file:
        for line in file:
            stripped = line.strip()
            if not stripped:
                continue
            row = json.loads(stripped)
            if isinstance(row, dict):
                rows.append(row)
    return rows


def _build_payload(chunk_row: dict[str, Any]) -> dict[str, Any]:
    section_keys = [str(key) for key in chunk_row.get("section_keys", []) if str(key).strip()]
    section_text_map = _section_text_map(chunk_row)
    return {
        "chunk_id": chunk_row.get("chunk_id", ""),
        "volume_no": chunk_row.get("volume_no"),
        "volume_title": chunk_row.get("volume_title", ""),
        "chapter_title": chunk_row.get("chapter_title", ""),
        "year_title": chunk_row.get("year_title", ""),
        "section_keys": section_keys,
        "section_text_map": section_text_map,
        "white_text": chunk_row.get("white_text", ""),
    }


def _section_text_map(chunk_row: dict[str, Any]) -> dict[str, str]:
    section_keys = [str(key) for key in chunk_row.get("section_keys", []) if str(key).strip()]
    parts = [part.strip() for part in str(chunk_row.get("white_text", "")).splitlines() if part.strip()]
    if len(parts) == len(section_keys) and section_keys:
        return dict(zip(section_keys, parts, strict=False))
    if len(section_keys) == 1:
        return {section_keys[0]: str(chunk_row.get("white_text", "")).strip()}
    return {}


if __name__ == "__main__":
    main()
