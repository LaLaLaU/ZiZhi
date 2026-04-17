from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from zizhi.manual_cleanup_rules import looks_like_translation_segment, strip_malformed_prefix
from zizhi.schemas import HistoricalChunk


NUMBERED_RE = re.compile(r"^\[?(\d+)\]?\s*(.+)$")
EMBEDDED_NUMBERED_RE = re.compile(r"(?<!^)(\[\d+\])")
VOLUME_RE = re.compile(r"^(?:资治)?通鉴第[一二三四五六七八九十百零〇两\d]+卷$")
PREAMBLE_RE = re.compile(r"^【[^】]+】")
YEAR_RE = re.compile(r"^[前中后元一二三四五六七八九十百千〇零两\d]+年[（(].*?[）)]?$")
CHAPTER_RE = re.compile(r"^.{0,24}纪.{0,32}[（(].*?[）)]?$")
ORIGINAL_VOLUME_HEADER_RE = re.compile(r"^[^\s]{1,12}纪（卷[一二三四五六七八九十百零〇两\d]+）$")
WATERMARK_RE = re.compile(r"^www\.", re.IGNORECASE)
SEPARATOR_RE = re.compile(r"^[-—─\s]{20,}$")
HTML_TAG_RE = re.compile(r"<[^>]+>")

MODERN_MARKERS = [
    "就是",
    "因为",
    "于是",
    "所以",
    "如果",
    "当初",
    "开始",
    "再次",
    "国君",
    "去世",
    "即位",
    "认为",
    "回答",
    "百姓",
    "意思",
    "这是",
    "这样",
    "派人",
    "前去",
    "希望",
    "皇帝",
    "皇宫",
    "大赦天下",
    "被任命",
    "任命",
    "当天",
    "当时",
    "当初",
    "这时",
    "此时",
    "立即",
    "立刻",
    "前往",
    "抵达",
    "决定",
    "宣布",
    "打算",
    "命令",
    "告诉",
    "请求",
    "表示",
    "全部",
    "一起",
    "自己",
    "率领",
    "公元",
]

CLASSICAL_MARKERS = [
    "臣光曰",
    "曰",
    "矣",
    "焉",
    "哉",
    "乎",
    "耳",
    "盖",
    "夫",
    "弗",
    "薨",
    "寡人",
    "岂",
    "孰",
    "何以",
    "不然",
    "乃",
    "则",
]

CHUNK_MIN_CHARS = 600
CHUNK_TARGET_MIN_CHARS = 900
CHUNK_TARGET_MAX_CHARS = 1400
CHUNK_HARD_MAX_CHARS = 1600
CHUNK_OVERLAP_SECTIONS = 1
TXT_CHUNK_VERSION = "txt-white-section-aware-v1"
SENTENCE_RE = re.compile(r"[^。！？；!?;]+[。！？；!?;]?")


@dataclass
class WorkingSection:
    section_key: str
    section_index: int | None
    volume_no: int
    volume_title: str
    chapter_title: str
    year_title: str
    preamble: str = ""
    original_parts: list[str] = field(default_factory=list)
    white_parts: list[str] = field(default_factory=list)
    last_added_is_modern: bool | None = None

    def add_paragraph(self, text: str, is_modern: bool) -> None:
        if is_modern:
            self.white_parts.append(text)
        else:
            self.original_parts.append(text)
        self.last_added_is_modern = is_modern

    def has_content(self) -> bool:
        return bool(self.original_parts or self.white_parts)


@dataclass
class ParsedSection:
    volume_no: int
    volume_title: str
    chapter_title: str
    year_title: str
    section_index: int | None
    section_key: str
    original_text: str
    white_text: str
    pair_type: str


