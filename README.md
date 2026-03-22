# AStack

AStack (Alpha Stack) 将因子挖掘流程中的关键环节拆解为独立的 skills，通过 Claude / Codex 驱动，实现可组合、可复用的 alpha 研究工作流。

灵感来源于 [gstack](https://github.com/gstack) 项目，AStack 在此基础上聚焦于：将因子生成、形式化、验证、去重、排序、进化等步骤模块化为 skill，让 LLM 能够像调用工具一样完成端到端的因子挖掘。

AStack 本身与市场无关，通过 adapter 适配不同资产类别（Crypto、股票、期货等）和回测框架。

## Skills

| Skill | 说明 |
|-------|------|
| **generate** | 基于研究目标和历史记忆生成 alpha 候选 |
| **formalize** | 将模糊的 idea 转化为严格的因子定义（公式、参数、方向） |
| **validate** | 通过 adapter 对接回测框架，评估可实现性与质量 |
| **dedupe** | 因子去重，过滤高相关性冗余 |
| **rank** | 综合打分排序 |
| **evolve** | 对存活因子做变异/交叉，扩展搜索空间 |
| **export** | 输出 adapter-ready 的因子定义和回测报告 |

## 架构

```text
research goal
  -> generate (skill)
  -> formalize (skill)
  -> validate (skill, via adapter)
  -> dedupe (skill)
  -> rank (skill)
  -> memory update
  -> evolve (skill)
  -> export (skill)
```

核心设计：
- **Skill-first**：每个环节都是独立 skill，可单独调用或组合成 pipeline
- **Framework-agnostic**：通过 adapter 对接任意回测/执行框架
- **Memory-guided**：记忆存储驱动搜索方向，避免重复探索

## Quick Start

```bash
pip install -e .
astack run --goal "Generate short-horizon crypto alphas around volume dislocation"
```

## 项目状态

当前为 v0.2 scaffold，已包含完整的 pipeline 骨架、schema 定义、memory store 和示例 adapter。

需要替换的 placeholder：
- LLM 接入（当前为 demo stub）
- 真实回测 adapter
- prompt 调优与准入阈值
