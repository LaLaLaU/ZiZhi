# Case Profile Spec

## 1. 目标

在长度受控的 `RetrievalChunk` 之上，新增一层按故事线与决策困境组织的 `CaseProfile`。

这层不替代原有 chunk，而是解决以下问题：

- 长度 chunk 适合检索，不一定适合现实映射
- 一个 chunk 内可能并列多个史事，难以直接形成管理启发
- 用户真正需要的不是“这一段讲了什么”，而是“这里有没有一个可迁移的案例”

这意味着在正式产品中：

- `case` 是主入库单元
- `chunk` 是原料与证据单元

## 2. 分层原则

正式语料分三层：

- `SourceSection`：最小可追溯文白单元
- `RetrievalChunk`：按长度控制的检索窗口
- `CaseProfile`：按故事线、决策链、关系结构组织的案例层

原则：

- `chunk` 继续服务原料供给、召回与展示
- `case` 专门服务现实问题映射与用户消费
- 一个 chunk 可生成 0 到多个 case
- 一个 case 可覆盖 1 到多个 section

## 3. 什么是 Case-Worthy

只有满足以下条件的史料片段才应进入 `CaseProfile`：

1. 存在一个主问题
2. 能识别主要决策者或主要承压者
3. 有相对清晰的因果链
4. 能提炼出可迁移的结构冲突
5. 能产出一句现代启发

若只是编年事实堆叠、并列史事罗列、无明显决策链，则不生成 case。

## 4. 输入来源

正式要求下，CaseProfile 的输入来源是：

- `.cache/zizhi_tagging_chunks.jsonl`

主输入字段：

- `tagging_chunks` 提供 section 顺序与白话文本
- `section_keys` 提供可追溯边界
- `white_text` 提供主要语义材料
- `volume/chapter/year` 提供上下文位置

## 5. 构建策略

### 5.1 候选切分

候选 case 不是按字数切，而是按故事线与冲突变化切。

具体规则：

- 先按 `section_key` 顺序读取 chunk 内的 section 序列
- 识别其中的主要角色、关键动作、冲突转折、结果落点
- 当故事主线、决策者或冲突结构发生明显切换时，视为新的 case 候选
- 每个候选仍需保留最小可追溯的 `section_keys`

这样可以把同一个长度 chunk 中并列的多条故事线拆开，而不依赖任何中间标注层先做视角切分。

### 5.2 候选聚合

若多个故事片段实际指向同一决策链，应合并为一个 case 候选。

合并后的 case 至少保留：

- `section_keys`
- `decision_actor`
- `core_conflict`
- `transferable_pattern`

### 5.3 Case-Worthy 评分

第一版使用规则评分，不依赖额外模型。

评分维度包括：

- 聚焦度：section 数是否足够小
- 决策信号：文本里是否出现“劝、议、请、让位、赴约、任命”等动作
- 是否存在可识别的主导者/承压者
- 是否能提炼出现代迁移句

低于阈值的候选写入 diagnostics，但不进入正式 case 输出。

## 6. 输出字段

`CaseProfile` 至少包含：

- `case_id`
- `title`
- `summary`
- `case_type`
- `section_keys`
- `chunk_ids`
- `actors`
- `perspectives`
- `decision_actor`
- `core_conflict`
- `trigger`
- `outcome`
- `transferable_pattern`
- `case_tags`
- `case_worthy_score`

`actors.role` 保留，但不作为古代官职字段使用。它应写成现代可映射的结构角色，例如 `最高决策者/组织负责人`、`策略建议者/说服者`、`一线负责人/关键执行者`、`关键接班人/承压者`、`内部追随者/声誉压力来源`。古代身份若需要保留，应放在 `stance` 或证据文本中自然呈现，不要让 `role` 只停留在 `君主/相国/大将/门客`。

## 7. 当前脚本

当前主脚本：

- `scripts/batch_extract_case_profiles.py`
- `scripts/render_case_prompt.py`

正式要求：

- 主生产链直接从 `tagging_chunks` 抽取 `case_profiles`

## 8. 直接 LLM 抽取

正式主链推荐由 LLM 直接从 chunk 抽取 case。

相关文件：

- `zizhi/case_profile_prompt.py`
- `prompts/case_extraction_system_prompt_v1.txt`
- `prompts/case_extraction_user_prompt_v1.txt`
- `scripts/render_case_prompt.py`
- `scripts/batch_extract_case_profiles.py`

正式输入：

- `tagging_chunks`

正式输出：

- `case_profiles.jsonl`
- `chunk_case_outputs.jsonl`
- `raw_responses.jsonl`

目标：

- 让模型直接判断是否存在 case-worthy 主线
- 允许输出 0 个 case
- 让模型在一个 chunk 中只保留 1 到 3 条最值得入库的案例

## 9. 使用建议

推荐顺序：

1. 优先直接从 `chunk -> case` 抽取主案例库
2. 对重点 chunk 做人工抽检与去重合并
3. 通过人工反馈继续收紧 prompt、阈值与 merge 规则

## 10. 去重与合并

当以下情况出现时，应优先考虑合并而不是保留两条 case：

- 两条 case 共享同一 `section_keys`
- 标题不同，但 `decision_actor + core_conflict + outcome` 基本一致
- 相邻 chunk 因 overlap 重复抽到同一故事
- 一条只讲“前因”，另一条只讲“爆发”，但现代启发本质属于同一决策链

建议后续单独增加：

- `deduped_case_profiles.jsonl`
- `merged_case_profiles.jsonl`

其中：

- `deduped` 解决同案多抽
- `merged` 解决跨 chunk 长故事拼装

## 11. 验收标准

- 一个长度 chunk 可以拆成多个故事 case
- case 结果仍能追溯到 `section_keys`
- diagnostics 可以解释为什么某些候选没有入库
- 对多线并列 chunk，不再强迫输出单个笼统结论
- overlap 导致的同案多抽可以被后处理识别
