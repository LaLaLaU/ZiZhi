# 资智 ZiZhi V1

基于《资治通鉴》的本地 Streamlit Demo：输入现实组织/职场困局，系统经过多 Agent 工作流完成问题理解、检索、历史映射、反思审校与结构化输出。

## 当前实现

- Streamlit 本地页面：自由文本输入、执行状态、报告/图谱/证据/诗词分区展示。
- 多 Agent 工作流：理解、改写、检索、策略映射、反思、汇总。
- Pydantic 结构化输出：状态、证据、最终输出均有 Schema 约束。
- 检索兜底：默认使用内置小型种子语料和关键词检索，可选 LanceDB + bge-m3。
- 反思回路：审校不通过时最多回到策略映射节点重试一次。
- 情绪旁路：命中压力、委屈、迷茫、疲惫等标签时追加克制诗词抚慰。

## 快速开始

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

默认不依赖外部模型，适合先跑通 Demo 流程。

## 可选：启用模型做意图路由

项目现在支持“规则路由 + 模型路由 + 失败回退规则”的混合模式。

只要系统环境里存在对应供应商的 API key，工作流初始化时会自动尝试启用路由模型；若请求失败或置信度不足，会自动回退到本地规则判断。

DeepSeek 示例：

```powershell
$env:DEEPSEEK_API_KEY="***"
$env:ZIZHI_ROUTER_ENABLED="1"
$env:ZIZHI_ROUTER_PROVIDER="deepseek"
$env:ZIZHI_ROUTER_MODEL="deepseek-chat"
$env:ZIZHI_ROUTER_BASE_URL="https://api.deepseek.com"
$env:ZIZHI_ROUTER_CONFIDENCE_THRESHOLD="0.72"
$env:ZIZHI_ROUTER_TIMEOUT_SECONDS="20"
```

火山方舟示例：

```powershell
$env:ARK_API_KEY="***"
$env:ZIZHI_ROUTER_ENABLED="1"
$env:ZIZHI_ROUTER_PROVIDER="ark"
$env:ZIZHI_ROUTER_MODEL="doubao-seed-2-0-mini-260215"
$env:ZIZHI_ROUTER_BASE_URL="https://ark.cn-beijing.volces.com/api/v3"
$env:ZIZHI_ROUTER_CONFIDENCE_THRESHOLD="0.72"
$env:ZIZHI_ROUTER_TIMEOUT_SECONDS="20"
```

说明：

- `DEEPSEEK_API_KEY`：推荐直接配置为系统环境变量，不要写进代码。
- `ARK_API_KEY`：火山方舟 API key，推荐直接配置为系统环境变量，不要写进代码。
- `ZIZHI_ROUTER_CONFIDENCE_THRESHOLD`：低于该值时，模型结果不会直接采用，而是回退规则路由。
- 目前路由只做三分类：`factual_lookup`、`commentary_lookup`、`analysis`。

## 本地书籍资源

- 当前正式语料使用 `sources/资治通鉴txt版 中华书局2012年18册 沈志华 张宏儒 传世经典·文白对照`。
- 语料构建会按 section 聚合成白话文检索 chunk，结果缓存为 `.cache/zizhi_corpus_chunks.jsonl`。
- 如果 `.cache/zizhi_corpus_chunks.jsonl` 存在，应用默认优先加载该缓存；否则回退到内置种子语料。
- 如需接入新的 EPUB 或 TXT 目录，可通过 `ZIZHI_CORPUS_PATH` 指定路径。

可手动重建语料：

```powershell
python scripts/build_corpus.py
```

可从白话汇总文件切分离线标注输入：

```powershell
python scripts/build_tagging_chunks.py
```

默认读取 `.cache/zizhi_white_corpus.txt`，输出：

- `.cache/zizhi_tagging_chunks.jsonl`：客观史实 chunk，含 `commentary_ids`
- `.cache/zizhi_simaguang_commentaries.jsonl`：单独抽离的司马光评论，通过 `commentary_id` / `linked_chunk_ids` 与事实 chunk 关联

如需指定其他资源：

```powershell
$env:ZIZHI_CORPUS_PATH="sources\新的资治通鉴资源.epub"
python scripts/build_corpus.py
```

## 可选：启用 LanceDB + bge-m3

```powershell
$env:ZIZHI_ENABLE_LANCEDB="1"
$env:ZIZHI_EMBEDDING_MODEL="BAAI/bge-m3"
streamlit run app.py
```

首次加载 bge-m3 可能需要下载模型。若模型或 LanceDB 不可用，系统会自动降级到内存关键词检索。

## 目录

- `app.py`：Streamlit 入口。
- `zizhi/schemas.py`：Pydantic 数据结构。
- `zizhi/corpus.py`：内置种子语料与 JSONL 加载。
- `zizhi/retrieval.py`：检索实现，支持 LanceDB 降级。
- `zizhi/agents.py`：六类 Agent 节点逻辑。
- `zizhi/tagging_prompt.py`：《资治通鉴》结构化标注 prompt 模板加载与渲染。
- `zizhi/workflow.py`：LangGraph 编排与手动兜底执行。
- `zizhi/rendering.py`：Markdown 与 Mermaid 前端渲染辅助。
- `prompts/`：结构化标注的 system/user prompt 与候选标签池。

## Specs

- `docs/specs/README.md`：规格文档索引。
- `docs/specs/product_spec.md`：产品规格。
- `docs/specs/data_ingest_spec.md`：数据清洗与正式入库规格。
- `docs/specs/chunking_spec.md`：chunk 切分规格。
- `docs/specs/retrieval_spec.md`：检索规格。
- `docs/specs/schema_spec.md`：数据结构规格。
- `docs/specs/perspective_tagging_spec.md`：视角标签与史案多视角映射规格。
- `docs/specs/answer_generation_spec.md`：回答生成规格。
