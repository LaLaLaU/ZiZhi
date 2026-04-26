# Schema Spec

## 1. 目标

统一语料层、检索层、工作流状态层、前端返回层的数据结构，避免当前 Demo 中“一个模型承担太多职责”的问题。

## 2. 当前基线

当前主 Schema 位于 `zizhi/schemas.py`，核心对象包括：

- `HistoricalChunk`
- `AnalysisState`
- `FinalOutput`
- `StrategyReport`
- `HistoricalMirror`
- `EvidenceCitation`

问题在于：

- `HistoricalChunk` 同时承担 section、chunk、展示文本、检索文本多种职责
- 缺少正式的 `section_key` 字段
- 缺少白话检索文本与展示文本的分层定义

## 3. 正式模型分层

建议拆成六层模型。

### 3.1 SourceSection

表示文白配对后的最小单位。

必填字段：

- `section_key`
- `volume_no`
- `volume_title`
- `chapter_title`
- `year_title`
- `section_index`
- `original_text`
- `white_text`
- `pair_type`
- `source_file`

可选字段：

- `preamble`
- `people`
- `events`
- `topic_tags`
- `situation_tags`

### 3.2 RetrievalChunk

表示检索索引单元。

必填字段：

- `chunk_id`
- `section_keys`
- `retrieval_text`
- `volume_no`
- `volume_title`
- `chapter_title`
- `year_title`
- `white_char_count`
- `section_count`
- `chunk_version`

可选字段：

- `topic_tags`
- `situation_tags`
- `people`
- `events`
- `vector_id`

### 3.3 PerspectiveProfile

表示某个历史事实在特定视角下的解释。

必填字段：

- `perspective_type`
- `perspective_summary`
- `event_labels`
- `risk_labels`
- `strategy_labels`
- `modern_scenes`
- `evidence_section_keys`

字段说明：

- `perspective_type` 取值为 `manager/subordinate/peer/observer/unknown`
- `event_labels` 描述事实模式，例如 `架空/结盟/夺权`
- `risk_labels` 描述该视角承担的风险
- `strategy_labels` 描述该视角可采用的动作
- `modern_scenes` 用于连接现代用户问题

标签取值以 `perspective_tagging_spec.md` 的扩展标签池为准。扩展标签池只增加枚举候选，不改变字段类型；所有标签仍必须能追溯到 `evidence_section_keys`。

### 3.4 CaseProfile

表示一个可被检索和引用的历史事件链。

必填字段：

- `case_id`
- `title`
- `summary`
- `section_keys`
- `chunk_ids`
- `start_volume_no`
- `end_volume_no`
- `actors`
- `perspectives`

可选字段：

- `start_year`
- `end_year`
- `core_conflict`
- `case_tags`
- `source_priority`

说明：

- 一个 `CaseProfile` 可以跨 section、跨 year、跨 volume
- `perspectives` 是 `PerspectiveProfile` 列表
- 同一个 case 可以在不同视角下拥有不同标签
- `actors.role` 表达人物在案例结构中的现代可映射位置，不写成单纯古代官职

### 3.5 RetrievedEvidence

表示检索返回结果。

必填字段：

- `chunk_id`
- `case_id`
- `section_keys`
- `retrieval_score`
- `retrieval_text`
- `mapping_reason`
- `matched_perspective`

可选字段：

- `matched_tags`
- `display_sections`
- `matched_case_profile`

### 3.6 ConversationState

对应当前 `AnalysisState`，用于工作流节点之间传递。

保留并强化以下字段：

- `problem_summary`
- `intent_type`
- `scene_type`
- `actors`
- `conflicts`
- `constraints`
- `user_perspective`
- `target_role`
- `counterparty_role`
- `perspective_confidence`
- `emotion_labels`
- `retrieval_queries`
- `evidence_pool`
- `historical_mirrors`
- `strategy_draft`
- `reflection_notes`
- `reflection_passed`
- `retry_count`

## 4. 前端输出模型

最终返回给前端的结果应区分：

- 主报告文本
- 历史证据卡片
- 原文/白话对照展示
- Mermaid 图
- 情绪安抚模块

不建议只给前端一个大对象字符串拼接展示。

## 5. 兼容策略

短期内可以保留 `HistoricalChunk`，但应逐步迁移为：

- `SourceSection`
- `RetrievalChunk`
- `PerspectiveProfile`
- `CaseProfile`
- `RetrievedEvidence`

迁移期间要求：

- 新字段优先补齐 `section_key`
- `text` 字段只作为兼容字段，不再作为唯一真源
- 视角字段先允许为空，但正式检索上线前必须可追溯到 `evidence_section_keys`

## 6. 字段约束

- 所有主键字段必须稳定、可重建
- 空值优先用显式空字符串或空数组，不混用 `None`
- 所有展示性字段与检索性字段分开
- 所有模型应支持 JSON 序列化

## 7. 验收标准

- 语料入库、检索、回答生成三层边界清晰
- 任一前端证据卡片都能追溯到 `section_key`
- 任一视角标签都能追溯到 `evidence_section_keys`
- 迁移后不会再出现“为了展示把原文硬塞进检索文本”的结构性问题
