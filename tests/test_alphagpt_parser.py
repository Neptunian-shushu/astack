"""Tests for AlphaGPTReportParser using real and synthetic factor_report.json data."""

import json
from pathlib import Path

from astack.adapters.alphagpt_parser import AlphaGPTReportParser
from astack.core.criteria import CriteriaEvaluator
from astack.schemas import AlphaSpec, BacktestMetrics


REAL_REPORT = Path("/Users/bohanshu/Documents/quant/AlphaGPT-main/reports_testsplit/factor_report.json")

SYNTHETIC_REPORT = {
    "generated_at": "2026-03-23",
    "mode": "time-series",
    "dataset_policy": {"data_role": "all"},
    "primary_horizon": 1,
    "factors": {
        "test_factor_good": {
            "description": "Volume spike reversal factor",
            "autocorr_1": 0.85,
            "signal_turnover": 0.12,
            "quantile_mode": "long_short",
            "ts_ic": {
                "1": {
                    "ic_mean": 0.04, "ic_median": 0.038, "ic_std": 0.012,
                    "ic_ir": 3.3, "ic_tstat": 5.5, "pct_positive": 95.0,
                    "pct_significant": 80.0, "n_tokens": 3,
                },
                "4": {
                    "ic_mean": 0.035, "ic_median": 0.033, "ic_std": 0.015,
                    "ic_ir": 2.3, "ic_tstat": 4.0, "pct_positive": 90.0,
                    "pct_significant": 70.0, "n_tokens": 3,
                },
            },
            "signal": {},
            "quantile_signal": {
                "1": {
                    "q10bp": {
                        "quantile": 0.999, "ann_sharpe": 1.2, "ann_ret": 0.15,
                        "cum_ret_mean": 0.08, "avg_n_trades": 30.0,
                        "total_n_trades": 90.0, "avg_trade_win_rate": 68.0,
                        "avg_realized_ret_per_trade_pct": 0.3,
                        "avg_holding_bars": 4.0, "avg_holding_hours": 1.0,
                        "avg_long_pct": 55.0, "avg_short_pct": 45.0,
                    }
                }
            },
            "decile_quality": {
                "1": {
                    "top_decile_mean_raw": 0.00015, "bottom_decile_mean_raw": -0.0001,
                    "top_bottom_spread_raw": 0.00025, "top_bottom_spread_stderr": 0.00005,
                    "top_bottom_spread_tstat": 5.0,
                    "pass_sign": True, "pass_separation": True,
                    "pass_head_tail": True, "separation_sigma": 1.0,
                }
            },
            "test_window_primary": {
                "test_bars": 500, "test_ann_sharpe": 0.9, "test_ann_ret": 0.1,
            },
        },
        "test_factor_bad": {
            "description": "Noisy factor with low IC",
            "autocorr_1": 0.99,
            "signal_turnover": 0.45,
            "quantile_mode": "long_short",
            "ts_ic": {
                "1": {
                    "ic_mean": 0.005, "ic_std": 0.05, "ic_ir": 0.1,
                    "ic_tstat": 0.2, "pct_positive": 55.0,
                    "pct_significant": 10.0, "n_tokens": 3,
                }
            },
            "signal": {},
            "quantile_signal": {
                "1": {
                    "q10bp": {
                        "quantile": 0.999, "ann_sharpe": -0.5, "ann_ret": -0.05,
                        "cum_ret_mean": -0.03, "avg_n_trades": 20.0,
                        "total_n_trades": 60.0, "avg_trade_win_rate": 48.0,
                        "avg_realized_ret_per_trade_pct": -0.1,
                        "avg_holding_bars": 5.0, "avg_holding_hours": 1.25,
                        "avg_long_pct": 50.0, "avg_short_pct": 50.0,
                    }
                }
            },
            "decile_quality": {
                "1": {"pass_sign": False, "pass_separation": False, "pass_head_tail": False}
            },
        },
    },
}


# --- 基础解析（兼容旧 tuple 接口）---

def test_parse_synthetic():
    parser = AlphaGPTReportParser()
    results = parser.parse_dict(SYNTHETIC_REPORT)
    assert len(results) == 2
    names = {r[0] for r in results}
    assert "test_factor_good" in names


def test_good_factor_quality():
    parser = AlphaGPTReportParser()
    results = parser.parse_dict(SYNTHETIC_REPORT)
    name, report, metrics = next(r for r in results if r[0] == "test_factor_good")
    assert report.quality_score > 0.5
    assert report.lookahead_safe is True
    assert report.turnover_risk == "low"
    assert metrics.ic_mean == 0.04
    assert metrics.icir == 3.3
    assert metrics.sharpe == 1.2


