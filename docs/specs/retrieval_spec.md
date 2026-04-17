# Retrieval Spec

## 1. 目标

从《资治通鉴》语料中召回对当前现实问题最相关的历史 section/chunk，为策略生成提供可解释证据。

## 2. 当前实现基线

当前代码位于 `zizhi/retrieval.py`，具备两条路径：

- 默认路径：关键词检索
- 可选路径：`LanceDB + SentenceTransformer`

现状特点：

- 默认不强依赖 embedding
- 若 LanceDB 初始化失败，自动降级到关键词检索
- 当前 `HistoricalChunk.text` 仍混合了白话、标题与部分原文

## 3. 正式检索目标

正式版本采用“白话优先 + 视角标签 + 史案拼装”的检索策略：

- 检索索引主文本：`retrieval_text`（白话文）
- 展示文本：通过 `section_key` 回查原文/白话对照
- 视角过滤：`user_perspective`
- 标签过滤：`event_labels/risk_labels/strategy_labels/modern_scenes`
- 元数据过滤：`volume/chapter/year/topic_tags/situation_tags`

## 4. 检索流程

### 4.1 查询理解

上游工作流需先生成：

- `problem_summary`
- `scene_type`
- `user_perspective`
- `perspective_confidence`
- `actors`
- `conflicts`
- `retrieval_queries`
- `event_labels`
- `risk_labels`
- `modern_scenes`

视角识别优先于标签匹配。若用户视角不明确，检索应使用 `unknown` 或多视角候选，而不是强行判定。

### 4.2 一级召回

一级召回建议至少支持两种方式：

- 稀疏召回：关键词 / BM25 类
- 稠密召回：embedding 向量检索
- 视角标签召回：匹配 `PerspectiveProfile`
- 史案召回：匹配 `CaseProfile`

V1.5 以前允许先保留“关键词优先、向量可选”的架构。

### 4.3 二级排序

二级排序的输入维度建议包括：

- 查询与白话文语义相似度
- `scene_type` 匹配度
- `user_perspective` 匹配度
- 视角下的事件/风险/策略标签命中度
- 历史角色/事件重叠度
- 证据 section 覆盖度
- `source_priority`

### 4.4 去重与聚合

返回结果前需做：

- 同 `section_key` 或同一 chunk 的去重
- 相邻 chunk 的适度聚合
- 同一 `case_id` 下的证据聚合
- 过高重复章节的抑制

### 4.5 跨卷史案拼装

当一个历史事件横跨多个年号或卷时，不应把它强行切成一个超长 chunk。

正式策略：

- chunk 保持局部可检索
- `CaseProfile` 负责组织跨 section / 跨卷事件链
- 检索先命中 seed chunk 或 perspective profile
- 再按 `case_id/section_keys/chunk_ids` 扩展上下文
- 最终返回一个 `EvidenceBundle`

`EvidenceBundle` 至少包含：

- `case_id`
- `matched_perspective`
- `matched_labels`
- `seed_chunk_ids`
- `expanded_chunk_ids`
- `section_keys`
- `case_summary`
- `mapping_reason`

## 5. top-k 建议

第一版默认建议：

- 一级召回：`12–20`
- 二级精排后保留：`4–6`
- 最终用于生成主回答的重点证据：`2–4`

## 6. 索引构建

### 6.1 最小可行实现

- 先用 JSONL/本地表构建 chunk 索引
- 若启用向量检索，则为 `retrieval_text` 生成向量
- 向量库可继续使用 LanceDB

### 6.2 embedding 原则

- 只对 `retrieval_text` 编码
- 不对整段原文重复编码
- 标签与元信息不并入主文本，而是单独存字段

## 7. 与工作流接口

检索层输入：

- `queries: list[str]`
- `user_perspective`
- `scene_type`
- `event_labels`
- `risk_labels`
- `modern_scenes`
- 可选过滤条件：`tags/volume range`

检索层输出：

- `chunk_id`
- `case_id`
- `section_keys`
- `retrieval_score`
- `retrieval_text`
- `matched_perspective`
- `matched_labels`
- 用于展示的 section 引用信息

## 8. 未来演进

建议分阶段升级：

- Phase 1：关键词 + 结构化过滤
- Phase 2：白话 embedding + LanceDB
- Phase 3：用户视角识别 + 视角标签召回
- Phase 4：CaseProfile 史案拼装
- Phase 5：加 reranker
- Phase 6：把“史例相似”与“策略可迁移性”分成双通道召回

## 9. 验收标准

- 默认无 embedding 时也可稳定工作
- 启用 embedding 后召回质量明显优于纯关键词
- 返回结果能解释“为什么命中”
- 返回结果能解释“为什么适合当前用户视角”
- 跨卷史案能通过 `CaseProfile` 拼装，而不是依赖超长 chunk
- 前端展示链路不因白话索引化而丢失原文内容
