from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


SourceType = Literal["original", "chen_guang_yue", "commentary"]
EvidenceUsage = Literal["support", "contrast", "caution"]
PerspectiveType = Literal["manager", "subordinate", "peer", "observer", "unknown"]
CaseType = Literal["decision", "relationship", "risk", "governance", "negotiation", "mixed"]


class Actor(BaseModel):
    name: str
    role: str = ""
    stance: str = ""
    goal: str = ""
    risk: str = ""


class HistoricalChunk(BaseModel):
    chunk_id: str
    book: str = "资治通鉴"
    volume_no: int | None = None
    volume: str = ""
    dynasty: str = ""
    year: str = ""
    chapter_title: str = ""
    chunk_type: SourceType
    section_key: str = ""
    section_keys: list[str] = Field(default_factory=list)
    retrieval_text: str = ""
    white_char_count: int = 0
    section_count: int = 0
    chunk_version: str = ""
    white_text: str = ""
    original_text: str = ""
    annotation_text: str = ""
    text: str
    people: list[str] = Field(default_factory=list)
    events: list[str] = Field(default_factory=list)
    topic_tags: list[str] = Field(default_factory=list)
    situation_tags: list[str] = Field(default_factory=list)
    source_priority: float = 0.5
    score: float = 0.0


class UserProblem(BaseModel):
    summary: str = ""
    scene_type: str = ""
    emotion_detected: bool = False
    emotion_labels: list[str] = Field(default_factory=list)
    confidence: float = 0.0


class SituationAnalysis(BaseModel):
    overall_judgement: str = ""
    core_conflicts: list[str] = Field(default_factory=list)
    actors: list[Actor] = Field(default_factory=list)


class HistoricalMirror(BaseModel):
    title: str
    source_type: SourceType
    excerpt: str
    mapping_reason: str
    confidence: float = 0.0


class PerspectiveProfile(BaseModel):
    perspective_type: PerspectiveType = "unknown"
    perspective_summary: str = ""
    event_labels: list[str] = Field(default_factory=list)
    risk_labels: list[str] = Field(default_factory=list)
    strategy_labels: list[str] = Field(default_factory=list)
    modern_scenes: list[str] = Field(default_factory=list)
    evidence_section_keys: list[str] = Field(default_factory=list)
    confidence: float = 0.0


class CaseProfile(BaseModel):
    case_id: str
    title: str
    summary: str = ""
    case_type: CaseType = "mixed"
    section_keys: list[str] = Field(default_factory=list)
    chunk_ids: list[str] = Field(default_factory=list)
    start_volume_no: int | None = None
    end_volume_no: int | None = None
    start_year: str = ""
    end_year: str = ""
    actors: list[Actor] = Field(default_factory=list)
    perspectives: list[PerspectiveProfile] = Field(default_factory=list)
    decision_actor: str = ""
    core_conflict: str = ""
    trigger: str = ""
    outcome: str = ""
    transferable_pattern: str = ""
    case_tags: list[str] = Field(default_factory=list)
    source_priority: float = 0.5
    case_worthy_score: float = 0.0


class RetrievedCase(BaseModel):
    case_id: str
    title: str
    summary: str = ""
    case_type: CaseType = "mixed"
    section_keys: list[str] = Field(default_factory=list)
    chunk_ids: list[str] = Field(default_factory=list)
    decision_actor: str = ""
    core_conflict: str = ""
    transferable_pattern: str = ""
    case_tags: list[str] = Field(default_factory=list)
    actor_roles: list[str] = Field(default_factory=list)
    retrieval_score: float = 0.0
    retrieval_text: str = ""
    matched_terms: list[str] = Field(default_factory=list)
    matched_fields: list[str] = Field(default_factory=list)
    mapping_reason: str = ""
    source_priority: float = 0.0


class StrategyOption(BaseModel):
    name: str
    applicable_when: str
    steps: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)


class StrategyReport(BaseModel):
    strategy_template_version: str = "zizhi_strategy_v1.0"
    main_recommendation: str = ""
    strategy_options: list[StrategyOption] = Field(default_factory=list)
    do_not_do: list[str] = Field(default_factory=list)
    next_actions_24h: list[str] = Field(default_factory=list)
    next_actions_7d: list[str] = Field(default_factory=list)


class PoetryComfort(BaseModel):
    triggered: bool = False
    poem: str = ""
    explanation: str = ""


class EvidenceCitation(BaseModel):
    title: str
    source_type: SourceType
    quote: str
    mapping_reason: str
    usage: EvidenceUsage = "support"
    confidence: float = 0.0


class FinalOutput(BaseModel):
    template_version: str = "zizhi_output_v1.0"
    user_problem: UserProblem
    situation_analysis: SituationAnalysis
    historical_mirrors: list[HistoricalMirror] = Field(default_factory=list)
    strategy_report: StrategyReport
    mermaid_graph: str
    poetry_comfort: PoetryComfort
    evidence_citations: list[EvidenceCitation] = Field(default_factory=list)


class AnalysisState(BaseModel):
    user_input: str
    problem_summary: str = ""
    intent_type: str = ""
    routing_source: str = ""
    routing_confidence: float = 0.0
    routing_reason: str = ""
    routing_model: str = ""
    scene_type: str = ""
    actors: list[Actor] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    emotion_labels: list[str] = Field(default_factory=list)
    retrieval_queries: list[str] = Field(default_factory=list)
    case_matches: list[RetrievedCase] = Field(default_factory=list)
    evidence_pool: list[HistoricalChunk] = Field(default_factory=list)
    situation_analysis: SituationAnalysis = Field(default_factory=SituationAnalysis)
    historical_mirrors: list[HistoricalMirror] = Field(default_factory=list)
    strategy_draft: StrategyReport = Field(default_factory=StrategyReport)
    graph_draft: str = ""
    reflection_notes: list[str] = Field(default_factory=list)
    reflection_passed: bool = False
    retry_count: int = 0
    final_output: FinalOutput | None = None
