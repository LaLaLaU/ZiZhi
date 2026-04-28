from __future__ import annotations

import re
from dataclasses import dataclass

from zizhi.case_retrieval import CaseRetriever
from zizhi.retrieval import HistoricalRetriever
from zizhi.router import IntentRouter
from zizhi.schemas import (
    Actor,
    AnalysisState,
    EvidenceCitation,
    FinalOutput,
    HistoricalMirror,
    PoetryComfort,
    SituationAnalysis,
    StrategyOption,
    StrategyReport,
    UserProblem,
)


SCENE_KEYWORDS: list[tuple[str, list[str]]] = [
    ("向上管理", ["领导", "老板", "上级", "汇报", "越级", "直属"]),
    ("横向协作", ["同事", "跨部门", "协作", "抢功", "配合"]),
    ("团队冲突", ["团队", "下属", "核心成员", "互相", "冲突", "看不顺眼"]),
    ("用人与授权", ["授权", "用人", "骨干", "责任", "岗位"]),
    ("信任与猜忌", ["不信任", "猜忌", "怀疑", "试探", "边缘化"]),
    ("谗言与谣言", ["谗言", "谣言", "造谣", "诬陷", "中伤", "背后说", "告状", "诋毁", "诽谤", "针对", "刁难", "挤兑"]),
    ("嫉妒与背叛", ["嫉妒", "眼红", "见不得", "过得好", "好友", "发小", "同村", "兄弟反目", "背叛", "翻脸", "背后捅刀"]),
    ("站队与表态", ["站队", "表态", "沉默", "内斗", "高层"]),
    ("合伙与控制权", ["合伙", "联合创始人", "控制权", "绕过我"]),
    ("去留与进退", ["离职", "留下", "去留", "进退", "跳槽"]),
    ("组织变革", ["变革", "调整", "改革", "重组"]),
    ("情绪恢复", ["累", "疲惫", "委屈", "焦虑", "失落", "迷茫"]),
]

MODERN_TO_CLASSICAL: list[tuple[list[str], list[str]]] = [
    (["老婆", "妻子", "媳妇", "家属", "家眷", "太太"], ["外戚", "妻妾", "后宫", "家属", "家眷"]),
    (["谣言", "造谣", "背后说", "嚼舌根"], ["谗言", "谣言", "诬陷", "中伤", "诽谤", "诋毁"]),
    (["针对", "刁难", "挤兑", "为难", "使绊子"], ["构陷", "排挤", "打压", "陷害", "离间"]),
    (["枕边风", "吹风", "耳边风"], ["谗言", "媚", "蛊惑", "偏信", "偏听"]),
    (["告状", "打小报告", "背后告状"], ["告密", "诬告", "进谗"]),
    (["排挤", "边缘化", "架空"], ["排挤", "边缘化", "清洗", "疏远"]),
    (["不信任", "怀疑", "猜疑"], ["猜忌", "猜疑", "疑忌", "不信任"]),
    (["空降", "新来的"], ["空降", "外来", "新进"]),
    (["抢功", "邀功", "邀宠"], ["争功", "邀功", "冒功"]),
    (["穿小鞋", "报复", "打击报复"], ["报复", "打击", "惩罚"]),
    (["心腹", "亲信", "嫡系"], ["亲信", "心腹", "宠臣", "近臣"]),
    (["站队", "表忠心", "投靠"], ["站队", "表态", "归附"]),
    (["被开除", "被辞退", "被干掉"], ["被诛", "被废", "被黜", "被逐"]),
    (["跳槽", "离职", "走人"], ["去国", "出走", "奔他国"]),
    (["嫉妒", "眼红", "见不得", "过得好", "红眼", "见不得人好", "看不惯", "不服气", "眼气", "酸"], ["嫉妒", "猜忌", "排挤", "打压", "构陷", "陷害"]),
    (["好友", "发小", "同村", "兄弟", "哥们", "闺蜜"], ["同僚", "旧交", "故人", "盟友"]),
    (["背叛", "翻脸", "背后捅刀", "反目", "决裂"], ["背叛", "反目", "反噬", "倒戈", "负义"]),
]

EMOTION_KEYWORDS: list[tuple[str, list[str]]] = [
    ("焦虑", ["焦虑", "担心", "不安", "害怕"]),
    ("压力", ["压力", "压迫", "喘不过气", "被质疑"]),
    ("委屈", ["委屈", "不公平", "被误解", "抢功"]),
    ("失落", ["失落", "灰心", "没价值"]),
    ("迷茫", ["迷茫", "不知道", "不确定", "该不该"]),
    ("疲惫", ["累", "疲惫", "尽力", "耗尽"]),
]

FACTUAL_PATTERNS = ["谁", "何时", "什么时候", "哪年", "哪一年", "哪里", "何地", "哪国", "几个", "哪些", "是什么", "是不是"]
FACTUAL_LOOKUP_KEYWORDS = ["是谁", "谁杀了", "谁任命", "谁拥立", "谁攻打", "有哪些故事", "讲讲", "生平", "经历"]
COMMENTARY_PATTERNS = ["司马光怎么看", "司马光如何评价", "司马光评价", "司马光评论", "臣司马光曰", "司马光怎么说"]
ANALYSIS_HINTS = [
    "怎么办",
    "如何处理",
    "怎么处理",
    "如何管理",
    "怎么管理",
    "如何应对",
    "怎么应对",
    "如何带队",
    "如何用人",
    "相关管理问题",
    "本质上相关",
]
FIRST_PERSON_HINTS = ["我", "我们", "我的", "我们团队", "我们公司", "老板", "领导", "同事", "下属", "合伙人"]
DOMAIN_HINTS = [
    "资治通鉴",
    "司马光",
    "历史",
    "史例",
    "史臣",
    "吴起",
    "智瑶",
    "君臣",
    "诸侯",
    "战国",
    "秦",
    "汉",
    "唐",
    "周",
    "晋",
    "魏",
    "赵",
    "韩",
    "楚",
    "齐",
    "燕",
    "老板",
    "领导",
    "同事",
    "下属",
    "汇报",
    "职场",
    "团队",
    "管理",
    "组织",
    "合伙人",
    "控制权",
]
OUT_OF_SCOPE_HINTS = [
    "红烧肉",
    "菜谱",
    "做饭",
    "烹饪",
    "炒菜",
    "炖肉",
    "天气",
    "股票",
    "足球比分",
    "电影推荐",
    "旅游攻略",
    "减肥餐",
    "Python报错",
]
LOOKUP_NOISE_TERMS = [
    "司马光怎么看",
    "司马光如何评价",
    "司马光评价",
    "司马光评论",
    "司马光怎么说",
    "是谁",
    "谁杀了",
    "杀了",
    "杀死",
    "有哪些故事",
    "故事",
    "讲讲",
    "生平",
    "经历",
    "如何评价",
    "怎么看",
    "怎么说",
    "评价",
    "评论",
    "有哪些",
    "哪些",
    "什么",
]
LOOKUP_SENTENCE_RE = re.compile(r"[^。！？；!?;\n]+[。！？；!?;]?")


