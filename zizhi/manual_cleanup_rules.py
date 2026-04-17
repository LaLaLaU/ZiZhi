from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path


DATE_NOTE_RE = re.compile(r"（[初十廿卅三一二四五六七八九\d]+[日月号]?")


@lru_cache(maxsize=1)
def _load_rule_table() -> dict[str, list[str]]:
    path = Path(__file__).with_name("manual_rule_table.json")
    return json.loads(path.read_text(encoding="utf-8"))


def strip_malformed_prefix(text: str) -> str:
    cleaned = text
    for prefix in _load_rule_table()["drop_prefixes"]:
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix) :]
    return cleaned


def looks_like_translation_segment(text: str) -> bool:
    if not text:
        return False
    rule_table = _load_rule_table()
    if text.startswith(tuple(rule_table["translation_prefixes"])):
        return True
    if DATE_NOTE_RE.search(text):
        return True
    score = sum(1 for marker in rule_table["translation_markers"] if marker in text)
    return score >= 2
