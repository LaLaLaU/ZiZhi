from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scripts.batch_extract_case_profiles import normalize_actor_role, safe_float


@dataclass(frozen=True)
class ChunkCatalog:
    chunk_index: dict[str, int]
    section_index: dict[str, tuple[int, int]]


ROLE_EXACT_CANONICAL_MAP = {
    "最高决策者": "最高决策者/组织负责人",
    "组织最高决策者": "最高决策者/组织负责人",
    "组织负责人/最高决策者": "最高决策者/组织负责人",
    "组织最高决策者/实际控制人": "最高决策者/组织负责人",
    "新政权最高决策者": "最高决策者/组织负责人",
    "组织最高决策者/规则制定者": "最高决策者/组织负责人",
    "谈判代表/说服者": "谈判代表/受命执行者",
    "策略建议者/幕僚": "策略建议者/说服者",
    "策略建议者/高级幕僚": "策略建议者/说服者",
    "内部谋士/策略建议者": "策略建议者/说服者",
    "外部协作方/盟友": "协作方/联盟伙伴",
    "核心高管/策略建议者": "核心高管/授权执行者",
    "核心高管/关键执行者": "核心高管/授权执行者",
}

ROLE_SUBSTRING_CANONICAL_RULES = (
    (("组织最高决策者",), "最高决策者/组织负责人"),
    (("最高决策者", "组织负责人"), "最高决策者/组织负责人"),
    (("策略建议者", "幕僚"), "策略建议者/说服者"),
    (("谈判代表", "说服"), "谈判代表/受命执行者"),
)


def build_chunk_catalog(chunks_path: Path) -> ChunkCatalog:
    chunk_index: dict[str, int] = {}
    section_index: dict[str, tuple[int, int]] = {}
    with chunks_path.open("r", encoding="utf-8") as file:
        for idx, line in enumerate(file):
            stripped = line.strip()
            if not stripped:
                continue
            row = json.loads(stripped)
            chunk_id = str(row.get("chunk_id", "")).strip()
            if not chunk_id:
                continue
            chunk_index[chunk_id] = idx
            for section_pos, section_key in enumerate(row.get("section_keys", [])):
                section_key = str(section_key).strip()
                if section_key:
                    section_index[section_key] = (idx, section_pos)
    return ChunkCatalog(chunk_index=chunk_index, section_index=section_index)


def canonicalize_role(role: str) -> str:
    value = role.strip()
    if not value:
        return ""
    if value in ROLE_EXACT_CANONICAL_MAP:
        return ROLE_EXACT_CANONICAL_MAP[value]
    if value == "决策者":
        return "最高决策者/组织负责人"
    if "叛将" in value:
        return "一线负责人/关键执行者"
    if any(token in value for token in ("庶兄", "宗室")) and "/" not in value:
        return "继承竞争者/内部挑战者"
    if "将" in value and "/" not in value and len(value) <= 4:
        return "一线负责人/关键执行者"
    for needles, canonical in ROLE_SUBSTRING_CANONICAL_RULES:
        if all(needle in value for needle in needles):
            return canonical
    return value


def normalize_case_record(case: dict[str, Any], catalog: ChunkCatalog) -> dict[str, Any]:
    normalized = dict(case)
    normalized["chunk_ids"] = sort_unique_strings(case.get("chunk_ids", []), key=lambda item: chunk_sort_key(item, catalog))
    normalized["section_keys"] = sort_unique_strings(
        case.get("section_keys", []),
        key=lambda item: section_sort_key(item, catalog),
    )
    normalized["case_tags"] = dedupe_preserve_order(case.get("case_tags", []))
    normalized["actors"] = normalize_actor_list(case.get("actors", []))
    normalized["perspectives"] = normalize_perspective_list(case.get("perspectives", []), catalog)
    normalized["title"] = str(case.get("title", "")).strip()
    normalized["summary"] = str(case.get("summary", "")).strip()
    normalized["decision_actor"] = str(case.get("decision_actor", "")).strip()
    normalized["core_conflict"] = str(case.get("core_conflict", "")).strip()
    normalized["trigger"] = str(case.get("trigger", "")).strip()
    normalized["outcome"] = str(case.get("outcome", "")).strip()
    normalized["transferable_pattern"] = str(case.get("transferable_pattern", "")).strip()
    normalized["case_type"] = str(case.get("case_type", "mixed")).strip() or "mixed"
    normalized["case_worthy_score"] = safe_float(case.get("case_worthy_score"))
    normalized["source_priority"] = safe_float(case.get("source_priority", 0.85)) or 0.85
    return normalized