@dataclass
class AgentContext:
    retriever: HistoricalRetriever
    case_retriever: CaseRetriever | None = None
    factual_retriever: HistoricalRetriever | None = None
    commentary_retriever: HistoricalRetriever | None = None
    intent_router: IntentRouter | None = None


def intent_scene_analyzer(state: AnalysisState, context: AgentContext) -> AnalysisState:
    text = state.user_input
    intent_type, routing_source, routing_confidence, routing_reason, routing_model = _resolve_intent(text, context)
    scene_type = _pick_scene(text)
    emotion_labels = _pick_emotions(text)
    actors = _extract_actors(text)
    conflicts = _extract_conflicts(text, scene_type)
    constraints = _extract_constraints(text)

    if intent_type == "factual_lookup":
        scene_type = "客观事实查询"
        conflicts = []
        constraints = ["优先直接回答史实，不进行策略映射"]
    elif intent_type == "commentary_lookup":
        scene_type = "史臣评论查询"
        conflicts = []
        constraints = ["优先检索史臣评论，不展开现实策略分析"]
    elif intent_type == "out_of_scope":
        scene_type = "域外问题"
        actors = []
        conflicts = []
        constraints = ["当前问题超出《资治通鉴》史实检索与历史映射分析范围"]

    state.problem_summary = _summarize_problem(text, scene_type)
    state.intent_type = intent_type
    state.routing_source = routing_source
    state.routing_confidence = routing_confidence
    state.routing_reason = routing_reason
    state.routing_model = routing_model
    state.scene_type = scene_type
    state.actors = actors
    state.conflicts = conflicts
    state.constraints = constraints
    state.emotion_labels = emotion_labels
    if intent_type in {"factual_lookup", "commentary_lookup"}:
        state.retrieval_queries = [text]
    state.situation_analysis = SituationAnalysis(
        overall_judgement=_overall_judgement(scene_type, conflicts, intent_type),
        core_conflicts=conflicts,
        actors=actors,
    )
    return state


def query_rewriter(state: AnalysisState, _: AgentContext) -> AnalysisState:
    queries = [state.user_input]
    rewritten = _rewrite_to_queries(state.user_input)
    if rewritten:
        queries.extend(rewritten)
    else:
        expanded = _expand_modern_terms(state.user_input)
        queries.extend(expanded)
    state.retrieval_queries = queries
    return state


def _expand_modern_terms(text: str) -> list[str]:
    expanded: list[str] = []
    seen_groups: set[int] = set()
    for index, (triggers, classical) in enumerate(MODERN_TO_CLASSICAL):
        if any(trigger in text for trigger in triggers):
            if index not in seen_groups:
                expanded.append(" ".join(classical))
                seen_groups.add(index)
    return expanded[:3]


_PATTERN_REWRITE_PROMPT = (
    "你是一个历史案例检索助手。用户会用口语化的方式描述一个职场或人际关系困境。"
    "请用不同的措辞把用户的问题重新表达3-5次，每次10-25字，用于检索相似的历史案例。"
    "\n要求："
    "\n1. 保持问题的具体性，不要过度抽象化"
    "\n2. 用书面语，可以用历史风格的词汇（如谗言、构陷、功高震主、外戚、同僚等）"
    "\n3. 每条表达侧重不同的关键词角度"
    "\n4. 不要给建议，只描述困境"
    "\n输出格式：每行一条，不要编号，不要其他内容"
    "\n\n示例输入：我带的新人抢了我的位置，老板还帮他说话"
    "\n示例输出："
    "\n新提拔的人取代了旧臣的位置"
    "\n上级偏袒新来的人，功劳被冒领"
    "\n老员工被新人架空，领导不主持公道"
    "\n功臣遭冷落，新人借势上位"
)


def _rewrite_to_queries(text: str) -> list[str]:
    import os

    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        return []

    try:
        from openai import OpenAI

        base_url = os.getenv("ZIZHI_ROUTER_BASE_URL", "https://api.deepseek.com").strip()
        model = os.getenv("ZIZHI_ROUTER_MODEL", "deepseek-chat").strip() or "deepseek-chat"
        timeout = float(os.getenv("ZIZHI_ROUTER_TIMEOUT_SECONDS", "15"))
        client = OpenAI(api_key=api_key, base_url=base_url, timeout=timeout)
        response = client.chat.completions.create(
            model=model,
            temperature=0.0,
            messages=[
                {"role": "system", "content": _PATTERN_REWRITE_PROMPT},
                {"role": "user", "content": text},
            ],
            max_tokens=200,
        )
        content = (response.choices[0].message.content or "").strip()
        if not content:
            return []
        queries = [line.strip() for line in content.split("\n") if line.strip() and len(line.strip()) >= 4]
        return queries[:5]
    except Exception:
        return []


def historical_retriever(state: AnalysisState, context: AgentContext) -> AnalysisState:
    if context.case_retriever is not None:
        state.case_matches = context.case_retriever.search(state.retrieval_queries, top_k=4)
        state.evidence_pool = context.case_retriever.expand_cases_to_chunks(state.case_matches, per_case_top_k=2, max_chunks=6)
        if state.case_matches:
            return state
    state.evidence_pool = context.retriever.search(state.retrieval_queries, top_k=4)
    return state


def factual_retriever(state: AnalysisState, context: AgentContext) -> AnalysisState:
    retriever = context.factual_retriever or context.retriever
    state.evidence_pool = retriever.search(state.retrieval_queries, top_k=4)
    return state


