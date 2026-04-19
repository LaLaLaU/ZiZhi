from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from statistics import mean, median
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


DEFAULT_INPUT_PATH = ROOT / ".cache" / "zizhi_white_corpus.txt"
DEFAULT_OUTPUT_PATH = ROOT / ".cache" / "zizhi_tagging_chunks.jsonl"
DEFAULT_COMMENTARY_OUTPUT_PATH = ROOT / ".cache" / "zizhi_simaguang_commentaries.jsonl"

CHUNK_MIN_CHARS = 600
CHUNK_TARGET_MIN_CHARS = 900
CHUNK_TARGET_MAX_CHARS = 1400
CHUNK_HARD_MAX_CHARS = 1600
CHUNK_OVERLAP_SECTIONS = 1
OVERSIZED_SECTION_OVERLAP_SENTENCES = 3
OVERSIZED_SECTION_OVERLAP_CHARS = 240
TAGGING_CHUNK_VERSION = "tagging-white-section-aware-v1"
SIMAGUANG_COMMENTARY_VERSION = "simaguang-commentary-v1"

VOLUME_HEADING_RE = re.compile(r"^=+\s*卷\s+(\d+)\s*\|\s*(.*?)\s*=+$")
CHAPTER_HEADING_RE = re.compile(r"^##\s+(.+?)\s*$")
YEAR_HEADING_RE = re.compile(r"^###\s+(.+?)\s*$")
SECTION_KEY_RE = re.compile(r"^\[(\d{3}-s\d{4})\]\s*$")
SENTENCE_RE = re.compile(r"[^。！？；!?;]+[。！？；!?;]?")
SIMAGUANG_MARKERS = ("臣司马光曰", "臣光曰")


@dataclass
class WhiteSection:
    section_key: str
    volume_no: int
    volume_title: str
    chapter_title: str
    year_title: str
    white_text: str
    commentary_ids: list[str] = field(default_factory=list)


@dataclass
class CommentaryRecord:
    commentary_id: str
    author: str
    source_section_key: str
    volume_no: int
    volume_title: str
    chapter_title: str
    year_title: str
    commentary_text: str
    commentary_char_count: int
    commentary_version: str = SIMAGUANG_COMMENTARY_VERSION
    linked_chunk_ids: list[str] = field(default_factory=list)


def parse_white_corpus(path: str | Path) -> list[WhiteSection]:
    input_path = Path(path)
    sections: list[WhiteSection] = []
    volume_no = 0
    volume_title = ""
    chapter_title = ""
    year_title = ""
    current_key = ""
    current_parts: list[str] = []

    def flush_current() -> None:
        nonlocal current_key, current_parts
        if not current_key:
            return
        white_text = normalize_section_text(" ".join(current_parts))
        if white_text:
            sections.append(
                WhiteSection(
                    section_key=current_key,
                    volume_no=volume_no,
                    volume_title=volume_title,
                    chapter_title=chapter_title,
                    year_title=year_title,
                    white_text=white_text,
                )
            )
        current_key = ""
        current_parts = []

    with input_path.open("r", encoding="utf-8") as file:
        for raw_line in file:
            line = raw_line.strip()
            if not line:
                continue

            volume_match = VOLUME_HEADING_RE.match(line)
            if volume_match:
                flush_current()
                volume_no = int(volume_match.group(1))
                volume_title = volume_match.group(2).strip()
                chapter_title = ""
                year_title = ""
                continue

            chapter_match = CHAPTER_HEADING_RE.match(line)
            if chapter_match:
                flush_current()
                chapter_title = chapter_match.group(1).strip()
                year_title = ""
                continue

            year_match = YEAR_HEADING_RE.match(line)
            if year_match:
                flush_current()
                year_title = year_match.group(1).strip()
                continue

            section_match = SECTION_KEY_RE.match(line)
            if section_match:
                flush_current()
                current_key = section_match.group(1)
                current_parts = []
                continue

            if current_key:
                current_parts.append(line)

    flush_current()
    return sections


