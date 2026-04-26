from __future__ import annotations

import json

import streamlit as st

from zizhi.rendering import final_output_to_markdown, render_mermaid
from zizhi.workflow import ZiZhiWorkflow


st.set_page_config(page_title="资智 ZiZhi", page_icon="📜", layout="wide")


def main() -> None:
    st.title("📜 资智 ZiZhi")
    st.caption("基于《资治通鉴》的历史案例映射系统 · V1 本地 Demo")

    with st.sidebar:
        st.header("使用边界")
        st.write("先判断局势，再定位相关案例，最后回查史料并给可执行建议。")
        st.write("不做法律、心理咨询、HR 合规结论，也不承诺精确预测。")

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

    with st.spinner("资智正在分析局势..."):
        workflow = ZiZhiWorkflow()
        result = workflow.run(user_input.strip(), progress_callback=on_step)

    if result.final_output is None:
        st.error("输出组装失败，请缩短问题后重试。")
        return

    output = result.final_output
    markdown_report = final_output_to_markdown(output)
    st.success("分析完成")

    tab_report, tab_graph, tab_evidence, tab_poetry, tab_json = st.tabs(
        ["幕僚报告", "Mermaid 图", "史料依据", "诗词抚慰", "结构化 JSON"]
    )

    with tab_report:
        st.markdown(markdown_report)
        st.download_button(
            "下载 Markdown 报告",
            data=markdown_report,
            file_name="zizhi_report.md",
            mime="text/markdown",
        )

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