def commentary_retriever(state: AnalysisState, context: AgentContext) -> AnalysisState:
    if context.commentary_retriever is None:
        state.evidence_pool = []
        return state
    state.evidence_pool = context.commentary_retriever.search(state.retrieval_queries, top_k=4)
    return state


def strategy_mapper(state: AnalysisState, _: AgentContext) -> AnalysisState:
    scene = state.scene_type
    state.strategy_draft = _build_case_driven_strategy(state) if state.case_matches else _build_scene_strategy(scene, state.retry_count)
    state.historical_mirrors = _build_historical_mirrors(state)
    state.graph_draft = _build_mermaid(state)
    return state


def reflection_critic(state: AnalysisState, _: AgentContext) -> AnalysisState:
    notes: list[str] = []
    if not state.evidence_pool:
        notes.append("检索证据不足，需要保守表达历史映射。")
    if len(state.strategy_draft.next_actions_24h) < 2:
        notes.append("24 小时动作不足，需要补足可执行步骤。")
    if len(state.strategy_draft.do_not_do) < 2:
        notes.append("禁忌动作不足，需要降低空泛风险。")
    if not _is_mermaid_safe(state.graph_draft):
        notes.append("Mermaid 草稿可能不可渲染，已要求重写为 flowchart TD。")
        state.graph_draft = _fallback_mermaid(state)

    if any(mirror.confidence < 0.45 for mirror in state.historical_mirrors):
        notes.append("存在低置信度类比，最终输出需说明借鉴边界。")

    state.reflection_notes = notes
    state.reflection_passed = len([note for note in notes if "不足" in note or "不可渲染" in note]) == 0
    if not state.reflection_passed:
        state.retry_count += 1
    return state


def response_composer(state: AnalysisState, _: AgentContext) -> AnalysisState:
    emotion_detected = bool(state.emotion_labels)
    poetry = _poetry_comfort(state.emotion_labels) if emotion_detected else PoetryComfort(triggered=False)
    state.final_output = FinalOutput(
        user_problem=UserProblem(
            summary=state.problem_summary,
            scene_type=state.scene_type,
            emotion_detected=emotion_detected,
            emotion_labels=state.emotion_labels,
            confidence=0.78 if state.scene_type else 0.55,
        ),
        situation_analysis=state.situation_analysis,
        historical_mirrors=state.historical_mirrors,
        strategy_report=state.strategy_draft,
        mermaid_graph=state.graph_draft if _is_mermaid_safe(state.graph_draft) else _fallback_mermaid(state),
        poetry_comfort=poetry,
        evidence_citations=_build_citations(state),
    )
    return state


def _build_scene_strategy(scene_type: str, retry_count: int) -> StrategyReport:
    next_24h, next_7d = _next_actions(scene_type)
    return StrategyReport(
        strategy_template_version="zizhi_strategy_scene_v1.0",
        main_recommendation=_main_recommendation(scene_type, retry_count),
        strategy_options=_strategy_options(scene_type),
        do_not_do=_do_not_do(scene_type),
        next_actions_24h=next_24h,
        next_actions_7d=next_7d,
    )


def _build_case_driven_strategy(state: AnalysisState) -> StrategyReport:
    next_24h, next_7d = _case_next_actions(state)
    return StrategyReport(
        strategy_template_version="zizhi_strategy_case_v2.0",
        main_recommendation=_case_main_recommendation(state),
        strategy_options=_case_strategy_options(state),
        do_not_do=_case_do_not_do(state),
        next_actions_24h=next_24h,
        next_actions_7d=next_7d,
    )


def _case_main_recommendation(state: AnalysisState) -> str:
    prefix = "在证据有限的前提下，" if state.retry_count else ""
    primary = state.case_matches[0]
    secondary = state.case_matches[1] if len(state.case_matches) > 1 else None
    focus = _case_focus(primary)
    conflict = _case_problem_frame(state, primary)
    sentence = (
        f"优先把当前问题当成“{conflict}”来处理，行动主线放在「{focus}」，"
        "先做可验证、可回撤的小动作，再根据反馈决定是否升级。"
    )
    case_anchor = f"命中的首个案例「{primary.title}」给出的可迁移模式就是：{focus}。"
    if secondary is None:
        return prefix + sentence + case_anchor

    second_focus = _case_focus(secondary)
    compare = (
        f"同时，第二个命中案例「{secondary.title}」补充提示「{second_focus}」，"
        "说明这类问题通常不是靠一次表态解决，而是靠边界澄清、证据积累或秩序重建逐步推进。"
    )
    return prefix + sentence + case_anchor + compare


def _case_strategy_options(state: AnalysisState) -> list[StrategyOption]:
    primary = state.case_matches[0]
    primary_frame = _case_problem_frame(state, primary)
    options = [
        StrategyOption(
            name="按首个命中案例推进",
            applicable_when=f"你判断当前局面最接近「{primary_frame}」时",
            steps=[
                f"先把问题改写成一个结构判断：{primary_frame}",
                f"围绕「{_case_focus(primary)}」设计一次最小动作，优先验证边界、承诺、职责或协作规则，而不是先争论动机",
                "执行后记录谁响应、谁回避、哪些事实变化，再决定是否升级动作",
            ],
            risks=[
                "如果误判了案例结构，策略会显得过慢或过软",
                "如果只摘取历史结论、不回到现实证据，执行时会变成空泛表态",
            ],
        )
    ]

    if len(state.case_matches) > 1:
        secondary = state.case_matches[1]
        options.append(
            StrategyOption(
                name="用第二案例交叉校验",
                applicable_when=f"你怀疑问题不止一层，或首个案例只能解释部分症状时；第二案例主线是「{_case_focus(secondary)}」",
                steps=[
                    f"把「{primary.title}」与「{secondary.title}」并排比较，确认当前更像哪一种结构问题",
                    f"如果第二案例更贴近，就把动作重心转向「{_case_focus(secondary)}」对应的那条主线",
                    "保留一条可回撤路径，避免一次性押注在单一判断上",
                ],
                risks=[
                    "双案例并看会增加判断成本",
                    "如果没有明确优先级，容易把团队带入反复摇摆",
                ],
            )
        )

    fallback_options = _strategy_options(state.scene_type)
    for option in fallback_options:
        if len(options) >= 3:
            break
        if option.name not in {existing.name for existing in options}:
            options.append(option)
    return options


