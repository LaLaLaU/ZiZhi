from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from openai import OpenAI

from zizhi.case_profile_prompt import build_case_extraction_messages


DEFAULT_CHUNKS_PATH = ROOT / ".cache" / "zizhi_tagging_chunks.jsonl"
DEFAULT_OUTPUT_ROOT = ROOT / ".cache" / "case_runs"

PROVIDER_DEFAULTS = {
    "openai": {"api_key_env": "OPENAI_API_KEY", "base_url": ""},
    "deepseek": {"api_key_env": "DEEPSEEK_API_KEY", "base_url": "https://api.deepseek.com"},
    "ark": {"api_key_env": "ARK_API_KEY", "base_url": "https://ark.cn-beijing.volces.com/api/v3"},
    "custom": {"api_key_env": "OPENAI_API_KEY", "base_url": ""},
}

MODERN_ROLE_MARKERS = (
    "决策者",
    "负责人",
    "承压者",
    "执行者",
    "建议者",
    "说服者",
    "谈判代表",
    "接班人",
    "压力来源",
    "外部强势方",
    "核心高管",
    "内部追随者",
    "资深功臣",
    "新晋高位者",
    "关键筹码",
    "外部对手",
    "外部协作方",
    "联盟成员",
    "实权操盘者",
    "高风险执行者",
    "非常规行动者",
    "非正式顾问",
    "不确定性来源",
    "代理负责人",
    "被动承压者",
    "利益获得者",
    "被安置者",
)

ANCIENT_ROLE_MAP = (
    ("魏国国相", "核心高管/授权执行者"),
    ("齐国国相", "核心高管/授权执行者"),
    ("赵章国相", "共谋者/叛乱执行者"),
    ("秦相", "核心高管/授权执行者"),
    ("齐相", "核心高管/授权执行者"),
    ("国相", "核心高管/授权执行者"),
    ("太子师傅", "接班人辅导者/风险提醒者"),
    ("太子宠妃", "亲近影响者/非正式权力来源"),
    ("宠妃", "亲近影响者/非正式权力来源"),
    ("爱姬", "亲近影响者/非正式权力来源"),
    ("宠臣", "亲近影响者/非正式权力来源"),
    ("太子", "关键接班人/承压者"),
    ("王子", "继承候选人/关键接班人"),
    ("继承人", "关键接班人/承压者"),
    ("新立国君", "新任负责人/权力承接者"),
    ("继任国君", "新任负责人/权力承接者"),
    ("新君", "新任负责人/权力承接者"),
    ("对手君主", "外部强势方/压力来源"),
    ("赵国国君", "最高决策者/组织负责人"),
    ("赵国主君", "最高决策者/组织负责人"),
    ("国君", "最高决策者/组织负责人"),
    ("君主", "最高决策者/组织负责人"),
    ("皇帝", "最高决策者/组织负责人"),
    ("最高统治者", "最高决策者/组织负责人"),
    ("秦王", "外部强势方/压力来源"),
    ("赵王", "最高决策者/组织负责人"),
    ("齐王", "最高决策者/组织负责人"),
    ("王", "最高决策者/组织负责人"),
    ("相国人选", "高位候选人/被评估者"),
    ("相国", "核心高管/授权执行者"),
    ("丞相", "核心高管/授权执行者"),
    ("令尹", "核心高管/授权执行者"),
    ("大臣", "核心下属/内部意见提供者"),
    ("臣下", "核心下属/内部意见提供者"),
    ("臣子", "核心下属/内部意见提供者"),
    ("权臣", "核心高管/实权操盘者"),
    ("执政重臣", "核心高管/授权执行者"),
    ("受托重臣", "受托负责人/关键守护者"),
    ("近臣", "亲近影响者/非正式权力来源"),
    ("谋士", "策略建议者/说服者"),
    ("谋臣", "策略建议者/说服者"),
    ("策士", "策略建议者/说服者"),
    ("顾问", "策略建议者/说服者"),
    ("军师", "策略建议者/说服者"),
    ("说客", "外部说服者/策略推动者"),
    ("纵横家", "外部说服者/策略推动者"),
    ("预言者", "风险提示者/外部观察者"),
    ("赵将", "一线负责人/关键执行者"),
    ("秦将", "一线负责人/关键执行者"),
    ("汉将", "一线负责人/关键执行者"),
    ("魏军主将", "一线负责人/关键执行者"),
    ("联军统帅之一", "联盟一线负责人/关键执行者"),
    ("守城方首领", "防守负责人/关键执行者"),
    ("主帅", "一线负责人/关键执行者"),
    ("主将", "一线负责人/关键执行者"),
    ("将军", "一线负责人/关键执行者"),
    ("大将", "一线负责人/关键执行者"),
    ("将领", "一线负责人/关键执行者"),
    ("将才", "关键执行者/专业人才"),
    ("地方官", "区域负责人/绩效承压者"),
    ("使者", "谈判代表/受命执行者"),
    ("游说者", "外部说服者/策略推动者"),
    ("门客", "内部追随者/声誉压力来源"),
    ("下属", "内部追随者/执行压力来源"),
    ("质子", "被约束的关键筹码"),
    ("人质", "被约束的关键筹码"),
    ("争位者", "竞争候选人/秩序挑战者"),
    ("被废黜者", "失势负责人/被动承压者"),
    ("攻伐者", "外部行动方/压力制造者"),
    ("进谏者", "风险提醒者/内部纠偏者"),
    ("谏臣", "风险提醒者/内部纠偏者"),
    ("劝谏者", "风险提醒者/内部纠偏者"),
    ("劝说者", "说服者/关系协调者"),
    ("举荐者", "资源推荐者/利益相关方"),
    ("同盟诸侯", "外部协作方/联盟成员"),
    ("诸侯", "外部利益相关方/联盟成员"),
    ("对手", "外部对手/竞争方"),
    ("刺客", "高风险执行者/非常规行动者"),
    ("方士", "非正式顾问/不确定性来源"),
    ("受封者", "利益获得者/被安置者"),
    ("目标", "被动承压者/目标对象"),
    ("进攻方", "外部行动方/压力制造者"),
    ("宫廷影响者", "亲近影响者/非正式权力来源"),
    ("摄政者", "代理负责人/权力托管者"),
    ("候选人", "候选负责人/被评估者"),
    ("盟友", "协作方/联盟伙伴"),
    ("长子", "继承候选人/关键接班人"),
    ("托人复仇者", "委托方/复仇推动者"),
    ("受命护送者", "受命执行者/安全负责人"),
    ("制衡者", "制衡方/风险控制者"),
    ("授权者", "授权方/最终批准者"),
    ("主权者", "最高决策者/组织负责人"),
    ("贤士", "关键人才/外部资源"),
    ("变法主导者", "变革负责人/改革推动者"),
    ("实际操盘者", "实权操盘者/关键执行者"),
    ("最终决策者", "最高决策者/组织负责人"),
    ("主导者", "主导方/关键推动者"),
    ("受劝者", "被说服者/决策承压者"),
    ("被索地者", "被施压方/资源让渡者"),
)


