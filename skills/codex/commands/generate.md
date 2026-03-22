# /alpha-generate

基于用户给定的研究目标和历史记忆，生成 alpha 候选 idea。

## 输入
- 研究目标（goal）
- 可选：市场/品种约束、数据字段限制

## 输出
每个 idea 需包含：
- 名称
- 假设（hypothesis）
- 经济直觉（intuition）
- 因子家族（family）
- 预期持仓周期（expected_horizon）
- 所需字段（required_fields）
- 约束条件（constraints）

## 要求
- 生成的 idea 应多样化，覆盖不同的经济逻辑和市场微观结构
- 避免生成已知冗余或过于相似的候选
- 参考历史记忆中的成功/失败模式来引导搜索方向
- 每个 idea 必须有清晰的经济含义，不做无逻辑的公式拼凑

## 输出格式
```json
{
  "name": "alpha_name",
  "hypothesis": "...",
  "intuition": "...",
  "family": "microstructure",
  "expected_horizon": "1-4 bars",
  "required_fields": ["open", "high", "low", "close", "volume"],
  "constraints": ["no lookahead"]
}
```