def _case_do_not_do(state: AnalysisState) -> list[str]:
    primary = state.case_matches[0]
    primary_frame = _case_problem_frame(state, primary)
    guardrails = [
        f"不要脱离命中案例的真实主线，只摘一句结论照搬；这次最关键的主线是「{_case_focus(primary)}」",
        "不要把结构问题重新说回成动机问题，尤其不要在证据不足时急着定义谁忠诚、谁恶意",
    ]
    if primary_frame:
        guardrails.append(f"不要绕开当前矛盾的核心结构：「{primary_frame}」")
    if len(state.case_matches) > 1:
        guardrails.append(f"不要忽略第二命中案例「{state.case_matches[1].title}」提供的反证或补充视角")
    guardrails.extend(_do_not_do(state.scene_type))
    return _unique_items(guardrails)[:5]


def _case_next_actions(state: AnalysisState) -> tuple[list[str], list[str]]:
    primary = state.case_matches[0]
    secondary = state.case_matches[1] if len(state.case_matches) > 1 else None
    core_issue = _case_problem_frame(state, primary)
    focus = _case_focus(primary)

    next_24h = [
        f"把当前问题先压缩成一句结构化判断：{core_issue}",
        f"围绕案例「{primary.title}」的主线「{focus}」，设计一个最小验证动作，优先验证边界、职责、承诺或协作接口",
        "把接下来需要确认的事实、相关人反馈和可回撤动作写成 3 列，避免边做边改口",
    ]
    if secondary is not None:
        next_24h.append(f"把第二命中案例「{secondary.title}」当作校验样本，检查自己有没有误判局势结构")

    next_7d = [
        f"完成一次围绕「{focus}」的小范围试探，并记录对方是否配合、拖延或反制",
        "根据试探反馈，判断问题更像边界失衡、信任坍塌、授权失控还是团队秩序冲突，再决定是否升级",
        "把有效动作沉淀成固定节奏，例如同步机制、规则清单、职责接口或阶段校验点",
    ]
    if secondary is not None:
        next_7d.append(f"复盘「{primary.title}」与「{secondary.title}」哪一个更贴近现实，再收敛为单一路径")

    return next_24h[:4], next_7d[:4]


def _case_focus(case) -> str:
    focus = case.transferable_pattern.strip() or case.core_conflict.strip() or case.summary.strip() or case.title.strip()
    return _brief_text(focus, 40)


def _case_problem_frame(state: AnalysisState, case) -> str:
    if state.conflicts:
        return _brief_text("、".join(state.conflicts), 26)
    if case.matched_terms:
        return _brief_text("、".join(case.matched_terms[:3]), 26)
    if case.case_tags:
        return _brief_text("、".join(case.case_tags[:3]), 26)
    if case.core_conflict.strip():
        return _brief_text(case.core_conflict, 26)
    return _brief_text(state.problem_summary or state.user_input, 26)


def _brief_text(text: str, limit: int) -> str:
    compact = re.sub(r"\s+", " ", text).strip("，。；;：: ")
    if len(compact) <= limit:
        return compact
    return f"{compact[: limit - 3]}..."


def _unique_items(items: list[str]) -> list[str]:
    unique: list[str] = []
    seen: set[str] = set()
    for item in items:
        cleaned = item.strip()
        if not cleaned or cleaned in seen:
            continue
        unique.append(cleaned)
        seen.add(cleaned)
    return unique


def factual_response_composer(state: AnalysisState, _: AgentContext) -> AnalysisState:
    answer = _build_lookup_answer(state, lookup_kind="factual")
    state.historical_mirrors = _build_lookup_mirrors(state)
    state.final_output = FinalOutput(
        user_problem=UserProblem(
            summary=state.problem_summary,
            scene_type=state.scene_type,
            emotion_detected=False,
            emotion_labels=[],
            confidence=0.9 if state.evidence_pool else 0.45,
        ),
        situation_analysis=SituationAnalysis(
            overall_judgement=answer,
            core_conflicts=[],
            actors=state.actors,
        ),
        historical_mirrors=state.historical_mirrors,
        strategy_report=StrategyReport(
            main_recommendation=answer,
            strategy_options=[],
            do_not_do=[],
            next_actions_24h=[],
            next_actions_7d=[],
        ),
        mermaid_graph=_fallback_mermaid(state),
        poetry_comfort=PoetryComfort(triggered=False),
        evidence_citations=_build_citations(state),
    )
    return state


def commentary_response_composer(state: AnalysisState, _: AgentContext) -> AnalysisState:
    answer = _build_lookup_answer(state, lookup_kind="commentary")
    state.historical_mirrors = _build_lookup_mirrors(state)
    state.final_output = FinalOutput(
        user_problem=UserProblem(
            summary=state.problem_summary,
            scene_type=state.scene_type,
            emotion_detected=False,
            emotion_labels=[],
            confidence=0.9 if state.evidence_pool else 0.45,
        ),
        situation_analysis=SituationAnalysis(
            overall_judgement=answer,
            core_conflicts=[],
            actors=state.actors,
        ),
        historical_mirrors=state.historical_mirrors,
        strategy_report=StrategyReport(
            main_recommendation=answer,
            strategy_options=[],
            do_not_do=[],
            next_actions_24h=[],
            next_actions_7d=[],
        ),
        mermaid_graph=_fallback_mermaid(state),
        poetry_comfort=PoetryComfort(triggered=False),
        evidence_citations=_build_citations(state),
    )
    return state


