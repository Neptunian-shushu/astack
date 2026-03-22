# AStack

AStack (Alpha Stack) 将 alpha research 视为结构化循环，把因子挖掘流程中的关键环节拆解为独立的 skills：

```
generate → formalize → evaluate → dedupe → rank → evolve
```

灵感来源于 [gstack](https://github.com/gstack) 项目。AStack 不是单次 prompt 工具，而是一个 **alpha research workflow system**，通过 Claude / Codex 驱动，实现可组合、可复用的因子研究工作流。

AStack 与市场无关，通过 adapter 适配不同资产类别（Crypto、股票、期货等）和回测框架。

## Skills

每个 skill 可独立调用，也可组合成完整 workflow：

| Skill | CLI | 说明 |
|-------|-----|------|
| **generate** | `astack generate --goal "..."` | 基于研究目标和历史记忆生成 alpha 候选 |
| **formalize** | `astack formalize --goal "..."` | 将 idea 转化为严格因子定义（公式、参数 ≤3、方向） |
| **evaluate** | `astack evaluate --goal "..."` | 按 12 条标准评估因子质量 |
| **dedupe** | — | 因子去重，过滤高相关性冗余 |
| **rank** | — | 综合打分排序 |
| **evolve** | `astack evolve --goal "..."` | 变异/交叉扩展搜索空间 |
| **run** | `astack run --goal "..."` | 执行完整 research loop |

## 架构

```
astack/
├── runtime/          # ResearchAgent — workflow 主控编排器
├── core/             # 各 skill 的实现
│   ├── generator     # 因子生成
│   ├── formalizer    # 形式化
│   ├── validator     # 验证（via adapter）
│   ├── criteria      # 12 条评价标准
│   ├── deduper       # 去重
│   ├── ranker        # 排序
│   ├── evolver       # 进化
│   ├── experience    # ExperienceMemory — 研究经验积累
│   ├── factor_library# FactorLibrary — 因子库管理
│   ├── memory        # 基础记忆存储
│   └── exporter      # 导出
├── schemas/          # 数据模型（AlphaIdea → AlphaSpec → ValidationReport → RankedAlpha）
├── interfaces/       # 抽象接口（adapter 需实现）
├── adapters/         # 具体 adapter 实现
├── prompts/          # LLM prompt 模板
├── cli.py            # 命令行入口
skills/
├── claude/           # Claude skill 定义
│   ├── SKILL.md      # 总入口
│   └── commands/     # 各 skill 独立文件
└── codex/            # Codex skill 定义（与 Claude 一致）
```

核心设计：
- **Skill-first**：每个环节都是独立 skill，可单独调用或组合成完整 loop
- **Framework-agnostic**：通过 adapter 对接任意回测/执行框架
- **Memory-guided**：ExperienceMemory 积累成功/失败模式，FactorLibrary 管理入库因子

## Quick Start

```bash
pip install -e .

# 完整 loop
astack run --goal "Generate short-horizon alphas around volume dislocation"

# 单独调用
astack generate --goal "momentum reversal factors"
astack evaluate --goal "volume compression alpha"
```

## 接入你的项目

AStack 不替代你的研究框架，而是给它增加一个 structured alpha research workflow 能力。

**Phase 1 — Skill-only**：把 `skills/claude/` 内容加到你的项目中，手动将输出送入回测。

**Phase 2 — Skill + Adapter**：写一个 adapter 对接你的回测框架，让 astack 输出直接进入评估链路。

**Phase 3 — Skill + Runtime + Memory**：完整闭环，ExperienceMemory 积累经验，FactorLibrary 管理因子库。

## 项目状态

当前为 v0.3，已包含：
- ResearchAgent workflow 编排器
- 12 条单因子评价标准（9 项评分 + 理想模板 + 否决条件 + 验证协议）
- ExperienceMemory 和 FactorLibrary
- 独立 skill 文件和 CLI
- 示例 adapter

需要替换的 placeholder：
- LLM 接入（当前 generator/formalizer/evolver 为 demo stub）
- 真实回测 adapter
- prompt 调优与准入阈值
