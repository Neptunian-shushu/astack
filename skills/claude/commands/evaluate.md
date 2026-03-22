# /alpha-evaluate

按 12 条单因子评价标准评估因子。

## Input

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| specs | list[AlphaSpec] | 是 | 来自 /alpha-formalize 的输出 |
| backtest_results | dict | 否 | adapter 回测返回的原始指标 |

或通过 CLI：`astack evaluate --input specs.json --output reports.json`

## Output Schema

```json
[
  {
    "alpha_name": "string",
    "implementable": true,
    "lookahead_safe": true,
    "data_available": true,
    "redundancy_score": 0.0,
    "quality_score": 0.0,
    "turnover_risk": "low | medium | high",
    "regime_risk": "low | medium | high",
    "metrics": {"IC": 0.0, "ICIR": 0.0, "sharpe": 0.0},
    "warnings": [],
    "critique": "string",
    "eval_report": null
  }
]
```

## 评分维度（标准 1-9，每项 0~1 分）

1. **预测能力** — IC/ICIR、十分组分层单调性、首尾组收益差、多空收益、夏普
2. **多持仓周期稳健性** — 一组相邻持有期上稳定表现
3. **年度一致性** — 多数年份方向一致，不依赖少数年份
4. **经济含义与交易逻辑** — 能解释偏差为何存在
5. **参数简洁性** — 核心参数 ≤ 3 个
6. **跨时间/跨品种稳健性** — 不同品种和市场状态下一致
7. **创新性** — 非旧因子机械变形
8. **信号可交易性** — 稳定排序、有效分层、方向清晰
9. **表达简洁可审查** — 干净、可复现

## 否决条件（标准 11）

| 编号 | 条件 | 处理 |
|------|------|------|
| 11.1 | 存在未来数据 | **一票否决** → verdict="fail" |
| 11.2 | 多空收益严重不均衡 | verdict 降级 |
| 11.3 | IC 接近零 + 分组混乱 | verdict 降级 |
| 11.4 | 参数敏感 | verdict 降级 |
| 11.5 | 近两年表现差 | verdict 降级 |

## 验证协议（标准 12）

7:2:1 train/val/test → val 效果接近 train → 初步通过 → test 确认 → 入库。

## 输出格式

```
## 因子评估: [名称]

### 逐项评分
| 标准 | 得分 | 通过 | 说明 |
|------|------|------|------|
| 1. 预测能力 | 0.x | ✓/✗ | ... |
| ... |

### 否决条件
- 11.1: ✗ 未触发
- ...

### 综合判定: pass / marginal / fail
### 改进建议
...
```

## Failure Cases
- 无回测数据 → 仅做定性评估（经济含义、参数简洁、表达简洁），其余标注"待回测补充"
- 触发 11.1 → 直接判定 fail，不需要看其他维度