def out_of_scope_response_composer(state: AnalysisState, _: AgentContext) -> AnalysisState:
    answer = (
        "当前问题与《资治通鉴》史实检索、司马光评论查询、或基于历史映射的组织/管理分析关系不大，"
        "不建议走本系统的历史检索链路。请改用通用问答，或把问题改写成历史/管理相关版本。"
    )
    state.historical_mirrors = []
    state.final_output = FinalOutput(
        user_problem=UserProblem(
            summary=state.problem_summary,
            scene_type=state.scene_type,
            emotion_detected=False,
            emotion_labels=[],
            confidence=max(state.routing_confidence, 0.85 if state.routing_source == "llm" else 0.65),
        ),
        situation_analysis=SituationAnalysis(
            overall_judgement=answer,
            core_conflicts=[],
            actors=[],
        ),
        historical_mirrors=[],
        strategy_report=StrategyReport(
            main_recommendation="请提出与《资治通鉴》史实、司马光评论或现实管理映射相关的问题。",
            strategy_options=[],
            do_not_do=[],
            next_actions_24h=[],
            next_actions_7d=[],
        ),
        mermaid_graph=_fallback_mermaid(state),
        poetry_comfort=PoetryComfort(triggered=False),
        evidence_citations=[],
    )
    return state


def _pick_intent(text: str) -> str:
    compact = text.replace(" ", "").strip()
    if _looks_out_of_scope(compact):
        return "out_of_scope"
    if any(pattern in compact for pattern in COMMENTARY_PATTERNS):
        return "commentary_lookup"
    if any(hint in compact for hint in ANALYSIS_HINTS):
        return "analysis"
    if any(hint in compact for hint in FIRST_PERSON_HINTS):
        return "analysis"
    if any(keyword in compact for keyword in FACTUAL_LOOKUP_KEYWORDS):
        return "factual_lookup"
    if any(pattern in compact for pattern in FACTUAL_PATTERNS) and len(compact) <= 36:
        return "factual_lookup"
    return "analysis"


def _looks_out_of_scope(text: str) -> bool:
    if any(keyword in text for keyword in DOMAIN_HINTS):
        return False
    if any(keyword in text for keyword in OUT_OF_SCOPE_HINTS):
        return True
    generic_howto_hints = ["怎么做", "如何做", "教程", "步骤", "配方", "食谱", "推荐"]
    return any(hint in text for hint in generic_howto_hints)


def _resolve_intent(text: str, context: AgentContext) -> tuple[str, str, float, str, str]:
    rule_intent = _pick_intent(text)
    if context.intent_router is None:
        return rule_intent, "rule", 0.0, "未启用模型路由，使用规则判断。", ""

    try:
        decision = context.intent_router.route(text, rule_hint=rule_intent)
    except Exception as exc:
        return rule_intent, "rule_fallback", 0.0, f"模型路由失败，已回退规则：{type(exc).__name__}", context.intent_router.model

    if decision.confidence >= context.intent_router.confidence_threshold:
        return decision.intent_type, "llm", decision.confidence, decision.reason, context.intent_router.model

    return (
        rule_intent,
        "rule_fallback",
        decision.confidence,
        f"模型置信度不足，回退规则：{decision.reason}",
        context.intent_router.model,
    )


def _pick_scene(text: str) -> str:
    scores = []
    for scene, keywords in SCENE_KEYWORDS:
        score = sum(1 for keyword in keywords if keyword in text)
        scores.append((score, scene))
    scores.sort(reverse=True)
    return scores[0][1] if scores and scores[0][0] > 0 else "横向协作"


def _pick_emotions(text: str) -> list[str]:
    labels = []
    for label, keywords in EMOTION_KEYWORDS:
        if any(keyword in text for keyword in keywords):
            labels.append(label)
    return labels


def _extract_actors(text: str) -> list[Actor]:
    actors = [Actor(name="我", role="提问者", goal="降低风险并推进目标", risk="信息不足时容易被动表态")]
    mapping = [
        ("直属领导", ["直属领导", "领导", "上级"], "直接评价与资源分配者"),
        ("老板/更高层", ["老板", "高层", "大老板"], "更高层权力来源"),
        ("同事", ["同事", "跨部门"], "横向协作方"),
        ("下属/团队成员", ["下属", "团队", "核心成员"], "执行与组织稳定相关方"),
        ("合伙人", ["合伙人", "联合创始人"], "控制权与边界相关方"),
        ("外部客户/伙伴", ["客户", "供应商", "外部"], "外部压力来源"),
    ]
    for name, keywords, role in mapping:
        if any(keyword in text for keyword in keywords):
            actors.append(Actor(name=name, role=role, goal="维护自身利益与影响力", risk="可能误读信号或放大冲突"))
    return actors


def _extract_conflicts(text: str, scene_type: str) -> list[str]:
    conflicts_by_scene = {
        "向上管理": ["直接上级信任不足", "更高层关注带来越级嫌疑", "信息透明与自我保护之间的张力"],
        "横向协作": ["功劳与责任边界不清", "协作依赖与利益竞争并存"],
        "团队冲突": ["关键成员互相牵制", "业务依赖与团队秩序冲突"],
        "用人与授权": ["授权效率与失控风险冲突", "人情信任与岗位校验冲突"],
        "信任与猜忌": ["低信任环境下的信号误读", "自证清白与过度解释冲突"],
        "谗言与谣言": ["非正式渠道的信息攻击难以直接对质", "决策者偏听偏信导致误判", "受害者无法自证清白又无力对抗"],
        "嫉妒与背叛": ["旧交因地位差距产生嫉妒", "曾经的信任基础被利益侵蚀", "公开对抗会失去道德高地"],
        "站队与表态": ["信息优势与表态风险并存", "短期安全与长期信用冲突"],
        "合伙与控制权": ["沟通绕过带来权力边界变化", "信任合作与控制权防线冲突"],
        "去留与进退": ["继续投入与机会成本冲突", "沉没成本与风险止损冲突"],
        "组织变革": ["变革目标与既有利益结构冲突", "速度与稳定冲突"],
        "情绪恢复": ["高压消耗与理性判断冲突", "被认可需求与现实反馈冲突"],
    }
    conflicts = conflicts_by_scene.get(scene_type, ["目标不清与关系风险交织"])
    if "绕过" in text and "沟通链路被绕过" not in conflicts:
        conflicts.append("沟通链路被绕过")
    if "不信任" in text and "关键关系信任不足" not in conflicts:
        conflicts.append("关键关系信任不足")
    return conflicts[:4]


def _extract_constraints(text: str) -> list[str]:
    constraints = []
    if "不能" in text or "不想" in text:
        constraints.append("用户存在明确的行动禁区或顾虑")
    if "离不开" in text:
        constraints.append("相关角色短期内不可替代")
    if "不知道" in text or "该不该" in text:
        constraints.append("当前信息不足，需先验证再决策")
    return constraints or ["信息来自用户单方描述，需要保留假设边界"]


