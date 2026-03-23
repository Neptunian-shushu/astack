"""Tests for the intelligence layer: search, pattern memory, library diagnostics."""

from pathlib import Path
from astack.core.pattern_memory import PatternMemory
from astack.core.search import SearchStrategy
from astack.core.experience import ExperienceMemory
from astack.core.factor_library import FactorLibrary
from astack.schemas import AlphaSpec, FactorRecord, MemoryEntry
from astack.config import AStackConfig
from astack.runtime.agent import ResearchAgent
from astack.adapters.example_adapter import ExampleAdapter


def _entries(kind, n, tags=None):
    return [
        MemoryEntry(kind=kind, title=f"factor_{i}", content=f"test {kind}",
                    tags=tags or ["medium", "medium"])
        for i in range(n)
    ]


# --- PatternMemory ---

def test_pattern_memory_extract_patterns():
    pm = PatternMemory()
    successes = _entries("success", 5, tags=["momentum", "low_turnover"])
    failures = _entries("failure", 3, tags=["momentum", "high_turnover"])
    patterns = pm.extract_patterns(successes, failures)
    assert len(patterns) > 0
    types = {p.pattern_type for p in patterns}
    assert "success" in types
    assert "failure" in types


def test_pattern_memory_search_constraints():
    pm = PatternMemory()
    successes = _entries("success", 5, tags=["volume", "stable"])
    failures = _entries("failure", 3, tags=["overfit", "unstable"])
    constraints = pm.get_search_constraints(successes, failures)
    assert "avoid_patterns" in constraints
    assert "explore_directions" in constraints
    assert "prefer_patterns" in constraints


def test_pattern_memory_risk_detection():
    pm = PatternMemory()
    successes = _entries("success", 3, tags=["momentum"])
    failures = _entries("failure", 5, tags=["momentum"])
    patterns = pm.extract_patterns(successes, failures)
    risk_patterns = [p for p in patterns if p.pattern_type == "risk"]
    assert len(risk_patterns) > 0
    assert "不稳定" in risk_patterns[0].description


# --- FactorLibrary.diagnostics ---

def test_library_diagnostics(tmp_path):
    lib = FactorLibrary(tmp_path)
    spec = AlphaSpec(name="test", description="d", formula_expression="x", required_fields=["close"])
    lib.add(FactorRecord(name="f1", spec=spec, status="admitted", family="momentum"))
    lib.add(FactorRecord(name="f2", spec=spec, status="admitted", family="momentum"))
    lib.add(FactorRecord(name="f3", spec=spec, status="admitted", family="volume"))

    diag = lib.diagnostics()
    assert diag["total_admitted"] == 3
    assert "momentum" in diag["family_distribution"]
    assert len(diag["missing_families"]) > 0  # should have many missing
    # momentum at 66.7% should be overcrowded
    assert "momentum" in diag["overcrowded_families"]


def test_library_diagnostics_empty(tmp_path):
    lib = FactorLibrary(tmp_path)
    diag = lib.diagnostics()
    assert diag["total_admitted"] == 0
    assert len(diag["missing_families"]) > 0


# --- SearchStrategy ---

def test_search_strategy_builds_context(tmp_path):
    lib = FactorLibrary(tmp_path / "lib")
    exp = ExperienceMemory(tmp_path / "exp")

    # Add some experience
    exp.record(MemoryEntry(kind="success", title="vol_alpha", content="good", tags=["volume"]))
    exp.record(MemoryEntry(kind="failure", title="bad_mom", content="failed", tags=["momentum"]))
    exp.record(MemoryEntry(kind="failure", title="bad_mom2", content="failed again", tags=["momentum"]))

    strategy = SearchStrategy(lib, exp)
    ctx = strategy.build_context()

    assert isinstance(ctx.prompt_hint, str)
    assert len(ctx.missing_spaces) > 0  # empty library → many missing
    prompt = ctx.to_prompt()
    assert "空白" in prompt or "探索" in prompt


# --- Integration: agent uses search context ---

def test_agent_uses_search_in_generate(tmp_path):
    config = AStackConfig(max_ideas=2, memory_dir=tmp_path / "memory")
    agent = ResearchAgent(config=config, adapter=ExampleAdapter())

    # First run populates experience
    agent.run(goal="test", symbol_set="demo")

    # Second generate should use search context
    ideas = agent.generate("volume alpha")
    assert len(ideas) == 2
    # The hypothesis should contain search hints
    assert "Search:" in ideas[0].hypothesis