def test_bad_factor_quality():
    parser = AlphaGPTReportParser()
    results = parser.parse_dict(SYNTHETIC_REPORT)
    name, report, metrics = next(r for r in results if r[0] == "test_factor_bad")
    assert report.quality_score < 0.3
    assert report.turnover_risk == "high"


def test_metrics_preserve_raw():
    parser = AlphaGPTReportParser()
    results = parser.parse_dict(SYNTHETIC_REPORT)
    _, _, metrics = results[0]
    assert "autocorr_1" in metrics.extra
    assert "quantile_mode" in metrics.extra
    # quantile data is now in quantile_results, not extra
    assert len(metrics.quantile_results) > 0


def test_decile_returns_constructed():
    parser = AlphaGPTReportParser()
    results = parser.parse_dict(SYNTHETIC_REPORT)
    _, _, metrics = next(r for r in results if r[0] == "test_factor_good")
    assert len(metrics.decile_returns) == 10
    assert metrics.decile_returns[0] < metrics.decile_returns[-1]


def test_criteria_evaluator_accepts_parsed_metrics():
    parser = AlphaGPTReportParser()
    results = parser.parse_dict(SYNTHETIC_REPORT)
    _, _, metrics = next(r for r in results if r[0] == "test_factor_good")
    spec = AlphaSpec(
        name="test_factor_good", description="Volume spike reversal",
        formula_expression="zscore(volume / sma(volume, 20))",
        required_fields=["close", "volume"], parameters={"lookback": 20},
    )
    evaluator = CriteriaEvaluator()
    eval_report = evaluator.evaluate(spec, metrics)
    assert eval_report.verdict in ("pass", "marginal", "fail")
    assert eval_report.overall_score > 0


# --- ParsedFactor 接口（新）---

def test_parse_file_returns_parsed_factors():
    parser = AlphaGPTReportParser()
    results = parser.parse_file_to_parsed(SYNTHETIC_REPORT)
    assert len(results) == 2
    pf = results[0]
    assert hasattr(pf, "completeness")
    assert hasattr(pf, "confidence")
    assert hasattr(pf, "missing_fields")


def test_completeness_scoring():
    parser = AlphaGPTReportParser()
    results = parser.parse_file_to_parsed(SYNTHETIC_REPORT)
    good = next(r for r in results if r.name == "test_factor_good")
    bad = next(r for r in results if r.name == "test_factor_bad")
    # good has test_window with bars > 0
    assert good.completeness > bad.completeness


def test_confidence_levels():
    parser = AlphaGPTReportParser()
    results = parser.parse_file_to_parsed(SYNTHETIC_REPORT)
    good = next(r for r in results if r.name == "test_factor_good")
    assert good.confidence == "high"  # has test_window with bars > 0


def test_batch_directory(tmp_path):
    # Write two report files
    (tmp_path / "factor_report_1.json").write_text(json.dumps(SYNTHETIC_REPORT))
    report2 = {**SYNTHETIC_REPORT, "factors": {"extra_factor": SYNTHETIC_REPORT["factors"]["test_factor_good"]}}
    (tmp_path / "factor_report_2.json").write_text(json.dumps(report2))

    parser = AlphaGPTReportParser()
    results, summary = parser.parse_directory(str(tmp_path))
    assert summary.total_files == 2
    assert summary.total_factors == 3  # 2 + 1
    assert summary.avg_quality > 0
    assert len(summary.top_factors) > 0


def test_batch_summary_structure(tmp_path):
    (tmp_path / "factor_report.json").write_text(json.dumps(SYNTHETIC_REPORT))
    parser = AlphaGPTReportParser()
    _, summary = parser.parse_directory(str(tmp_path))
    d = summary.to_dict()
    assert "total_factors" in d
    assert "by_confidence" in d
    assert "avg_quality" in d
    assert "top_factors" in d
    assert "common_warnings" in d


# --- 真实文件测试 ---

def test_parse_real_file():
    if not REAL_REPORT.exists():
        return
    parser = AlphaGPTReportParser()
    results = parser.parse_file(str(REAL_REPORT))
    assert len(results) >= 1
    for pf in results:
        assert pf.report.alpha_name == pf.name
        assert 0 <= pf.report.quality_score <= 1
        assert pf.metrics.ic_mean is not None
        assert pf.report.metrics.get("source") == "alphagpt"
        assert pf.confidence in ("high", "medium", "low")
