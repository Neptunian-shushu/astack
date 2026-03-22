"""
AStack ↔ AlphaGPT 最小接入示例

展示如何写一个 adapter 将 astack 接入你的回测框架。
这个 adapter 只需要实现 EvaluationInterface.evaluate_alpha()，
将 AlphaSpec 转成你的框架能理解的格式，调用回测，再把结果转回 ValidationReport。

使用方式：
  1. 替换 YourBacktestEngine 为你的真实回测类
  2. 用 ResearchAgent 替代 AlphaPipeline
  3. astack 负责生成/评估/进化，AlphaGPT 负责回测

数据流：
  astack generate → AlphaSpec → adapter → AlphaGPT backtest → ValidationReport → astack rank/evolve
"""

from pathlib import Path
from astack.interfaces import EvaluationInterface
from astack.schemas import AlphaSpec, ValidationReport
from astack.config import AStackConfig
from astack.runtime.agent import ResearchAgent


# ---------------------------------------------------------------------------
# Step 1: 实现你的 adapter
# ---------------------------------------------------------------------------

class AlphaGPTAdapter(EvaluationInterface):
    """
    将 astack 的 AlphaSpec 接入 AlphaGPT 回测框架。

    你需要替换这里的伪代码为真实的回测调用。
    """

    def __init__(self, backtest_engine=None):
        self.engine = backtest_engine

    def evaluate_alpha(self, alpha_spec: AlphaSpec, symbol_set: str) -> ValidationReport:
        # --- 真实接入时替换以下内容 ---

        # 1. 将 AlphaSpec 转成你的框架能理解的格式
        # factor_code = alpha_spec.implementation_stub
        # factor_name = alpha_spec.name
        # fields = alpha_spec.required_fields

        # 2. 调用你的回测引擎
        # result = self.engine.run_factor_test(
        #     factor_code=factor_code,
        #     symbol_set=symbol_set,
        #     fields=fields,
        # )

        # 3. 解析回测结果，转成 ValidationReport
        # return ValidationReport(
        #     alpha_name=alpha_spec.name,
        #     implementable=result.implementable,
        #     lookahead_safe=result.lookahead_check_passed,
        #     data_available=result.data_check_passed,
        #     redundancy_score=result.correlation_with_existing,
        #     quality_score=result.composite_score,
        #     turnover_risk=result.turnover_category,
        #     regime_risk=result.regime_category,
        #     metrics={
        #         "IC": result.ic_mean,
        #         "ICIR": result.icir,
        #         "sharpe": result.sharpe,
        #         "long_return": result.long_return,
        #         "short_return": result.short_return,
        #     },
        #     warnings=result.warnings,
        #     critique=result.critique_text,
        # )

        # --- 伪实现（演示用）---
        quality = min(0.95, 0.55 + (len(alpha_spec.formula_expression) % 20) / 50.0)
        return ValidationReport(
            alpha_name=alpha_spec.name,
            implementable=True,
            lookahead_safe=True,
            data_available=True,
            redundancy_score=0.25,
            quality_score=quality,
            turnover_risk="medium",
            regime_risk="medium",
            metrics={"IC": 0.03, "ICIR": 0.9, "sharpe": 1.2, "symbol_set": symbol_set},
            critique="AlphaGPT adapter demo. Replace with real backtest.",
        )


# ---------------------------------------------------------------------------
# Step 2: 用 ResearchAgent 跑完整 workflow
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # 初始化
    config = AStackConfig(max_ideas=5, output_dir=Path("outputs"))
    adapter = AlphaGPTAdapter()
    agent = ResearchAgent(config=config, adapter=adapter)

    # 完整 loop
    result = agent.run(
        goal="Generate short-horizon alphas around volume dislocation",
        symbol_set="SOL,ETH,BTC",
    )

    print(f"Generated {len(result.ideas)} ideas")
    print(f"Survived {len(result.survivors)} factors")
    print(f"Evolved {len(result.evolved)} variants")
    print(f"Ranked {len(result.rankings)} total")
    print(f"Report: {result.export_path}")

    # 也可以单独调用某个 skill
    print("\n--- 单独调用 generate ---")
    ideas = agent.generate("momentum reversal factors")
    for idea in ideas:
        print(f"  {idea.name}: {idea.hypothesis[:60]}")

    # 查看 factor library
    print(f"\n--- Factor Library ---")
    lib = agent.library.summary()
    print(f"Total: {lib['total']}, By status: {lib['by_status']}")

    # 查看 experience memory
    print(f"\n--- Experience Summary ---")
    exp = agent.experience.summary()
    print(f"Successes: {exp['total_successes']}, Failures: {exp['total_failures']}")
