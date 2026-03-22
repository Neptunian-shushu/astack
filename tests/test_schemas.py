"""Schema roundtrip tests — serialize and deserialize."""

from astack.schemas import (
    AlphaIdea,
    AlphaSpec,
    BacktestMetrics,
    CriterionScore,
    FactorEvalReport,
    FactorRecord,
    MemoryEntry,
    RankedAlpha,
    RedFlag,
    ValidationReport,
)


def test_alpha_idea_roundtrip():
    idea = AlphaIdea(
        name="test", hypothesis="h", intuition="i",
        family="f", expected_horizon="1h", required_fields=["close"],
    )
    data = idea.model_dump_json()
    restored = AlphaIdea.model_validate_json(data)
    assert restored.name == "test"


def test_alpha_spec_roundtrip():
    spec = AlphaSpec(
        name="test", description="d",
        formula_expression="zscore(x)", required_fields=["close"],
        parameters={"lookback": 20}, direction="both",
    )
    data = spec.model_dump_json()
    restored = AlphaSpec.model_validate_json(data)
    assert restored.parameters["lookback"] == 20


def test_validation_report_roundtrip():
    report = ValidationReport(
        alpha_name="test", implementable=True, lookahead_safe=True,
        data_available=True, redundancy_score=0.1, quality_score=0.8,
        turnover_risk="low", regime_risk="medium",
    )
    data = report.model_dump_json()
    restored = ValidationReport.model_validate_json(data)
    assert restored.quality_score == 0.8


def test_ranked_alpha_roundtrip():
    ranked = RankedAlpha(alpha_name="test", rank_score=0.9, rationale="good")
    data = ranked.model_dump_json()
    restored = RankedAlpha.model_validate_json(data)
    assert restored.rank_score == 0.9


def test_memory_entry_roundtrip():
    entry = MemoryEntry(kind="success", title="a", content="b", tags=["t"])
    data = entry.model_dump_json()
    restored = MemoryEntry.model_validate_json(data)
    assert restored.kind == "success"


def test_factor_record_roundtrip():
    spec = AlphaSpec(
        name="test", description="d",
        formula_expression="x", required_fields=["close"],
    )
    record = FactorRecord(name="test", spec=spec, status="testing", family="momentum")
    data = record.model_dump_json()
    restored = FactorRecord.model_validate_json(data)
    assert restored.family == "momentum"
    assert restored.spec.name == "test"


def test_backtest_metrics_roundtrip():
    m = BacktestMetrics(ic_mean=0.03, sharpe=1.5, annual_returns={"2024": 0.1})
    data = m.model_dump_json()
    restored = BacktestMetrics.model_validate_json(data)
    assert restored.ic_mean == 0.03
    assert restored.annual_returns["2024"] == 0.1


def test_factor_eval_report_roundtrip():
    report = FactorEvalReport(
        alpha_name="test", overall_score=0.7, verdict="pass",
        criteria_scores=[CriterionScore(criterion_id=1, name="predictive", score=0.8, passed=True)],
        red_flags=[RedFlag(flag_id="11.1", description="lookahead", triggered=False)],
    )
    data = report.model_dump_json()
    restored = FactorEvalReport.model_validate_json(data)
    assert restored.verdict == "pass"
    assert len(restored.criteria_scores) == 1
