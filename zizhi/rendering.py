from __future__ import annotations

import html

import streamlit as st
import streamlit.components.v1 as components

from zizhi.schemas import FinalOutput


def final_output_to_markdown(output: FinalOutput) -> str:
    if output.user_problem.scene_type == "域外问题":
        return "\n".join(
            [
                f"# 资智适用范围提示（{output.template_version}）",
                "",
                "## 查询摘要",
                output.user_problem.summary,
                "",
                "## 判断结果",
                output.situation_analysis.overall_judgement,
                "",
                "## 可尝试的改写方向",
                "- 如果你想查《资治通鉴》史实，可以问：某人做过什么、某事是谁做的、某年发生了什么。",
                "- 如果你想查评论，可以问：司马光怎么看某人或某事。",
                "- 如果你想做现实管理分析，可以把问题改写成组织、用人、权力边界、汇报沟通、团队冲突等场景。",
            ]
        )

    if output.user_problem.scene_type in {"客观事实查询", "史臣评论查询"}:
        mirrors = "\n".join(
            f"- {mirror.title}（{mirror.source_type}）：{mirror.mapping_reason}"
            for mirror in output.historical_mirrors
        )
        return "\n".join(
            [
                f"# 资智检索结果（{output.template_version}）",
                "",
                "## 查询摘要",
                output.user_problem.summary,
                "",
                "## 检索结论",
                output.situation_analysis.overall_judgement,
                "",
                "## 相关证据",
                mirrors or "- 暂未检索到足够证据",
            ]
        )

    actors = "\n".join(
        f"- {actor.name}：{actor.role}；目标：{actor.goal or '待确认'}；风险：{actor.risk or '待确认'}"
        for actor in output.situation_analysis.actors
    )
    conflicts = "\n".join(f"- {item}" for item in output.situation_analysis.core_conflicts)
    mirrors = "\n".join(
        f"- {mirror.title}（{mirror.source_type}）：{mirror.mapping_reason}"
        for mirror in output.historical_mirrors
    )
    options = "\n".join(
        "\n".join(
            [
                f"### {option.name}",
                f"- 适用条件：{option.applicable_when}",
                *[f"- 步骤：{step}" for step in option.steps],
                *[f"- 风险：{risk}" for risk in option.risks],
            ]
        )
        for option in output.strategy_report.strategy_options
    )
    do_not = "\n".join(f"- {item}" for item in output.strategy_report.do_not_do)
    next_24h = "\n".join(f"- {item}" for item in output.strategy_report.next_actions_24h)
    next_7d = "\n".join(f"- {item}" for item in output.strategy_report.next_actions_7d)
    poetry = ""
    if output.poetry_comfort.triggered:
        poetry = (
            "\n## 古诗词抚慰\n"
            f"> {output.poetry_comfort.poem}\n\n"
            f"{output.poetry_comfort.explanation}\n"
        )

    return "\n".join(
        [
            f"# 资智幕僚报告（{output.template_version}）",
            "",
            "## 用户问题摘要",
            output.user_problem.summary,
            "",
            "## 局势概述",
            output.situation_analysis.overall_judgement,
            "",
            "## 关键矛盾",
            conflicts or "- 暂未识别明确矛盾",
            "",
            "## 人物与关系判断",
            actors or "- 暂未识别关键角色",
            "",
            "## 《资治通鉴》历史镜像",
            mirrors or "- 检索较弱，本轮仅能给出保守类比",
            "",
            "## 策略建议",
            output.strategy_report.main_recommendation,
            "",
            options,
            "",
            "## 风险预警",
            do_not,
            "",
            "## 建议的下一步动作",
            "### 24 小时内",
            next_24h,
            "",
            "### 7 天内",
            next_7d,
            poetry,
        ]
    )


def render_mermaid(graph: str) -> None:
    escaped_graph = html.escape(graph)
    components.html(
        f"""
        <pre class="mermaid">{escaped_graph}</pre>
        <script type="module">
          import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
          mermaid.initialize({{ startOnLoad: true, securityLevel: 'loose' }});
        </script>
        """,
        height=420,
        scrolling=True,
    )
    st.caption("若本地网络无法加载 Mermaid CDN，请使用上方 Mermaid 源码复制到支持 Mermaid 的编辑器中渲染。")