def _summarize_problem(text: str, scene_type: str) -> str:
    shortened = text.strip().replace("\n", " ")
    if len(shortened) > 90:
        shortened = f"{shortened[:87]}..."
    return f"这是一个偏「{scene_type}」的问题：{shortened}"


def _overall_judgement(scene_type: str, conflicts: list[str], intent_type: str = "analysis") -> str:
    if intent_type == "factual_lookup":
        return "当前问题更像客观事实查询，适合直接检索相关史实证据。"
    if intent_type == "commentary_lookup":
        return "当前问题更像史臣评论查询，适合优先检索司马光等观察者评论。"
    if intent_type == "out_of_scope":
        return "当前问题不在《资治通鉴》检索与历史映射分析的适用范围内。"
    if scene_type == "情绪恢复":
        return "当前重点不是立刻做重大决定，而是先降低情绪消耗，再把问题拆成可验证事实。"
    return f"当前局势的关键不是单点对错，而是处理「{conflicts[0]}」时避免让关系结构进一步失衡。"


def _main_recommendation(scene_type: str, retry_count: int) -> str:
    prefix = "在证据有限的前提下，" if retry_count else ""
    recommendations = {
        "向上管理": "采取“透明汇报 + 不抢解释权 + 留痕确认”的策略，让直属领导看到你没有绕开他，同时让更高层获得稳定信息。",
        "横向协作": "先把功劳、责任和交付边界写清楚，再用共同目标压低个人竞争。",
        "团队冲突": "不要急于站边，先把两人的不可替代能力拆开，再建立规则化协作与替补机制。",
        "用人与授权": "授权可以继续，但必须增加阶段性校验、责任边界和可撤回机制。",
        "信任与猜忌": "先停止情绪化自证，改用可验证的小承诺逐步重建可信度。",
        "谗言与谣言": "不要急着自证清白，先找到能绕过谗言来源的第三方信息验证渠道，用事实和成果说话，让决策者自己核实。",
        "嫉妒与背叛": "降低炫耀感，用低调和分享机会来缓解对方的嫉妒压力；如果对方已经翻脸，优先保护自己的核心利益而非试图修复关系。",
        "站队与表态": "不要抢先表态，优先维持事实中立、降低信息外泄风险，并观察权力格局是否明朗。",
        "合伙与控制权": "把绕过沟通视为边界信号，先谈规则而不是动机，尽快重建共同决策机制。",
        "去留与进退": "先做可逆动作和信息收集，不在情绪峰值做不可逆决定。",
        "组织变革": "先稳定关键利益相关方，再推进制度化调整，避免把变革变成个人对抗。",
        "情绪恢复": "先把自己从持续消耗中抽离出来，用最小行动恢复控制感，再处理关系策略。",
    }
    return prefix + recommendations.get(scene_type, "先澄清目标、角色与风险，再做低成本试探。")


def _strategy_options(scene_type: str) -> list[StrategyOption]:
    common_safe = StrategyOption(
        name="稳态推进",
        applicable_when="局势未明、关系仍需维持时",
        steps=["把事实、判断、请求分开表达", "优先做低风险沟通", "每次推进后留下简短记录"],
        risks=["节奏偏慢", "对方可能误以为你回避问题"],
    )
    options_by_scene = {
        "向上管理": [
            StrategyOption(
                name="双层透明",
                applicable_when="直属领导与更高层之间存在信息落差时",
                steps=["向直属领导同步老板关注的问题", "汇报时多用团队口径", "把关键结论抄送或会后确认"],
                risks=["处理不当会被理解成表演式透明"],
            ),
            common_safe,
        ],
        "团队冲突": [
            StrategyOption(
                name="拆能力、立规则",
                applicable_when="两名关键成员都不可替代时",
                steps=["列出两人的关键职责", "明确协作接口和冲突升级机制", "给双方设置共同交付指标"],
                risks=["短期内双方都可能觉得被约束"],
            ),
            common_safe,
        ],
        "谗言与谣言": [
            StrategyOption(
                name="第三方验证",
                applicable_when="有人通过非正式渠道向决策者传递关于你的负面信息时",
                steps=[
                    "不要直接对质谗言来源，先收集能证明自己工作成果的客观证据",
                    "找到决策者信任的第三方，通过正常工作汇报让事实自然呈现",
                    "如果决策者主动提起，用事实回应而非情绪化辩解",
                ],
                risks=["如果谗言来源有更高信任度，事实澄清可能不够"],
            ),
            common_safe,
        ],
        "嫉妒与背叛": [
            StrategyOption(
                name="降调共荣",
                applicable_when="旧交因你的成功而产生嫉妒，关系开始变质时",
                steps=[
                    "主动降低炫耀感，分享机会和资源给对方",
                    "找到双方都能受益的合作点，把零和博弈变成正和",
                    "如果对方已经翻脸，保护核心利益，不要试图用感情挽回",
                ],
                risks=["过度示弱可能被对方视为软弱可欺"],
            ),
            common_safe,
        ],
        "合伙与控制权": [
            StrategyOption(
                name="边界重申",
                applicable_when="合伙人开始绕过你影响团队时",
                steps=["约一次非指责式沟通", "讨论哪些事项必须共同决策", "把沟通边界写成团队规则"],
                risks=["对方若已有夺权意图，可能转入更隐蔽行动"],
            ),
            common_safe,
        ],
    }
    return options_by_scene.get(scene_type, [common_safe])


def _do_not_do(scene_type: str) -> list[str]:
    general = ["不要在信息不足时给对方贴动机标签", "不要用情绪化长消息争取理解"]
    specific = {
        "向上管理": ["不要越过直属领导邀功", "不要向老板抱怨直属领导"],
        "谗言与谣言": ["不要直接找谗言来源对质或报复", "不要在情绪激动时向决策者辩解", "不要试图用另一条谣言反击"],
        "嫉妒与背叛": ["不要公开炫耀成就刺激对方", "不要用旧情绑架对方接受现状", "不要试图用对抗方式证明自己更强"],
        "站队与表态": ["不要传播未经验证的信息", "不要用沉默伪装成承诺"],
        "合伙与控制权": ["不要私下拉人对抗合伙人", "不要把规则问题说成忠诚问题"],
        "团队冲突": ["不要简单二选一站边", "不要让冲突双方私下定义团队规则"],
    }
    return specific.get(scene_type, []) + general


