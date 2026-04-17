from __future__ import annotations

import os
import sys
import csv
from pathlib import Path
from statistics import mean, median

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from zizhi.txt_ingest import summarize_txt_corpus_lengths, write_length_csv


DEFAULT_ROOT = Path("sources") / "资治通鉴txt版 中华书局2012年18册 沈志华 张宏儒 传世经典·文白对照"


def write_outlier_csv(rows: list[dict[str, int | str]], output_path: Path) -> None:
    enriched = []
    for row in rows:
        paired = int(row["paired_sections"])
        original_only = int(row["original_only_sections"])
        white_only = int(row["white_only_sections"])
        total_sections = paired + original_only + white_only
        original_only_ratio = (original_only / total_sections) if total_sections else 0.0
        if original_only >= 4 or original_only_ratio >= 0.05:
            enriched.append(
                {
                    **row,
                    "total_sections": total_sections,
                    "original_only_ratio": round(original_only_ratio, 4),
                }
            )

    enriched.sort(
        key=lambda item: (int(item["original_only_sections"]), item["original_only_ratio"]),
        reverse=True,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "volume_no",
                "file",
                "paired_sections",
                "original_only_sections",
                "white_only_sections",
                "total_sections",
                "original_only_ratio",
                "original_chars",
                "white_chars",
            ],
        )
        writer.writeheader()
        writer.writerows(enriched)


def main() -> None:
    corpus_root = Path(os.getenv("ZIZHI_TXT_CORPUS_PATH", DEFAULT_ROOT))
    rows = summarize_txt_corpus_lengths(corpus_root)
    output_path = ROOT / ".cache" / "zizhi_txt_white_lengths.csv"
    write_length_csv(rows, output_path)
    outlier_path = ROOT / ".cache" / "zizhi_original_only_outliers.csv"
    write_outlier_csv(rows, outlier_path)

    white_vals = [int(row["white_chars"]) for row in rows]
    original_vals = [int(row["original_chars"]) for row in rows]

    print(f"count={len(rows)}")
    print(f"white_min={min(white_vals)}")
    print(f"white_max={max(white_vals)}")
    print(f"white_avg={mean(white_vals):.1f}")
    print(f"white_median={median(white_vals):.1f}")
    print(f"white_total={sum(white_vals)}")
    print(f"original_total={sum(original_vals)}")
    print(f"csv={output_path}")
    print(f"outliers={outlier_path}")
    print("TOP5_WHITE_SMALL")
    for row in sorted(rows, key=lambda item: int(item["white_chars"]))[:5]:
        print(row["volume_no"], row["white_chars"], row["file"])
    print("TOP5_WHITE_LARGE")
    for row in sorted(rows, key=lambda item: int(item["white_chars"]), reverse=True)[:5]:
        print(row["volume_no"], row["white_chars"], row["file"])


if __name__ == "__main__":
    main()
