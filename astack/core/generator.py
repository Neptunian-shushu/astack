from typing import List, Optional, TYPE_CHECKING
from astack.schemas import AlphaIdea, MemoryEntry

if TYPE_CHECKING:
    from astack.core.search import SearchContext


class Generator:
    """Demo generator. Replace this with your LLM-backed idea generation.

    Accepts SearchContext to guide generation toward underexplored spaces
    and away from known failure patterns.
    """

    def generate(
        self,
        goal: str,
        memory: List[MemoryEntry],
        max_ideas: int,
        search_context: Optional["SearchContext"] = None,
    ) -> List[AlphaIdea]:
        memory_hint = "; ".join([m.title for m in memory]) if memory else "no memory priors"
        search_hint = search_context.to_prompt() if search_context else "no search constraints"

        ideas = []
        for i in range(max_ideas):
            ideas.append(
                AlphaIdea(
                    name=f"alpha_idea_{i+1}",
                    hypothesis=f"{goal}. Memory: {memory_hint}. Search: {search_hint}. Candidate #{i+1}.",
                    intuition="Abnormal volume and short-horizon volatility patterns may imply directional or mean-reverting edge.",
                    family="microstructure",
                    expected_horizon="1-4 bars",
                    required_fields=["open", "high", "low", "close", "volume"],
                    constraints=["avoid lookahead bias", "prefer implementable formulas", "follow search strategy"],
                )
            )
        return ideas
