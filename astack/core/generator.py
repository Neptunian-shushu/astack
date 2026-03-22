from typing import Dict, List, Optional
from astack.schemas import AlphaIdea, MemoryEntry


class Generator:
    """Demo generator. Replace this with your LLM-backed idea generation.

    Accepts library_context to avoid generating redundant factors
    and to steer exploration toward underexplored families.
    """

    def generate(
        self,
        goal: str,
        memory: List[MemoryEntry],
        max_ideas: int,
        library_context: Optional[Dict] = None,
    ) -> List[AlphaIdea]:
        memory_hint = "; ".join([m.title for m in memory]) if memory else "no memory priors"

        # Build context from library and experience
        ctx_parts = []
        if library_context:
            existing = library_context.get("existing_names", [])
            if existing:
                ctx_parts.append(f"已有因子({len(existing)}个): {', '.join(existing[:10])}")
            families = library_context.get("family_distribution", {})
            if families:
                ctx_parts.append(f"Family分布: {families}")
            rejected = library_context.get("top_rejection_reasons", [])
            if rejected:
                ctx_parts.append(f"常见失败原因: {', '.join(r[0] for r in rejected[:3])}")
            explore = library_context.get("suggested_exploration", [])
            if explore:
                ctx_parts.append(f"建议探索: {', '.join(explore)}")

        library_hint = "; ".join(ctx_parts) if ctx_parts else "no library context"

        ideas = []
        for i in range(max_ideas):
            ideas.append(
                AlphaIdea(
                    name=f"alpha_idea_{i+1}",
                    hypothesis=f"{goal}. Memory: {memory_hint}. Library: {library_hint}. Candidate #{i+1}.",
                    intuition="Abnormal volume and short-horizon volatility patterns may imply directional or mean-reverting edge.",
                    family="microstructure",
                    expected_horizon="1-4 bars",
                    required_fields=["open", "high", "low", "close", "volume"],
                    constraints=["avoid lookahead bias", "prefer implementable formulas", "avoid redundancy with existing library"],
                )
            )
        return ideas