def normalize_actor_list(values: Any) -> list[dict[str, str]]:
    merged: dict[str, dict[str, str]] = {}
    for item in values:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        if not name:
            continue
        stance = str(item.get("stance", "")).strip()
        role = canonicalize_role(normalize_actor_role(name=name, role=str(item.get("role", "")).strip(), stance=stance))
        current = merged.get(name)
        candidate = {"name": name, "role": role, "stance": stance}
        if current is None:
            merged[name] = candidate
            continue
        if len(candidate["role"]) > len(current["role"]):
            current["role"] = candidate["role"]
        if len(candidate["stance"]) > len(current["stance"]):
            current["stance"] = candidate["stance"]
    return list(merged.values())[:5]


def normalize_perspective_list(values: Any, catalog: ChunkCatalog) -> list[dict[str, Any]]:
    seen: set[tuple[str, str]] = set()
    normalized: list[dict[str, Any]] = []
    for item in values:
        if not isinstance(item, dict):
            continue
        perspective_type = str(item.get("perspective_type", "unknown")).strip() or "unknown"
        perspective_summary = str(item.get("perspective_summary", "")).strip()
        key = (perspective_type, perspective_summary)
        if key in seen:
            continue
        seen.add(key)
        normalized.append(
            {
                "perspective_type": perspective_type,
                "perspective_summary": perspective_summary,
                "event_labels": dedupe_preserve_order(item.get("event_labels", [])),
                "risk_labels": dedupe_preserve_order(item.get("risk_labels", [])),
                "strategy_labels": dedupe_preserve_order(item.get("strategy_labels", [])),
                "modern_scenes": dedupe_preserve_order(item.get("modern_scenes", [])),
                "evidence_section_keys": sort_unique_strings(
                    item.get("evidence_section_keys", []),
                    key=lambda value: section_sort_key(value, catalog),
                ),
                "confidence": safe_float(item.get("confidence")),
            }
        )
    return normalized


def dedupe_and_merge_cases(cases: list[dict[str, Any]], catalog: ChunkCatalog) -> tuple[list[dict[str, Any]], int]:
    by_exact_key: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for case in cases:
        by_exact_key[exact_case_key(case)].append(case)

    exact_merged = [merge_case_group(group, catalog) for group in by_exact_key.values()]
    exact_merged.sort(key=lambda item: case_sort_key(item, catalog))

    merged_cases: list[dict[str, Any]] = []
    merges = 0
    for case in exact_merged:
        merged = False
        for index in range(len(merged_cases) - 1, max(-1, len(merged_cases) - 6), -1):
            current = merged_cases[index]
            if should_merge_cases(current, case, catalog):
                merged_cases[index] = merge_two_cases(current, case, catalog)
                merges += 1
                merged = True
                break
        if not merged:
            merged_cases.append(case)
    merged_cases.sort(key=lambda item: case_sort_key(item, catalog))
    return merged_cases, merges + max(0, len(cases) - len(exact_merged))


def exact_case_key(case: dict[str, Any]) -> tuple[Any, ...]:
    return (
        case.get("decision_actor", ""),
        case.get("case_type", ""),
        tuple(case.get("section_keys", [])),
        normalize_text(case.get("title", "")),
        normalize_text(case.get("core_conflict", "")),
    )


def should_merge_cases(left: dict[str, Any], right: dict[str, Any], catalog: ChunkCatalog) -> bool:
    if left.get("decision_actor", "") != right.get("decision_actor", ""):
        return False
    if left.get("case_type", "") != right.get("case_type", ""):
        return False

    left_chunks = [chunk_sort_key(chunk_id, catalog) for chunk_id in left.get("chunk_ids", [])]
    right_chunks = [chunk_sort_key(chunk_id, catalog) for chunk_id in right.get("chunk_ids", [])]
    if not left_chunks or not right_chunks:
        return False

    overlapping_sections = bool(set(left.get("section_keys", [])) & set(right.get("section_keys", [])))
    chunk_distance = abs(min(left_chunks) - min(right_chunks))
    if not overlapping_sections and chunk_distance > 1:
        return False

    similarity = text_similarity(case_compare_text(left), case_compare_text(right))
    return similarity >= 0.82 or (overlapping_sections and similarity >= 0.72)


