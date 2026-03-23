"""
AlphaGPT Report Parser

将 AlphaGPT 的 factor_report.json 解析为 astack 标准格式：
  factor_report.json → ValidationReport + BacktestMetrics

使用方式：
  parser = AlphaGPTReportParser()
  results = parser.parse_file("path/to/factor_report.json")
  for name, report, metrics in results:
      print(name, report.quality_score, metrics.ic_mean)

保留原始报告片段以便追溯 (raw_report 存入 metrics.extra)。
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from astack.schemas import BacktestMetrics, ValidationReport


class AlphaGPTReportParser:
    """解析 AlphaGPT factor_report.json"""

    def parse_file(self, path: str) -> List[Tuple[str, ValidationReport, BacktestMetrics]]:
        """解析整个报告文件，返回 [(factor_name, ValidationReport, BacktestMetrics), ...]"""
        data = json.loads(Path(path).read_text())
        return self.parse_dict(data)

    def parse_dict(self, data: dict) -> List[Tuple[str, ValidationReport, BacktestMetrics]]:
        """解析已加载的 dict"""
        results = []
        primary_h = str(data.get("primary_horizon", 1))
        factors = data.get("factors", {})

        for name, fd in factors.items():
            metrics = self._extract_metrics(fd, primary_h)
            report = self._build_report(name, fd, metrics, primary_h)
            results.append((name, report, metrics))

        return results

    def _extract_metrics(self, fd: dict, primary_h: str) -> BacktestMetrics:
        """从单个因子的报告数据中提取 BacktestMetrics"""
        # --- IC ---
        ts_ic = fd.get("ts_ic", {}).get(primary_h, {})
        ic_mean = ts_ic.get("ic_mean")
        ic_std = ts_ic.get("ic_std")
        icir = ts_ic.get("ic_ir")

        # --- Signal (if available) ---
        sig = fd.get("signal", {}).get(primary_h, {})
        sharpe = sig.get("ann_sharpe")

        # --- Quantile signal: use best quantile (q10bp = top 0.1%) ---
        qsig = fd.get("quantile_signal", {}).get(primary_h, {})
        best_q = self._best_quantile(qsig)
        q_sharpe = best_q.get("ann_sharpe") if best_q else None
        q_ann_ret = best_q.get("ann_ret") if best_q else None

        # 用 quantile sharpe 如果 signal sharpe 不可用
        if sharpe is None and q_sharpe is not None:
            sharpe = q_sharpe

        # --- Long/Short from quantile ---
        long_pct = best_q.get("avg_long_pct", 50) if best_q else 50
        short_pct = best_q.get("avg_short_pct", 50) if best_q else 50
        # 用 long/short 占比推算方向偏好
        long_return = q_ann_ret * (long_pct / 100) if q_ann_ret and long_pct else None
        short_return = q_ann_ret * (short_pct / 100) if q_ann_ret and short_pct else None

        # --- Decile ---
        decile = fd.get("decile_quality", {}).get(primary_h, {})
        top_decile = decile.get("top_decile_mean_raw")
        bottom_decile = decile.get("bottom_decile_mean_raw")
        decile_returns = []
        if top_decile is not None and bottom_decile is not None:
            # 构造简化的 10 分组（只有首尾真实，中间线性插值）
            for i in range(10):
                decile_returns.append(bottom_decile + (top_decile - bottom_decile) * i / 9)

        # --- Per-horizon sharpes (holding period robustness) ---
        holding_period_sharpes = {}
        for h, ic_data in fd.get("ts_ic", {}).items():
            h_sig = fd.get("signal", {}).get(h, {})
            h_qsig = fd.get("quantile_signal", {}).get(h, {})
            h_best = self._best_quantile(h_qsig)
            s = h_sig.get("ann_sharpe") or (h_best.get("ann_sharpe") if h_best else None)
            if s is not None:
                holding_period_sharpes[f"h{h}"] = s

        # --- Test/Val window ---
        test_win = fd.get("test_window_primary", {})
        val_win = fd.get("validation_window_primary", {})
        train_sharpe = sharpe  # 主 sharpe 视为 train
        val_sharpe = val_win.get("ann_sharpe") if val_win else None
        test_sharpe = test_win.get("test_ann_sharpe") if test_win else None

        return BacktestMetrics(
            ic_mean=ic_mean,
            ic_std=ic_std,
            icir=icir,
            decile_returns=decile_returns,
            long_return=long_return,
            short_return=short_return,
            long_short_return=(q_ann_ret if q_ann_ret else None),
            sharpe=sharpe,
            holding_period_sharpes=holding_period_sharpes,
            train_sharpe=train_sharpe,
            val_sharpe=val_sharpe,
            test_sharpe=test_sharpe,
            extra={
                "autocorr_1": fd.get("autocorr_1"),
                "signal_turnover": fd.get("signal_turnover"),
                "quantile_mode": fd.get("quantile_mode"),
                "decile_quality": fd.get("decile_quality", {}),
                "test_window_primary": test_win,
                "validation_window_primary": val_win,
                "raw_quantile_signal": fd.get("quantile_signal", {}),
            },
        )

    def _build_report(self, name: str, fd: dict, metrics: BacktestMetrics, primary_h: str) -> ValidationReport:
        """构建 ValidationReport"""
        warnings = []

        # --- implementable ---
        implementable = True  # AlphaGPT 能跑说明可实现

        # --- lookahead check ---
        lookahead_safe = True
        if metrics.ic_mean is not None and abs(metrics.ic_mean) > 0.15:
            lookahead_safe = False
            warnings.append(f"IC 异常高({metrics.ic_mean:.4f})，可能存在未来数据")

        # --- quality score ---
        quality_score = self._compute_quality(metrics, fd, primary_h)

        # --- redundancy (需要外部对比，暂用 autocorr 近似) ---
        autocorr = fd.get("autocorr_1", 0)
        redundancy_score = min(1.0, max(0.0, autocorr))

        # --- turnover risk ---
        turnover = fd.get("signal_turnover", 0)
        if turnover > 0.3:
            turnover_risk = "high"
        elif turnover > 0.15:
            turnover_risk = "medium"
        else:
            turnover_risk = "low"

        # --- decile quality check ---
        decile = fd.get("decile_quality", {}).get(primary_h, {})
        if not decile.get("pass_head_tail", True):
            warnings.append("十分组首尾收益差不显著")
        if not decile.get("pass_sign", True):
            warnings.append("十分组方向不正确")

        # --- test window check ---
        test_win = fd.get("test_window_primary", {})
        if test_win.get("test_bars", 0) == 0:
            warnings.append("无测试集数据")
        elif test_win.get("test_ann_sharpe") is not None and test_win["test_ann_sharpe"] < 0:
            warnings.append(f"测试集夏普为负({test_win['test_ann_sharpe']:.2f})")

        return ValidationReport(
            alpha_name=name,
            implementable=implementable,
            lookahead_safe=lookahead_safe,
            data_available=True,
            redundancy_score=redundancy_score,
            quality_score=quality_score,
            turnover_risk=turnover_risk,
            regime_risk="medium",
            metrics={
                "IC": metrics.ic_mean,
                "ICIR": metrics.icir,
                "sharpe": metrics.sharpe,
                "ann_ret": metrics.long_short_return,
                "source": "alphagpt",
            },
            warnings=warnings,
            critique=fd.get("description", ""),
        )

    def _compute_quality(self, metrics: BacktestMetrics, fd: dict, primary_h: str) -> float:
        """综合质量评分 0~1"""
        scores = []

        # IC 贡献
        if metrics.ic_mean is not None:
            scores.append(min(abs(metrics.ic_mean) / 0.05, 1.0) * 0.3)

        # ICIR 贡献
        if metrics.icir is not None:
            scores.append(min(abs(metrics.icir) / 3.0, 1.0) * 0.2)

        # Sharpe 贡献
        if metrics.sharpe is not None:
            scores.append(max(0, min(metrics.sharpe / 2.0, 1.0)) * 0.25)

        # Decile 质量
        decile = fd.get("decile_quality", {}).get(primary_h, {})
        if decile:
            decile_score = 0.0
            if decile.get("pass_sign", False):
                decile_score += 0.4
            if decile.get("pass_separation", False):
                decile_score += 0.3
            if decile.get("pass_head_tail", False):
                decile_score += 0.3
            scores.append(decile_score * 0.15)

        # Turnover penalty
        turnover = fd.get("signal_turnover", 0)
        if turnover > 0.3:
            scores.append(-0.05)

        # IC 稳定性 (pct_positive)
        ts_ic = fd.get("ts_ic", {}).get(primary_h, {})
        pct_pos = ts_ic.get("pct_positive", 50)
        if pct_pos is not None:
            scores.append((pct_pos / 100) * 0.1)

        total = sum(scores)
        return round(max(0.0, min(1.0, total)), 3)

    @staticmethod
    def _best_quantile(qdict: dict) -> Optional[dict]:
        """选择最优的 quantile 策略结果（优先 q10bp = top 0.1%）"""
        for key in ["q10bp", "q50bp", "q100bp", "q500bp", "q1000bp"]:
            if key in qdict:
                return qdict[key]
        return next(iter(qdict.values()), None) if qdict else None
