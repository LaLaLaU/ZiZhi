from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from zizhi.case_postprocess import load_rows, resolve_json_family_path


DEFAULT_RUN_DIR = ROOT / ".cache" / "case_runs" / "case-corpus-through1200"
DEFAULT_CHUNKS_PATH = ROOT / ".cache" / "zizhi_tagging_chunks.jsonl"

REQUIRED_TEXT_FIELDS = (
    "title",
    "summary",
    "decision_actor",
    "core_conflict",
    "trigger",
    "outcome",
    "transferable_pattern",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit a CaseProfile corpus for observational stats under the current accepted extraction mode.")
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR, help="Case run directory containing case_profiles.json/jsonl.")
    parser.add_argument("--chunks", type=Path, default=DEFAULT_CHUNKS_PATH, help="Tagging chunks JSON/JSONL for chunk coverage stats.")
    parser.add_argument("--output-dir", type=Path, default=None, help="Directory for audit outputs. Defaults to <run-dir>/audit.")
    parser.add_argument("--low-score-threshold", type=float, default=0.75, help="Flag cases below this case_worthy_score.")
    parser.add_argument("--large-section-group-threshold", type=int, default=6, help="Flag section-key groups with at least this many cases.")
    parser.add_argument("--large-chunk-group-threshold", type=int, default=4, help="Flag chunk groups with at least this many cases.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_dir = args.run_dir.resolve()
    chunks_path = args.chunks.resolve()
    output_dir = (args.output_dir.resolve() if args.output_dir else run_dir / "audit")
    output_dir.mkdir(parents=True, exist_ok=True)

    case_path = resolve_json_family_path(run_dir / "case_profiles.jsonl")
    chunk_output_path = resolve_json_family_path(run_dir / "chunk_case_outputs.jsonl")
    cases = load_rows(case_path)
    chunk_outputs = load_rows(chunk_output_path)
    source_chunks = load_rows(chunks_path)

    audit = build_audit(
        cases=cases,
        chunk_outputs=chunk_outputs,
        source_chunks=source_chunks,
        low_score_threshold=args.low_score_threshold,
        large_section_group_threshold=args.large_section_group_threshold,
        large_chunk_group_threshold=args.large_chunk_group_threshold,
    )

    (output_dir / "case_quality_audit.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    write_jsonl(output_dir / "review_candidates.jsonl", audit["review_candidates"])
    (output_dir / "case_quality_audit.md").write_text(render_markdown(audit), encoding="utf-8")
    print(json.dumps({"output_dir": str(output_dir), **audit["summary"]}, ensure_ascii=False, indent=2))


def build_audit(
    cases: list[dict[str, Any]],
    chunk_outputs: list[dict[str, Any]],
    source_chunks: list[dict[str, Any]],
    low_score_threshold: float,
    large_section_group_threshold: int,
    large_chunk_group_threshold: int,
) -> dict[str, Any]:
    case_type_counts = Counter(str(case.get("case_type", "mixed") or "mixed") for case in cases)
    score_values = [safe_float(case.get("case_worthy_score")) for case in cases]
    missing_fields = {
        field: sum(1 for case in cases if not str(case.get(field, "")).strip())
        for field in REQUIRED_TEXT_FIELDS
    }

    section_groups = group_cases(cases, key_func=lambda case: "|".join(case.get("section_keys", [])))
    chunk_groups = group_cases(cases, key_func=lambda case: "|".join(case.get("chunk_ids", [])))
    decision_actor_counts = Counter(str(case.get("decision_actor", "")).strip() for case in cases if case.get("decision_actor"))

    low_score_cases = sorted(
        [case for case in cases if safe_float(case.get("case_worthy_score")) < low_score_threshold],
        key=lambda case: safe_float(case.get("case_worthy_score")),
    )
    large_section_groups = top_large_groups(section_groups, large_section_group_threshold)
    large_chunk_groups = top_large_groups(chunk_groups, large_chunk_group_threshold)
    repeated_title_groups = top_large_groups(group_cases(cases, key_func=lambda case: normalize_text(case.get("title", ""))), 2)

    chunk_case_counts = [safe_int(row.get("cases_accepted")) for row in chunk_outputs]
    zero_case_chunks = [row.get("chunk_id", "") for row in chunk_outputs if safe_int(row.get("cases_accepted")) == 0]
    source_chunk_count = len(source_chunks)

    summary = {
        "cases": len(cases),
        "source_chunks": source_chunk_count,
        "completed_chunks": len(chunk_outputs),
        "case_coverage_ratio": round(len(chunk_outputs) / source_chunk_count, 4) if source_chunk_count else 0.0,
        "avg_cases_per_completed_chunk": round(sum(chunk_case_counts) / len(chunk_case_counts), 3) if chunk_case_counts else 0.0,
        "zero_case_chunks": len(zero_case_chunks),
        "low_score_cases": len(low_score_cases),
        "large_section_groups": len(large_section_groups),
        "large_chunk_groups": len(large_chunk_groups),
        "repeated_title_groups": len(repeated_title_groups),
        "score_min": round(min(score_values), 3) if score_values else 0.0,
        "score_avg": round(sum(score_values) / len(score_values), 3) if score_values else 0.0,
        "score_max": round(max(score_values), 3) if score_values else 0.0,
    }

    return {
        "summary": summary,
        "case_type_counts": dict(case_type_counts.most_common()),
        "top_decision_actors": dict(decision_actor_counts.most_common(20)),
        "missing_fields": missing_fields,
        "zero_case_chunk_ids_sample": zero_case_chunks[:50],
        "large_section_groups": large_section_groups[:50],
        "large_chunk_groups": large_chunk_groups[:50],
        "repeated_title_groups": repeated_title_groups[:50],
        "review_candidates": [],
    }


def group_cases(cases: list[dict[str, Any]], key_func) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for case in cases:
        key = str(key_func(case)).strip()
        if key:
            groups[key].append(case)
    return groups


def top_large_groups(groups: dict[str, list[dict[str, Any]]], threshold: int) -> list[dict[str, Any]]:
    rows = []
    for key, group in groups.items():
        if len(group) < threshold:
            continue
        rows.append(
            {
                "key": key,
                "count": len(group),
                "case_ids": [str(case.get("case_id", "")) for case in group],
                "titles": [str(case.get("title", "")) for case in group],
                "decision_actors": sorted({str(case.get("decision_actor", "")) for case in group if case.get("decision_actor")}),
                "case_types": dict(Counter(str(case.get("case_type", "mixed")) for case in group).most_common()),
            }
        )
    return sorted(rows, key=lambda row: (-row["count"], row["key"]))


def build_review_candidates(
    low_score_cases: list[dict[str, Any]],
    large_chunk_groups: list[dict[str, Any]],
    repeated_title_groups: list[dict[str, Any]],
    cases_by_id: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    candidates: dict[str, dict[str, Any]] = {}

    def add_case(case: dict[str, Any], reason: str, group_key: str = "") -> None:
        case_id = str(case.get("case_id", "")).strip()
        if not case_id:
            return
        row = candidates.setdefault(
            case_id,
            {
                "case_id": case_id,
                "title": case.get("title", ""),
                "case_type": case.get("case_type", ""),
                "case_worthy_score": safe_float(case.get("case_worthy_score")),
                "section_keys": case.get("section_keys", []),
                "chunk_ids": case.get("chunk_ids", []),
                "decision_actor": case.get("decision_actor", ""),
                "core_conflict": case.get("core_conflict", ""),
                "transferable_pattern": case.get("transferable_pattern", ""),
                "review_reasons": [],
                "group_keys": [],
            },
        )
        if reason not in row["review_reasons"]:
            row["review_reasons"].append(reason)
        if group_key and group_key not in row["group_keys"]:
            row["group_keys"].append(group_key)

    for case in low_score_cases[:100]:
        add_case(case, "low_case_worthy_score")
    for group in large_chunk_groups[:30]:
        for case_id in group["case_ids"]:
            add_case(cases_by_id.get(case_id, {}), "many_cases_share_chunk_ids", group["key"])
    for group in repeated_title_groups[:30]:
        for case_id in group["case_ids"]:
            add_case(cases_by_id.get(case_id, {}), "repeated_title", group["key"])

    return sorted(
        candidates.values(),
        key=lambda row: (-len(row["review_reasons"]), row["case_worthy_score"], row["case_id"]),
    )


def render_markdown(audit: dict[str, Any]) -> str:
    summary = audit["summary"]
    lines = [
        "# Case Corpus Quality Audit",
        "",
        "## Summary",
        "",
        f"- Cases: {summary['cases']}",
        f"- Completed chunks: {summary['completed_chunks']} / {summary['source_chunks']} ({summary['case_coverage_ratio']:.2%})",
        f"- Average cases per completed chunk: {summary['avg_cases_per_completed_chunk']}",
        f"- Zero-case chunks: {summary['zero_case_chunks']}",
        f"- Score range: {summary['score_min']} / {summary['score_avg']} / {summary['score_max']}",
        f"- Low-score cases: {summary['low_score_cases']}",
        f"- Large same-section groups: {summary['large_section_groups']}",
        f"- Large same-chunk groups: {summary['large_chunk_groups']}",
        f"- Repeated title groups: {summary['repeated_title_groups']}",
        "",
        "## Case Types",
        "",
    ]
    for name, count in audit["case_type_counts"].items():
        lines.append(f"- {name}: {count}")

    lines.extend(["", "## Missing Fields", ""])
    for name, count in audit["missing_fields"].items():
        lines.append(f"- {name}: {count}")

    lines.extend(["", "## Top Same-Section Groups", ""])
    for group in audit["large_section_groups"][:12]:
        title_preview = "；".join(group["titles"][:3])
        lines.append(f"- `{group['key']}`: {group['count']} cases. {title_preview}")

    lines.extend(
        [
            "",
            "> Note: multiple cases under the same section are treated as an informational cluster, not an automatic review risk.",
        ]
    )

    lines.extend(
        [
            "",
            "## Review Policy",
            "",
            "- Under the current production mode, all extracted cases are treated as accepted by default.",
            "- Low-score cases, repeated titles, and large same-section clusters remain observable statistics, not blocking review gates.",
        ]
    )

    return "\n".join(lines) + "\n"


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(row, ensure_ascii=False) + "\n")


def safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def safe_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def normalize_text(value: Any) -> str:
    return "".join(str(value or "").split()).lower()


if __name__ == "__main__":
    main()
