from __future__ import annotations

import json
import os
from typing import Literal

from openai import OpenAI
from pydantic import BaseModel, Field


IntentType = Literal["factual_lookup", "commentary_lookup", "analysis", "out_of_scope"]


class IntentRouteDecision(BaseModel):
    intent_type: IntentType
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    reason: str = ""


class IntentRouter:
    def __init__(
        self,
        client: OpenAI,
        model: str,
        provider: str = "deepseek",
        confidence_threshold: float = 0.72,
    ) -> None:
        self.client = client
        self.model = model
        self.provider = provider
        self.confidence_threshold = confidence_threshold

    @classmethod
    def from_env(cls) -> IntentRouter | None:
        enabled = os.getenv("ZIZHI_ROUTER_ENABLED", "1").strip().lower()
        if enabled in {"0", "false", "no", "off"}:
            return None

        provider = os.getenv("ZIZHI_ROUTER_PROVIDER", "deepseek").strip().lower() or "deepseek"
        if provider == "deepseek":
            api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("ZIZHI_ROUTER_API_KEY")
            if not api_key:
                return None
            model = os.getenv("ZIZHI_ROUTER_MODEL", "deepseek-chat").strip() or "deepseek-chat"
            base_url = os.getenv("ZIZHI_ROUTER_BASE_URL", "https://api.deepseek.com").strip()
        elif provider in {"ark", "volcengine", "volcengine-ark"}:
            api_key = os.getenv("ARK_API_KEY") or os.getenv("ZIZHI_ROUTER_API_KEY")
            if not api_key:
                return None
            model = os.getenv("ZIZHI_ROUTER_MODEL", "doubao-seed-2-0-mini-260215").strip()
            base_url = os.getenv("ZIZHI_ROUTER_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3").strip()
            provider = "ark"
        else:
            api_key = os.getenv("ZIZHI_ROUTER_API_KEY")
            if not api_key:
                return None
            model = os.getenv("ZIZHI_ROUTER_MODEL", "").strip()
            base_url = os.getenv("ZIZHI_ROUTER_BASE_URL", "").strip()
            if not model:
                return None

        timeout_seconds = float(os.getenv("ZIZHI_ROUTER_TIMEOUT_SECONDS", "20"))
        confidence_threshold = float(os.getenv("ZIZHI_ROUTER_CONFIDENCE_THRESHOLD", "0.72"))
        client = OpenAI(api_key=api_key, base_url=base_url or None, timeout=timeout_seconds)
        return cls(
            client=client,
            model=model,
            provider=provider,
            confidence_threshold=confidence_threshold,
        )

    def route(self, text: str, rule_hint: str | None = None) -> IntentRouteDecision:
        system_prompt = (
            "你是一个中文意图路由器，只做四分类，并返回 JSON。"
            "分类标签只有：factual_lookup、commentary_lookup、analysis、out_of_scope。"
            "factual_lookup：用户在问客观历史事实、人物、时间、地点、事件经过。"
            "commentary_lookup：用户明确在问司马光怎么看、如何评价、评论什么。"
            "analysis：用户在问怎么办、如何处理、如何管理、如何借历史类比现实，或问题本质相关。"
            "out_of_scope：问题与《资治通鉴》史实、司马光评论、历史映射现实管理这三个方向都无明显关系，例如菜谱、纯生活常识、无关闲聊。"
            "优先按用户真正目的判断，不要被表面词迷惑。"
            "必须输出 JSON 对象，字段只有 intent_type、confidence、reason。"
            "confidence 取 0 到 1。reason 保持简短。"
        )
        user_payload = {
            "text": text,
            "rule_hint": rule_hint or "",
        }
        response = self.client.chat.completions.create(
            model=self.model,
            temperature=0.0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
            ],
            max_tokens=180,
        )
        content = response.choices[0].message.content or ""
        if not content.strip():
            raise ValueError("empty router response")
        return IntentRouteDecision.model_validate(json.loads(content))
