from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PROMPTS_DIR = ROOT / "prompts"
SYSTEM_PROMPT_V1_PATH = PROMPTS_DIR / "case_extraction_system_prompt_v1.txt"
USER_PROMPT_V1_PATH = PROMPTS_DIR / "case_extraction_user_prompt_v1.txt"


def load_case_extraction_system_prompt(version: str = "v1", max_cases: int = 3) -> str:
    return _render_template(_resolve_prompt_path(kind="system", version=version).read_text(encoding="utf-8"), max_cases=max_cases)


def load_case_extraction_user_prompt_template(version: str = "v1") -> str:
    return _resolve_prompt_path(kind="user", version=version).read_text(encoding="utf-8")


def render_case_extraction_user_prompt(input_payload: dict[str, Any], version: str = "v1", max_cases: int = 3) -> str:
    prompt = load_case_extraction_user_prompt_template(version=version)
    prompt = _render_template(prompt, max_cases=max_cases)
    return prompt.replace("{{INPUT_JSON}}", json.dumps(input_payload, ensure_ascii=False, indent=2))


def build_case_extraction_messages(input_payload: dict[str, Any], version: str = "v1", max_cases: int = 3) -> dict[str, str]:
    return {
        "system_prompt": load_case_extraction_system_prompt(version=version, max_cases=max_cases),
        "user_prompt": render_case_extraction_user_prompt(input_payload, version=version, max_cases=max_cases),
    }


def _render_template(prompt: str, max_cases: int) -> str:
    if max_cases <= 0:
        rule = "不设数量上限；在不重复、不降低 case-worthy 标准的前提下，尽可能完整枚举所有值得入库的 case"
    else:
        rule = f"最多输出 {max_cases} 个 case"
    return prompt.replace("{{CASE_COUNT_RULE}}", rule)


def _resolve_prompt_path(kind: str, version: str) -> Path:
    normalized = version.strip().lower()
    if normalized == "v1":
        return SYSTEM_PROMPT_V1_PATH if kind == "system" else USER_PROMPT_V1_PATH
    raise ValueError(f"Unsupported case extraction prompt version: {version}")
