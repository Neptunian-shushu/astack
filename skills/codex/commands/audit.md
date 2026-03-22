# /audit-factor

解析旧因子，输出审计报告。搞清楚这个因子到底在干什么、是否合格。

## Input

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| factor_code | string | 是 | 因子的 Python 代码或公式表达式 |
| factor_name | string | 是 | 因子名称 |
| documentation | string | 否 | 因子说明文档 |

或通过 CLI：`astack audit --input specs.json --output audits.json`

## Output Schema

```json
{
  "factor_name": "volume_spike_reversal_v1",
  "core_logic": "放量但价格未突破 → 短期回归",
  "factor_type": "成交量反转",
  "hypothesis_clarity": 0.75,
  "implementation_clarity": 0.6,
  "required_fields": ["close", "volume"],
  "potential_issues": [
    "窗口定义不明确",
    "对极端行情敏感"
  ],
  "lookahead_risk": false,
  "turnover_estimate": "medium",
  "migratable": true,
  "suggested_action": "migrate | rewrite | deprecate | keep_as_is"
}
```

## 审计维度
1. **核心逻辑**：这个因子到底在做什么？经济含义是什么？
2. **假设清晰度**：假设是否明确、可验证？
3. **实现清晰度**：代码是否干净、可审查？
4. **未来数据风险**：是否存在 lookahead bias？
5. **可迁移性**：能否转成标准 AlphaSpec？
6. **潜在问题**：参数过多、极端行情敏感、窗口不明确等

## Failure Cases
- 因子代码无法解析 → `implementation_clarity: 0`, `migratable: false`, `suggested_action: "rewrite"`
- 因子逻辑无法理解 → `hypothesis_clarity: 0`, 在 `potential_issues` 中说明
