from typing import List
from astack.schemas import AlphaSpec


class Evolver:
    """Very light mutation stub for v0.2. Replace with LLM-guided mutation and crossover prompts."""

    def evolve(self, survivors: List[AlphaSpec], max_children: int) -> List[AlphaSpec]:
        children: List[AlphaSpec] = []
        for i, spec in enumerate(survivors[:max_children]):
            mutated = spec.model_copy(deep=True)
            mutated.name = f"{spec.name}_mut{i+1}"
            mutated.description = spec.description + " [mutated variant]"
            mutated.formula_expression = spec.formula_expression + " * rank(volatility_20)"
            children.append(mutated)
        return children
