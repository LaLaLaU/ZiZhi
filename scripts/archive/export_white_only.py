from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from zizhi.txt_ingest import parse_txt_volume


DEFAULT_ROOT = Path("sources") / "资治通鉴txt版 中华书局2012年18册 沈志华 张宏儒 传世经典·文白对照"


def main() -> None:
    corpus_root = Path(os.getenv("ZIZHI_TXT_CORPUS_PATH", DEFAULT_ROOT))
    output_path = ROOT / ".cache" / "white_only_remaining.jsonl"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    count = 0
    with output_path.open("w", encoding="utf-8") as file:
        for path in sorted(corpus_root.rglob("*.txt")):
            if not path.stem.isdigit():
                continue
            for section in parse_txt_volume(path):
                if section.pair_type != "white_only":
                    continue
                count += 1
                file.write(
                    json.dumps(
                        {
                            "volume_no": int(path.stem),
                            "section_key": section.section_key,
                            "file": path.relative_to(corpus_root).as_posix(),
                            "chapter_title": section.chapter_title,
                            "year_title": section.year_title,
                            "white_text": section.white_text,
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )

    print(f"white_only_count={count}")
    print(f"output={output_path}")


if __name__ == "__main__":
    main()
