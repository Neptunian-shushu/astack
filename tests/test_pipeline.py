from astack.config import AStackConfig
from astack.core.pipeline import AlphaPipeline
from astack.adapters.example_adapter import ExampleAdapter


def test_pipeline_runs(tmp_path):
    config = AStackConfig(output_dir=tmp_path / "outputs", memory_dir=tmp_path / "memory")
    pipeline = AlphaPipeline(config=config, adapter=ExampleAdapter())
    out = pipeline.run(goal="volume dislocation alpha", symbol_set="demo")
    assert out.exists()
