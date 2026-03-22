# /migrate-factor

将旧因子统一为标准 AlphaSpec 格式。这是因子治理中最关键的一步——所有旧因子必须统一成 AlphaSpec，否则无法系统化管理。

## Input

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| specs | list[AlphaSpec] | 是 | 旧因子（可能格式不完整） |
| audits | list[FactorAuditReport] | 否 | 对应的审计报告 |

或通过 CLI：`astack migrate --input specs.json --output migrated.json`

## Output Schema

```json
{
  "name": "volume_spike_reversal",
  "description": "成交量异常放大但价格未突破，短期存在回归",
  "formula_expression": "...",
  "required_fields": ["close", "volume"],
  "parameters": {"lookback": 12, "z_window": 48},
  "output_type": "signal",
  "direction": "both",
  "implementation_stub": "def compute(df): ..."
}
```

## 迁移规则
1. 名称规范化：小写、下划线分隔、去空格
2. 方向必须明确：unknown → 推断或标注为 both
3. 描述必须完整：缺失则从审计报告的 core_logic 补充
4. 参数 ≤ 3 个：多余参数标记为固定值
5. 实现代码必须可执行

## Failure Cases
- 审计报告标记 `migratable: false` → 输出中标注 `description: "[NEEDS REWRITE] ..."`, 不做强制迁移
- 公式为空 → 返回空 spec，在 description 中说明需要人工补充
