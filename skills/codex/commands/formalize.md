# /alpha-formalize

将模糊的 alpha idea 转化为严格的因子定义（AlphaSpec）。

## Input

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| ideas | list[AlphaIdea] | 是 | 来自 /alpha-generate 的输出 |

或通过 CLI：`astack formalize --input ideas.json --output specs.json`

## Output Schema

```json
[
  {
    "name": "string (唯一标识，与 idea 对应)",
    "description": "string (因子描述和假设)",
    "formula_expression": "string (明确的数学公式)",
    "required_fields": ["string"],
    "parameters": {"string": "any (核心参数 ≤ 3 个)"},
    "output_type": "signal | score | rank",
    "direction": "long | short | both",
    "implementation_stub": "string (可执行的 Python 代码)"
  }
]
```

## 要求
- 公式必须严格因果，所有 rolling/shift 只依赖当时及历史数据
- 核心参数 ≤ 3 个，其余由主参数派生
- implementation_stub 应干净、可直接运行
- direction 必须明确

## Failure Cases
- idea 过于模糊无法形式化 → 返回 `implementation_stub: ""` 并在 description 中标注 "needs clarification"
- required_fields 中包含不可获取的字段 → 在 constraints 中标注

## Example

```json
{
  "name": "volume_shock_reversal",
  "description": "异常放量后短期价格回归",
  "formula_expression": "-zscore(volume / sma(volume, 20)) * sign(return_1)",
  "required_fields": ["close", "volume"],
  "parameters": {"lookback": 20},
  "output_type": "signal",
  "direction": "both",
  "implementation_stub": "def compute(df):\n    vol_ratio = df['volume'] / df['volume'].rolling(20).mean()\n    ret = df['close'].pct_change()\n    signal = -((vol_ratio - vol_ratio.rolling(20).mean()) / vol_ratio.rolling(20).std()) * ret.apply(lambda x: 1 if x > 0 else -1)\n    return signal"
}
```
