# /alpha-generate

基于研究目标和历史记忆生成 alpha 候选 idea。

## Input

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| goal | string | 是 | 研究目标 |
| constraints | list[string] | 否 | 数据字段限制、市场约束等 |
| max_ideas | int | 否 | 生成数量，默认 10 |

## Output Schema

```json
[
  {
    "name": "string (唯一标识)",
    "hypothesis": "string (核心假设)",
    "intuition": "string (经济直觉)",
    "family": "string (因子家族: microstructure/momentum/mean_reversion/...)",
    "expected_horizon": "string (预期持仓周期)",
    "required_fields": ["string (所需数据字段)"],
    "constraints": ["string (约束条件)"]
  }
]
```

## 要求
- 候选因子应多样化，覆盖不同经济逻辑
- 参考历史记忆中的成功/失败模式引导搜索方向
- 避免与 FactorLibrary 中已有因子高度重复
- 每个 idea 必须有清晰的经济含义

## Failure Cases
- 未提供 goal → 报错，要求提供研究目标
- 所有生成的 idea 与已有 library 重复 → 提示扩大搜索范围或更换方向

## Example

```json
{
  "name": "volume_shock_reversal",
  "hypothesis": "异常放量后短期价格回归，因为噪音交易者推动的价格偏离会被套利修正",
  "intuition": "突然的成交量放大往往伴随价格过度反应，后续存在均值回复",
  "family": "microstructure",
  "expected_horizon": "1-4 bars",
  "required_fields": ["close", "volume"],
  "constraints": ["no lookahead", "max 2 parameters"]
}
```