def merge_case_group(group: list[dict[str, Any]], catalog: ChunkCatalog) -> dict[str, Any]:
    merged = group[0]
    for item in group[1:]:
        merged = merge_two_cases(merged, item, catalog)
    return merged


def merge_two_cases(left: dict[str, Any], right: dict[str, Any], catalog: ChunkCatalog) -> dict[str, Any]:
    preferred, secondary = choose_preferred_case(left, right)
    merged = dict(preferred)
    merged["chunk_ids"] = sort_unique_strings(
        list(preferred.get("chunk_ids", [])) + list(secondary.get("chunk_ids", [])),
        key=lambda item: chunk_sort_key(item, catalog),
    )
    merged["section_keys"] = sort_unique_strings(
        list(preferred.get("section_keys", [])) + list(secondary.get("section_keys", [])),
        key=lambda item: section_sort_key(item, catalog),
    )
    merged["case_tags"] = dedupe_preserve_order(list(preferred.get("case_tags", [])) + list(secondary.get("case_tags", [])))
    merged["actors"] = normalize_actor_list(list(preferred.get("actors", [])) + list(secondary.get("actors", [])))
    merged["perspectives"] = normalize_perspective_list(
        list(preferred.get("perspectives", [])) + list(secondary.get("perspectives", [])),
        catalog,
    )
    for field in ("title", "summary", "decision_actor", "core_conflict", "trigger", "outcome", "transferable_pattern"):
        merged[field] = pick_better_text(str(preferred.get(field, "")).strip(), str(secondary.get(field, "")).strip())
    merged["case_worthy_score"] = max(safe_float(preferred.get("case_worthy_score")), safe_float(secondary.get("case_worthy_score")))
    merged["source_priority"] = max(safe_float(preferred.get("source_priority", 0.85)), safe_float(secondary.get("source_priority", 0.85)))
    merged["start_volume_no"] = pick_numeric_boundary(merged.get("chunk_ids", []), preferred, secondary, catalog, start=True)
    merged["end_volume_no"] = pick_numeric_boundary(merged.get("chunk_ids", []), preferred, secondary, catalog, start=False)
    merged["start_year"] = pick_boundary_text(preferred, secondary, start=True, catalog=catalog)
    merged["end_year"] = pick_boundary_text(preferred, secondary, start=False, catalog=catalog)
    return merged


