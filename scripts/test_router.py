from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from zizhi.workflow import ZiZhiWorkflow


DEFAULT_QUERIES = [
    "是谁杀了侠累",
    "司马光怎么看智瑶",
    "我被同事绕过汇报怎么办",
    "如何做红烧肉",
]


def main() -> None:
    queries = sys.argv[1:] or DEFAULT_QUERIES
    workflow = ZiZhiWorkflow()
    for query in queries:
        state = workflow.run(query)
        payload = {
            "query": query,
            "intent_type": state.intent_type,
            "routing_source": state.routing_source,
            "routing_confidence": state.routing_confidence,
            "routing_reason": state.routing_reason,
            "routing_model": state.routing_model,
            "scene_type": state.scene_type,
        }
        print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
