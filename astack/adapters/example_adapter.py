from astack.interfaces import EvaluationInterface
from astack.schemas import AlphaSpec, ValidationReport


class ExampleAdapter(EvaluationInterface):
    """Demo adapter. Replace with your real crypto backtest/evaluation adapter."""

    def evaluate_alpha(self, alpha_spec: AlphaSpec, symbol_set: str) -> ValidationReport:
        quality = min(0.95, 0.55 + (len(alpha_spec.formula_expression) % 20) / 50.0)
        redundancy = 0.2 + (len(alpha_spec.name) % 10) / 20.0
        return ValidationReport(
            alpha_name=alpha_spec.name,
            implementable=True,
            lookahead_safe=True,
            data_available=True,
            redundancy_score=redundancy,
            quality_score=quality,
            turnover_risk="medium",
            regime_risk="medium",
            metrics={"IC": round(quality / 10.0, 4), "ICIR": round(quality, 4), "symbol_set": symbol_set},
            warnings=[],
            critique="Demo evaluation only. Replace with real metrics from your framework.",
        )
