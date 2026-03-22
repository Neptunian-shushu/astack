# /alpha-rank

对多个已评估的因子进行综合排序。

## Input

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| reports | list[ValidationReport] | 是 | 来自 /alpha-evaluate 的输出 |

或通过 CLI：`astack rank --input reports.json --output ranked.json`

## Output Schema

```json
[
  {
    "alpha_name": "string",
    "rank_score": 0.0,
    "rationale": "string (排序理由)",
    "tags": ["string"]
  }
]
```

## 排序依据
- 各因子的 quality_score / overall_score
- 因子间相关性（避免冗余入库）
- 理想模板匹配度
- 否决条件触发情况（触发 red flag 的排在后面）

## 输出格式

```
## 因子排序

| 排名 | 因子 | 得分 | 判定 | 关键优势 | 主要风险 |
|------|------|------|------|---------|---------|
| 1 | ... | 0.xx | pass | ... | ... |

### 入库建议
- 推荐入库: ...
- 待改进后复审: ...
- 建议放弃: ...
```

## Failure Cases
- 输入为空 → 返回空列表
- 所有因子均触发 11.1 → 全部 fail，提示重新生成