def choose_preferred_case(left: dict[str, Any], right: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    left_score = (
        safe_float(left.get("case_worthy_score")),
        len(case_compare_text(left)),
        len(left.get("summary", "")),
    )
    right_score = (
        safe_float(right.get("case_worthy_score")),
        len(case_compare_text(right)),
        len(right.get("summary", "")),
    )
    if right_score > left_score:
        return right, left
    return left, right


def pick_better_text(primary: str, secondary: str) -> str:
    if not primary:
        return secondary
    if not secondary:
        return primary
    if len(secondary) > len(primary) + 20:
        return secondary
    return primary


def pick_numeric_boundary(
    merged_chunk_ids: list[str],
    left: dict[str, Any],
    right: dict[str, Any],
    catalog: ChunkCatalog,
    start: bool,
) -> int | None:
    boundary_chunk = merged_chunk_ids[0] if start else merged_chunk_ids[-1]
    left_chunk = left.get("chunk_ids", [""])[0 if start else -1]
    right_chunk = right.get("chunk_ids", [""])[0 if start else -1]
    if chunk_sort_key(left_chunk, catalog) == chunk_sort_key(boundary_chunk, catalog):
        return left.get("start_volume_no" if start else "end_volume_no")
    if chunk_sort_key(right_chunk, catalog) == chunk_sort_key(boundary_chunk, catalog):
        return right.get("start_volume_no" if start else "end_volume_no")
    return left.get("start_volume_no" if start else "end_volume_no")


def pick_boundary_text(left: dict[str, Any], right: dict[str, Any], start: bool, catalog: ChunkCatalog) -> str:
    field = "start_year" if start else "end_year"
    left_chunk = left.get("chunk_ids", [""])[0 if start else -1]
    right_chunk = right.get("chunk_ids", [""])[0 if start else -1]
    if start:
        return left.get(field, "") if chunk_sort_key(left_chunk, catalog) <= chunk_sort_key(right_chunk, catalog) else right.get(field, "")
    return left.get(field, "") if chunk_sort_key(left_chunk, catalog) >= chunk_sort_key(right_chunk, catalog) else right.get(field, "")


def case_compare_text(case: dict[str, Any]) -> str:
    return " ".join(
        normalize_text(str(case.get(field, "")))
        for field in ("title", "core_conflict", "transferable_pattern")
    ).strip()


def text_similarity(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    left_tokens = set(character_ngrams(left))
    right_tokens = set(character_ngrams(right))
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def character_ngrams(text: str, size: int = 2) -> list[str]:
    compact = normalize_text(text)
    if len(compact) <= size:
        return [compact] if compact else []
    return [compact[index : index + size] for index in range(len(compact) - size + 1)]


def normalize_text(value: str) -> str:
    text = re.sub(r"\s+", "", value)
    return re.sub(r"[^\w\u4e00-\u9fff]", "", text).lower()


def case_sort_key(case: dict[str, Any], catalog: ChunkCatalog) -> tuple[int, int, str, float]:
    chunk_ids = case.get("chunk_ids", [])
    section_keys = case.get("section_keys", [])
    first_chunk = chunk_sort_key(chunk_ids[0], catalog) if chunk_ids else 10**9
    first_section = section_sort_key(section_keys[0], catalog) if section_keys else (10**9, 10**9)
    return (first_chunk, first_section[1], str(case.get("decision_actor", "")), -safe_float(case.get("case_worthy_score")))


def chunk_sort_key(chunk_id: str, catalog: ChunkCatalog) -> int:
    return catalog.chunk_index.get(str(chunk_id).strip(), 10**9)


def section_sort_key(section_key: str, catalog: ChunkCatalog) -> tuple[int, int]:
    return catalog.section_index.get(str(section_key).strip(), (10**9, 10**9))


def sort_unique_strings(values: Any, key) -> list[str]:
    deduped = dedupe_preserve_order(values)
    return sorted(deduped, key=key)


def dedupe_preserve_order(values: Any) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        text = str(value).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        deduped.append(text)
    return deduped


def load_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    if path.suffix == ".jsonl":
        with path.open("r", encoding="utf-8") as file:
            return [json.loads(line) for line in file if line.strip()]
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else []


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_json(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def postprocess_case_run(run_dir: Path, chunks_path: Path) -> dict[str, Any]:
    catalog = build_chunk_catalog(chunks_path)
    case_path = resolve_existing_path(run_dir, "case_profiles")
    chunk_output_path = resolve_existing_path(run_dir, "chunk_case_outputs")
    if case_path is None or chunk_output_path is None:
        raise FileNotFoundError(f"Missing case output files under {run_dir}")

    raw_cases = load_rows(case_path)
    raw_chunk_outputs = load_rows(chunk_output_path)

    normalized_cases = [normalize_case_record(case, catalog) for case in raw_cases]
    merged_cases, merged_count = dedupe_and_merge_cases(normalized_cases, catalog)

    chunk_outputs_by_id: dict[str, dict[str, Any]] = {}
    for row in raw_chunk_outputs:
        chunk_id = str(row.get("chunk_id", "")).strip()
        if not chunk_id:
            continue
        current = chunk_outputs_by_id.get(chunk_id)
        candidate = {
            "chunk_id": chunk_id,
            "cases_returned": int(row.get("cases_returned", 0) or 0),
            "cases_accepted": int(row.get("cases_accepted", 0) or 0),
            "global_notes": dedupe_preserve_order(row.get("global_notes", [])),
        }
        if current is None:
            chunk_outputs_by_id[chunk_id] = candidate
            continue
        current["cases_returned"] = max(current["cases_returned"], candidate["cases_returned"])
        current["cases_accepted"] = max(current["cases_accepted"], candidate["cases_accepted"])
        current["global_notes"] = dedupe_preserve_order(current["global_notes"] + candidate["global_notes"])

    processed_chunk_outputs = sorted(
        chunk_outputs_by_id.values(),
        key=lambda item: chunk_sort_key(item["chunk_id"], catalog),
    )

    write_jsonl(run_dir / "case_profiles.jsonl", merged_cases)
    write_json(run_dir / "case_profiles.json", merged_cases)
    write_jsonl(run_dir / "chunk_case_outputs.jsonl", processed_chunk_outputs)
    write_json(run_dir / "chunk_case_outputs.json", processed_chunk_outputs)

    summary_path = run_dir / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else {}
    selected = max(int(summary.get("selected", 0) or 0), len(processed_chunk_outputs))
    summary.update(
        {
            "selected": selected,
            "completed": len(processed_chunk_outputs),
            "failed": max(0, selected - len(processed_chunk_outputs)),
            "raw_case_count": len(raw_cases),
            "accepted_cases": len(merged_cases),
            "merged_case_reduction": max(0, len(raw_cases) - len(merged_cases)),
            "merge_operations": merged_count,
            "case_profiles_path": str(run_dir / "case_profiles.jsonl"),
            "chunk_case_outputs_path": str(run_dir / "chunk_case_outputs.jsonl"),
        }
    )
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


def build_consolidated_corpus(run_dirs: list[Path], output_run_dir: Path, chunks_path: Path) -> dict[str, Any]:
    catalog = build_chunk_catalog(chunks_path)
    all_cases: list[dict[str, Any]] = []
    all_chunk_outputs: list[dict[str, Any]] = []
    for run_dir in run_dirs:
        case_path = resolve_existing_path(run_dir, "case_profiles")
        chunk_output_path = resolve_existing_path(run_dir, "chunk_case_outputs")
        if case_path is None or chunk_output_path is None:
            continue
        all_cases.extend(load_rows(case_path))
        all_chunk_outputs.extend(load_rows(chunk_output_path))

    normalized_cases = [normalize_case_record(case, catalog) for case in all_cases]
    merged_cases, merged_count = dedupe_and_merge_cases(normalized_cases, catalog)

    chunk_outputs_by_id: dict[str, dict[str, Any]] = {}
    for row in all_chunk_outputs:
        chunk_id = str(row.get("chunk_id", "")).strip()
        if not chunk_id:
            continue
        current = chunk_outputs_by_id.get(chunk_id)
        candidate = {
            "chunk_id": chunk_id,
            "cases_returned": int(row.get("cases_returned", 0) or 0),
            "cases_accepted": int(row.get("cases_accepted", 0) or 0),
            "global_notes": dedupe_preserve_order(row.get("global_notes", [])),
        }
        if current is None:
            chunk_outputs_by_id[chunk_id] = candidate
            continue
        current["cases_returned"] = max(current["cases_returned"], candidate["cases_returned"])
        current["cases_accepted"] = max(current["cases_accepted"], candidate["cases_accepted"])
        current["global_notes"] = dedupe_preserve_order(current["global_notes"] + candidate["global_notes"])

    processed_chunk_outputs = sorted(
        chunk_outputs_by_id.values(),
        key=lambda item: chunk_sort_key(item["chunk_id"], catalog),
    )

    output_run_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(output_run_dir / "case_profiles.jsonl", merged_cases)
    write_json(output_run_dir / "case_profiles.json", merged_cases)
    write_jsonl(output_run_dir / "chunk_case_outputs.jsonl", processed_chunk_outputs)
    write_json(output_run_dir / "chunk_case_outputs.json", processed_chunk_outputs)

    summary = {
        "source_runs": [str(path) for path in run_dirs],
        "raw_case_count": len(all_cases),
        "accepted_cases": len(merged_cases),
        "merged_case_reduction": max(0, len(all_cases) - len(merged_cases)),
        "merge_operations": merged_count,
        "completed": len(processed_chunk_outputs),
        "case_profiles_path": str(output_run_dir / "case_profiles.jsonl"),
        "chunk_case_outputs_path": str(output_run_dir / "chunk_case_outputs.jsonl"),
    }
    (output_run_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


def resolve_existing_path(run_dir: Path, stem: str) -> Path | None:
    for suffix in (".jsonl", ".json"):
        path = run_dir / f"{stem}{suffix}"
        if path.exists():
            return path
    return None
