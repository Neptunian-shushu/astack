"""
因子改进器 — 基于评估结果给出升级版本

Demo 实现：简单变异。
真实场景应由 LLM 基于审计报告和回测结果，针对性改进因子。
"""

from typing import List
from astack.schemas import AlphaSpec, ImprovementSpec, ValidationReport


class FactorImprover:

    def improve(self, spec: AlphaSpec, report: ValidationReport) -> ImprovementSpec:
        improvements = []
        new_spec = spec.model_copy(deep=True)

        # 基于评估结果判断改进方向
        if report.turnover_risk == "high":
            improvements.append("加入平滑处理降低换手")
            new_spec.formula_expression = f"ema({spec.formula_expression}, 3)"

        if report.redundancy_score > 0.5:
            improvements.append("正交化处理降低冗余")

        if report.quality_score < 0.6:
            improvements.append("加入波动率调整增强稳健性")
            new_spec.formula_expression = f"({spec.formula_expression}) / realized_vol_20"

        if not improvements:
            improvements.append("微调参数窗口")
            if "lookback" in new_spec.parameters:
                new_spec.parameters["lookback"] = int(new_spec.parameters["lookback"] * 1.5)

        new_spec.name = f"{spec.name}_v2"
        new_spec.description = f"{spec.description} [improved: {'; '.join(improvements)}]"

        risk_notes = []
        if report.regime_risk in ("medium", "high"):
            risk_notes.append("原因子有 regime 风险，改进版需重新验证")

        return ImprovementSpec(
            original_name=spec.name,
            improved_name=new_spec.name,
            improvements=improvements,
            new_spec=new_spec,
            expected_gains="降低换手/冗余，提高稳健性",
            risk_notes=risk_notes,
        )