def main() -> None:
    args = parse_args()
    provider_defaults = PROVIDER_DEFAULTS[args.provider]
    api_key_env = args.api_key_env or provider_defaults["api_key_env"]
    base_url = args.base_url if args.base_url is not None else provider_defaults["base_url"]
    run_dir = make_run_dir(args.output_root, args.run_name)

    rows = load_chunk_rows(args.chunks, chunk_id=args.chunk_id, start=args.start, limit=args.limit)
    if not rows:
        raise SystemExit("No chunks selected.")

    write_run_config(
        run_dir,
        args,
        api_key_env=api_key_env,
        base_url=base_url,
        selected_count=len(rows),
    )

    first_payload = build_payload(rows[0])
    first_messages = build_case_extraction_messages(first_payload, version=args.prompt_version)
    (run_dir / "sample_prompt_system.txt").write_text(first_messages["system_prompt"], encoding="utf-8")
    (run_dir / "sample_prompt_user.txt").write_text(first_messages["user_prompt"], encoding="utf-8")

    if not args.execute:
        print(f"DRY RUN: selected {len(rows)} chunks.")
        print(f"Run directory: {run_dir}")
        print(f"Chunks source: {args.chunks}")
        print("Add --execute to call the remote model.")
        return

    api_key = os.getenv(api_key_env)
    if not api_key:
        raise SystemExit(f"Missing API key environment variable: {api_key_env}")

    client = OpenAI(api_key=api_key, base_url=base_url or None, timeout=args.timeout_seconds)
    existing_chunk_ids = load_existing_completed_chunk_ids(run_dir) if args.resume else set()

    completed = 0
    skipped = 0
    failed = 0
    accepted_cases = 0
    started_at = time.perf_counter()

    with (
        (run_dir / "case_profiles.jsonl").open("a", encoding="utf-8") as case_file,
        (run_dir / "chunk_case_outputs.jsonl").open("a", encoding="utf-8") as chunk_outputs_file,
        (run_dir / "raw_responses.jsonl").open("a", encoding="utf-8") as raw_file,
        (run_dir / "errors.jsonl").open("a", encoding="utf-8") as errors_file,
    ):
        for offset, chunk_row in enumerate(rows, start=1):
            chunk_id = str(chunk_row.get("chunk_id", ""))
            if args.resume and chunk_id in existing_chunk_ids:
                skipped += 1
                print(f"[{offset}/{len(rows)}] SKIP {chunk_id}")
                continue

            payload = build_payload(chunk_row)
            messages = build_case_extraction_messages(payload, version=args.prompt_version)
            if args.save_prompts:
                prompt_dir = run_dir / "prompts"
                prompt_dir.mkdir(parents=True, exist_ok=True)
                (prompt_dir / f"{chunk_id}.system.txt").write_text(messages["system_prompt"], encoding="utf-8")
                (prompt_dir / f"{chunk_id}.user.txt").write_text(messages["user_prompt"], encoding="utf-8")

            try:
                last_parse_exc: Exception | None = None
                for parse_attempt in range(args.max_retries + 1):
                    elapsed, raw_content, usage = call_model(
                        client=client,
                        model=args.model,
                        system_prompt=messages["system_prompt"],
                        user_prompt=messages["user_prompt"],
                        temperature=args.temperature,
                        max_tokens=args.max_tokens,
                        json_mode=not args.disable_json_mode,
                        system_as_user=args.system_as_user,
                        max_retries=args.max_retries,
                        retry_sleep_seconds=args.retry_sleep_seconds,
                    )
                    try:
                        parsed = parse_json_content(raw_content)
                        break
                    except Exception as exc:
                        last_parse_exc = exc
                        if parse_attempt >= args.max_retries:
                            raise
                        time.sleep(args.retry_sleep_seconds)
                else:
                    raise last_parse_exc if last_parse_exc is not None else ValueError("Failed to parse model response.")
                cases = [item for item in parsed.get("cases", []) if isinstance(item, dict)]
                accepted = 0
                for index, case_row in enumerate(cases, start=1):
                    score = safe_float(case_row.get("case_worthy_score"))
                    if score < args.min_case_worthy_score:
                        continue
                    normalized = normalize_case_row(
                        chunk_id=chunk_id,
                        chunk_row=chunk_row,
                        case_row=case_row,
                        model=args.model,
                        provider=args.provider,
                        prompt_version=args.prompt_version,
                        usage=usage,
                        elapsed=elapsed,
                        case_index=index,
                    )
                    case_file.write(json.dumps(normalized, ensure_ascii=False) + "\n")
                    accepted += 1
                case_file.flush()

                chunk_outputs_file.write(
                    json.dumps(
                        {
                            "chunk_id": chunk_id,
                            "cases_returned": len(cases),
                            "cases_accepted": accepted,
                            "global_notes": parsed.get("global_notes", []),
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
                chunk_outputs_file.flush()

                raw_file.write(
                    json.dumps(
                        {
                            "chunk_id": chunk_id,
                            "model": args.model,
                            "provider": args.provider,
                            "elapsed_seconds": round(elapsed, 3),
                            "usage": usage,
                            "content": raw_content,
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
                raw_file.flush()

                completed += 1
                accepted_cases += accepted
                print(f"[{offset}/{len(rows)}] OK {chunk_id} cases={accepted} {elapsed:.2f}s")
            except Exception as exc:
                failed += 1
                errors_file.write(
                    json.dumps(
                        {
                            "chunk_id": chunk_id,
                            "error_type": type(exc).__name__,
                            "error": str(exc),
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
                errors_file.flush()
                print(f"[{offset}/{len(rows)}] FAIL {chunk_id}: {type(exc).__name__}: {exc}")

            if args.sleep_seconds > 0:
                time.sleep(args.sleep_seconds)

    total_elapsed = time.perf_counter() - started_at
    summary = {
        "selected": len(rows),
        "completed": completed,
        "skipped": skipped,
        "failed": failed,
        "accepted_cases": accepted_cases,
        "elapsed_seconds": round(total_elapsed, 3),
        "case_profiles_path": str(run_dir / "case_profiles.jsonl"),
        "chunk_case_outputs_path": str(run_dir / "chunk_case_outputs.jsonl"),
        "raw_responses_path": str(run_dir / "raw_responses.jsonl"),
        "errors_path": str(run_dir / "errors.jsonl"),
    }
    (run_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Batch extract story-level case profiles directly from tagging chunks.")
    parser.add_argument("--chunks", type=Path, default=DEFAULT_CHUNKS_PATH, help="Path to tagging chunks JSONL.")
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT, help="Directory for case extraction runs.")
    parser.add_argument("--run-name", default="", help="Optional run directory name.")
    parser.add_argument("--provider", choices=sorted(PROVIDER_DEFAULTS), default="openai")
    parser.add_argument("--api-key-env", default="", help="Environment variable name for the API key.")
    parser.add_argument("--base-url", default=None, help="OpenAI-compatible base URL. Empty string means default.")
    parser.add_argument("--model", required=True, help="Model name, e.g. gpt-5.4-mini.")
    parser.add_argument("--prompt-version", choices=["v1"], default="v1")
    parser.add_argument("--chunk-id", default="", help="Only process one chunk_id.")
    parser.add_argument("--start", type=int, default=0, help="0-based start row.")
    parser.add_argument("--limit", type=int, default=0, help="Maximum number of chunks. 0 means no limit.")
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--max-tokens", type=int, default=4000)
    parser.add_argument("--timeout-seconds", type=float, default=90.0)
    parser.add_argument("--sleep-seconds", type=float, default=0.0)
    parser.add_argument("--max-retries", type=int, default=2)
    parser.add_argument("--retry-sleep-seconds", type=float, default=3.0)
    parser.add_argument("--disable-json-mode", action="store_true", help="Do not pass response_format=json_object.")
    parser.add_argument(
        "--system-as-user",
        action="store_true",
        help="Merge system prompt into the user message for providers that do not accept role=system.",
    )
    parser.add_argument("--save-prompts", action="store_true", help="Save each prompt under the run directory.")
    parser.add_argument("--resume", action="store_true", help="Skip chunk_ids already present in case_profiles.jsonl.")
    parser.add_argument("--execute", action="store_true", help="Actually call the remote model.")
    parser.add_argument("--min-case-worthy-score", type=float, default=0.65)
    return parser.parse_args()


def load_chunk_rows(path: Path, chunk_id: str = "", start: int = 0, limit: int = 0) -> list[dict[str, Any]]:
    if not path.exists():
        raise SystemExit(f"Chunk file not found: {path}")
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as file:
        for row_index, line in enumerate(file):
            if row_index < start:
                continue
            stripped = line.strip()
            if not stripped:
                continue
            row = json.loads(stripped)
            current_chunk_id = str(row.get("chunk_id", ""))
            if chunk_id and current_chunk_id != chunk_id:
                continue
            rows.append(row)
            if limit and len(rows) >= limit:
                break
    return rows


def build_payload(chunk_row: dict[str, Any]) -> dict[str, Any]:
    section_keys = [str(key) for key in chunk_row.get("section_keys", []) if str(key).strip()]
    return {
        "chunk_id": str(chunk_row.get("chunk_id", "")),
        "volume_no": chunk_row.get("volume_no"),
        "volume_title": chunk_row.get("volume_title", ""),
        "chapter_title": chunk_row.get("chapter_title", ""),
        "year_title": chunk_row.get("year_title", ""),
        "section_keys": section_keys,
        "section_text_map": section_text_map(chunk_row),
        "white_text": chunk_row.get("white_text", ""),
    }


def section_text_map(chunk_row: dict[str, Any]) -> dict[str, str]:
    section_keys = [str(key) for key in chunk_row.get("section_keys", []) if str(key).strip()]
    parts = [part.strip() for part in str(chunk_row.get("white_text", "")).splitlines() if part.strip()]
    if len(parts) == len(section_keys) and section_keys:
        return dict(zip(section_keys, parts, strict=False))
    if len(section_keys) == 1:
        return {section_keys[0]: str(chunk_row.get("white_text", "")).strip()}
    return {}


def call_model(
    client: OpenAI,
    model: str,
    system_prompt: str,
    user_prompt: str,
    temperature: float,
    max_tokens: int,
    json_mode: bool,
    system_as_user: bool,
    max_retries: int,
    retry_sleep_seconds: float,
) -> tuple[float, str, dict[str, Any]]:
    last_exc: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            started = time.perf_counter()
            kwargs: dict[str, Any] = {
                "model": model,
                "temperature": temperature,
                "messages": build_chat_messages(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    system_as_user=system_as_user,
                ),
                "max_tokens": max_tokens,
            }
            if json_mode:
                kwargs["response_format"] = {"type": "json_object"}
            response = client.chat.completions.create(**kwargs)
            elapsed = time.perf_counter() - started
            content = response.choices[0].message.content or ""
            usage = response.usage.model_dump() if response.usage is not None else {}
            return elapsed, content, usage
        except Exception as exc:
            last_exc = exc
            if attempt >= max_retries:
                break
            time.sleep(retry_sleep_seconds)
    raise last_exc if last_exc is not None else RuntimeError("Model call failed without exception.")


def parse_json_content(content: str) -> dict[str, Any]:
    text = content.strip()
    if not text:
        raise ValueError("Empty model response.")
    if text.startswith("```"):
        lines = text.splitlines()
        if len(lines) >= 3:
            text = "\n".join(lines[1:-1]).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise
        return json.loads(text[start : end + 1])


def build_chat_messages(system_prompt: str, user_prompt: str, system_as_user: bool) -> list[dict[str, str]]:
    if system_as_user:
        return [{"role": "user", "content": f"{system_prompt}\n\n{user_prompt}"}]
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def normalize_case_row(
    chunk_id: str,
    chunk_row: dict[str, Any],
    case_row: dict[str, Any],
    model: str,
    provider: str,
    prompt_version: str,
    usage: dict[str, Any],
    elapsed: float,
    case_index: int,
) -> dict[str, Any]:
    normalized_section_keys = [key for key in case_row.get("section_keys", []) if key in chunk_row.get("section_keys", [])]
    if not normalized_section_keys:
        normalized_section_keys = list(chunk_row.get("section_keys", []))

    return {
        "case_id": build_case_id(chunk_row, chunk_id, case_index, case_row),
        "title": str(case_row.get("title", "")).strip(),
        "summary": str(case_row.get("summary", "")).strip(),
        "case_type": str(case_row.get("case_type", "mixed")).strip() or "mixed",
        "section_keys": normalized_section_keys,
        "chunk_ids": [chunk_id],
        "start_volume_no": chunk_row.get("volume_no"),
        "end_volume_no": chunk_row.get("volume_no"),
        "start_year": str(chunk_row.get("year_title", "")),
        "end_year": str(chunk_row.get("year_title", "")),
        "actors": normalize_actors(case_row.get("actors", [])),
        "perspectives": normalize_perspectives(case_row.get("perspectives", []), normalized_section_keys),
        "decision_actor": str(case_row.get("decision_actor", "")).strip(),
        "core_conflict": str(case_row.get("core_conflict", "")).strip(),
        "trigger": str(case_row.get("trigger", "")).strip(),
        "outcome": str(case_row.get("outcome", "")).strip(),
        "transferable_pattern": str(case_row.get("transferable_pattern", "")).strip(),
        "case_tags": [str(tag).strip() for tag in case_row.get("case_tags", []) if str(tag).strip()],
        "source_priority": 0.85,
        "case_worthy_score": safe_float(case_row.get("case_worthy_score")),
    }


def normalize_actors(values: Any) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
    for item in values:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        if not name:
            continue
        role = str(item.get("role", "")).strip()
        stance = str(item.get("stance", "")).strip()
        normalized.append(
            {
                "name": name,
                "role": normalize_actor_role(name=name, role=role, stance=stance),
                "stance": stance,
            }
        )
    return normalized[:5]


def normalize_actor_role(name: str, role: str, stance: str = "") -> str:
    role = role.strip()
    stance = stance.strip()
    if not role:
        return ""
    if any(marker in role for marker in MODERN_ROLE_MARKERS):
        return role

    if "蔺相如" in name and ("上卿" in role or "避让" in stance):
        return "新晋高位者/主动避让者"
    if "廉颇" in name and ("大将" in role or "不满" in stance or "请罪" in stance):
        return "资深功臣/不满者"
    if "门客" in name or "门客" in role:
        if "羞耻" in stance or "避让" in stance or "声誉" in stance:
            return "内部追随者/声誉压力来源"

    for ancient_role, modern_role in ANCIENT_ROLE_MAP:
        if ancient_role in role:
            if modern_role == "一线负责人/关键执行者" and ("不满" in stance or "功" in stance):
                return "资深功臣/不满者"
            if modern_role == "最高决策者/组织负责人" and ("对手" in role or "压" in stance or "胁" in stance):
                return "外部强势方/压力来源"
            return modern_role
    return role


def normalize_perspectives(values: Any, valid_section_keys: list[str]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for item in values:
        if not isinstance(item, dict):
            continue
        normalized.append(
            {
                "perspective_type": str(item.get("perspective_type", "unknown")).strip() or "unknown",
                "perspective_summary": str(item.get("perspective_summary", "")).strip(),
                "event_labels": [str(label).strip() for label in item.get("event_labels", []) if str(label).strip()],
                "risk_labels": [str(label).strip() for label in item.get("risk_labels", []) if str(label).strip()],
                "strategy_labels": [str(label).strip() for label in item.get("strategy_labels", []) if str(label).strip()],
                "modern_scenes": [str(label).strip() for label in item.get("modern_scenes", []) if str(label).strip()],
                "evidence_section_keys": [key for key in item.get("evidence_section_keys", []) if key in valid_section_keys],
                "confidence": safe_float(item.get("confidence")),
            }
        )
    return normalized


def build_case_id(chunk_row: dict[str, Any], chunk_id: str, case_index: int, case_row: dict[str, Any]) -> str:
    volume_no = int(chunk_row.get("volume_no") or 0)
    case_type = str(case_row.get("case_type", "mixed")).strip() or "mixed"
    actor = slugify(str(case_row.get("decision_actor", "")).strip()) or f"c{case_index:02d}"
    return f"llm-case-v{volume_no:03d}-{case_type}-{actor}-{chunk_id.split('-')[-1]}-{case_index:02d}"


def slugify(text: str) -> str:
    value = "".join(ch if ch.isalnum() or "\u4e00" <= ch <= "\u9fff" else "-" for ch in text.lower()).strip("-")
    return value[:24]


def safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def make_run_dir(output_root: Path, run_name: str) -> Path:
    output_root.mkdir(parents=True, exist_ok=True)
    if run_name:
        run_dir = output_root / run_name
    else:
        run_dir = output_root / datetime.now().strftime("case-%Y%m%d-%H%M%S")
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def write_run_config(
    run_dir: Path,
    args: argparse.Namespace,
    api_key_env: str,
    base_url: str | None,
    selected_count: int,
) -> None:
    config = {
        "chunks_path": str(args.chunks),
        "provider": args.provider,
        "api_key_env": api_key_env,
        "base_url": base_url,
        "model": args.model,
        "prompt_version": args.prompt_version,
        "temperature": args.temperature,
        "max_tokens": args.max_tokens,
        "system_as_user": args.system_as_user,
        "selected": selected_count,
        "chunk_id": args.chunk_id,
        "start": args.start,
        "limit": args.limit,
        "min_case_worthy_score": args.min_case_worthy_score,
    }
    (run_dir / "config.json").write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")


def load_existing_chunk_ids(path: Path) -> set[str]:
    chunk_ids: set[str] = set()
    with path.open("r", encoding="utf-8") as file:
        for line in file:
            stripped = line.strip()
            if not stripped:
                continue
            row = json.loads(stripped)
            for chunk_id in row.get("chunk_ids", []):
                chunk_id = str(chunk_id).strip()
                if chunk_id:
                    chunk_ids.add(chunk_id)
    return chunk_ids


def load_existing_completed_chunk_ids(run_dir: Path) -> set[str]:
    chunk_ids: set[str] = set()
    chunk_output_path = run_dir / "chunk_case_outputs.jsonl"
    if chunk_output_path.exists():
        with chunk_output_path.open("r", encoding="utf-8") as file:
            for line in file:
                stripped = line.strip()
                if not stripped:
                    continue
                row = json.loads(stripped)
                chunk_id = str(row.get("chunk_id", "")).strip()
                if chunk_id:
                    chunk_ids.add(chunk_id)
    case_profile_path = run_dir / "case_profiles.jsonl"
    if case_profile_path.exists():
        chunk_ids.update(load_existing_chunk_ids(case_profile_path))
    return chunk_ids


if __name__ == "__main__":
    main()
