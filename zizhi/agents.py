from __future__ import annotations

import re
from dataclasses import dataclass

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
    ("站队与表态", ["站队", "表态", "沉默", "内斗", "高层"]),
    ("合伙与控制权", ["合伙", "联合创始人", "控制权", "绕过我"]),
    ("去留与进退", ["离职", "留下", "去留", "进退", "跳槽"]),
    ("组织变革", ["变革", "调整", "改革", "重组"]),
    ("情绪恢复", ["累", "疲惫", "委屈", "焦虑", "失落", "迷茫"]),
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
    bridges = {
        "向上管理": ["君臣 进谏 取信 兼听 偏信", "直属上级 更高层 信任边界 越级风险"],
        "横向协作": ["同僚 协作 争功 制衡", "功劳归属 横向联盟"],
        "团队冲突": ["用人 制衡 两强相争 团队秩序", "核心成员 冲突 调停"],
        "用人与授权": ["授权 用人失察 责任边界", "关键岗位 信任 校验"],
        "信任与猜忌": ["取信 猜忌 试探 承诺", "低信任关系 风险控制"],
        "站队与表态": ["内斗 进退 时机 表态", "不偏不倚 保全证据"],
        "合伙与控制权": ["联盟 反噬 控制权 绕过", "合伙人 边界 授权"],
        "去留与进退": ["进退 时机 风险 最小代价", "去留 判断"],
        "组织变革": ["组织稳定 功臣安置 制度分工", "变革 阻力 秩序"],
        "情绪恢复": ["困厄 守正 节制 情绪恢复", "压力 疲惫 克制"],
    }
    state.retrieval_queries = [
        state.user_input,
        state.scene_type,
        *bridges.get(state.scene_type, []),
        f"假设这是一个{state.scene_type}问题，核心矛盾是{'、'.join(state.conflicts)}",
    ]
    return state


def historical_retriever(state: AnalysisState, context: AgentContext) -> AnalysisState:
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
    next_24h, next_7d = _next_actions(scene)
    state.strategy_draft = StrategyReport(
        main_recommendation=_main_recommendation(scene, state.retry_count),
        strategy_options=_strategy_options(scene),
        do_not_do=_do_not_do(scene),
        next_actions_24h=next_24h,
        next_actions_7d=next_7d,
    )
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
        "站队与表态": ["不要传播未经验证的信息", "不要用沉默伪装成承诺"],
        "合伙与控制权": ["不要私下拉人对抗合伙人", "不要把规则问题说成忠诚问题"],
        "团队冲突": ["不要简单二选一站边", "不要让冲突双方私下定义团队规则"],
    }
    return specific.get(scene_type, []) + general


def _next_actions(scene_type: str) -> tuple[list[str], list[str]]:
    next_24h = {
        "向上管理": ["整理最近三次关键沟通事实", "给直属领导发一次简短同步，说明老板关注点和你的后续动作", "避免单独评价直属领导"],
        "团队冲突": ["分别访谈冲突双方，只问事实和交付阻碍", "列出双方共同依赖的任务", "暂停公开评价谁对谁错"],
        "合伙与控制权": ["记录被绕过的具体事项", "准备一次以规则为主题的沟通提纲", "观察团队是否收到相互矛盾的指令"],
    }.get(scene_type, ["写下已知事实、推测和未知问题", "选择一个最小可逆动作", "暂停不可逆表态"])
    next_7d = {
        "向上管理": ["形成固定同步机制", "让直属领导在关键汇报前先看到版本", "观察信任是否改善"],
        "团队冲突": ["建立协作接口表", "设置共同目标与冲突升级规则", "培养至少一个备份人选"],
        "合伙与控制权": ["确认共同决策清单", "建立团队沟通规则", "评估是否需要股权或职责层面的正式约定"],
    }.get(scene_type, ["完成一次事实复盘", "做一次低风险沟通", "根据反馈决定是否升级策略"])
    return next_24h, next_7d


def _build_historical_mirrors(state: AnalysisState) -> list[HistoricalMirror]:
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
    if scene_type in {"合伙与控制权", "站队与表态"} and "联盟" in chunk.topic_tags:
        return "该史例体现联盟失衡与反噬风险，可提醒不要把短期优势误判为长期控制力。"
    if scene_type in {"团队冲突", "用人与授权"} and "用人" in chunk.topic_tags:
        return "该史例对应关键岗位、授权与问责问题，可映射到现代团队管理。"
    return "该史例与当前问题在权力关系、信任边界或行动时机上存在可借鉴的结构相似性，但不能机械套用。"


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
