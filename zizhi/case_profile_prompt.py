from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PROMPTS_DIR = ROOT / "prompts"
SYSTEM_PROMPT_V1_PATH = PROMPTS_DIR / "case_extraction_system_prompt_v1.txt"
USER_PROMPT_V1_PATH = PROMPTS_DIR / "case_extraction_user_prompt_v1.txt"


def load_case_extraction_system_prompt(version: str = "v1") -> str:
    return _resolve_prompt_path(kind="system", version=version).read_text(encoding="utf-8")


def load_case_extraction_user_prompt_template(version: str = "v1") -> str:
    return _resolve_prompt_path(kind="user", version=version).read_text(encoding="utf-8")


def render_case_extraction_user_prompt(input_payload: dict[str, Any], version: str = "v1") -> str:
    prompt = load_case_extraction_user_prompt_template(version=version)
    return prompt.replace("{{INPUT_JSON}}", json.dumps(input_payload, ensure_ascii=False, indent=2))


def build_case_extraction_messages(input_payload: dict[str, Any], version: str = "v1") -> dict[str, str]:
    return {
        "system_prompt": load_case_extraction_system_prompt(version=version),
        "user_prompt": render_case_extraction_user_prompt(input_payload, version=version),
    }


def _resolve_prompt_path(kind: str, version: str) -> Path:
    normalized = version.strip().lower()
    if normalized == "v1":
        return SYSTEM_PROMPT_V1_PATH if kind == "system" else USER_PROMPT_V1_PATH
    raise ValueError(f"Unsupported case extraction prompt version: {version}")
