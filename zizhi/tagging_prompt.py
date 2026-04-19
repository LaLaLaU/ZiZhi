from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PROMPTS_DIR = ROOT / "prompts"
SYSTEM_PROMPT_PATH = PROMPTS_DIR / "tagging_system_prompt.txt"
USER_PROMPT_PATH = PROMPTS_DIR / "tagging_user_prompt.txt"
LABEL_POOLS_PATH = PROMPTS_DIR / "tagging_label_pools.json"


def load_tagging_system_prompt() -> str:
    return SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")


def load_tagging_user_prompt_template() -> str:
    return USER_PROMPT_PATH.read_text(encoding="utf-8")


def load_tagging_label_pools() -> dict[str, list[str]]:
    data = json.loads(LABEL_POOLS_PATH.read_text(encoding="utf-8"))
    return {
        "event_labels": list(data.get("event_labels", [])),
        "risk_labels": list(data.get("risk_labels", [])),
        "strategy_labels": list(data.get("strategy_labels", [])),
        "modern_scenes": list(data.get("modern_scenes", [])),
    }


def render_tagging_user_prompt(
    input_payload: dict[str, Any],
    label_pools: dict[str, list[str]] | None = None,
) -> str:
    pools = label_pools or load_tagging_label_pools()
    prompt = load_tagging_user_prompt_template()
    replacements = {
        "{{EVENT_LABELS}}": _render_json_array(pools.get("event_labels", [])),
        "{{RISK_LABELS}}": _render_json_array(pools.get("risk_labels", [])),
        "{{STRATEGY_LABELS}}": _render_json_array(pools.get("strategy_labels", [])),
        "{{MODERN_SCENES}}": _render_json_array(pools.get("modern_scenes", [])),
        "{{INPUT_JSON}}": json.dumps(input_payload, ensure_ascii=False, indent=2),
    }
    for placeholder, value in replacements.items():
        prompt = prompt.replace(placeholder, value)
    return prompt


def build_tagging_messages(
    input_payload: dict[str, Any],
    label_pools: dict[str, list[str]] | None = None,
) -> dict[str, str]:
    return {
        "system_prompt": load_tagging_system_prompt(),
        "user_prompt": render_tagging_user_prompt(input_payload, label_pools=label_pools),
    }


def _render_json_array(values: list[str]) -> str:
    return json.dumps(values, ensure_ascii=False, indent=2)
