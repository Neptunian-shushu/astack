# /alpha-evolve

对存活因子做变异或交叉，扩展搜索空间。

## Input

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| specs | list[AlphaSpec] | 是 | 通过筛选的因子（survivors） |

或通过 CLI：`astack evolve --input specs.json --output evolved.json`

## Output Schema

```json
[
  {
    "name": "string (parent_name + _mutN / _crossN)",
    "description": "string (包含变异方式说明)",
    "formula_expression": "string",
    "required_fields": ["string"],
    "parameters": {},
    "output_type": "signal | score | rank",
    "direction": "long | short | both",
    "implementation_stub": "string"
  }
]
```

## 变异策略
- 基于原因子的经济逻辑做合理延伸
- 调整参数 / 时间窗口 / 运算符
- 组合不同因子的核心 idea（交叉）
- 尝试不同的标准化方式
- 探索相邻的信号构造方法

## 要求
- 每个变体必须有独立的经济含义
- 不只是改参数值，要改信号结构
- 保持表达简洁，不做无意义堆砌
- 变体数量合理，不做暴力搜索

## Failure Cases
- 输入为空 → 返回空列表
- 所有变体与 parent 过于相似 → 在 description 中标注 "minor variant"

## Example

```json
{
  "name": "volume_shock_reversal_mut1",
  "description": "volume_shock_reversal 变体: 用 EMA 替代 SMA，加入波动率调整",
  "formula_expression": "-zscore(volume / ema(volume, 20)) * sign(return_1) / realized_vol_10",
  "required_fields": ["close", "volume"],
  "parameters": {"lookback": 20, "vol_window": 10},
  "output_type": "signal",
  "direction": "both",
  "implementation_stub": "def compute(df): ..."
}
```
