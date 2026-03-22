"""Runtime integration tests."""

from pathlib import Path
from astack.config import AStackConfig
from astack.runtime.agent import ResearchAgent
from astack.adapters.example_adapter import ExampleAdapter


def test_agent_run(tmp_path):
    config = AStackConfig(
        max_ideas=3,
        output_dir=tmp_path / "outputs",
        memory_dir=tmp_path / "memory",
    )
    agent = ResearchAgent(config=config, adapter=ExampleAdapter())
    result = agent.run(goal="volume alpha", symbol_set="demo")

    assert result.export_path is not None
    assert Path(result.export_path).exists()
    assert len(result.ideas) == 3
    assert len(result.specs) == 3
    assert len(result.rankings) > 0


def test_agent_individual_skills(tmp_path):
    config = AStackConfig(max_ideas=2, memory_dir=tmp_path / "memory")
    agent = ResearchAgent(config=config, adapter=ExampleAdapter())

    ideas = agent.generate("momentum factor")
    assert len(ideas) == 2

    specs = agent.formalize(ideas)
    assert len(specs) == 2

    reports = agent.validate(specs)
    assert len(reports) == 2

    deduped = agent.dedupe(reports)
    assert len(deduped) <= len(reports)

    rankings = agent.rank(reports)
    assert len(rankings) == 2

    evolved = agent.evolve(specs)
    assert len(evolved) > 0


def test_agent_library_and_experience(tmp_path):
    config = AStackConfig(
        max_ideas=2,
        output_dir=tmp_path / "outputs",
        memory_dir=tmp_path / "memory",
    )
    agent = ResearchAgent(config=config, adapter=ExampleAdapter())
    agent.run(goal="test alpha", symbol_set="demo")

    # Factor library should have entries
    lib = agent.library.list_all()
    assert len(lib) > 0

    # Experience memory should have entries
    exp_summary = agent.experience.summary()
    assert exp_summary["total_successes"] + exp_summary["total_failures"] > 0


def test_agent_library_context_injected(tmp_path):
    config = AStackConfig(max_ideas=2, memory_dir=tmp_path / "memory")
    agent = ResearchAgent(config=config, adapter=ExampleAdapter())

    ctx = agent._build_library_context()
    assert "existing_names" in ctx
    assert "family_distribution" in ctx
    assert "top_rejection_reasons" in ctx
