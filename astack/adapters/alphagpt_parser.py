"""
AlphaGPT Report Parser

将 AlphaGPT 的 factor_report.json 解析为 astack 标准格式：
  factor_report.json → ValidationReport + BacktestMetrics

支持：
- 单文件解析
- 批量目录解析（合并多个 factor_report.json）
- 报告完整性和指标置信度评估
- 原始报告保留（extra 字段）

使用方式：
  parser = AlphaGPTReportParser()

  # 单文件
  results = parser.parse_file("path/to/factor_report.json")

  # 批量目录
  results, summary = parser.parse_directory("path/to/reports/")
"""

import json
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple

from astack.schemas import BacktestMetrics, QuantileAnnualReturn, QuantileResult, ValidationReport


class ParsedFactor:
    """单个因子的解析结果，包含完整性评估"""
    def __init__(
        self,
        name: str,
        report: ValidationReport,
        metrics: BacktestMetrics,
        completeness: float,
        confidence: str,
        missing_fields: List[str],
        source_file: str = "",
    ):
        self.name = name
        self.report = report
        self.metrics = metrics
        self.completeness = completeness      # 0~1, 字段完整度
        self.confidence = confidence           # "high" | "medium" | "low"
        self.missing_fields = missing_fields   # 缺失的关键字段
        self.source_file = source_file


class BatchSummary:
    """批量解析汇总"""
    def __init__(
        self,
        total_factors: int,
        total_files: int,
        by_confidence: Dict[str, int],
        by_turnover_risk: Dict[str, int],
        avg_quality: float,
        avg_completeness: float,
        top_factors: List[Tuple[str, float]],
        common_warnings: List[Tuple[str, int]],
        common_missing: List[Tuple[str, int]],
    ):
        self.total_factors = total_factors
        self.total_files = total_files
        self.by_confidence = by_confidence
        self.by_turnover_risk = by_turnover_risk
        self.avg_quality = avg_quality
        self.avg_completeness = avg_completeness
        self.top_factors = top_factors
        self.common_warnings = common_warnings
        self.common_missing = common_missing

    def to_dict(self) -> dict:
        return {
            "total_factors": self.total_factors,
            "total_files": self.total_files,
            "by_confidence": self.by_confidence,
            "by_turnover_risk": self.by_turnover_risk,
            "avg_quality": round(self.avg_quality, 3),
            "avg_completeness": round(self.avg_completeness, 3),
            "top_factors": [{"name": n, "quality": round(q, 3)} for n, q in self.top_factors],
            "common_warnings": [{"warning": w, "count": c} for w, c in self.common_warnings],
            "common_missing": [{"field": f, "count": c} for f, c in self.common_missing],
        }


