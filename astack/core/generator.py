from typing import List
from astack.schemas import AlphaIdea, MemoryEntry


class Generator:
    """Demo generator. Replace this with your LLM-backed idea generation."""

    def generate(self, goal: str, memory: List[MemoryEntry], max_ideas: int) -> List[AlphaIdea]:
        memory_hint = "; ".join([m.title for m in memory]) if memory else "no memory priors"
        ideas = []
        for i in range(max_ideas):
            ideas.append(
                AlphaIdea(
                    name=f"alpha_idea_{i+1}",
                    hypothesis=f"{goal}. Guided by {memory_hint}. Candidate #{i+1}.",
                    intuition="Abnormal volume and short-horizon volatility patterns may imply directional or mean-reverting edge.",
                    family="microstructure",
                    expected_horizon="1-4 bars",
                    required_fields=["open", "high", "low", "close", "volume"],
                    constraints=["avoid lookahead bias", "prefer implementable formulas"],
                )
            )
        return ideas
