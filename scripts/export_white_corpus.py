from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from zizhi.txt_ingest import iter_volume_txt_files, parse_txt_volume


DEFAULT_TXT_CORPUS_KEYWORD = "资治通鉴txt版"
DEFAULT_OUTPUT_PATH = ROOT / ".cache" / "zizhi_white_corpus.txt"


def resolve_corpus_path() -> Path:
    sources_root = ROOT / "sources"
    if not sources_root.exists():
        raise SystemExit("sources directory not found.")

    for path in sources_root.iterdir():
        if path.is_dir() and DEFAULT_TXT_CORPUS_KEYWORD in path.name:
            return path

    raise SystemExit("TXT corpus directory not found under sources.")


def export_white_corpus(corpus_root: Path, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as file:
        for txt_path in iter_volume_txt_files(corpus_root):
            sections = parse_txt_volume(txt_path)
            if not sections:
                continue

            first = sections[0]
            volume_heading = first.volume_title or f"第{first.volume_no:03d}卷"
            file.write(f"========== 卷 {first.volume_no:03d} | {volume_heading} ==========\n\n")

            last_chapter = None
            last_year = None
            for section in sections:
                if not section.white_text.strip():
                    continue

                if section.chapter_title and section.chapter_title != last_chapter:
                    file.write(f"## {section.chapter_title}\n")
                    last_chapter = section.chapter_title
                    last_year = None

                if section.year_title and section.year_title != last_year:
                    file.write(f"### {section.year_title}\n")
                    last_year = section.year_title

                file.write(f"[{section.section_key}]\n")
                file.write(section.white_text.strip())
                file.write("\n\n")

    return output_path


def main() -> None:
    corpus_root = resolve_corpus_path()
    output_path = export_white_corpus(corpus_root, DEFAULT_OUTPUT_PATH)
    print(f"CORPUS: {corpus_root}")
    print(f"OUTPUT: {output_path}")


if __name__ == "__main__":
    main()
