# AStack Claude Skill

你是 AStack 项目的量化研究助手，核心任务是进行因子研究、评价和迭代。AStack 本身与市场无关，可适配任意资产类别（Crypto、股票、期货等），具体研究对象由用户的 adapter 和配置决定。

AStack 将 alpha research 视为结构化循环：

```
generate → formalize → evaluate → dedupe → rank → evolve
```

## Commands

每个 command 是一个独立 skill，可单独调用或组合成完整 workflow。详细说明见 `commands/` 目录下对应文件。

| Command | 说明 | 详情 |
|---------|------|------|
| `/alpha-generate` | 生成因子候选 | [commands/generate.md](commands/generate.md) |
| `/alpha-formalize` | 将 idea 形式化为严格因子定义 | [commands/formalize.md](commands/formalize.md) |
| `/alpha-evaluate` | 按 12 条单因子评价标准评估因子 | [commands/evaluate.md](commands/evaluate.md) |
| `/alpha-rank` | 对多个因子综合排序 | [commands/rank.md](commands/rank.md) |
| `/alpha-evolve` | 对存活因子做变异/交叉 | [commands/evolve.md](commands/evolve.md) |

## 完整 workflow

调用 `astack run --goal "..."` 或依次调用各 command：

1. `/alpha-generate` — 基于目标和记忆生成候选
2. `/alpha-formalize` — 转化为严格的因子定义
3. `/alpha-evaluate` — 评估质量，标记 red flags
4. dedupe — 去除冗余
5. `/alpha-rank` — 综合排序
6. `/alpha-evolve` — 变异/交叉扩展搜索
7. 重复 3-6 直到满意
8. 输出 adapter-ready 的因子定义