def normalize_text(text: str) -> str:
    text = text.replace("\ufeff", "").replace("\u3000", " ").replace("\xa0", " ")
    text = HTML_TAG_RE.sub("", text)
    text = strip_malformed_prefix(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def read_txt_paragraphs(path: str | Path) -> list[str]:
    raw = Path(path).read_bytes().decode("gb18030")
    paragraphs = [normalize_text(line) for line in raw.splitlines()]
    expanded: list[str] = []
    for paragraph in paragraphs:
        if not paragraph or WATERMARK_RE.match(paragraph) or SEPARATOR_RE.match(paragraph):
            continue
        expanded.extend(split_embedded_numbered_paragraph(paragraph))
    return expanded


def split_embedded_numbered_paragraph(paragraph: str) -> list[str]:
    if paragraph.count("[") <= 1:
        return [paragraph]
    parts = EMBEDDED_NUMBERED_RE.split(paragraph)
    if len(parts) <= 1:
        return [paragraph]

    result: list[str] = []
    current = parts[0]
    index = 1
    while index < len(parts):
        marker = parts[index]
        body = parts[index + 1] if index + 1 < len(parts) else ""
        if current.strip():
            result.append(normalize_text(current))
        current = f"{marker}{body}"
        index += 2
    if current.strip():
        result.append(normalize_text(current))
    return result or [paragraph]


def split_inline_original_white_paragraph(paragraph: str, original_paragraphs: set[str]) -> list[str]:
    if not original_paragraphs or paragraph in original_paragraphs or " " not in paragraph:
        return [paragraph]

    parts = paragraph.split(" ")
    best_split: tuple[str, str] | None = None
    for index in range(1, len(parts)):
        left = normalize_text(" ".join(parts[:index]))
        right = normalize_text(" ".join(parts[index:]))
        if not left or not right:
            continue
        if left in original_paragraphs and _looks_modern(right):
            best_split = (left, right)
    if best_split is None:
        for index in range(1, len(parts)):
            left = normalize_text(" ".join(parts[:index]))
            right = normalize_text(" ".join(parts[index:]))
            if not left or not right:
                continue
            if left == right:
                best_split = (left, right)
                break
            if left[-1:] not in "。！？；”’":
                continue
            if looks_like_translation_segment(right):
                best_split = (left, right)
                break

    if best_split is None:
        return [paragraph]
    return [best_split[0], best_split[1]]


def parse_txt_volume(path: str | Path) -> list[ParsedSection]:
    file_path = Path(path)
    volume_no = int(file_path.stem)
    paragraphs = read_txt_paragraphs(file_path)
    original_index = load_whole_original_index(file_path.parents[1])
    original_paragraphs = original_index.get(volume_no, set())
    expanded_paragraphs: list[str] = []
    for paragraph in paragraphs:
        expanded_paragraphs.extend(split_inline_original_white_paragraph(paragraph, original_paragraphs))
    paragraphs = expanded_paragraphs

    volume_title = ""
    chapter_title = ""
    year_title = ""
    current_preamble = ""
    sections: list[ParsedSection] = []
    current_section: WorkingSection | None = None
    section_sequence = 0

    for paragraph in paragraphs:
        paragraph_type = _classify_paragraph(paragraph)

        if paragraph_type == "volume":
            _flush_section(sections, current_section)
            current_section = None
            volume_title = paragraph
            continue

        if paragraph_type == "preamble":
            _flush_section(sections, current_section)
            current_section = None
            current_preamble = paragraph
            continue

        if paragraph_type == "chapter":
            if _is_duplicate_context_title(current_section, chapter_title, paragraph):
                chapter_title = paragraph
                continue
            _flush_section(sections, current_section)
            current_section = None
            chapter_title = paragraph
            continue

        if paragraph_type == "year":
            if _is_duplicate_context_title(current_section, year_title, paragraph):
                year_title = paragraph
                continue
            _flush_section(sections, current_section)
            current_section = None
            year_title = paragraph
            continue

        section_index, body = _split_numbered(paragraph)
        if section_index is not None:
            if current_section is None or current_section.section_index != section_index:
                _flush_section(sections, current_section)
                section_sequence += 1
                current_section = WorkingSection(
                    section_key=f"{volume_no:03d}-s{section_sequence:04d}",
                    section_index=section_index,
                    volume_no=volume_no,
                    volume_title=volume_title,
                    chapter_title=chapter_title,
                    year_title=year_title,
                    preamble=current_preamble,
                )
            current_section.add_paragraph(
                body,
                _decide_is_modern(current_section, body, numbered=True, original_paragraphs=original_paragraphs),
            )
            continue

        if current_section is None:
            section_sequence += 1
            current_section = WorkingSection(
                section_key=f"{volume_no:03d}-s{section_sequence:04d}",
                section_index=None,
                volume_no=volume_no,
                volume_title=volume_title,
                chapter_title=chapter_title,
                year_title=year_title,
                preamble=current_preamble,
            )

        current_section.add_paragraph(
            paragraph,
            _decide_is_modern(current_section, paragraph, numbered=False, original_paragraphs=original_paragraphs),
        )

    _flush_section(sections, current_section)
    return sections


def parse_txt_volume_to_chunks(path: str | Path) -> list[HistoricalChunk]:
    sections = parse_txt_volume(path)
    file_path = Path(path)
    return build_retrieval_chunks_from_sections(sections, source_stem=file_path.stem)


def build_retrieval_chunks_from_sections(
    sections: list[ParsedSection],
    source_stem: str = "txt",
    min_chars: int = CHUNK_MIN_CHARS,
    target_min_chars: int = CHUNK_TARGET_MIN_CHARS,
    target_max_chars: int = CHUNK_TARGET_MAX_CHARS,
    hard_max_chars: int = CHUNK_HARD_MAX_CHARS,
    overlap_sections: int = CHUNK_OVERLAP_SECTIONS,
) -> list[HistoricalChunk]:
    chunks: list[HistoricalChunk] = []
    buffer: list[ParsedSection] = []
    buffer_has_new_since_emit = False
    current_context: tuple[int, str] | None = None
    chunk_index = 1

    def flush_buffer(force: bool = False) -> None:
        nonlocal buffer, buffer_has_new_since_emit, chunk_index
        if not buffer or not buffer_has_new_since_emit:
            buffer = [] if force else buffer
            return
        chunks.append(_make_chunk(source_stem, chunk_index, buffer))
        chunk_index += 1
        buffer = []
        buffer_has_new_since_emit = False

    for section in sections:
        white_length = len(section.white_text)
        if white_length == 0:
            continue

        section_context = (section.volume_no, section.chapter_title)
        if current_context is None:
            current_context = section_context
        elif section_context != current_context:
            flush_buffer(force=True)
            current_context = section_context

        if white_length > hard_max_chars:
            flush_buffer(force=True)
            for part_index, white_part in enumerate(_split_oversized_white_text(section.white_text, target_max_chars), start=1):
                chunks.append(_make_chunk(source_stem, chunk_index, [section], white_override=white_part, sub_index=part_index))
                chunk_index += 1
            continue

        projected_length = _sections_white_length(buffer) + white_length + (1 if buffer else 0)
        if buffer and projected_length > hard_max_chars:
            chunks.append(_make_chunk(source_stem, chunk_index, buffer))
            chunk_index += 1
            buffer = _overlap_tail(buffer, overlap_sections)
            buffer_has_new_since_emit = False
            if _sections_white_length(buffer) + white_length + (1 if buffer else 0) > hard_max_chars:
                buffer = []
        elif buffer and _sections_white_length(buffer) >= target_min_chars and projected_length > target_max_chars:
            chunks.append(_make_chunk(source_stem, chunk_index, buffer))
            chunk_index += 1
            buffer = _overlap_tail(buffer, overlap_sections)
            buffer_has_new_since_emit = False
            if _sections_white_length(buffer) + white_length + (1 if buffer else 0) > hard_max_chars:
                buffer = []

        buffer.append(section)
        buffer_has_new_since_emit = True

        if _sections_white_length(buffer) >= hard_max_chars:
            chunks.append(_make_chunk(source_stem, chunk_index, buffer))
            chunk_index += 1
            buffer = _overlap_tail(buffer, overlap_sections)
            buffer_has_new_since_emit = False

    flush_buffer(force=True)
    return chunks


def _sections_white_length(sections: list[ParsedSection]) -> int:
    non_empty_count = sum(1 for section in sections if section.white_text)
    separator_count = max(0, non_empty_count - 1)
    return sum(len(section.white_text) for section in sections) + separator_count


def _overlap_tail(sections: list[ParsedSection], overlap_sections: int) -> list[ParsedSection]:
    if overlap_sections <= 0:
        return []
    return [section for section in sections[-overlap_sections:] if section.white_text]


def _split_oversized_white_text(white_text: str, target_max_chars: int) -> list[str]:
    sentences = [match.group(0).strip() for match in SENTENCE_RE.finditer(white_text) if match.group(0).strip()]
    if not sentences:
        sentences = [white_text[index : index + target_max_chars] for index in range(0, len(white_text), target_max_chars)]

    parts: list[str] = []
    current = ""
    for sentence in sentences:
        if len(sentence) > target_max_chars:
            if current:
                parts.append(current)
                current = ""
            parts.extend(sentence[index : index + target_max_chars] for index in range(0, len(sentence), target_max_chars))
            continue
        if current and len(current) + len(sentence) > target_max_chars:
            parts.append(current)
            current = sentence
        else:
            current += sentence
    if current:
        parts.append(current)
    return parts


def _make_chunk(
    source_stem: str,
    chunk_index: int,
    sections: list[ParsedSection],
    white_override: str | None = None,
    sub_index: int | None = None,
) -> HistoricalChunk:
    first = sections[0]
    section_keys = [section.section_key for section in sections]
    white_text = white_override or "\n".join(section.white_text for section in sections if section.white_text)
    original_text = "\n".join(section.original_text for section in sections if section.original_text)
    chunk_type = _infer_chunk_type(original_text, white_text)
    year_text = _merged_year_title(sections)
    retrieval_text = " ".join(
        filter(
            None,
            [
                first.chapter_title,
                year_text,
                white_text,
            ],
        )
    )
    chunk_suffix = f"{chunk_index:04d}" if sub_index is None else f"{chunk_index:04d}-s{sub_index:02d}"
    primary_text = retrieval_text or white_text or original_text
    pair_summary = _pair_type_summary(sections)
    return HistoricalChunk(
        chunk_id=f"{source_stem}-c{chunk_suffix}",
        volume_no=first.volume_no,
        volume=first.volume_title or f"{first.volume_no:03d}",
        year=year_text,
        chapter_title=first.chapter_title or first.volume_title or f"{first.volume_no:03d}",
        chunk_type=chunk_type,
        section_key=section_keys[0],
        section_keys=section_keys,
        retrieval_text=retrieval_text,
        white_char_count=len(white_text),
        section_count=len(section_keys),
        chunk_version=TXT_CHUNK_VERSION,
        white_text=white_text,
        original_text=original_text,
        annotation_text=pair_summary,
        text=primary_text,
        people=extract_people(primary_text),
        events=extract_events(primary_text),
        topic_tags=extract_topic_tags(primary_text),
        situation_tags=extract_situation_tags(primary_text),
        source_priority=0.9 if chunk_type == "chen_guang_yue" else 0.84,
    )


def _pair_type_summary(sections: list[ParsedSection]) -> str:
    counts: dict[str, int] = {}
    for section in sections:
        counts[section.pair_type] = counts.get(section.pair_type, 0) + 1
    return ";".join(f"{key}:{counts[key]}" for key in sorted(counts))


def _merged_year_title(sections: list[ParsedSection]) -> str:
    year_titles = []
    for section in sections:
        if section.year_title and section.year_title not in year_titles:
            year_titles.append(section.year_title)
    if not year_titles:
        return ""
    if len(year_titles) == 1:
        return year_titles[0]
    return f"{year_titles[0]} 至 {year_titles[-1]}"


def parse_txt_corpus_to_chunks(root: str | Path) -> list[HistoricalChunk]:
    corpus_root = Path(root)
    chunks: list[HistoricalChunk] = []
    for path in iter_volume_txt_files(corpus_root):
        chunks.extend(parse_txt_volume_to_chunks(path))
    return chunks


@lru_cache(maxsize=4)
def load_whole_original_index(corpus_root: str | Path) -> dict[int, set[str]]:
    root = Path(corpus_root)
    whole_path = root / "资治通鉴整书原文.txt"
    if not whole_path.exists():
        return {}

    paragraphs = read_original_txt_paragraphs(whole_path)
    original_index: dict[int, set[str]] = {}
    current_volume_no = 0
    in_body = False

    for index, paragraph in enumerate(paragraphs):
        if ORIGINAL_VOLUME_HEADER_RE.match(paragraph):
            next_paragraph = paragraphs[index + 1] if index + 1 < len(paragraphs) else ""
            if ORIGINAL_VOLUME_HEADER_RE.match(next_paragraph):
                continue
            if next_paragraph in {"目录", "Cover Page"}:
                continue
            current_volume_no += 1
            original_index[current_volume_no] = set()
            in_body = True
            continue

        if not in_body or current_volume_no == 0:
            continue

        if _classify_original_paragraph(paragraph) == "content":
            original_index[current_volume_no].add(paragraph)

    return original_index


def read_original_txt_paragraphs(path: str | Path) -> list[str]:
    text = Path(path).read_text(encoding="utf-8")
    paragraphs = [normalize_text(line) for line in text.splitlines()]
    return [paragraph for paragraph in paragraphs if paragraph and paragraph not in {"目录", "Cover Page"}]


def summarize_txt_corpus_lengths(root: str | Path) -> list[dict[str, int | str]]:
    corpus_root = Path(root)
    rows: list[dict[str, int | str]] = []
    for path in iter_volume_txt_files(corpus_root):
        sections = parse_txt_volume(path)
        rows.append(
            {
                "volume_no": int(path.stem),
                "file": str(path.relative_to(corpus_root)).replace("\\", "/"),
                "original_chars": sum(len(section.original_text) for section in sections),
                "white_chars": sum(len(section.white_text) for section in sections),
                "paired_sections": sum(1 for section in sections if section.pair_type == "paired"),
                "original_only_sections": sum(1 for section in sections if section.pair_type == "original_only"),
                "white_only_sections": sum(1 for section in sections if section.pair_type == "white_only"),
            }
        )
    return rows


def iter_volume_txt_files(root: str | Path) -> list[Path]:
    corpus_root = Path(root)
    return sorted(path for path in corpus_root.rglob("*.txt") if path.stem.isdigit())


def write_length_csv(rows: list[dict[str, int | str]], output_path: str | Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "volume_no",
                "file",
                "original_chars",
                "white_chars",
                "paired_sections",
                "original_only_sections",
                "white_only_sections",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)
    return path


def write_chunks_jsonl(chunks: list[HistoricalChunk], output_path: str | Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        for chunk in chunks:
            file.write(json.dumps(chunk.model_dump(), ensure_ascii=False) + "\n")
    return path


def _split_numbered(paragraph: str) -> tuple[int | None, str]:
    match = NUMBERED_RE.match(paragraph)
    if not match:
        return None, paragraph
    number = int(match.group(1))
    if number <= 0 or number >= 1000:
        return None, paragraph
    return number, normalize_text(match.group(2))


def _classify_paragraph(paragraph: str) -> str:
    if NUMBERED_RE.match(paragraph):
        return "content"
    if VOLUME_RE.match(paragraph):
        return "volume"
    if PREAMBLE_RE.match(paragraph):
        return "preamble"
    if "纪" in paragraph and "（" in paragraph and ("前" in paragraph or "公元" in paragraph or "元年" in paragraph):
        return "chapter"
    if (
        len(paragraph) <= 40
        and any(keyword in paragraph for keyword in ["皇帝", "帝", "王"])
        and "（" in paragraph
        and ("前" in paragraph or "公元" in paragraph)
    ):
        return "chapter"
    if (
        len(paragraph) <= 40
        and any(keyword in paragraph for keyword in ["皇帝", "帝", "王"])
        and any(bracket in paragraph for bracket in ["（", "("])
        and ("前" in paragraph or "公元" in paragraph)
    ):
        return "chapter"
    if paragraph.count("纪") >= 2 and paragraph.count("（") >= 2:
        return "chapter"
    if CHAPTER_RE.match(paragraph):
        return "chapter"
    if YEAR_RE.match(paragraph):
        return "year"
    return "content"


def _classify_original_paragraph(paragraph: str) -> str:
    if ORIGINAL_VOLUME_HEADER_RE.match(paragraph):
        return "volume"
    if paragraph.startswith("起") and "凡" in paragraph and "年" in paragraph:
        return "preamble"
    if "纪" in paragraph and "（" in paragraph and ("前" in paragraph or "公元" in paragraph):
        return "chapter"
    if YEAR_RE.match(paragraph):
        return "year"
    return "content"


def _looks_modern(text: str) -> bool:
    modern_score = sum(text.count(marker) for marker in MODERN_MARKERS)
    classical_score = sum(text.count(marker) for marker in CLASSICAL_MARKERS)
    if text.startswith("臣司马光曰"):
        modern_score += 6
    if text.startswith("臣光曰"):
        classical_score += 6
    if "公元" in text:
        modern_score += 2
    if re.search(r"（[初十廿三一二四五六七八九\d]+日", text):
        modern_score += 3
    if re.search(r"（[^）]*公元[^）]*）", text):
        modern_score += 3
    if re.search(r"[一二三四五六七八九十]+日", text):
        modern_score += 1
    if text.startswith(("周威烈王", "秦国", "魏惠王去世", "春季", "夏季", "秋季", "冬季", "当天", "当初", "这时", "此时")):
        modern_score += 2
    if len(text) <= 16 and any(word in text for word in ["去世", "开始", "再次", "任命", "降到"]):
        modern_score += 2
    return modern_score > classical_score


def _decide_is_modern(
    current_section: WorkingSection,
    text: str,
    numbered: bool,
    original_paragraphs: set[str] | None = None,
) -> bool:
    if original_paragraphs and text in original_paragraphs:
        return False
    heuristic = _looks_modern(text)
    if current_section.section_index is not None and numbered:
        if not current_section.original_parts and not current_section.white_parts:
            if original_paragraphs and text not in original_paragraphs and heuristic:
                return True
            return False
        if current_section.original_parts and not current_section.white_parts:
            if text.startswith("臣光曰"):
                return False
            return True
    if current_section.section_index is not None and not numbered:
        if current_section.last_added_is_modern is False:
            return True if heuristic or len(text) > 14 else False
        if current_section.last_added_is_modern is True:
            return False if not heuristic else True
    if current_section.section_index is None:
        if text.startswith("臣司马光曰"):
            return True
        if text.startswith("臣光曰"):
            return False
        if original_paragraphs and text not in original_paragraphs and heuristic:
            return True
        if current_section.last_added_is_modern is False and heuristic:
            return True
        if current_section.last_added_is_modern is True and not heuristic:
            return False
    return heuristic


def _infer_chunk_type(original_text: str, white_text: str) -> str:
    pivot = original_text or white_text
    if pivot.startswith("臣光曰") or pivot.startswith("臣司马光曰"):
        return "chen_guang_yue"
    return "original"


def _flush_section(sections: list[ParsedSection], current_section: WorkingSection | None) -> None:
    if current_section is None or not current_section.has_content():
        return

    original_parts = list(current_section.original_parts)
    white_parts = list(current_section.white_parts)
    if not original_parts and len(white_parts) >= 2:
        recovered_original_parts, recovered_white_parts = _recover_pairs_from_white_parts(white_parts)
        if recovered_original_parts:
            original_parts = recovered_original_parts
            white_parts = recovered_white_parts

    original_text = " ".join(original_parts)
    white_text = " ".join(white_parts)
    if not original_text and white_text and _is_metadata_only_white(current_section, white_text):
        return
    if original_text and white_text:
        pair_type = "paired"
    elif original_text:
        pair_type = "original_only"
    else:
        pair_type = "white_only"

    sections.append(
        ParsedSection(
            volume_no=current_section.volume_no,
            volume_title=current_section.volume_title,
            chapter_title=current_section.chapter_title,
            year_title=current_section.year_title,
            section_index=current_section.section_index,
            section_key=current_section.section_key,
            original_text=original_text,
            white_text=white_text,
            pair_type=pair_type,
        )
    )


def _is_metadata_only_white(current_section: WorkingSection, white_text: str) -> bool:
    if white_text in {current_section.chapter_title, current_section.year_title, current_section.volume_title}:
        return True
    return _classify_paragraph(white_text) in {"volume", "chapter", "year", "preamble"}


def _recover_pairs_from_white_parts(white_parts: list[str]) -> tuple[list[str], list[str]]:
    original_parts: list[str] = []
    recovered_white_parts: list[str] = []
    index = 0
    recovered_count = 0
    while index < len(white_parts):
        current = white_parts[index]
        next_part = white_parts[index + 1] if index + 1 < len(white_parts) else ""
        if next_part and looks_like_translation_segment(next_part) and not looks_like_translation_segment(current):
            original_parts.append(current)
            recovered_white_parts.append(next_part)
            recovered_count += 1
            index += 2
            continue

        recovered_white_parts.append(current)
        index += 1

    if recovered_count == 0:
        return [], white_parts
    return original_parts, recovered_white_parts


def _is_duplicate_context_title(
    current_section: WorkingSection | None,
    current_title: str,
    new_title: str,
) -> bool:
    if current_section is None or not current_title:
        return False
    if current_section.white_parts:
        return False
    if not current_section.original_parts:
        return False
    current_head = current_title.split("（", 1)[0].strip()
    new_head = new_title.split("（", 1)[0].strip()
    return bool(current_head) and current_head == new_head


def extract_people(text: str) -> list[str]:
    surnames = [
        "王",
        "公",
        "侯",
        "君",
        "帝",
        "后",
        "太后",
        "太子",
        "相",
        "将军",
        "使者",
        "大夫",
        "魏",
        "赵",
        "韩",
        "秦",
        "楚",
        "齐",
        "燕",
        "汉",
        "唐",
        "晋",
        "周",
    ]
    matches = re.findall(r"[一-龥]{1,4}(?:王|公|侯|君|帝|后|太后|太子|相|将军|大夫)", text)
    people = list(dict.fromkeys(matches[:6]))
    for surname in surnames:
        if surname in text and surname not in people and len(people) < 6:
            people.append(surname)
    return people


def extract_events(text: str) -> list[str]:
    patterns = ["为诸侯", "攻", "伐", "围", "杀", "诛", "免", "拜", "封", "立", "降", "反", "盟"]
    events = [pattern for pattern in patterns if pattern in text]
    return events[:5]


def extract_topic_tags(text: str) -> list[str]:
    mapping = {
        "权力": ["君", "帝", "王", "位", "诸侯"],
        "用人": ["相", "将军", "用", "拜", "封"],
        "联盟": ["盟", "合从", "连横"],
        "猜忌": ["疑", "谗", "间", "忌"],
        "进退": ["退", "进", "去", "留"],
        "时机": ["时", "机", "势"],
        "信任": ["信", "诚", "托"],
        "沟通": ["言", "谏", "奏", "书"],
        "制衡": ["制", "衡", "分", "礼"],
    }
    return [tag for tag, keywords in mapping.items() if any(keyword in text for keyword in keywords)][:3]


def extract_situation_tags(text: str) -> list[str]:
    mapping = {
        "君臣": ["帝", "王", "臣", "相"],
        "同僚": ["将军", "大夫", "同列"],
        "结盟": ["盟", "合从", "连横"],
        "离间": ["间", "谗", "疑"],
        "试探": ["试", "探", "窥"],
        "进谏": ["谏", "奏", "书"],
    }
    return [tag for tag, keywords in mapping.items() if any(keyword in text for keyword in keywords)][:3]