def extract_simaguang_commentaries(sections: list[WhiteSection]) -> tuple[list[WhiteSection], list[CommentaryRecord]]:
    cleaned_sections: list[WhiteSection] = []
    commentary_records: list[CommentaryRecord] = []
    commentary_index = 1

    for section in sections:
        factual_text, commentary_text = split_factual_and_simaguang_commentary(section.white_text)
        commentary_ids: list[str] = []

        if commentary_text:
            commentary_id = f"sg-v{section.volume_no:03d}-m{commentary_index:05d}"
            commentary_index += 1
            commentary_records.append(
                CommentaryRecord(
                    commentary_id=commentary_id,
                    author="司马光",
                    source_section_key=section.section_key,
                    volume_no=section.volume_no,
                    volume_title=section.volume_title,
                    chapter_title=section.chapter_title,
                    year_title=section.year_title,
                    commentary_text=commentary_text,
                    commentary_char_count=len(commentary_text),
                )
            )
            commentary_ids.append(commentary_id)

        cleaned_sections.append(
            WhiteSection(
                section_key=section.section_key,
                volume_no=section.volume_no,
                volume_title=section.volume_title,
                chapter_title=section.chapter_title,
                year_title=section.year_title,
                white_text=factual_text,
                commentary_ids=commentary_ids,
            )
        )

    return cleaned_sections, commentary_records


def build_tagging_chunks_from_sections(
    sections: list[WhiteSection],
    min_chars: int = CHUNK_MIN_CHARS,
    target_min_chars: int = CHUNK_TARGET_MIN_CHARS,
    target_max_chars: int = CHUNK_TARGET_MAX_CHARS,
    hard_max_chars: int = CHUNK_HARD_MAX_CHARS,
    overlap_sections: int = CHUNK_OVERLAP_SECTIONS,
) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    buffer: list[WhiteSection] = []
    buffer_has_new_since_emit = False
    current_context: tuple[int, str] | None = None
    chunk_index = 1

    def emit_buffer(force: bool = False) -> None:
        nonlocal buffer, buffer_has_new_since_emit, chunk_index
        if not buffer or not buffer_has_new_since_emit:
            if force:
                buffer = []
            return
        chunks.append(make_tagging_chunk(chunk_index, buffer))
        chunk_index += 1
        buffer = []
        buffer_has_new_since_emit = False

    for section in sections:
        if not section.white_text:
            continue

        section_context = (section.volume_no, section.chapter_title)
        if current_context is None:
            current_context = section_context
        elif section_context != current_context:
            emit_buffer(force=True)
            current_context = section_context

        if len(section.white_text) > hard_max_chars:
            emit_buffer(force=True)
            oversized_parts = split_oversized_text(
                section.white_text,
                target_max_chars,
                overlap_sentences=OVERSIZED_SECTION_OVERLAP_SENTENCES,
                overlap_chars=OVERSIZED_SECTION_OVERLAP_CHARS,
            )
            for part_index, white_part in enumerate(oversized_parts, start=1):
                chunks.append(make_tagging_chunk(chunk_index, [section], white_override=white_part, sub_index=part_index))
            if oversized_parts:
                chunk_index += 1
            continue

        projected_length = sections_white_length(buffer) + len(section.white_text) + (1 if buffer else 0)
        if buffer and projected_length > hard_max_chars:
            chunks.append(make_tagging_chunk(chunk_index, buffer))
            chunk_index += 1
            buffer = overlap_tail(buffer, overlap_sections)
            buffer_has_new_since_emit = False
            if sections_white_length(buffer) + len(section.white_text) + (1 if buffer else 0) > hard_max_chars:
                buffer = []
        elif buffer and sections_white_length(buffer) >= target_min_chars and projected_length > target_max_chars:
            chunks.append(make_tagging_chunk(chunk_index, buffer))
            chunk_index += 1
            buffer = overlap_tail(buffer, overlap_sections)
            buffer_has_new_since_emit = False
            if sections_white_length(buffer) + len(section.white_text) + (1 if buffer else 0) > hard_max_chars:
                buffer = []

        buffer.append(section)
        buffer_has_new_since_emit = True

        if sections_white_length(buffer) >= hard_max_chars:
            chunks.append(make_tagging_chunk(chunk_index, buffer))
            chunk_index += 1
            buffer = overlap_tail(buffer, overlap_sections)
            buffer_has_new_since_emit = False

    emit_buffer(force=True)
    return chunks


