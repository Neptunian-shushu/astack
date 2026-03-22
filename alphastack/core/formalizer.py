from alphastack.schemas import AlphaIdea, AlphaSpec


class Formalizer:
    """Converts AlphaIdea into AlphaSpec. Replace with LLM- or rule-based formalization."""

    def formalize(self, idea: AlphaIdea) -> AlphaSpec:
        formula = "zscore(volume / sma(volume, 20)) * -zscore(abs(return_1))"
        stub = (
            f"def compute_{idea.name}(df):\n"
            "    volume_ratio = df['volume'] / df['volume'].rolling(20).mean()\n"
            "    abs_ret = df['close'].pct_change().abs()\n"
            "    signal = ((volume_ratio - volume_ratio.rolling(20).mean()) / volume_ratio.rolling(20).std()) * -((abs_ret - abs_ret.rolling(20).mean()) / abs_ret.rolling(20).std())\n"
            "    return signal\n"
        )
        return AlphaSpec(
            name=idea.name,
            description=idea.hypothesis,
            formula_expression=formula,
            required_fields=idea.required_fields,
            parameters={"lookback": 20},
            direction="both",
            implementation_stub=stub,
        )
