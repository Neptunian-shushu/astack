from alphastack.config import AlphaStackConfig
from alphastack.core.pipeline import AlphaPipeline
from alphastack.adapters.example_adapter import ExampleAdapter

config = AlphaStackConfig(max_ideas=5)
pipeline = AlphaPipeline(config=config, adapter=ExampleAdapter())
result = pipeline.run(
    goal="Generate short-horizon crypto alphas around volume dislocation and volatility compression",
    symbol_set="demo-crypto",
)
print(result)
