"""Factor governance tests."""

from astack.core.auditor import FactorAuditor
from astack.core.migrator import FactorMigrator
from astack.core.improver import FactorImprover
from astack.core.decider import FactorDecider
from astack.schemas import AlphaSpec, ValidationReport
from astack.config import AStackConfig
from astack.runtime.agent import ResearchAgent
from astack.adapters.example_adapter import ExampleAdapter


def _make_spec(**kwargs):
    defaults = dict(
        name="test_factor",
        description="volume dislocation factor",
        formula_expression="zscore(volume / sma(volume, 20))",
        required_fields=["close", "volume"],
        parameters={"lookback": 20},
        direction="both",
        implementation_stub="def compute(df): ...",
    )
    defaults.update(kwargs)
    return AlphaSpec(**defaults)


def _make_report(**kwargs):
    defaults = dict(
        alpha_name="test_factor",
        implementable=True, lookahead_safe=True, data_available=True,
        redundancy_score=0.3, quality_score=0.7,
        turnover_risk="medium", regime_risk="medium",
    )
    defaults.update(kwargs)
    return ValidationReport(**defaults)


def test_auditor():
    spec = _make_spec()
    auditor = FactorAuditor()
    audit = auditor.audit(spec)
    assert audit.factor_name == "test_factor"
    assert audit.migratable is True
    assert audit.suggested_action == "migrate"
    assert "成交量" in audit.factor_type


def test_auditor_bad_factor():
    spec = _make_spec(
        formula_expression="",
        required_fields=[],
        implementation_stub="",
        description="",
    )
    auditor = FactorAuditor()
    audit = auditor.audit(spec)
    assert audit.migratable is False
    assert len(audit.potential_issues) >= 2


def test_migrator():
    spec = _make_spec(direction="unknown", name="  My Factor ")
    auditor = FactorAuditor()
    migrator = FactorMigrator()
    audit = auditor.audit(spec)
    migrated = migrator.migrate(spec, audit)
    assert migrated.name == "my_factor"
    assert migrated.direction == "both"


def test_improver():
    spec = _make_spec()
    report = _make_report(quality_score=0.5, turnover_risk="high")
    improver = FactorImprover()
    improvement = improver.improve(spec, report)
    assert improvement.original_name == "test_factor"
    assert improvement.improved_name == "test_factor_v2"
    assert len(improvement.improvements) > 0


def test_decider_admit():
    spec = _make_spec()
    audit = FactorAuditor().audit(spec)
    report = _make_report(quality_score=0.85, redundancy_score=0.2)
    improvement = FactorImprover().improve(spec, report)
    decision = FactorDecider().decide(spec, audit, report, improvement)
    assert decision.decision == "admit"


def test_decider_deprecate():
    spec = _make_spec()
    audit = FactorAuditor().audit(spec)
    report = _make_report(quality_score=0.3)
    improvement = FactorImprover().improve(spec, report)
    decision = FactorDecider().decide(spec, audit, report, improvement)
    assert decision.decision == "deprecate"


def test_decider_upgrade():
    spec = _make_spec()
    audit = FactorAuditor().audit(spec)
    report = _make_report(quality_score=0.6)
    improvement = FactorImprover().improve(spec, report)
    decision = FactorDecider().decide(spec, audit, report, improvement)
    assert decision.decision == "upgrade"
    assert decision.replacement is not None


def test_agent_govern(tmp_path):
    config = AStackConfig(max_ideas=2, memory_dir=tmp_path / "memory")
    agent = ResearchAgent(config=config, adapter=ExampleAdapter())
    specs = [_make_spec(name=f"factor_{i}") for i in range(3)]
    decisions = agent.govern(specs, symbol_set="demo")
    assert len(decisions) == 3
    assert all(d.decision in ("admit", "upgrade", "deprecate", "remove", "hold") for d in decisions)


def test_governance_cli_pipeline(tmp_path):
    """Test governance CLI: audit → migrate → improve → decide."""
    import subprocess, sys, json

    # Create test specs
    specs = [_make_spec(name=f"old_factor_{i}").model_dump() for i in range(2)]
    specs_path = tmp_path / "specs.json"
    specs_path.write_text(json.dumps(specs))

    def run(args):
        return subprocess.run(
            [sys.executable, "-m", "astack.cli"] + args,
            capture_output=True, text=True, timeout=30,
        )

    # audit
    audits_path = tmp_path / "audits.json"
    r = run(["audit", "-i", str(specs_path), "-o", str(audits_path)])
    assert r.returncode == 0

    # migrate
    migrated_path = tmp_path / "migrated.json"
    r = run(["migrate", "-i", str(specs_path), "-o", str(migrated_path)])
    assert r.returncode == 0

    # decide
    decisions_path = tmp_path / "decisions.json"
    r = run(["decide", "-i", str(specs_path), "-o", str(decisions_path)])
    assert r.returncode == 0
    assert decisions_path.exists()

    # govern (full loop)
    gov_path = tmp_path / "gov.json"
    r = run(["govern", "-i", str(specs_path), "-o", str(gov_path)])
    assert r.returncode == 0
    assert gov_path.exists()