def make_tagging_chunk(
    chunk_index: int,
    sections: list[WhiteSection],
    white_override: str | None = None,
    sub_index: int | None = None,
) -> dict[str, Any]:
    first = sections[0]
    section_keys = [section.section_key for section in sections]
    white_text = white_override or "\n".join(section.white_text for section in sections if section.white_text)
    chunk_suffix = f"{chunk_index:05d}" if sub_index is None else f"{chunk_index:05d}-p{sub_index:02d}"
    year_title = merged_year_title(sections)
    commentary_ids = unique_preserve_order(
        commentary_id
        for section in sections
        for commentary_id in section.commentary_ids
    )
    return {
        "chunk_id": f"tagging-v{first.volume_no:03d}-c{chunk_suffix}",
        "section_keys": section_keys,
        "volume_no": first.volume_no,
        "volume_title": first.volume_title,
        "chapter_title": first.chapter_title,
        "year_title": year_title,
        "white_text": white_text,
        "white_char_count": len(white_text),
        "section_count": len(section_keys),
        "commentary_ids": commentary_ids,
        "commentary_count": len(commentary_ids),
        "chunk_version": TAGGING_CHUNK_VERSION,
    }


def write_jsonl(rows: list[dict[str, Any]], output_path: str | Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(row, ensure_ascii=False) + "\n")
    return path


def write_commentaries_jsonl(commentaries: list[CommentaryRecord], output_path: str | Path) -> Path:
    rows = [
        {
            "commentary_id": commentary.commentary_id,
            "author": commentary.author,
            "source_section_key": commentary.source_section_key,
            "volume_no": commentary.volume_no,
            "volume_title": commentary.volume_title,
            "chapter_title": commentary.chapter_title,
            "year_title": commentary.year_title,
            "commentary_text": commentary.commentary_text,
            "commentary_char_count": commentary.commentary_char_count,
            "commentary_version": commentary.commentary_version,
            "linked_chunk_ids": commentary.linked_chunk_ids,
        }
        for commentary in commentaries
    ]
    return write_jsonl(rows, output_path)


def normalize_section_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def split_factual_and_simaguang_commentary(text: str) -> tuple[str, str]:
    marker_positions = [text.find(marker) for marker in SIMAGUANG_MARKERS if marker in text]
    if not marker_positions:
        return text, ""
    start = min(position for position in marker_positions if position >= 0)
    factual_text = normalize_section_text(text[:start])
    commentary_text = normalize_section_text(text[start:])
    return factual_text, commentary_text


def sections_white_length(sections: list[WhiteSection]) -> int:
    non_empty_count = sum(1 for section in sections if section.white_text)
    separator_count = max(0, non_empty_count - 1)
    return sum(len(section.white_text) for section in sections) + separator_count


def overlap_tail(sections: list[WhiteSection], overlap_sections: int) -> list[WhiteSection]:
    if overlap_sections <= 0:
        return []
    return [section for section in sections[-overlap_sections:] if section.white_text]


def split_oversized_text(
    text: str,
    target_max_chars: int,
    overlap_sentences: int = OVERSIZED_SECTION_OVERLAP_SENTENCES,
    overlap_chars: int = OVERSIZED_SECTION_OVERLAP_CHARS,
) -> list[str]:
    sentences = [match.group(0).strip() for match in SENTENCE_RE.finditer(text) if match.group(0).strip()]
    if not sentences:
        return split_oversized_text_by_chars(text, target_max_chars, overlap_chars=overlap_chars)

    parts: list[str] = []
    start = 0
    while start < len(sentences):
        current = sentences[start]
        end = start + 1

        while end < len(sentences) and len(current) + len(sentences[end]) <= target_max_chars:
            current += sentences[end]
            end += 1

        if len(current) > target_max_chars:
            parts.extend(split_oversized_text_by_chars(current, target_max_chars, overlap_chars=overlap_chars))
        else:
            parts.append(current)

        if end >= len(sentences):
            break

        if overlap_sentences > 0:
            next_start = max(start + 1, end - overlap_sentences)
            start = next_start if next_start > start else end
        else:
            start = end

    if (
        len(parts) >= 2
        and len(parts[-1]) < CHUNK_MIN_CHARS
        and len(parts[-2]) + len(parts[-1]) <= CHUNK_HARD_MAX_CHARS
    ):
        parts[-2] = f"{parts[-2]}{parts[-1]}"
        parts.pop()
    return parts


