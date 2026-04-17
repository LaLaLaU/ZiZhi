# Perspective Tagging Spec

## 1. 目标

为《资治通鉴》史料建立“视角优先”的语义标签层，解决同一历史事实在不同角色位置下会产生不同解读的问题。

核心原则：

- 事件标签回答“发生了什么”
- 视角标签回答“这对谁意味着什么”
- 策略标签回答“这个位置上的人可以怎么做”

## 2. 为什么需要视角

同一件历史事件不能只打一个通用标签。

例如“被架空”：

- 管理者视角：可能是 `被夺权`、`被绕过`、`控制力下降`
- 被管理者视角：可能是 `另结同盟`、`寻求保护`、`对上级失去信任`
- 平级视角：可能是 `派系重组`、`同级竞争`、`联盟替代正式权威`
- 第三方视角：可能是 `权力真空`、`组织失衡`、`可乘之机`

因此正式标签体系必须采用：

`perspective -> event_labels -> risk_labels -> strategy_labels`

而不是只有一层平铺标签。

## 3. 标准视角类型

第一版使用 5 类视角：

- `manager`：管理者、上位者、负责人、名义权威
- `subordinate`：被管理者、下属、执行者、弱势承压者
- `peer`：平级、同僚、合伙人、同级竞争者
- `observer`：第三方、顾问、中间人、旁观判断者
- `unknown`：无法稳定判断时的兜底视角

## 4. 用户问题侧视角识别

用户输入后，系统需要先识别：

- `user_perspective`
- `target_role`
- `counterparty_role`
- `perspective_confidence`
- `perspective_reason`

示例：

```json
{
  "user_perspective": "manager",
  "target_role": "我/负责人",
  "counterparty_role": "同事/下属/绕过我的人",
  "perspective_confidence": 0.82,
  "perspective_reason": "用户描述自己被同事绕过与架空，核心损失是管理控制权。"
}
```

## 5. 史料侧视角化摘要

小模型离线摘要《资治通鉴》时，不应只输出“本卷有哪些标签”，而应输出多视角解读。

每个卷级 profile 和史案级 profile 都应包含 `perspectives` 字段。

每个 perspective 下至少包含：

- `perspective_type`
- `perspective_summary`
- `event_labels`
- `risk_labels`
- `strategy_labels`
- `modern_scenes`
- `evidence_section_keys`

## 6. 标签层级

### 6.1 事件标签

描述事实模式：

- `架空`
- `夺权`
- `结盟`
- `背叛`
- `离间`
- `削权`
- `专权`
- `夺兵权`
- `托孤`
- `进谏`
- `用人失察`
- `权柄旁落`

### 6.2 风险标签

描述视角下的风险：

- `失去控制权`
- `被孤立`
- `信任崩塌`
- `被迫站队`
- `信息不透明`
- `联盟反噬`
- `权责不匹配`
- `名义责任与实际权力分离`

### 6.3 策略标签

描述可选动作：

- `先稳后动`
- `公开确认边界`
- `建立证据链`
- `分化联盟`
- `争取第三方背书`
- `暂不表态`
- `低风险试探`
- `重建汇报链路`
- `授权但设校验`

### 6.4 现代场景标签

用于连接用户现代问题：

- `被同事架空`
- `被绕过汇报`
- `被抢功`
- `被边缘化`
- `合伙人失衡`
- `团队内斗`
- `授权失控`
- `站队压力`
- `老板不信任`

## 7. 输出示例

```json
{
  "case_id": "case-power-bypass-example",
  "title": "某权臣绕过正式权威控制政务",
  "section_keys": ["084-s0031", "084-s0032", "084-s0033"],
  "perspectives": [
    {
      "perspective_type": "manager",
      "perspective_summary": "名义负责人仍在位，但关键命令链被他人控制，实际权柄旁落。",
      "event_labels": ["架空", "削权", "绕过中枢"],
      "risk_labels": ["失去控制权", "名义责任与实际权力分离"],
      "strategy_labels": ["公开确认边界", "建立证据链", "争取第三方背书"],
      "modern_scenes": ["被同事架空", "被绕过汇报"],
      "evidence_section_keys": ["084-s0031", "084-s0032"]
    },
    {
      "perspective_type": "peer",
      "perspective_summary": "同级势力重新结盟，正式权威之外出现新的协作中心。",
      "event_labels": ["结盟", "派系重组", "同级竞争"],
      "risk_labels": ["联盟反噬", "被迫站队"],
      "strategy_labels": ["暂不表态", "低风险试探"],
      "modern_scenes": ["同级博弈", "团队内斗"],
      "evidence_section_keys": ["084-s0032", "084-s0033"]
    }
  ]
}
```

## 8. 小模型标注要求

离线标注时必须遵守：

- 标签必须绑定 `evidence_section_keys`
- 不允许只给抽象标签而不给证据
- 同一事件必须允许多个视角并存
- 每个视角下的标签必须解释“对该视角意味着什么”
- 无证据支持的现代映射不得入库

## 9. 检索使用方式

查询时流程为：

1. 识别用户视角
2. 抽取现代场景标签
3. 扩展事件/风险/策略标签
4. 检索匹配的 perspective profiles
5. 召回对应 `case_id/chunk_id/section_key`
6. 回查白话 chunk 与古文原文

## 10. 验收标准

- 同一历史事件能按不同视角返回不同解读
- 用户视角识别错误时，系统能降级到 `unknown` 或多视角候选
- 每个视角标签都能追溯到 section 证据
- 检索结果能解释“为什么这个史例适合当前用户位置”
