from __future__ import annotations

from collections.abc import Callable
from typing import Any

from zizhi.agents import (
    AgentContext,
    historical_retriever,
    intent_scene_analyzer,
    query_rewriter,
    reflection_critic,
    response_composer,
    strategy_mapper,
)
from zizhi.retrieval import HistoricalRetriever
from zizhi.schemas import AnalysisState


ProgressCallback = Callable[[str], None]


class ZiZhiWorkflow:
    def __init__(self, retriever: HistoricalRetriever | None = None) -> None:
        self.context = AgentContext(retriever=retriever or HistoricalRetriever())
        self._graph = self._try_build_langgraph()

    def run(self, user_input: str, progress_callback: ProgressCallback | None = None) -> AnalysisState:
        initial_state = AnalysisState(user_input=user_input)
        if self._graph is not None:
            return self._run_langgraph(initial_state, progress_callback)
        return self._run_manual(initial_state, progress_callback)

    def _try_build_langgraph(self) -> Any | None:
        try:
            from langgraph.graph import END, StateGraph
        except Exception:
            return None

        graph = StateGraph(dict)
        graph.add_node("analyze", self._node(intent_scene_analyzer, "正在理解问题"))
        graph.add_node("rewrite", self._node(query_rewriter, "正在改写检索查询"))
        graph.add_node("retrieve", self._node(historical_retriever, "正在检索史例"))
        graph.add_node("map_strategy", self._node(strategy_mapper, "正在生成策略"))
        graph.add_node("reflect", self._node(reflection_critic, "正在反思审校"))
        graph.add_node("compose", self._node(response_composer, "正在输出结果"))

        graph.set_entry_point("analyze")
        graph.add_edge("analyze", "rewrite")
        graph.add_edge("rewrite", "retrieve")
        graph.add_edge("retrieve", "map_strategy")
        graph.add_edge("map_strategy", "reflect")
        graph.add_conditional_edges(
            "reflect",
            self._should_retry,
            {"retry": "map_strategy", "compose": "compose"},
        )
        graph.add_edge("compose", END)
        return graph.compile()

    def _run_langgraph(
        self,
        state: AnalysisState,
        progress_callback: ProgressCallback | None,
    ) -> AnalysisState:
        payload = {"state": state, "progress_callback": progress_callback}
        result = self._graph.invoke(payload)
        return result["state"]

    def _run_manual(
        self,
        state: AnalysisState,
        progress_callback: ProgressCallback | None,
    ) -> AnalysisState:
        for label, func in [
            ("正在理解问题", intent_scene_analyzer),
            ("正在改写检索查询", query_rewriter),
            ("正在检索史例", historical_retriever),
            ("正在生成策略", strategy_mapper),
            ("正在反思审校", reflection_critic),
        ]:
            if progress_callback:
                progress_callback(label)
            state = func(state, self.context)

        if not state.reflection_passed and state.retry_count <= 1:
            if progress_callback:
                progress_callback("审校未通过，正在重试策略")
            state = strategy_mapper(state, self.context)
            if progress_callback:
                progress_callback("正在二次反思审校")
            state = reflection_critic(state, self.context)

        if progress_callback:
            progress_callback("正在输出结果")
        return response_composer(state, self.context)

    def _node(self, func, label: str):
        def wrapped(payload: dict[str, Any]) -> dict[str, Any]:
            callback = payload.get("progress_callback")
            if callback:
                callback(label)
            payload["state"] = func(payload["state"], self.context)
            return payload

        return wrapped

    @staticmethod
    def _should_retry(payload: dict[str, Any]) -> str:
        state: AnalysisState = payload["state"]
        if not state.reflection_passed and state.retry_count <= 1:
            callback = payload.get("progress_callback")
            if callback:
                callback("审校未通过，正在重试策略")
            return "retry"
        return "compose"
