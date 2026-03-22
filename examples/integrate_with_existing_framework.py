"""Replace this adapter with calls into your existing backtest engine."""

from alphastack.interfaces import EvaluationInterface
from alphastack.schemas import AlphaSpec, ValidationReport


class ExampleCryptoAdapter(EvaluationInterface):
    def __init__(self, framework) -> None:
        self.framework = framework

    def evaluate_alpha(self, alpha_spec: AlphaSpec, symbol_set: str) -> ValidationReport:
        metrics = {"IC": 0.03, "ICIR": 0.9}
        return ValidationReport(
            alpha_name=alpha_spec.name,
            implementable=True,
            lookahead_safe=True,
            data_available=True,
            redundancy_score=0.25,
            quality_score=0.77,
            turnover_risk="medium",
            regime_risk="medium",
            metrics=metrics,
            critique="Connected to existing framework.",
        )