def split_oversized_text_by_chars(text: str, target_max_chars: int, overlap_chars: int) -> list[str]:
    if not text:
        return []
    if len(text) <= target_max_chars:
        return [text]

    step = max(1, target_max_chars - max(0, overlap_chars))
    parts: list[str] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + target_max_chars)
        parts.append(text[start:end])
        if end >= len(text):
            break
        start += step
    return parts


def merged_year_title(sections: list[WhiteSection]) -> str:
    year_titles: list[str] = []
    for section in sections:
        if section.year_title and section.year_title not in year_titles:
            year_titles.append(section.year_title)
    if not year_titles:
        return ""
    if len(year_titles) == 1:
        return year_titles[0]
    return f"{year_titles[0]} 至 {year_titles[-1]}"


def unique_preserve_order(values: Any) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def summarize_chunks(chunks: list[dict[str, Any]]) -> dict[str, Any]:
    lengths = [int(chunk["white_char_count"]) for chunk in chunks]
    if not lengths:
        return {
            "chunk_count": 0,
            "min_chars": 0,
            "max_chars": 0,
            "avg_chars": 0,
            "median_chars": 0,
            "target_range_count": 0,
            "over_hard_max_count": 0,
        }
    return {
        "chunk_count": len(chunks),
        "min_chars": min(lengths),
        "max_chars": max(lengths),
        "avg_chars": round(mean(lengths), 1),
        "median_chars": round(median(lengths), 1),
        "target_range_count": sum(CHUNK_TARGET_MIN_CHARS <= length <= CHUNK_TARGET_MAX_CHARS for length in lengths),
        "over_hard_max_count": sum(length > CHUNK_HARD_MAX_CHARS for length in lengths),
    }


def main() -> None:
    input_path = Path(sys.argv[1]) if len(sys.argv) >= 2 else DEFAULT_INPUT_PATH
    output_path = Path(sys.argv[2]) if len(sys.argv) >= 3 else DEFAULT_OUTPUT_PATH
    commentary_output_path = Path(sys.argv[3]) if len(sys.argv) >= 4 else DEFAULT_COMMENTARY_OUTPUT_PATH
    raw_sections = parse_white_corpus(input_path)
    sections, commentaries = extract_simaguang_commentaries(raw_sections)
    chunks = build_tagging_chunks_from_sections(sections)
    commentary_to_chunks: dict[str, list[str]] = {}
    for chunk in chunks:
        for commentary_id in chunk.get("commentary_ids", []):
            commentary_to_chunks.setdefault(commentary_id, []).append(chunk["chunk_id"])
    for commentary in commentaries:
        commentary.linked_chunk_ids = commentary_to_chunks.get(commentary.commentary_id, [])
    write_jsonl(chunks, output_path)
    write_commentaries_jsonl(commentaries, commentary_output_path)
    summary = summarize_chunks(chunks)

    print(f"INPUT: {input_path}")
    print(f"OUTPUT: {output_path}")
    print(f"COMMENTARY_OUTPUT: {commentary_output_path}")
    print(f"SECTIONS: {len(sections)}")
    print(f"SIMAGUANG_COMMENTARIES: {len(commentaries)}")
    for key, value in summary.items():
        print(f"{key.upper()}: {value}")
    if chunks:
        print(f"SAMPLE_CHUNK_ID: {chunks[0]['chunk_id']}")
        print(f"SAMPLE_SECTION_KEYS: {','.join(chunks[0]['section_keys'])}")


if __name__ == "__main__":
    main()
