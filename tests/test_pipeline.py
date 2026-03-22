from alphastack.config import AlphaStackConfig
from alphastack.core.pipeline import AlphaPipeline
from alphastack.adapters.example_adapter import ExampleAdapter


def test_pipeline_runs(tmp_path):
    config = AlphaStackConfig(output_dir=tmp_path / "outputs", memory_dir=tmp_path / "memory")
    pipeline = AlphaPipeline(config=config, adapter=ExampleAdapter())
    out = pipeline.run(goal="volume dislocation alpha", symbol_set="demo")
    assert out.exists()
