from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from zizhi.epub_ingest import parse_epub_to_chunks, write_chunks_jsonl as write_epub_chunks_jsonl
from zizhi.txt_ingest import parse_txt_corpus_to_chunks, write_chunks_jsonl as write_txt_chunks_jsonl


DEFAULT_TXT_CORPUS_KEYWORD = "资治通鉴txt版"


def resolve_corpus_path() -> Path:
    configured_path = os.getenv("ZIZHI_CORPUS_PATH")
    if configured_path:
        return Path(configured_path)

    sources_root = ROOT / "sources"
    if sources_root.exists():
        for path in sources_root.iterdir():
            if path.is_dir() and DEFAULT_TXT_CORPUS_KEYWORD in path.name:
                return path

    raise SystemExit(
        "Please set ZIZHI_CORPUS_PATH to a valid EPUB, TXT file, or TXT corpus directory before building corpus."
    )


def main() -> None:
    corpus_path = resolve_corpus_path()
    output_path = Path(".cache") / "zizhi_corpus_chunks.jsonl"

    if corpus_path.is_dir():
        chunks = parse_txt_corpus_to_chunks(corpus_path)
        write_txt_chunks_jsonl(chunks, output_path)
    elif corpus_path.suffix.lower() == ".epub":
        chunks = parse_epub_to_chunks(corpus_path)
        write_epub_chunks_jsonl(chunks, output_path)
    else:
        raise SystemExit("Unsupported corpus path. Use an EPUB file or a TXT corpus directory.")

    print(f"CORPUS: {corpus_path}")
    print(f"OUTPUT: {output_path}")
    print(f"CHUNKS: {len(chunks)}")
    print(f"SAMPLE: {chunks[0].chapter_title if chunks else 'NONE'}")


if __name__ == "__main__":
    main()