class AlphaGPTReportParser:
    """解析 AlphaGPT factor_report.json"""

    # 关键字段及其权重（用于完整性评分）
    CRITICAL_FIELDS = {
        "ts_ic": 0.25,
        "quantile_signal": 0.2,
        "decile_quality": 0.15,
        "signal_turnover": 0.1,
        "test_window_primary": 0.2,
        "validation_window_primary": 0.1,
    }

    def parse_file(self, path: str) -> List[ParsedFactor]:
        """解析单个报告文件"""
        data = json.loads(Path(path).read_text())
        return self._parse_dict(data, source_file=str(path))

    def parse_directory(self, dir_path: str) -> Tuple[List[ParsedFactor], BatchSummary]:
        """批量解析目录下所有 factor_report*.json"""
        p = Path(dir_path)
        files = sorted(p.glob("*factor_report*.json")) + sorted(p.glob("**/factor_report*.json"))
        seen = set()
        all_results: List[ParsedFactor] = []

        for f in files:
            if f.resolve() in seen:
                continue
            seen.add(f.resolve())
            results = self.parse_file(str(f))
            all_results.extend(results)

        summary = self._build_batch_summary(all_results, len(seen))
        return all_results, summary

    def parse_dict(self, data: dict) -> List[Tuple[str, ValidationReport, BacktestMetrics]]:
        """兼容旧接口：返回 [(name, report, metrics), ...]"""
        parsed = self._parse_dict(data)
        return [(p.name, p.report, p.metrics) for p in parsed]

    def parse_file_to_parsed(self, data_or_path) -> List[ParsedFactor]:
        """返回 ParsedFactor 对象列表（支持 dict 或文件路径）"""
        if isinstance(data_or_path, dict):
            return self._parse_dict(data_or_path)
        return self.parse_file(str(data_or_path))

    # ------------------------------------------------------------------
    # 核心解析
    # ------------------------------------------------------------------

    def _parse_dict(self, data: dict, source_file: str = "") -> List[ParsedFactor]:
        results = []
        primary_h = str(data.get("primary_horizon", 1))
        factors = data.get("factors", {})

        for name, fd in factors.items():
            metrics = self._extract_metrics(fd, primary_h)
            report = self._build_report(name, fd, metrics, primary_h)
            completeness, missing = self._assess_completeness(fd, primary_h)
            confidence = self._assess_confidence(completeness, report, metrics)
            results.append(ParsedFactor(
                name=name, report=report, metrics=metrics,
                completeness=completeness, confidence=confidence,
                missing_fields=missing, source_file=source_file,
            ))

        return results

    def _extract_metrics(self, fd: dict, primary_h: str) -> BacktestMetrics:
        """从单个因子的报告数据中提取 BacktestMetrics"""
        ts_ic = fd.get("ts_ic", {}).get(primary_h, {})
        ic_mean = ts_ic.get("ic_mean")
        ic_std = ts_ic.get("ic_std")
        icir = ts_ic.get("ic_ir")

        # --- 提取所有分位数策略结果 ---
        qsig = fd.get("quantile_signal", {}).get(primary_h, {})
        quantile_results = []
        for label, qdata in qsig.items():
            # 年度收益（如果 AlphaGPT 导出了）
            raw_annual = qdata.get("annual_returns", {})
            annual = {
                yr: QuantileAnnualReturn(**vals) if isinstance(vals, dict) else QuantileAnnualReturn(cum_ret=vals)
                for yr, vals in raw_annual.items()
            }
            # 月度收益
            raw_monthly = qdata.get("monthly_returns", {})
            monthly = {
                mo: QuantileAnnualReturn(**vals) if isinstance(vals, dict) else QuantileAnnualReturn(cum_ret=vals)
                for mo, vals in raw_monthly.items()
            }
            quantile_results.append(QuantileResult(
                quantile=qdata.get("quantile", 0),
                label=label,
                ann_sharpe=qdata.get("ann_sharpe"),
                ann_ret=qdata.get("ann_ret"),
                cum_ret=qdata.get("cum_ret_mean"),
                avg_n_trades=qdata.get("avg_n_trades"),
                win_rate=qdata.get("avg_trade_win_rate"),
                avg_holding_bars=qdata.get("avg_holding_bars"),
                long_pct=qdata.get("avg_long_pct"),
                short_pct=qdata.get("avg_short_pct"),
                annual_returns=annual,
                monthly_returns=monthly,
                per_symbol_returns=qdata.get("per_symbol_returns", {}),
            ))
        # 按分位数从高到低排序（0.999 = 最严格在前）
        quantile_results.sort(key=lambda q: q.quantile, reverse=True)

        # 最优分位数（最严格的正收益分位数）
        best_q_data = self._best_quantile(qsig)
        sharpe = best_q_data.get("ann_sharpe") if best_q_data else None
        q_ann_ret = best_q_data.get("ann_ret") if best_q_data else None

        # 兼容旧字段
        sig = fd.get("signal", {}).get(primary_h, {})
        if sharpe is None:
            sharpe = sig.get("ann_sharpe")

        long_pct = best_q_data.get("avg_long_pct", 50) if best_q_data else 50
        short_pct = best_q_data.get("avg_short_pct", 50) if best_q_data else 50
        long_return = q_ann_ret * (long_pct / 100) if q_ann_ret and long_pct else None
        short_return = q_ann_ret * (short_pct / 100) if q_ann_ret and short_pct else None

        decile = fd.get("decile_quality", {}).get(primary_h, {})
        top_decile = decile.get("top_decile_mean_raw")
        bottom_decile = decile.get("bottom_decile_mean_raw")
        decile_returns = []
        if top_decile is not None and bottom_decile is not None:
            for i in range(10):
                decile_returns.append(bottom_decile + (top_decile - bottom_decile) * i / 9)

        # 多持仓周期：每个 horizon 的最优分位数 sharpe
        holding_period_sharpes = {}
        for h in fd.get("ts_ic", {}):
            h_qsig = fd.get("quantile_signal", {}).get(h, {})
            h_best = self._best_quantile(h_qsig)
            s = (h_best.get("ann_sharpe") if h_best else None) or fd.get("signal", {}).get(h, {}).get("ann_sharpe")
            if s is not None:
                holding_period_sharpes[f"h{h}"] = s

        test_win = fd.get("test_window_primary", {})
        val_win = fd.get("validation_window_primary", {})
        train_sharpe = sharpe
        val_sharpe = val_win.get("ann_sharpe") if val_win else None
        test_sharpe = test_win.get("test_ann_sharpe") if test_win else None

        return BacktestMetrics(
            ic_mean=ic_mean, ic_std=ic_std, icir=icir,
            decile_returns=decile_returns,
            quantile_results=quantile_results,
            long_return=long_return, short_return=short_return,
            long_short_return=(q_ann_ret if q_ann_ret else None),
            sharpe=sharpe,
            holding_period_sharpes=holding_period_sharpes,
            train_sharpe=train_sharpe, val_sharpe=val_sharpe, test_sharpe=test_sharpe,
            extra={
                "autocorr_1": fd.get("autocorr_1"),
                "signal_turnover": fd.get("signal_turnover"),
                "quantile_mode": fd.get("quantile_mode"),
                "decile_quality": fd.get("decile_quality", {}),
                "test_window_primary": test_win,
                "validation_window_primary": val_win,
            },
        )

    def _build_report(self, name: str, fd: dict, metrics: BacktestMetrics, primary_h: str) -> ValidationReport:
        warnings = []
        lookahead_safe = True
        if metrics.ic_mean is not None and abs(metrics.ic_mean) > 0.15:
            lookahead_safe = False
            warnings.append(f"IC 异常高({metrics.ic_mean:.4f})，可能存在未来数据")

        quality_score = self._compute_quality(metrics, fd, primary_h)

        autocorr = fd.get("autocorr_1", 0)
        redundancy_score = min(1.0, max(0.0, autocorr))

        turnover = fd.get("signal_turnover", 0)
        if turnover > 0.3:
            turnover_risk = "high"
        elif turnover > 0.15:
            turnover_risk = "medium"
        else:
            turnover_risk = "low"

        decile = fd.get("decile_quality", {}).get(primary_h, {})
        if not decile.get("pass_head_tail", True):
            warnings.append("十分组首尾收益差不显著")
        if not decile.get("pass_sign", True):
            warnings.append("十分组方向不正确")

        test_win = fd.get("test_window_primary", {})
        if test_win.get("test_bars", 0) == 0:
            warnings.append("无测试集数据")
        elif test_win.get("test_ann_sharpe") is not None and test_win["test_ann_sharpe"] < 0:
            warnings.append(f"测试集夏普为负({test_win['test_ann_sharpe']:.2f})")

        return ValidationReport(
            alpha_name=name, implementable=True, lookahead_safe=lookahead_safe,
            data_available=True, redundancy_score=redundancy_score,
            quality_score=quality_score, turnover_risk=turnover_risk, regime_risk="medium",
            metrics={
                "IC": metrics.ic_mean, "ICIR": metrics.icir,
                "sharpe": metrics.sharpe, "ann_ret": metrics.long_short_return,
                "source": "alphagpt",
            },
            warnings=warnings,
            critique=fd.get("description", ""),
        )

    # ------------------------------------------------------------------
    # 完整性和置信度
    # ------------------------------------------------------------------

    def _assess_completeness(self, fd: dict, primary_h: str) -> Tuple[float, List[str]]:
        """评估报告完整度 0~1 和缺失字段"""
        score = 0.0
        missing = []

        for field_key, weight in self.CRITICAL_FIELDS.items():
            if field_key in ("ts_ic", "quantile_signal", "decile_quality"):
                val = fd.get(field_key, {}).get(primary_h)
                if val:
                    score += weight
                else:
                    missing.append(field_key)
            elif field_key == "test_window_primary":
                tw = fd.get(field_key, {})
                if tw and tw.get("test_bars", 0) > 0:
                    score += weight
                else:
                    missing.append("test_window (无测试集)")
            elif field_key == "validation_window_primary":
                vw = fd.get(field_key)
                if vw:
                    score += weight
                else:
                    missing.append("validation_window")
            else:
                if fd.get(field_key) is not None:
                    score += weight
                else:
                    missing.append(field_key)

        return round(score, 3), missing

    def _assess_confidence(self, completeness: float, report: ValidationReport, metrics: BacktestMetrics) -> str:
        """评估指标置信度"""
        if completeness >= 0.8 and metrics.test_sharpe is not None:
            return "high"
        if completeness >= 0.5 and metrics.ic_mean is not None:
            return "medium"
        return "low"

    # ------------------------------------------------------------------
    # 质量评分
    # ------------------------------------------------------------------

    def _compute_quality(self, metrics: BacktestMetrics, fd: dict, primary_h: str) -> float:
        scores = []
        if metrics.ic_mean is not None:
            scores.append(min(abs(metrics.ic_mean) / 0.05, 1.0) * 0.3)
        if metrics.icir is not None:
            scores.append(min(abs(metrics.icir) / 3.0, 1.0) * 0.2)
        if metrics.sharpe is not None:
            scores.append(max(0, min(metrics.sharpe / 2.0, 1.0)) * 0.25)

        decile = fd.get("decile_quality", {}).get(primary_h, {})
        if decile:
            ds = 0.0
            if decile.get("pass_sign", False): ds += 0.4
            if decile.get("pass_separation", False): ds += 0.3
            if decile.get("pass_head_tail", False): ds += 0.3
            scores.append(ds * 0.15)

        turnover = fd.get("signal_turnover", 0)
        if turnover > 0.3:
            scores.append(-0.05)

        ts_ic = fd.get("ts_ic", {}).get(primary_h, {})
        pct_pos = ts_ic.get("pct_positive", 50)
        if pct_pos is not None:
            scores.append((pct_pos / 100) * 0.1)

        return round(max(0.0, min(1.0, sum(scores))), 3)

    # ------------------------------------------------------------------
    # 批量汇总
    # ------------------------------------------------------------------

    def _build_batch_summary(self, results: List[ParsedFactor], n_files: int) -> BatchSummary:
        if not results:
            return BatchSummary(0, n_files, {}, {}, 0, 0, [], [], [])

        conf_counts = Counter(r.confidence for r in results)
        risk_counts = Counter(r.report.turnover_risk for r in results)
        avg_q = sum(r.report.quality_score for r in results) / len(results)
        avg_c = sum(r.completeness for r in results) / len(results)

        top = sorted(results, key=lambda r: r.report.quality_score, reverse=True)[:10]
        top_factors = [(r.name, r.report.quality_score) for r in top]

        all_warnings: Counter = Counter()
        for r in results:
            for w in r.report.warnings:
                all_warnings[w] += 1

        all_missing: Counter = Counter()
        for r in results:
            for m in r.missing_fields:
                all_missing[m] += 1

        return BatchSummary(
            total_factors=len(results), total_files=n_files,
            by_confidence=dict(conf_counts), by_turnover_risk=dict(risk_counts),
            avg_quality=avg_q, avg_completeness=avg_c,
            top_factors=top_factors,
            common_warnings=all_warnings.most_common(5),
            common_missing=all_missing.most_common(5),
        )

    @staticmethod
    def _best_quantile(qdict: dict) -> Optional[dict]:
        for key in ["q10bp", "q50bp", "q100bp", "q500bp", "q1000bp"]:
            if key in qdict:
                return qdict[key]
        return next(iter(qdict.values()), None) if qdict else None
