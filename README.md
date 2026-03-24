# AStack

AStack (Alpha Stack) 是一个 **alpha research workflow system + factor governance system**。

两条核心 workflow：

```
Alpha Research:     generate → formalize → evaluate → dedupe → rank → evolve
Factor Governance:  audit → migrate → evaluate → improve → decide
```

灵感来源于 [gstack](https://github.com/gstack) 项目。AStack 不是单次 prompt 工具，而是通过 Claude / Codex 驱动的结构化因子研究和治理系统。

AStack 与市场无关，通过 adapter 适配不同资产类别（Crypto、股票、期货等）和回测框架。

## Skills

每个 skill 可独立调用，也可组合成完整 workflow：

| Skill | CLI | 说明 |
|-------|-----|------|
| **generate** | `astack generate --goal "..." -o ideas.json` | 基于研究目标和历史记忆生成 alpha 候选 |
| **formalize** | `astack formalize -i ideas.json -o specs.json` | 将 idea 转化为严格因子定义 |
| **evaluate** | `astack evaluate -i specs.json -o reports.json` | 按 12 条标准评估因子质量 |
| **dedupe** | `astack dedupe -i reports.json -o deduped.json` | 因子去重，过滤高相关性冗余 |
| **rank** | `astack rank -i reports.json -o ranked.json` | 综合打分排序 |
| **evolve** | `astack evolve -i specs.json -o evolved.json` | 变异/交叉扩展搜索空间 |
| **run** | `astack run --goal "..."` | 执行完整 research loop |

### Factor Governance（因子治理）

| Skill | CLI | 说明 |
|-------|-----|------|
| **audit** | `astack audit -i factors.json -o audits.json` | 审计旧因子，输出审计报告 |
| **migrate** | `astack migrate -i factors.json -o migrated.json` | 将旧因子统一为标准 AlphaSpec |
| **improve** | `astack improve -i specs.json -o improvements.json` | 基于评估结果给出升级版本 |
| **decide** | `astack decide -i specs.json -o decisions.json` | 决定因子的最终命运 |
| **govern** | `astack govern -i factors.json` | 执行完整治理 loop |

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
astack generate --goal "momentum reversal factors" -o ideas.json
astack formalize -i ideas.json -o specs.json
astack evaluate -i specs.json -o reports.json
astack dedupe -i reports.json -o deduped.json
astack rank -i deduped.json -o ranked.json
astack evolve -i specs.json -o evolved.json
```

## 接入你的项目

AStack 不替代你的研究框架，而是给它增加一个 structured alpha research workflow 能力。

**最小接入示例**（以 AlphaGPT 为例）：

```bash
# 1. 在你的回测框架中跑因子并导出报告
python -m model_core.factor_test --export-json

# 2. astack 一键导入 + 治理
astack ingest -i reports/factor_report.json -o governance/

# 3. 查看治理结论
cat governance/summary.json
# → {"total_audited": 5, "by_decision": {"admit": 2, "upgrade": 2, "hold": 1}, ...}
```

更完整的 adapter 示例见 [`examples/integrate_with_alphagpt.py`](examples/integrate_with_alphagpt.py)。

**分阶段路线**：

**Phase 1 — Skill-only**：把 `skills/claude/` 内容加到你的项目中，手动将输出送入回测。

**Phase 2 — Skill + Adapter**：写一个 adapter 对接你的回测框架，让 astack 输出直接进入评估链路。

**Phase 3 — Skill + Runtime + Memory**：完整闭环，ExperienceMemory 积累经验，FactorLibrary 管理因子库。

## 项目状态

### 能力矩阵

| 能力 | 状态 | 说明 |
|------|------|------|
| Alpha Research Workflow | **可用** | generate → formalize → evaluate → dedupe → rank → evolve |
| Factor Governance | **可用** | audit → migrate → evaluate → improve → decide + GovernanceSummary |
| 评价标准（8维多分位数加权） | **可用** | 分位数突破策略收益，10% 权重最高 |
| AlphaGPT 集成 | **可用** | parser + batch ingest + confidence-aware decisions |
| SearchStrategy | **可用** | pattern memory + library diagnostics → 引导式搜索 |
| Artifact-based CLI | **可用** | 14 个子命令，全部支持 -i/-o |
| Claude / Codex Skills | **可用** | 9 个 command，独立文件 + 严格 I/O contract |
| LLM-native Generation | **demo stub** | generator/formalizer/evolver 需接入真实 LLM |
| Auto Factor Registration | **未实现** | AlphaSpec → torch factor → FactorRegistry 自动注册 |

### Artifact 输出结构

`astack run` 和 `astack govern` 会自动生成结构化的 artifact 目录：

```
outputs/
├── research/              # astack run 产出
│   ├── ideas.json
│   ├── specs.json
│   ├── reports.json
│   └── ranked.json
├── governance/            # astack govern 产出
│   ├── audits.json
│   ├── migrated.json
│   ├── reports.json
│   ├── improvements.json
│   ├── decisions.json
│   └── summary.json       # GovernanceSummary 汇总报告
├── manifest.json          # 实验元数据（时间、goal、版本）
└── astack_report_*.json   # 兼容旧版导出
```

### Roadmap

| 优先级 | 目标 | 状态 |
|--------|------|------|
| **P0** | 用真实 AlphaGPT 数据跑完整治理流程 | 待执行 |
| **P1** | 接入 Claude API 做真实因子生成 | 待开发 |
| **P2** | AlphaSpec → torch factor 自动注册 | 待设计 |
| **P3** | 多轮自动研究循环（generate → evaluate → evolve → repeat） | 待设计 |
