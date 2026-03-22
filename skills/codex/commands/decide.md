# /decide-factor

决定因子在库中的最终命运。综合审计、评估和改进方案，给出决策。

## Input

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| factor_name | string | 是 | 因子名称 |
| audit | FactorAuditReport | 是 | 审计报告 |
| report | ValidationReport | 是 | 评估报告 |
| improvement | ImprovementSpec | 否 | 改进方案 |

或通过 CLI：`astack decide --input decisions_input.json --output decisions.json`

## Output Schema

```json
{
  "factor_name": "volume_spike_reversal",
  "decision": "admit | upgrade | deprecate | remove | hold",
  "reason": "质量评分=0.82，冗余度低，直接入库",
  "replacement": "volume_spike_reversal_v2",
  "priority": "high | medium | low"
}
```

## 决策规则

| 条件 | 决策 | 优先级 |
|------|------|--------|
| 存在未来数据 | **remove** | high |
| 无法迁移 | **remove** | medium |
| quality ≥ 0.75 且冗余低 | **admit** | high |
| quality ≥ 0.5 且有改进空间 | **upgrade** | medium |
| quality < 0.4 | **deprecate** | low |
| 其余情况 | **hold** | low |

## 输出格式

```
## 因子决策: [名称]

| 因子 | 决策 | 原因 | 替代 | 优先级 |
|------|------|------|------|--------|
| ... | admit/upgrade/deprecate/remove/hold | ... | ... | ... |
```

## Failure Cases
- 缺少审计或评估报告 → 返回 `decision: "hold"`, `reason: "数据不足，暂不决策"`
