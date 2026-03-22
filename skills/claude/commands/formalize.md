# /alpha-formalize

将模糊的 alpha idea 转化为严格的因子定义（AlphaSpec）。

## 输入
- 一个或多个 AlphaIdea

## 输出
每个 AlphaSpec 需包含：
- 名称（name）
- 描述（description）
- 明确的公式表达（formula_expression）
- 所需字段（required_fields）
- 参数（parameters）— 核心参数 ≤ 3 个
- 方向（direction）：long / short / both
- 可执行的实现代码（implementation_stub）

## 要求
- 公式必须严格因果，不允许未来数据
- 参数尽量少，由主参数派生
- 实现代码应干净、可直接运行
- 所有 rolling/shift/标准化操作必须明确窗口和方向

## 输出格式
```json
{
  "name": "alpha_name",
  "description": "...",
  "formula_expression": "zscore(volume / sma(volume, 20))",
  "required_fields": ["close", "volume"],
  "parameters": {"lookback": 20},
  "direction": "both",
  "implementation_stub": "def compute(df): ..."
}
```
