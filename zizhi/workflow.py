from __future__ import annotations

from collections.abc import Callable
from typing import Any

from zizhi.agents import (
    AgentContext,
    commentary_response_composer,
    commentary_retriever,
    factual_retriever,
    factual_response_composer,
    historical_retriever,
    intent_scene_analyzer,
    out_of_scope_response_composer,
    query_rewriter,
    reflection_critic,
    response_composer,
    strategy_mapper,
)
from zizhi.case_retrieval import CaseRetriever
from zizhi.corpus import load_simaguang_commentary_corpus, load_tagging_chunk_corpus
from zizhi.retrieval import HistoricalRetriever
from zizhi.router import IntentRouter
from zizhi.schemas import AnalysisState


ProgressCallback = Callable[[str], None]


class ZiZhiWorkflow:
    def __init__(self, retriever: HistoricalRetriever | None = None) -> None:
        base_retriever = retriever or HistoricalRetriever()
        factual_chunks = load_tagging_chunk_corpus()
        commentary_chunks = load_simaguang_commentary_corpus()
        intent_router = IntentRouter.from_env()
        self.context = AgentContext(
            retriever=base_retriever,
            case_retriever=CaseRetriever(),
            factual_retriever=HistoricalRetriever(chunks=factual_chunks, enable_lancedb=False)
            if factual_chunks
            else base_retriever,
            commentary_retriever=HistoricalRetriever(chunks=commentary_chunks, enable_lancedb=False)
            if commentary_chunks
            else None,
            intent_router=intent_router,
        )
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
        graph.add_node("retrieve_factual", self._node(factual_retriever, "正在检索史实"))
        graph.add_node("retrieve_commentary", self._node(commentary_retriever, "正在检索评论"))
        graph.add_node("rewrite", self._node(query_rewriter, "正在改写检索查询"))
        graph.add_node("retrieve", self._node(historical_retriever, "正在检索史例"))
        graph.add_node("map_strategy", self._node(strategy_mapper, "正在生成策略"))
        graph.add_node("reflect", self._node(reflection_critic, "正在反思审校"))
        graph.add_node("compose_factual", self._node(factual_response_composer, "正在输出事实结果"))
        graph.add_node("compose_commentary", self._node(commentary_response_composer, "正在输出评论结果"))
        graph.add_node("compose_out_of_scope", self._node(out_of_scope_response_composer, "正在提示适用范围"))
        graph.add_node("compose", self._node(response_composer, "正在输出结果"))

        graph.set_entry_point("analyze")
        graph.add_conditional_edges(
            "analyze",
            self._route_after_analyze,
            {
                "factual": "retrieve_factual",
                "commentary": "retrieve_commentary",
                "out_of_scope": "compose_out_of_scope",
                "analysis": "rewrite",
            },
        )
        graph.add_edge("retrieve_factual", "compose_factual")
        graph.add_edge("retrieve_commentary", "compose_commentary")
        graph.add_edge("rewrite", "retrieve")
        graph.add_edge("retrieve", "map_strategy")
        graph.add_edge("map_strategy", "reflect")
        graph.add_conditional_edges(
            "reflect",
            self._should_retry,
            {"retry": "map_strategy", "compose": "compose"},
        )
        graph.add_edge("compose", END)
        graph.add_edge("compose_factual", END)
        graph.add_edge("compose_commentary", END)
        graph.add_edge("compose_out_of_scope", END)
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
        if progress_callback:
            progress_callback("正在理解问题")
        state = intent_scene_analyzer(state, self.context)

        if state.intent_type == "factual_lookup":
            if progress_callback:
                progress_callback("正在检索史实")
            state = factual_retriever(state, self.context)
            if progress_callback:
                progress_callback("正在输出事实结果")
            return factual_response_composer(state, self.context)

        if state.intent_type == "commentary_lookup":
            if progress_callback:
                progress_callback("正在检索评论")
            state = commentary_retriever(state, self.context)
            if progress_callback:
                progress_callback("正在输出评论结果")
            return commentary_response_composer(state, self.context)

        if state.intent_type == "out_of_scope":
            if progress_callback:
                progress_callback("正在提示适用范围")
            return out_of_scope_response_composer(state, self.context)

        for label, func in [
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

    @staticmethod
    def _route_after_analyze(payload: dict[str, Any]) -> str:
        state: AnalysisState = payload["state"]
        if state.intent_type == "factual_lookup":
            return "factual"
        if state.intent_type == "commentary_lookup":
            return "commentary"
        if state.intent_type == "out_of_scope":
            return "out_of_scope"
        return "analysis"
