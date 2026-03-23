from astack.core.criteria import CriteriaEvaluator
from astack.schemas import AlphaSpec, BacktestMetrics, QuantileResult


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


def _good_quantile_results():
    return [
        QuantileResult(quantile=0.999, label="q10bp", ann_sharpe=1.2, ann_ret=0.15, win_rate=68, long_pct=55, short_pct=45),
        QuantileResult(quantile=0.995, label="q50bp", ann_sharpe=0.9, ann_ret=0.10, win_rate=65, long_pct=52, short_pct=48),
        QuantileResult(quantile=0.99, label="q100bp", ann_sharpe=0.6, ann_ret=0.07, win_rate=62, long_pct=51, short_pct=49),
        QuantileResult(quantile=0.95, label="q500bp", ann_sharpe=0.3, ann_ret=0.03, win_rate=58, long_pct=50, short_pct=50),
    ]


def test_good_factor():
    spec = _make_spec()
    metrics = BacktestMetrics(
        ic_mean=0.035, ic_std=0.02, icir=1.2,
        quantile_results=_good_quantile_results(),
        decile_returns=[-0.05, -0.03, -0.01, 0.0, 0.01, 0.02, 0.03, 0.04, 0.06, 0.08],
        sharpe=1.2,
        annual_returns={"2021": 0.12, "2022": 0.08, "2023": 0.15, "2024": 0.10},
        per_symbol_returns={"SOL": 0.12, "ETH": 0.09, "BTC": 0.07},
        recent_2y_return=0.12, recent_2y_max_drawdown=-0.08,
        train_sharpe=1.2, val_sharpe=1.0, test_sharpe=0.9,
    )
    evaluator = CriteriaEvaluator()
    report = evaluator.evaluate(spec, metrics)
    assert report.verdict == "pass"
    assert report.overall_score >= 0.6
    assert not any(f.triggered for f in report.red_flags)
    # 标准 1 应该用到分位数数据
    c1 = next(s for s in report.criteria_scores if s.criterion_id == 1)
    assert "top_q" in c1.detail


def test_bad_factor_future_data():
    spec = _make_spec()
    metrics = BacktestMetrics(ic_mean=0.25, sharpe=5.0)
    evaluator = CriteriaEvaluator()
    report = evaluator.evaluate(spec, metrics)
    assert report.red_flags[0].triggered  # 10.1 未来数据
    assert report.verdict == "fail"


def test_bad_factor_unbalanced():
    spec = _make_spec()
    metrics = BacktestMetrics(
        ic_mean=0.03, icir=0.8,
        long_return=0.20, short_return=0.15,
        long_short_return=0.05, sharpe=0.8,
    )
    evaluator = CriteriaEvaluator()
    report = evaluator.evaluate(spec, metrics)
    flag = next(f for f in report.red_flags if f.flag_id == "10.2")
    assert flag.triggered


def test_bad_factor_unbalanced_quantile():
    """头部分位数策略严重偏向单方向"""
    spec = _make_spec()
    metrics = BacktestMetrics(
        ic_mean=0.03,
        quantile_results=[
            QuantileResult(quantile=0.999, label="q10bp", ann_sharpe=1.0, ann_ret=0.1,
                           long_pct=95, short_pct=5),  # 95% 多头 → 不均衡
        ],
    )
    evaluator = CriteriaEvaluator()
    report = evaluator.evaluate(spec, metrics)
    flag = next(f for f in report.red_flags if f.flag_id == "10.2")
    assert flag.triggered


def test_too_many_params():
    spec = _make_spec(parameters={f"p{i}": i for i in range(7)})
    metrics = BacktestMetrics()
    evaluator = CriteriaEvaluator()
    report = evaluator.evaluate(spec, metrics)
    c5 = next(s for s in report.criteria_scores if s.criterion_id == 5)
    assert not c5.passed
    flag = next(f for f in report.red_flags if f.flag_id == "10.4")
    assert flag.triggered


def test_recent_failure():
    spec = _make_spec()
    metrics = BacktestMetrics(
        ic_mean=0.02, sharpe=0.5,
        recent_2y_return=-0.05, recent_2y_max_drawdown=-0.35,
    )
    evaluator = CriteriaEvaluator()
    report = evaluator.evaluate(spec, metrics)
    flag = next(f for f in report.red_flags if f.flag_id == "10.5")
    assert flag.triggered


def test_validation_protocol():
    spec = _make_spec()
    metrics = BacktestMetrics(train_sharpe=1.5, val_sharpe=1.3, test_sharpe=1.1)
    evaluator = CriteriaEvaluator()
    report = evaluator.evaluate(spec, metrics)
    assert "val/train 接近" in report.validation_protocol


def test_negative_top_quantile_return():
    """头部分位数收益为负 → 标准 1 得分降低"""
    spec = _make_spec()
    metrics = BacktestMetrics(
        ic_mean=0.02,
        quantile_results=[
            QuantileResult(quantile=0.999, label="q10bp", ann_sharpe=-0.5, ann_ret=-0.05, win_rate=48),
            QuantileResult(quantile=0.99, label="q100bp", ann_sharpe=-0.3, ann_ret=-0.03, win_rate=46),
        ],
    )
    evaluator = CriteriaEvaluator()
    report = evaluator.evaluate(spec, metrics)
    c1 = next(s for s in report.criteria_scores if s.criterion_id == 1)
    assert c1.score < 0.4  # 头部收益为负，不应通过


def test_8_criteria_not_9():
    """确认只有 8 个评分维度"""
    spec = _make_spec()
    metrics = BacktestMetrics(ic_mean=0.03, sharpe=1.0)
    evaluator = CriteriaEvaluator()
    report = evaluator.evaluate(spec, metrics)
    assert len(report.criteria_scores) == 8


def test_criterion_1_high_weight():
    """标准 1 权重应为 3.0（最高）"""
    from astack.core.criteria import CriteriaEvaluator
    spec = _make_spec()
    # 只有标准 1 得分高，其他都低 → overall 仍应较高
    metrics = BacktestMetrics(
        ic_mean=0.05, icir=1.5,
        quantile_results=[
            QuantileResult(quantile=0.999, label="q10bp", ann_sharpe=2.0, ann_ret=0.2, win_rate=72),
            QuantileResult(quantile=0.99, label="q100bp", ann_sharpe=1.5, ann_ret=0.15, win_rate=68),
        ],
    )
    evaluator = CriteriaEvaluator()
    report = evaluator.evaluate(spec, metrics)
    c1 = next(s for s in report.criteria_scores if s.criterion_id == 1)
    assert c1.score > 0.7  # 标准 1 得分高
    # overall 应该被标准 1 的高权重拉高
    assert report.overall_score > 0.5