def _next_actions(scene_type: str) -> tuple[list[str], list[str]]:
    next_24h = {
        "向上管理": ["整理最近三次关键沟通事实", "给直属领导发一次简短同步，说明老板关注点和你的后续动作", "避免单独评价直属领导"],
        "谗言与谣言": ["整理近期工作成果的客观证据（邮件、文档、数据）", "找一个决策者信任且与谗言无关的第三方，通过正常工作接触让事实自然呈现", "不要主动提起谣言，除非决策者先问"],
        "嫉妒与背叛": ["回忆近期是否有刺激对方的具体事件", "找一个双方都信任的中间人了解对方真实想法", "暂停一切可能被解读为炫耀的行为"],
        "团队冲突": ["分别访谈冲突双方，只问事实和交付阻碍", "列出双方共同依赖的任务", "暂停公开评价谁对谁错"],
        "合伙与控制权": ["记录被绕过的具体事项", "准备一次以规则为主题的沟通提纲", "观察团队是否收到相互矛盾的指令"],
    }.get(scene_type, ["写下已知事实、推测和未知问题", "选择一个最小可逆动作", "暂停不可逆表态"])
    next_7d = {
        "向上管理": ["形成固定同步机制", "让直属领导在关键汇报前先看到版本", "观察信任是否改善"],
        "谗言与谣言": ["通过持续稳定的工作输出建立不可替代性", "观察决策者态度是否因谗言而变化", "如果谣言持续，考虑找合适时机用事实做一次正式澄清"],
        "嫉妒与背叛": ["评估这段关系是否还有修复价值", "如果决定修复，创造一次低压力的共处机会", "如果决定疏远，逐步减少信息暴露面，保护核心资源"],
        "团队冲突": ["建立协作接口表", "设置共同目标与冲突升级规则", "培养至少一个备份人选"],
        "合伙与控制权": ["确认共同决策清单", "建立团队沟通规则", "评估是否需要股权或职责层面的正式约定"],
    }.get(scene_type, ["完成一次事实复盘", "做一次低风险沟通", "根据反馈决定是否升级策略"])
    return next_24h, next_7d


def _build_historical_mirrors(state: AnalysisState) -> list[HistoricalMirror]:
    if state.case_matches:
        return _build_case_mirrors(state)
    mirrors = []
    for chunk in state.evidence_pool[:3]:
        excerpt = _evidence_excerpt(chunk)
        mirrors.append(
            HistoricalMirror(
                title=chunk.chapter_title or chunk.chunk_id,
                source_type=chunk.chunk_type,
                excerpt=excerpt,
                mapping_reason=_mapping_reason(chunk, state.scene_type),
                confidence=min(0.95, 0.45 + chunk.score / 3),
            )
        )
    return mirrors


def _build_case_mirrors(state: AnalysisState) -> list[HistoricalMirror]:
    mirrors = []
    for case in state.case_matches[:3]:
        source_type = _case_source_type(case.chunk_ids, state.evidence_pool)
        excerpt = case.summary.strip() or case.transferable_pattern.strip() or case.title.strip()
        if len(excerpt) > 280:
            excerpt = f"{excerpt[:277]}..."
        mirrors.append(
            HistoricalMirror(
                title=case.title,
                source_type=source_type,
                excerpt=excerpt,
                mapping_reason=case.mapping_reason,
                confidence=min(0.95, 0.52 + case.retrieval_score),
            )
        )
    return mirrors


def _build_lookup_mirrors(state: AnalysisState) -> list[HistoricalMirror]:
    mirrors = []
    for chunk in state.evidence_pool[:4]:
        mirrors.append(
            HistoricalMirror(
                title=chunk.chapter_title or chunk.chunk_id,
                source_type=chunk.chunk_type,
                excerpt=_lookup_excerpt(chunk, state.user_input),
                mapping_reason="这是与当前查询最相关的直接史料证据。" if chunk.chunk_type != "commentary" else "这是与当前查询最相关的史臣评论证据。",
                confidence=min(0.95, 0.45 + chunk.score / 3),
            )
        )
    return mirrors


def _evidence_excerpt(chunk) -> str:
    text = chunk.white_text or chunk.retrieval_text or chunk.original_text or chunk.annotation_text
    text = text.replace("\n", " ").strip()
    if len(text) <= 280:
        return text
    return f"{text[:277]}..."


def _mapping_reason(chunk, scene_type: str) -> str:
    if scene_type in {"向上管理", "信任与猜忌"} and "信任" in chunk.topic_tags:
        return "该史例强调信任与承诺对组织秩序的作用，可用于判断低信任关系中的行动边界。"
    if scene_type == "谗言与谣言" and any(tag in chunk.topic_tags for tag in {"谗言", "谣言", "信任", "构陷"}):
        return "该史例涉及谗言、谣言或信任危机，可映射到现代职场中非正式渠道信息攻击的应对策略。"
    if scene_type == "嫉妒与背叛" and any(tag in chunk.topic_tags for tag in {"嫉妒", "功高震主", "背叛", "猜忌", "反目"}):
        return "该史例涉及旧交嫉妒或盟友反目，可映射到现代关系中因地位差距导致的信任瓦解。"
    if scene_type in {"合伙与控制权", "站队与表态"} and "联盟" in chunk.topic_tags:
        return "该史例体现联盟失衡与反噬风险，可提醒不要把短期优势误判为长期控制力。"
    if scene_type in {"团队冲突", "用人与授权"} and "用人" in chunk.topic_tags:
        return "该史例对应关键岗位、授权与问责问题，可映射到现代团队管理。"
    return "该史例与当前问题在权力关系、信任边界或行动时机上存在可借鉴的结构相似性，但不能机械套用。"


def _case_source_type(chunk_ids: list[str], evidence_pool) -> str:
    evidence_by_id = {chunk.chunk_id: chunk for chunk in evidence_pool}
    for chunk_id in chunk_ids:
        chunk = evidence_by_id.get(chunk_id)
        if chunk is not None:
            return chunk.chunk_type
    return "original"


