from astack.config import AStackConfig
from astack.core.pipeline import AlphaPipeline
from astack.adapters.example_adapter import ExampleAdapter

config = AStackConfig(max_ideas=5)
pipeline = AlphaPipeline(config=config, adapter=ExampleAdapter())
result = pipeline.run(
    goal="Generate short-horizon crypto alphas around volume dislocation and volatility compression",
    symbol_set="demo-crypto",
)
print(result)
