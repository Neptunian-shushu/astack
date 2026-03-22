from astack.interfaces import EvaluationInterface
from astack.schemas import AlphaSpec, ValidationReport


class Validator:
    def __init__(self, evaluator: EvaluationInterface) -> None:
        self.evaluator = evaluator

    def validate(self, alpha_spec: AlphaSpec, symbol_set: str) -> ValidationReport:
        return self.evaluator.evaluate_alpha(alpha_spec=alpha_spec, symbol_set=symbol_set)
