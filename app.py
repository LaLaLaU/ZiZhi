from __future__ import annotations

import json

import streamlit as st

from zizhi.rendering import final_output_to_markdown, render_mermaid
from zizhi.workflow import ZiZhiWorkflow


st.set_page_config(page_title="资智 ZiZhi", page_icon="📜", layout="wide")


def _short_text(text: str, limit: int = 220) -> str:
    compact = " ".join(text.split()).strip()
    if len(compact) <= limit:
        return compact
    return f"{compact[: limit - 3]}..."


def _chunk_preview(chunk) -> str:
    text = chunk.white_text or chunk.retrieval_text or chunk.original_text or chunk.annotation_text or chunk.text
    return _short_text(text, limit=260)


def _render_case_matches(result) -> None:
    st.subheader("命中的案例")
    if not result.case_matches:
        st.info("本轮没有先命中 case，系统应当是直接走了底层史料检索。")
        return

    st.caption(f"共命中 {len(result.case_matches)} 个 case，下面展示本轮实际拿来生成报告的候选案例。")
    for index, case in enumerate(result.case_matches, start=1):
        with st.container(border=True):
            st.markdown(f"**{index}. {case.title}**")
            st.write(f"case_id：`{case.case_id}`")
            st.write(f"检索分数：`{case.retrieval_score:.4f}` · 类型：`{case.case_type}`")
            if case.matched_fields:
                st.write(f"命中字段：{' / '.join(case.matched_fields)}")
            if case.matched_terms:
                st.write(f"命中线索：{'、'.join(case.matched_terms)}")
            if case.case_tags:
                st.write(f"案例标签：{'、'.join(case.case_tags)}")
            if case.actor_roles:
                st.write(f"现代角色：{'、'.join(case.actor_roles)}")
            if case.transferable_pattern:
                st.write(f"可迁移模式：{case.transferable_pattern}")
            if case.summary:
                st.write(f"案例摘要：{case.summary}")
            if case.mapping_reason:
                st.write(f"为什么命中：{case.mapping_reason}")
            if case.chunk_ids:
                st.write(f"关联 chunk：{'、'.join(case.chunk_ids)}")


def _render_evidence_pool(result) -> None:
    st.subheader("展开的史料窗口")
    if not result.evidence_pool:
        st.info("本轮没有展开到史料窗口。")
        return

    st.caption(f"共展开 {len(result.evidence_pool)} 条底层史料 chunk，用于证据引用和回查。")
    for index, chunk in enumerate(result.evidence_pool, start=1):
        with st.container(border=True):
            title = chunk.chapter_title or chunk.chunk_id
            st.markdown(f"**{index}. {title}**")
            st.write(
                f"chunk_id：`{chunk.chunk_id}` · 来源：`{chunk.chunk_type}` · 分数：`{chunk.score:.4f}`"
            )
            volume_bits = [item for item in [chunk.volume, chunk.dynasty, chunk.year] if item]
            if volume_bits:
                st.write(f"卷次/时代：{' / '.join(volume_bits)}")
            if chunk.people:
                st.write(f"人物：{'、'.join(chunk.people[:10])}")
            if chunk.topic_tags:
                st.write(f"主题标签：{'、'.join(chunk.topic_tags)}")
            if chunk.section_keys:
                st.write(f"section_keys：{'、'.join(chunk.section_keys[:8])}")
            st.write(f"史料预览：{_chunk_preview(chunk)}")


def _render_retrieval_trace(result) -> None:
    st.subheader("检索输入")
    queries = [query for query in result.retrieval_queries if query.strip()]
    if queries:
        st.code("\n".join(queries), language="text")
    else:
        st.info("本轮没有记录 retrieval queries。")

    st.divider()
    _render_case_matches(result)
    st.divider()
    _render_evidence_pool(result)


def main() -> None:
    st.title("📜 资智 ZiZhi")
    st.caption("基于《资治通鉴》的历史案例映射系统 · V1 本地 Demo")
    retrieval_status_placeholder = None

    with st.sidebar:
        st.header("使用边界")
        st.write("先判断局势，再定位相关案例，最后回查史料并给可执行建议。")
        st.write("不做法律、心理咨询、HR 合规结论，也不承诺精确预测。")
        st.divider()
        st.subheader("检索状态")
        retrieval_status_placeholder = st.empty()
        retrieval_status_placeholder.info("等待本轮初始化案例检索器。")

    user_input = st.text_area(
        "请描述你的现实困局",
        height=180,
        placeholder="例如：我现在直属领导不太信任我，但老板又经常单独找我汇报，我该怎么做？",
    )
    submitted = st.button("开始分析", type="primary", disabled=not user_input.strip())

    if not submitted:
        st.info("输入一段真实场景，系统会输出幕僚报告、相关历史案例、史料依据与必要的诗词抚慰。")
        return

    status_box = st.container(border=True)
    status_placeholder = status_box.empty()
    steps_seen: list[str] = []

    def on_step(step_name: str) -> None:
        steps_seen.append(step_name)
        status_placeholder.markdown("\n".join(f"- {step}" for step in steps_seen))

    steps_seen.append("正在初始化案例检索器（首次可能下载模型并建立向量索引）")
    status_placeholder.markdown("\n".join(f"- {step}" for step in steps_seen))

    with st.spinner("资智正在分析局势..."):
        workflow = ZiZhiWorkflow()
        case_retriever = getattr(workflow.context, "case_retriever", None)
        if case_retriever is not None:
            summary = case_retriever.status_summary()
            steps_seen.append(summary)
            status_placeholder.markdown("\n".join(f"- {step}" for step in steps_seen))
            if retrieval_status_placeholder is not None:
                if case_retriever.status.get("dense_backend_ready"):
                    retrieval_status_placeholder.success(summary)
                elif case_retriever.status.get("dense_requested"):
                    retrieval_status_placeholder.warning(summary)
                else:
                    retrieval_status_placeholder.info(summary)
        result = workflow.run(user_input.strip(), progress_callback=on_step)

    if result.final_output is None:
        st.error("输出组装失败，请缩短问题后重试。")
        return

    output = result.final_output
    markdown_report = final_output_to_markdown(output)
    st.success("分析完成")

    tab_report, tab_retrieval, tab_graph, tab_evidence, tab_poetry, tab_json = st.tabs(
        ["幕僚报告", "检索命中", "Mermaid 图", "史料依据", "诗词抚慰", "结构化 JSON"]
    )

    with tab_report:
        st.markdown(markdown_report)
        st.download_button(
            "下载 Markdown 报告",
            data=markdown_report,
            file_name="zizhi_report.md",
            mime="text/markdown",
        )

    with tab_retrieval:
        _render_retrieval_trace(result)

    with tab_graph:
        st.code(output.mermaid_graph, language="mermaid")
        render_mermaid(output.mermaid_graph)

    with tab_evidence:
        for citation in output.evidence_citations:
            with st.container(border=True):
                st.subheader(citation.title)
                st.write(f"来源类型：{citation.source_type}")
                st.write(f"用途：{citation.usage} · 置信度：{citation.confidence:.2f}")
                st.write(citation.quote)
                st.write(citation.mapping_reason)

    with tab_poetry:
        if output.poetry_comfort.triggered:
            st.markdown(f"> {output.poetry_comfort.poem}")
            st.write(output.poetry_comfort.explanation)
        else:
            st.write("本轮未触发诗词抚慰模块。")

    with tab_json:
        st.json(json.loads(output.model_dump_json()))


if __name__ == "__main__":
    main()
