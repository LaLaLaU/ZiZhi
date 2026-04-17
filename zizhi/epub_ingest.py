from __future__ import annotations

import json
import re
import zipfile
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path

from zizhi.schemas import HistoricalChunk


ANNOTATION_PATTERN = re.compile(r"［(.*?)］")
YEAR_PATTERN = re.compile(r"（([^（）]*?公元[^（）]*?)）")


@dataclass
class HtmlElement:
    tag: str
    text: str


class StructuredHtmlParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._stack: list[str] = []
        self._buffer: list[str] = []
        self.elements: list[HtmlElement] = []
        self._targets = {"h1", "h2", "h3", "p", "blockquote"}

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in self._targets:
            self._stack.append(tag)
            self._buffer = []

    def handle_data(self, data: str) -> None:
        if self._stack:
            cleaned = data.strip()
            if cleaned:
                self._buffer.append(cleaned)

    def handle_endtag(self, tag: str) -> None:
        if self._stack and self._stack[-1] == tag:
            text = normalize_text(" ".join(self._buffer))
            if text:
                self.elements.append(HtmlElement(tag=tag, text=text))
            self._stack.pop()
            self._buffer = []


def normalize_text(text: str) -> str:
    text = text.replace("\u3000", " ").replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def parse_epub_to_chunks(epub_path: str | Path) -> list[HistoricalChunk]:
    path = Path(epub_path)
    chunks: list[HistoricalChunk] = []
    current_volume = ""
    current_chapter = ""
    current_year = ""

    with zipfile.ZipFile(path) as archive:
        html_files = sorted(
            name
            for name in archive.namelist()
            if name.startswith("text/") and name.endswith(".html")
        )
        for file_name in html_files:
            raw = archive.read(file_name).decode("utf-8", errors="ignore")
            parser = StructuredHtmlParser()
            parser.feed(raw)
            if not parser.elements:
                continue

            for element_index, element in enumerate(parser.elements):
                content = normalize_text(element.text)
                if not content or content in {"未知", "Cover", "目录", "总目录"}:
                    continue

                if element.tag == "h1":
                    if content.startswith("卷"):
                        current_volume = content
                        current_chapter = ""
                        current_year = ""
                    continue
                if element.tag == "h2":
                    current_chapter = content
                    continue
                if element.tag == "h3":
                    current_year = content
                    continue
                if element.tag == "blockquote" and ("公元" in content or content.startswith("起")):
                    continue
                if len(content) < 8:
                    continue
                if not current_volume:
                    continue

                annotation_text = "；".join(ANNOTATION_PATTERN.findall(content))
                original_text = ANNOTATION_PATTERN.sub("", content).replace(" 。", "。").strip()
                if len(original_text) < 8:
                    continue

                chunk_type = "chen_guang_yue" if original_text.startswith("臣光曰") else "original"
                year_match = YEAR_PATTERN.search(current_year)
                year = year_match.group(1) if year_match else current_year
                chapter_title = current_chapter or current_volume or file_name
                combined_text = " ".join(filter(None, [original_text, annotation_text, current_volume, current_chapter, current_year]))

                chunks.append(
                    HistoricalChunk(
                        chunk_id=f"{Path(file_name).stem}-{element_index:03d}",
                        volume=current_volume,
                        year=year,
                        chapter_title=chapter_title,
                        chunk_type=chunk_type,
                        white_text="",
                        original_text=original_text,
                        annotation_text=annotation_text,
                        text=combined_text,
                        people=extract_people(original_text),
                        events=extract_events(original_text),
                        topic_tags=extract_topic_tags(original_text),
                        situation_tags=extract_situation_tags(original_text),
                        source_priority=0.92 if chunk_type == "chen_guang_yue" else 0.84,
                    )
                )
    return chunks


def write_chunks_jsonl(chunks: list[HistoricalChunk], output_path: str | Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        for chunk in chunks:
            file.write(json.dumps(chunk.model_dump(), ensure_ascii=False) + "\n")
    return path


def load_chunks_jsonl(path: str | Path) -> list[HistoricalChunk]:
    chunks: list[HistoricalChunk] = []
    with Path(path).open("r", encoding="utf-8") as file:
        for line in file:
            stripped = line.strip()
            if stripped:
                chunks.append(HistoricalChunk.model_validate(json.loads(stripped)))
    return chunks


def extract_people(text: str) -> list[str]:
    surnames = [
        "王", "公", "侯", "君", "帝", "后", "太后", "太子", "相", "将军", "使者", "大夫",
        "魏", "赵", "韩", "秦", "楚", "齐", "燕", "汉", "唐", "晋", "周",
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
    tags = [tag for tag, keywords in mapping.items() if any(keyword in text for keyword in keywords)]
    return tags[:3]


def extract_situation_tags(text: str) -> list[str]:
    mapping = {
        "君臣": ["帝", "王", "臣", "相"],
        "同僚": ["将军", "大夫", "同列"],
        "结盟": ["盟", "合从", "连横"],
        "离间": ["间", "谗", "疑"],
        "试探": ["试", "探", "窥"],
        "进谏": ["谏", "奏", "书"],
    }
    tags = [tag for tag, keywords in mapping.items() if any(keyword in text for keyword in keywords)]
    return tags[:3]
