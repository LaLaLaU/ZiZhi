# 资智 ZiZhi V1

基于《资治通鉴》的本地分析 Demo 与离线案例构建工具链。

当前项目已经形成两层能力：

- 产品层：把《资治通鉴》逐步整理成可借鉴的历史案例库
- 基础设施层：用 chunk、检索与原文回查为案例提供证据

一句话说，`chunk / retrieval` 负责把材料找回来，`case profile` 负责把材料变成今天还能用的案例。

## 项目北极星

项目最终目标不是“做一个古文向量检索器”，而是“做一个基于《资治通鉴》的历史案例库”。

这意味着：

- 用户最终消费的主单元应该是 `case`，不是 `chunk`
- `chunk` 是检索窗口与证据容器，不是最终产品形态
- 向量检索、关键词检索、白话召回都只是底层能力，不是项目本身
- 好坏标准应优先看“是否形成可迁移案例”，再看“召回是否准确”

## 当前实现

- Streamlit 本地页面：自由文本输入、执行状态、报告/图谱/证据/诗词分区展示。
- 多 Agent 工作流：理解、改写、检索、历史映射、反思、汇总。
- Pydantic 结构化输出：状态、证据、最终输出均有 Schema 约束。
- 检索兜底：默认使用内置小型种子语料和关键词检索，可选 LanceDB + bge-m3。
- 反思回路：审校不通过时最多回到策略映射节点重试一次。
- 情绪旁路：命中压力、委屈、迷茫、疲惫等标签时追加克制诗词抚慰。
- 离线案例层：正式方向改为从“离线 case 源 chunk”直接构建 `case profile` 历史案例库。

## 快速开始

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

默认不依赖外部模型，适合先跑通本地 Demo 流程。

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

## 本地书籍资源与案例流水线

- 当前正式语料使用 `sources/资治通鉴txt版 中华书局2012年18册 沈志华 张宏儒 传世经典·文白对照`。
- 语料构建会按 section 聚合成白话文检索 chunk，结果缓存为 `.cache/zizhi_corpus_chunks.jsonl`。
- 如果 `.cache/zizhi_corpus_chunks.jsonl` 存在，应用默认优先加载该缓存；否则回退到内置种子语料。
- 如需接入新的 EPUB 或 TXT 目录，可通过 `ZIZHI_CORPUS_PATH` 指定路径。

可手动重建语料：

```powershell
python scripts/build_corpus.py
```

可从白话汇总文件切分离线 case 源 chunk：

```powershell
python scripts/build_tagging_chunks.py
```

默认读取 `.cache/zizhi_white_corpus.txt`，输出：

- `.cache/zizhi_tagging_chunks.jsonl`：离线 case 源 chunk，文件名沿用历史命名，含 `commentary_ids`
- `.cache/zizhi_simaguang_commentaries.jsonl`：单独抽离的司马光评论，通过 `commentary_id` / `linked_chunk_ids` 与事实 chunk 关联

这里的 `.cache/zizhi_tagging_chunks.jsonl` 虽然文件名保留了 `tagging`，但当前语义只是“离线 case 原料”，不是旧 annotation 流程的继续延伸，也不是最终面向用户的知识单元。

如需把某个 chunk 渲染成案例抽取 prompt，便于复制到网页模型测试：

```powershell
python scripts/render_case_prompt.py --chunk-id tagging-v001-c00002-p02
```

也可以按 JSONL 行号取第 N 条：

```powershell
python scripts/render_case_prompt.py --index 2
```

如需用云端 OpenAI 兼容模型直接批量抽取 case，可先 dry-run 生成集中输出目录和样例 prompt：

```powershell
python scripts/batch_extract_case_profiles.py --provider openai --model gpt-5.4-mini --limit 2
```

确认 prompt 后加 `--execute` 才会真正调用模型：

```powershell
$env:OPENAI_API_KEY="***"
python scripts/batch_extract_case_profiles.py --provider openai --model gpt-5.4-mini --limit 10 --execute
```

火山方舟、DeepSeek 或自定义 OpenAI 兼容地址也可使用同一个脚本：

```powershell
$env:ARK_API_KEY="***"
python scripts/batch_extract_case_profiles.py --provider ark --model doubao-seed-2-0-mini-260215 --limit 10 --execute

$env:DEEPSEEK_API_KEY="***"
python scripts/batch_extract_case_profiles.py --provider deepseek --model deepseek-chat --limit 10 --execute

python scripts/batch_extract_case_profiles.py --provider custom --api-key-env MY_API_KEY --base-url https://example.com/v1 --model your-model --limit 10 --execute
```

