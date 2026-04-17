# Chunking Spec

## 1. 目标

为检索系统生成高召回、可解释、长度适中的 chunk，并最大化白话文的语义承载能力。

## 2. 核心原则

- 检索理解以白话文为主，不以古文原文为主索引文本
- 古文原文不进入主检索文本窗口，只通过 `section_key` 关联展示
- chunk 不等于单段，也不等于整卷
- chunk 必须尊重历史上下文边界，不跨明显章节/年份乱拼

## 3. 原子单元

chunk 构建的原子单元是 `section`，不是 TXT 段落。

一个 `section` 至少包含：

- 一个稳定的 `section_key`
- 对应的 `white_text`
- 可选的 `original_text`
- 所属 `volume/chapter/year`

## 4. 分组边界

chunk 合并时必须遵守以下边界：

- 不跨 `volume_no`
- 尽量不跨 `chapter_title`
- 尽量不跨 `year_title`
- 不打散单个 section

允许的最小回退策略：

- 若 section 过短，可在同 `chapter_title + year_title` 内向后拼接
- 若某年下 section 太少，可在同章内做有限拼接
- 默认禁止跨卷拼接

## 5. 长度建议

第一版正式规则建议：

- 目标长度：白话文 `900–1400` 字
- 最小长度：约 `600` 字
- 最大长度：约 `1600` 字
- overlap：按 `section_key` 级重叠 `1–2` 个 section，而不是按固定字数硬切

原因：

- 当前每卷白话文平均约 `16,859` 字
- 单段常常过短，信息覆盖不足
- 直接把原文和白话一起塞进 chunk，会显著压缩白话有效上下文

## 6. 构建规则

### 6.1 标准合并

1. 读取同一 `chapter_title + year_title` 下的 section 序列
2. 以白话字数累积到目标长度区间
3. 保留组成该 chunk 的 `section_key` 列表
4. 生成一个独立的 `chunk_id`

### 6.2 超长 section

若单个 `section.white_text` 已超过最大长度：

- 允许在 section 内再按语义句群切分
- 子块必须继承同一个 `section_key`
- 需要新增 `sub_index`

### 6.3 超短 section

若多个连续 section 都很短：

- 优先向后合并
- 如已到边界，可向前补 1 个 section 做 overlap

## 7. 文本字段设计

正式 chunk 至少包含两套文本视图：

- `retrieval_text`：仅白话文，用于 embedding / keyword / rerank
- `display_payload`：返回前端时根据 `section_key` 回查原文与白话配对内容

不建议继续把以下内容全部揉进一个 `text` 字段：

- 白话文
- 古文原文
- 注释
- 标签
- 标题

应改为“主检索文本 + 结构化元数据”模式。

## 8. 输出字段

chunk 至少包含：

- `chunk_id`
- `section_keys`
- `volume_no`
- `volume_title`
- `chapter_title`
- `year_title`
- `retrieval_text`
- `white_char_count`
- `section_count`
- `chunk_version`

## 9. 当前实现

当前 TXT 语料构建已落地 `txt-white-section-aware-v1`：

- 构建入口：`zizhi/txt_ingest.py`
- 默认最小长度：`600` 字
- 目标区间：`900–1400` 字
- 硬上限：`1600` 字
- overlap：`1` 个 section
- 检索文本：`retrieval_text`，以白话文为主
- 古文原文：保留在 `original_text`，通过 `section_keys` 关联展示

最近一次全量构建结果：

- chunk 数：`5061`
- 平均白话长度：约 `1131` 字
- 中位数：约 `1281` 字
- `900–1400` 字 chunk：`3493`
- `1401–1600` 字 chunk：`521`

## 10. 验收标准

- chunk 平均长度稳定落在目标区间附近
- 单个查询返回的 chunk 能独立支撑历史情境理解
- 前端仍可用 `section_key` 完整展示原文与白话对照
- embedding 成本主要花在白话文，而非展示性原文