def _build_lookup_answer(state: AnalysisState, lookup_kind: str) -> str:
    if not state.evidence_pool:
        if lookup_kind == "commentary":
            return "当前未检索到足以支持回答的司马光评论证据。"
        return "当前未检索到足以支持回答的直接史实证据。"

    top = state.evidence_pool[0]
    excerpt = _lookup_excerpt(top, state.user_input)
    if lookup_kind == "commentary":
        return f"根据当前检索，最相关的史臣评论来自“{top.chapter_title or top.chunk_id}”：{excerpt}"
    return f"根据当前检索，最相关的史实证据来自“{top.chapter_title or top.chunk_id}”：{excerpt}"


def _lookup_excerpt(chunk, query: str) -> str:
    text = (chunk.white_text or chunk.retrieval_text or chunk.original_text or chunk.annotation_text).strip()
    if not text:
        return ""

    sentences = [match.group(0).strip() for match in LOOKUP_SENTENCE_RE.finditer(text) if match.group(0).strip()]
    if not sentences:
        return _evidence_excerpt(chunk)

    for term in _extract_lookup_terms(query):
        for index, sentence in enumerate(sentences):
            if term not in sentence:
                continue
            window = sentences[max(0, index - 1) : min(len(sentences), index + 2)]
            excerpt = "".join(window).replace("\n", " ").strip()
            if len(excerpt) <= 280:
                return excerpt
            return f"{excerpt[:277]}..."
    return _evidence_excerpt(chunk)


def _extract_lookup_terms(query: str) -> list[str]:
    compact = query.replace(" ", "").strip()
    cleaned = compact
    for noise in sorted(LOOKUP_NOISE_TERMS, key=len, reverse=True):
        cleaned = cleaned.replace(noise, " ")
    cleaned = re.sub(r"[^\u4e00-\u9fffA-Za-z0-9_]+", " ", cleaned)

    terms: set[str] = set()
    for token in re.findall(r"[\u4e00-\u9fff]{2,12}|[A-Za-z0-9_]{2,}", cleaned):
        if re.fullmatch(r"[\u4e00-\u9fff]+", token):
            if 2 <= len(token) <= 4:
                terms.add(token)
            elif len(token) > 4:
                for size in range(2, min(4, len(token)) + 1):
                    for index in range(len(token) - size + 1):
                        terms.add(token[index : index + size])
        else:
            terms.add(token)
    return sorted(terms, key=len, reverse=True)


def _build_mermaid(state: AnalysisState) -> str:
    actor_nodes = state.actors[:6]
    lines = ["flowchart TD"]
    for index, actor in enumerate(actor_nodes):
        node_id = f"A{index}"
        safe_name = actor.name.replace('"', "")
        lines.append(f'  {node_id}["{safe_name}"]')
    if len(actor_nodes) == 1:
        lines.append('  A0 -->|"梳理事实"| A0')
    else:
        for index in range(1, len(actor_nodes)):
            relation = _relation_label(state.scene_type, index)
            lines.append(f'  A{index} -->|"{relation}"| A0')
        if len(actor_nodes) >= 3:
            lines.append('  A1 -.->|"制衡/影响"| A2')
    return "\n".join(lines)


def _relation_label(scene_type: str, index: int) -> str:
    if scene_type == "向上管理":
        return "评价/关注" if index == 1 else "关注/压力"
    if scene_type == "合伙与控制权":
        return "绕过/试探"
    if scene_type == "团队冲突":
        return "依赖/冲突"
    return "影响/压力"


def _is_mermaid_safe(graph: str) -> bool:
    if not graph.strip().startswith(("flowchart TD", "graph TD")):
        return False
    return "-->" in graph and "[" in graph and "]" in graph


def _fallback_mermaid(state: AnalysisState) -> str:
    return "\n".join(
        [
            "flowchart TD",
            '  A["我"]',
            '  B["关键相关方"]',
            '  C["压力来源"]',
            '  B -->|"影响/制衡"| A',
            '  C -->|"施压"| A',
        ]
    )


def _build_citations(state: AnalysisState) -> list[EvidenceCitation]:
    if state.case_matches and state.evidence_pool:
        case_by_chunk_id: dict[str, str] = {}
        for case in state.case_matches:
            for chunk_id in case.chunk_ids:
                case_by_chunk_id.setdefault(chunk_id, case.title)

        citations = []
        for chunk in state.evidence_pool[:6]:
            related_case_title = case_by_chunk_id.get(chunk.chunk_id, chunk.chapter_title or chunk.chunk_id)
            citations.append(
                EvidenceCitation(
                    title=chunk.chapter_title or chunk.chunk_id,
                    source_type=chunk.chunk_type,
                    quote=_evidence_excerpt(chunk),
                    mapping_reason=f"这是命中案例「{related_case_title}」对应的证据窗口，可用于回查白话史料细节。",
                    usage="support",
                    confidence=min(0.92, 0.48 + chunk.score),
                )
            )
        return citations

    citations = []
    for mirror in state.historical_mirrors:
        citations.append(
            EvidenceCitation(
                title=mirror.title,
                source_type=mirror.source_type,
                quote=mirror.excerpt,
                mapping_reason=mirror.mapping_reason,
                usage="support" if mirror.confidence >= 0.55 else "caution",
                confidence=mirror.confidence,
            )
        )
    return citations


def _poetry_comfort(labels: list[str]) -> PoetryComfort:
    if "疲惫" in labels or "压力" in labels:
        return PoetryComfort(
            triggered=True,
            poem="行到水穷处，坐看云起时。",
            explanation="这句适合提醒自己先停一停，把不可控的压力拆回可处理的下一步。",
        )
    if "委屈" in labels or "失落" in labels:
        return PoetryComfort(
            triggered=True,
            poem="莫愁前路无知己，天下谁人不识君。",
            explanation="这里不是劝你硬撑，而是提醒不要用一时评价否定自己的长期价值。",
        )
    if "迷茫" in labels or "焦虑" in labels:
        return PoetryComfort(
            triggered=True,
            poem="山重水复疑无路，柳暗花明又一村。",
            explanation="当前最重要的是保留选择，而不是在迷雾中仓促做最终判断。",
        )
    return PoetryComfort(triggered=False)
