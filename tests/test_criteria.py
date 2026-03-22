from astack.core.criteria import CriteriaEvaluator
from astack.schemas import AlphaSpec, BacktestMetrics


def _make_spec(**kwargs):
    defaults = dict(
        name="test_alpha",
        description="volume dislocation factor",
        formula_expression="zscore(volume / sma(volume, 20))",
        required_fields=["close", "volume"],
        parameters={"lookback": 20},
        direction="both",
        implementation_stub="def compute(df): ...",
    )
    defaults.update(kwargs)
    return AlphaSpec(**defaults)


def test_good_factor():
    spec = _make_spec()
    metrics = BacktestMetrics(
        ic_mean=0.035, ic_std=0.02, icir=1.2,
        decile_returns=[-0.05, -0.03, -0.01, 0.0, 0.01, 0.02, 0.03, 0.04, 0.06, 0.08],
        long_return=0.15, short_return=-0.10, long_short_return=0.25,
        sharpe=1.8,
        annual_returns={"2021": 0.12, "2022": 0.08, "2023": 0.15, "2024": 0.10},
        per_symbol_returns={"SOL": 0.12, "ETH": 0.09, "BTC": 0.07},
        recent_2y_return=0.12, recent_2y_max_drawdown=-0.08,
        train_sharpe=1.8, val_sharpe=1.5, test_sharpe=1.3,
    )
    evaluator = CriteriaEvaluator()
    report = evaluator.evaluate(spec, metrics)
    assert report.verdict == "pass"
    assert report.overall_score >= 0.6
    assert not any(f.triggered for f in report.red_flags)


def test_bad_factor_future_data():
    spec = _make_spec()
    metrics = BacktestMetrics(ic_mean=0.25, sharpe=5.0)  # 异常高 IC
    evaluator = CriteriaEvaluator()
    report = evaluator.evaluate(spec, metrics)
    assert report.red_flags[0].triggered  # 14.1 未来数据
    assert report.verdict == "fail"


def test_bad_factor_unbalanced():
    spec = _make_spec()
    metrics = BacktestMetrics(
        ic_mean=0.03, icir=0.8,
        long_return=0.20, short_return=0.15,  # 多空同向 → red flag 14.2
        long_short_return=0.05, sharpe=0.8,
    )
    evaluator = CriteriaEvaluator()
    report = evaluator.evaluate(spec, metrics)
    flag_142 = next(f for f in report.red_flags if f.flag_id == "14.2")
    assert flag_142.triggered


def test_too_many_params():
    spec = _make_spec(parameters={f"p{i}": i for i in range(7)})
    metrics = BacktestMetrics()
    evaluator = CriteriaEvaluator()
    report = evaluator.evaluate(spec, metrics)
    c6 = next(s for s in report.criteria_scores if s.criterion_id == 6)
    assert not c6.passed
    flag_144 = next(f for f in report.red_flags if f.flag_id == "14.4")
    assert flag_144.triggered


def test_recent_failure():
    spec = _make_spec()
    metrics = BacktestMetrics(
        ic_mean=0.02, sharpe=0.5,
        recent_2y_return=-0.05, recent_2y_max_drawdown=-0.35,
    )
    evaluator = CriteriaEvaluator()
    report = evaluator.evaluate(spec, metrics)
    flag_145 = next(f for f in report.red_flags if f.flag_id == "14.5")
    assert flag_145.triggered


def test_validation_protocol():
    spec = _make_spec()
    metrics = BacktestMetrics(train_sharpe=1.5, val_sharpe=1.3, test_sharpe=1.1)
    evaluator = CriteriaEvaluator()
    report = evaluator.evaluate(spec, metrics)
    assert "val/train 接近" in report.validation_protocol
