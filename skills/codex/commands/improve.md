# /improve-factor

基于评估结果对因子进行针对性改进。不是删掉，而是升级。

## Input

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| specs | list[AlphaSpec] | 是 | 待改进的因子 |
| reports | list[ValidationReport] | 是 | 对应的评估报告 |

或通过 CLI：`astack improve --input specs.json --reports reports.json --output improvements.json`

## Output Schema

```json
{
  "original_name": "volume_spike_reversal",
  "improved_name": "volume_spike_reversal_v2",
  "improvements": [
    "加入波动率过滤",
    "减少极端行情影响"
  ],
  "new_spec": { "...AlphaSpec..." },
  "expected_gains": "降低换手/冗余，提高稳健性",
  "risk_notes": ["原因子有 regime 风险，改进版需重新验证"]
}
```

## 改进策略
根据评估报告的问题，选择对应改进方式：

| 问题 | 改进方向 |
|------|---------|
| 换手率高 | 加平滑（EMA）、降低信号频率 |
| 冗余度高 | 正交化处理、换用不同的核心逻辑 |
| 质量分低 | 加波动率调整、regime filter |
| 参数过多 | 固定非核心参数、减少自由度 |
| 近期失效 | 加自适应窗口、regime 检测 |

## 要求
- 改进版必须保持原因子的经济含义内核
- 不做无意义的复杂化
- 改进点必须明确列出，方便后续验证

## Failure Cases
- 评估报告为 pass → 无需改进，返回原 spec
- 评估报告触发 11.1（未来数据）→ 不改进，直接标记为 "needs complete rewrite"
