from __future__ import annotations

import json
import os
import statistics
import sys
import time
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from openai import OpenAI


SYSTEM_PROMPT = (
    "你是一个中文意图路由器，只做四分类，并返回 JSON。"
    "分类标签只有：factual_lookup、commentary_lookup、analysis、out_of_scope。"
    "factual_lookup：用户在问客观历史事实、人物、时间、地点、事件经过。"
    "commentary_lookup：用户明确在问司马光怎么看、如何评价、评论什么。"
    "analysis：用户在问怎么办、如何处理、如何管理、如何借历史类比现实，或问题本质相关。"
    "out_of_scope：问题与《资治通鉴》史实、司马光评论、历史映射现实管理这三个方向都无明显关系。"
    "必须输出 JSON 对象，字段只有 intent_type、confidence、reason。"
)

QUERIES = [
    "是谁杀了侠累",
    "吴起有哪些故事",
    "司马光怎么看智瑶",
    "我被同事绕过汇报怎么办",
    "带兵治军相关管理问题，吴起的故事能给我什么启发？",
    "如何做红烧肉",
]


@dataclass(frozen=True)
class Target:
    name: str
    env_key: str
    base_url: str
    model: str


TARGETS = [
    Target(
        name="ark-doubao-seed-2-0-mini",
        env_key="ARK_API_KEY",
        base_url="https://ark.cn-beijing.volces.com/api/v3",
        model="doubao-seed-2-0-mini-260215",
    ),
    Target(
        name="deepseek-chat",
        env_key="DEEPSEEK_API_KEY",
        base_url="https://api.deepseek.com",
        model="deepseek-chat",
    ),
]


def call_once(client: OpenAI, model: str, query: str) -> tuple[float, str]:
    started = time.perf_counter()
    response = client.chat.completions.create(
        model=model,
        temperature=0.0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps({"text": query}, ensure_ascii=False)},
        ],
        max_tokens=160,
    )
    elapsed = time.perf_counter() - started
    return elapsed, response.choices[0].message.content or ""


def summarize(values: list[float]) -> dict[str, float]:
    return {
        "count": float(len(values)),
        "avg_s": round(statistics.mean(values), 3),
        "median_s": round(statistics.median(values), 3),
        "min_s": round(min(values), 3),
        "max_s": round(max(values), 3),
    }


def main() -> None:
    repeats = int(os.getenv("ZIZHI_ROUTER_BENCH_REPEATS", "3"))
    for target in TARGETS:
        api_key = os.getenv(target.env_key)
        print(f"\\n=== {target.name} | model={target.model} ===")
        if not api_key:
            print(json.dumps({"skipped": True, "reason": f"missing {target.env_key}"}, ensure_ascii=False))
            continue

        client = OpenAI(api_key=api_key, base_url=target.base_url, timeout=30)
        latencies: list[float] = []
        errors = 0
        for round_index in range(repeats):
            for query in QUERIES:
                try:
                    elapsed, content = call_once(client, target.model, query)
                    latencies.append(elapsed)
                    print(json.dumps(
                        {
                            "round": round_index + 1,
                            "query": query,
                            "latency_s": round(elapsed, 3),
                            "response": content,
                        },
                        ensure_ascii=False,
                    ))
                except Exception as exc:
                    errors += 1
                    print(json.dumps(
                        {
                            "round": round_index + 1,
                            "query": query,
                            "error": type(exc).__name__,
                            "message": str(exc)[:500],
                        },
                        ensure_ascii=False,
                    ))

        if latencies:
            print(json.dumps({"summary": summarize(latencies), "errors": errors}, ensure_ascii=False))
        else:
            print(json.dumps({"summary": None, "errors": errors}, ensure_ascii=False))


if __name__ == "__main__":
    main()