默认会在 `.cache/case_runs/<run-name>/` 下输出：

- `case_profiles.jsonl`：通过阈值的正式案例
- `chunk_case_outputs.jsonl`：每个 chunk 的 case 返回数量与接收数量
- `raw_responses.jsonl`：模型原始响应
- `errors.jsonl`：失败记录
- `sample_prompt_system.txt` / `sample_prompt_user.txt`：样例 prompt

如需把某个 run 规范化成稳定输出：

```powershell
python scripts/postprocess_case_runs.py --run-dir .cache/case_runs/<run-name>
```

如需把多个 run 汇总成一个总案例库：

```powershell
python scripts/postprocess_case_runs.py --run-dir .cache/case_runs/<run-a> --run-dir .cache/case_runs/<run-b> --output-run-dir .cache/case_runs/<corpus-name>
```

当前最佳实践是：

1. 主链优先做 `chunk -> case profile`
2. 对单个 run 执行 `postprocess_case_runs.py`，统一做角色归一化、排序与保守去重
3. 再把多个 run 汇总成总案例库

补充说明：

- `.cache/case_runs/` 下的内容是生成产物，不是手工维护目录。
- `scripts/archive/` 保存历史分析、导出和 router 实验脚本，不属于当前主生产链。

如需指定其他资源：

```powershell
$env:ZIZHI_CORPUS_PATH="sources\新的资治通鉴资源.epub"
python scripts/build_corpus.py
```

## 可选：启用 LanceDB + case dense 检索

```powershell
$env:ZIZHI_ENABLE_LANCEDB="1"
$env:ZIZHI_EMBEDDING_MODEL="BAAI/bge-m3"

$env:ZIZHI_CASE_ENABLE_DENSE="1"
$env:ZIZHI_CASE_EMBEDDING_MODEL="BAAI/bge-large-zh-v1.5"
$env:ZIZHI_CASE_LANCEDB_PATH=".zizhi_case_lancedb"
streamlit run app.py
```

说明：

- `ZIZHI_ENABLE_LANCEDB` / `ZIZHI_EMBEDDING_MODEL`：控制旧的 chunk 检索向量化能力。
- `ZIZHI_CASE_ENABLE_DENSE` / `ZIZHI_CASE_EMBEDDING_MODEL`：控制新的 case-first dense 检索。
- 当前 case dense 默认模型为 `BAAI/bge-large-zh-v1.5`，用于 `title + transferable_pattern` 的语义召回。
- 首次加载模型可能需要下载；若模型或 LanceDB 不可用，系统会自动降级到无向量模式继续工作。

注意：embedding / LanceDB 只服务“找材料更稳”，并不改变项目最终以 `case library` 为中心的方向。

## 目录

- `app.py`：Streamlit 入口。
- `zizhi/schemas.py`：Pydantic 数据结构。
- `zizhi/corpus.py`：内置种子语料与 JSONL 加载。
- `zizhi/retrieval.py`：检索实现，支持 LanceDB 降级；定位上属于底层能力层。
- `zizhi/agents.py`：六类 Agent 节点逻辑。
- `zizhi/case_profile_prompt.py`：第二阶段 CaseProfile 抽取 prompt 模板加载与渲染。
- `prompts/case_extraction_system_prompt_v1.txt` / `prompts/case_extraction_user_prompt_v1.txt`：批量案例抽取 prompt，强调 case-worthy 主线与最小 section 窗口。
- `scripts/postprocess_case_runs.py`：对单个 run 或多个 run 做角色归一化、排序与保守合并，生成更稳定的案例库输出。
- `zizhi/workflow.py`：LangGraph 编排与手动兜底执行。
- `zizhi/rendering.py`：Markdown 与 Mermaid 前端渲染辅助。
- `prompts/`：结构化标注的 system/user prompt 与候选标签池。
- `scripts/archive/`：保留历史分析、导出、router benchmark 等非主链脚本。

## Specs

- `docs/specs/README.md`：规格文档索引。
- `docs/specs/north_star_spec.md`：项目北极星与分层原则。
- `docs/specs/product_spec.md`：产品规格。
- `docs/specs/data_ingest_spec.md`：数据清洗与正式入库规格。
- `docs/specs/chunking_spec.md`：chunk 切分规格。
- `docs/specs/case_profile_spec.md`：故事案例层规格。
- `docs/specs/retrieval_spec.md`：检索规格。
- `docs/specs/schema_spec.md`：数据结构规格。
- `docs/specs/perspective_tagging_spec.md`：视角标签与史案多视角映射规格。
- `docs/specs/answer_generation_spec.md`：回答生成规格。
