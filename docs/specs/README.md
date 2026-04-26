# ZiZhi Spec Index

本目录存放《资智 ZiZhi》项目的第一版正式规格文档，目标是把当前 Demo 的实现、已确认的产品决策、后续工程化方向统一下来。

## 文档清单

- `docs/specs/north_star_spec.md`：项目北极星、产品层与基础设施层的分工。
- `docs/specs/product_spec.md`：产品目标、用户、场景、边界与 V1 成功标准。
- `docs/specs/data_ingest_spec.md`：TXT 语料清洗、文白配对、入库流程与异常处理。
- `docs/specs/chunking_spec.md`：正式 chunk 切分规则、长度控制、编号与上下文策略。
- `docs/specs/case_profile_spec.md`：故事线案例层的构建规则、case-worthy 标准与输出字段。
- `docs/specs/retrieval_spec.md`：检索链路、召回排序、索引构建与未来演进。
- `docs/specs/schema_spec.md`：核心数据模型、字段约束、前后端返回结构。
- `docs/specs/perspective_tagging_spec.md`：用户视角、史案多视角标签与现代场景映射。文件名沿用历史命名，但它服务的是当前 case 检索层。
- `docs/specs/answer_generation_spec.md`：答案组织方式、引文展示、置信度与防幻觉规则。

## 使用原则

- 这些文档以当前仓库实现为基线，但允许对“正式入库版本”提出目标规范。
- 若不同 spec 出现冲突，以 `north_star_spec.md` 的产品分层判断为总纲。
- 如果“当前代码”与“目标规范”不一致，以 spec 作为后续改造依据。
- 任何涉及语料结构、chunk 规则、检索字段、前端返回结构的修改，需同步更新对应 spec。
- 若目录或文件名仍保留早期命名痕迹，应以其当前在 `chunk -> case -> retrieval` 主链中的职责理解，而不是按旧 annotation 流程理解。
