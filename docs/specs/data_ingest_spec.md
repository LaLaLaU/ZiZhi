# Data Ingest Spec

## 1. 目标

将《资治通鉴》文白对照 TXT 资源解析成可正式入库的结构化 section 数据，并为后续 chunking / retrieval 提供稳定输入。

## 2. 数据源

当前正式数据源为：

- 目录语料：`sources/资治通鉴txt版 中华书局2012年18册 沈志华 张宏儒 传世经典·文白对照`
- 全书原文索引：`sources/资治通鉴txt版 中华书局2012年18册 沈志华 张宏儒 传世经典·文白对照/资治通鉴整书原文.txt`

辅助脚本：

- `scripts/build_corpus.py`
- `scripts/analyze_txt_corpus.py`
- `zizhi/txt_ingest.py`

## 3. 入库目标层级

正式入库分为两层：

- `section` 层：文白配对后的最小语义单元
- `chunk` 层：由多个 `section` 组合后的检索单元

禁止直接把原始 TXT 段落当作最终检索单元入库。

## 4. section 解析规则

### 4.1 元信息识别

每卷解析时需识别：

- `volume_no`
- `volume_title`
- `chapter_title`
- `year_title`
- `section_index`
- `section_key`

标题识别优先级：

- 卷标题
- 前导说明/序信息
- 纪/帝/王相关章节标题
- 年标题
- 正文段落

### 4.2 正文识别

正文分两类：

- 古文原文
- 白话文解释

允许出现以下异常情况：

- 有编号段
- 无编号段
- 同一行同时包含原文和白话
- 标题误混入正文
- OCR/复制造成的前缀污染

### 4.3 文白配对规则

正式规则采用“整书原文索引 + 本卷局部规则”的组合方式：

1. 先从 `资治通鉴整书原文.txt` 建立分卷原文索引
2. 若某段落命中原文索引，则判定为原文
3. 同 section 下紧随其后的解释性段落，判定为白话文
4. 若同一行混合原文与白话，则先拆分再归类
5. 若无编号，则允许生成 `u###` 型 synthetic section

### 4.4 清洗规则

需清理以下内容：

- 水印
- 超长分隔符
- HTML 标签
- 异常前缀
- 纯元信息白话段

人工规则层由以下文件承载：

- `zizhi/manual_cleanup_rules.py`
- `zizhi/manual_rule_table.json`

## 5. 当前数据快照

基于 `.cache/zizhi_txt_white_lengths.csv` 的最近一次分析：

- 总卷数：`294`
- 白话文总字数：`4,956,659`
- 原文字数：`2,994,391`
- 已配对 section：`21,257`
- `original_only`：`40`
- `white_only`：`143`
- 当前文白配对率：约 `99.15%`

说明：

- 该比例表示绝大多数 section 已完成文白对应
- 剩余异常 section 需继续通过规则表清洗，而不是在查询阶段临时兜底

## 6. 正式入库产物

正式入库应输出两类文件或表：

- `sections`：文白配对后的 section 级数据
- `chunks`：供检索使用的白话文 chunk 数据

section 级至少包含：

- `section_key`
- `volume_no`
- `volume_title`
- `chapter_title`
- `year_title`
- `original_text`
- `white_text`
- `pair_type`
- `source_file`

## 7. 失败处理

遇到以下情况时不应静默吞掉：

- 某卷完全无法解码
- 某卷标题层级错乱
- 原文索引与分卷明显错位
- 异常 section 数量突然飙升

必须产出：

- 卷级统计
- 异常 section 清单
- 可回放的清洗规则记录

## 8. 验收标准

- 每卷都能产出可追溯的 section 列表
- `section_key` 在全库唯一且稳定
- 文白配对率长期保持在高位
- 剩余异常项可通过规则表持续收敛
- 下游 chunking 不再依赖原始 TXT 的临时判断
