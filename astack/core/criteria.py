"""
单因子评价标准 skill

将 13 条评价标准拆分为：
- 10 个评分维度（标准 1-10）：每项 0~1 分
- 理想模板匹配（标准 11）：综合描述
- 5 个否决条件（标准 12.1-12.5）：触发任一则 verdict 降级
- 验证协议（标准 13）：7:2:1 train/val/test 结果对比

量化指标由 adapter 回测提供（BacktestMetrics），
定性指标由 LLM 或人工评估填入。
"""

from typing import List, Optional
from astack.schemas import (
    AlphaSpec,
    BacktestMetrics,
    CriterionScore,
    FactorEvalReport,
    RedFlag,
)

# ---------------------------------------------------------------------------
# 标准定义
# ---------------------------------------------------------------------------

CRITERIA = {
    1: "预测能力（IC/分层/多空/夏普）",
    2: "多持仓周期稳健性",
    3: "年度一致性",
    4: "经济含义与交易逻辑",
    5: "参数简洁性（≤3个）",
    6: "数据边界合规",
    7: "跨时间/跨品种稳健性",
    8: "创新性（非旧因子机械变形）",
    9: "信号可交易性",
    10: "表达简洁可审查",
}

RED_FLAG_DEFS = {
    "12.1": "存在未来数据",
    "12.2": "多空收益严重不均衡",
    "12.3": "IC接近零且分组混乱",
    "12.4": "参数敏感/过拟合嫌疑",
    "12.5": "近两年表现差或巨大回撤",
}


class CriteriaEvaluator:
    """基于回测指标的量化评分 + 定性维度的 placeholder。"""

    def evaluate(
        self,
        spec: AlphaSpec,
        metrics: BacktestMetrics,
        qualitative: Optional[dict] = None,
    ) -> FactorEvalReport:
        scores = self._score_criteria(spec, metrics, qualitative or {})
        flags = self._check_red_flags(spec, metrics)
        overall = self._compute_overall(scores, flags)
        verdict = self._decide_verdict(overall, flags)
        ideal_match = self._ideal_template_summary(metrics)
        val_protocol = self._validation_protocol_summary(metrics)

        return FactorEvalReport(
            alpha_name=spec.name,
            backtest_metrics=metrics,
            criteria_scores=scores,
            red_flags=flags,
            overall_score=overall,
            verdict=verdict,
            ideal_template_match=ideal_match,
            validation_protocol=val_protocol,
            summary=self._build_summary(spec.name, overall, verdict, flags),
        )

    # ------------------------------------------------------------------
    # 标准 1-10 评分
    # ------------------------------------------------------------------

    def _score_criteria(
        self, spec: AlphaSpec, m: BacktestMetrics, q: dict
    ) -> List[CriterionScore]:
        scorers = [
            self._c1_predictive_power,
            self._c2_holding_period_robustness,
            self._c3_annual_consistency,
            self._c4_economic_logic,
            self._c5_param_simplicity,
            self._c6_data_boundary,
            self._c7_cross_robustness,
            self._c8_novelty,
            self._c9_tradability,
            self._c10_expression_clarity,
        ]
        return [fn(spec, m, q) for fn in scorers]

    def _c1_predictive_power(self, spec: AlphaSpec, m: BacktestMetrics, q: dict) -> CriterionScore:
        sub_scores = []
        if m.ic_mean is not None:
            sub_scores.append(min(abs(m.ic_mean) / 0.05, 1.0))
        if m.icir is not None:
            sub_scores.append(min(abs(m.icir) / 1.5, 1.0))
        if len(m.decile_returns) >= 5:
            mono = self._monotonicity(m.decile_returns)
            sub_scores.append(mono)
        if m.long_short_return is not None:
            sub_scores.append(min(m.long_short_return / 0.3, 1.0) if m.long_short_return > 0 else 0.0)
        if m.sharpe is not None:
            sub_scores.append(min(m.sharpe / 2.0, 1.0) if m.sharpe > 0 else 0.0)

        score = sum(sub_scores) / max(len(sub_scores), 1)
        return CriterionScore(
            criterion_id=1, name=CRITERIA[1],
            score=round(score, 3), passed=score >= 0.4,
            detail=f"IC={m.ic_mean}, ICIR={m.icir}, sharpe={m.sharpe}, L/S={m.long_short_return}",
        )

    def _c2_holding_period_robustness(self, spec: AlphaSpec, m: BacktestMetrics, q: dict) -> CriterionScore:
        if not m.holding_period_sharpes:
            return CriterionScore(
                criterion_id=2, name=CRITERIA[2],
                score=0.5, passed=True, detail="无多周期数据，待补充",
            )
        sharpes = list(m.holding_period_sharpes.values())
        positive_ratio = sum(1 for s in sharpes if s > 0) / len(sharpes)
        score = positive_ratio
        return CriterionScore(
            criterion_id=2, name=CRITERIA[2],
            score=round(score, 3), passed=score >= 0.6,
            detail=f"正夏普周期占比={positive_ratio:.0%}, periods={list(m.holding_period_sharpes.keys())}",
        )

    def _c3_annual_consistency(self, spec: AlphaSpec, m: BacktestMetrics, q: dict) -> CriterionScore:
        if not m.annual_returns:
            return CriterionScore(
                criterion_id=3, name=CRITERIA[3],
                score=0.5, passed=True, detail="无年度数据，待补充",
            )
        returns = list(m.annual_returns.values())
        positive_ratio = sum(1 for r in returns if r > 0) / len(returns)
        score = positive_ratio
        return CriterionScore(
            criterion_id=3, name=CRITERIA[3],
            score=round(score, 3), passed=score >= 0.6,
            detail=f"正收益年份占比={positive_ratio:.0%}, years={list(m.annual_returns.keys())}",
        )

    def _c4_economic_logic(self, spec: AlphaSpec, m: BacktestMetrics, q: dict) -> CriterionScore:
        score = q.get("economic_logic_score", 0.5)
        return CriterionScore(
            criterion_id=4, name=CRITERIA[4],
            score=score, passed=score >= 0.4,
            detail=q.get("economic_logic_detail", "待 LLM 或人工评估"),
        )

    def _c5_param_simplicity(self, spec: AlphaSpec, m: BacktestMetrics, q: dict) -> CriterionScore:
        n_params = len(spec.parameters)
        if n_params <= 1:
            score = 1.0
        elif n_params <= 3:
            score = 0.8
        elif n_params <= 5:
            score = 0.4
        else:
            score = 0.1
        return CriterionScore(
            criterion_id=5, name=CRITERIA[5],
            score=score, passed=n_params <= 3,
            detail=f"参数数量={n_params}, params={list(spec.parameters.keys())}",
        )

    def _c6_data_boundary(self, spec: AlphaSpec, m: BacktestMetrics, q: dict) -> CriterionScore:
        passed = q.get("data_boundary_ok", True)
        return CriterionScore(
            criterion_id=6, name=CRITERIA[6],
            score=1.0 if passed else 0.0, passed=passed,
            detail=f"required_fields={spec.required_fields}",
        )

    def _c7_cross_robustness(self, spec: AlphaSpec, m: BacktestMetrics, q: dict) -> CriterionScore:
        if not m.per_symbol_returns:
            return CriterionScore(
                criterion_id=7, name=CRITERIA[7],
                score=0.5, passed=True, detail="无分品种数据，待补充",
            )
        returns = list(m.per_symbol_returns.values())
        positive_ratio = sum(1 for r in returns if r > 0) / len(returns)
        if len(returns) >= 2:
            import statistics
            std = statistics.stdev(returns)
            mean = statistics.mean(returns)
            cv = std / abs(mean) if mean != 0 else 999
            balance = max(0, 1 - cv / 2)
        else:
            balance = 0.5
        score = 0.6 * positive_ratio + 0.4 * balance
        return CriterionScore(
            criterion_id=7, name=CRITERIA[7],
            score=round(score, 3), passed=score >= 0.5,
            detail=f"正收益品种占比={positive_ratio:.0%}, symbols={list(m.per_symbol_returns.keys())}",
        )

    def _c8_novelty(self, spec: AlphaSpec, m: BacktestMetrics, q: dict) -> CriterionScore:
        score = q.get("novelty_score", 0.5)
        return CriterionScore(
            criterion_id=8, name=CRITERIA[8],
            score=score, passed=score >= 0.4,
            detail=q.get("novelty_detail", "待 LLM 或人工评估"),
        )

    def _c9_tradability(self, spec: AlphaSpec, m: BacktestMetrics, q: dict) -> CriterionScore:
        sub = []
        if len(m.decile_returns) >= 5:
            sub.append(self._monotonicity(m.decile_returns))
        if m.long_return is not None and m.short_return is not None:
            both_meaningful = (m.long_return > 0 and m.short_return < 0) or (m.long_return < 0 and m.short_return > 0)
            sub.append(0.8 if both_meaningful else 0.3)
        score = sum(sub) / max(len(sub), 1) if sub else q.get("tradability_score", 0.5)
        return CriterionScore(
            criterion_id=9, name=CRITERIA[9],
            score=round(score, 3), passed=score >= 0.4,
            detail=f"long={m.long_return}, short={m.short_return}",
        )

    def _c10_expression_clarity(self, spec: AlphaSpec, m: BacktestMetrics, q: dict) -> CriterionScore:
        expr_len = len(spec.formula_expression)
        if expr_len <= 60:
            score = 1.0
        elif expr_len <= 120:
            score = 0.7
        elif expr_len <= 200:
            score = 0.4
        else:
            score = 0.2
        override = q.get("expression_clarity_score")
        if override is not None:
            score = override
        return CriterionScore(
            criterion_id=10, name=CRITERIA[10],
            score=score, passed=score >= 0.4,
            detail=f"formula_len={expr_len}",
        )

    # ------------------------------------------------------------------
    # 标准 12：否决条件
    # ------------------------------------------------------------------

    def _check_red_flags(self, spec: AlphaSpec, m: BacktestMetrics) -> List[RedFlag]:
        return [
            self._rf_121_lookahead(m),
            self._rf_122_unbalanced_ls(m),
            self._rf_123_low_ic_chaotic(m),
            self._rf_124_param_sensitive(spec, m),
            self._rf_125_recent_failure(m),
        ]

    def _rf_121_lookahead(self, m: BacktestMetrics) -> RedFlag:
        suspicious = m.ic_mean is not None and abs(m.ic_mean) > 0.15
        return RedFlag(
            flag_id="12.1", description=RED_FLAG_DEFS["12.1"],
            triggered=suspicious,
            detail=f"IC={m.ic_mean}，异常高可能存在未来数据" if suspicious else "",
        )

    def _rf_122_unbalanced_ls(self, m: BacktestMetrics) -> RedFlag:
        if m.long_return is None or m.short_return is None:
            return RedFlag(flag_id="12.2", description=RED_FLAG_DEFS["12.2"], triggered=False)
        both_positive = m.long_return > 0.05 and m.short_return > 0.05
        both_negative = m.long_return < -0.05 and m.short_return < -0.05
        triggered = both_positive or both_negative
        return RedFlag(
            flag_id="12.2", description=RED_FLAG_DEFS["12.2"],
            triggered=triggered,
            detail=f"long={m.long_return:.3f}, short={m.short_return:.3f}" if triggered else "",
        )

    def _rf_123_low_ic_chaotic(self, m: BacktestMetrics) -> RedFlag:
        low_ic = m.ic_mean is not None and abs(m.ic_mean) < 0.01
        chaotic = len(m.decile_returns) >= 5 and self._monotonicity(m.decile_returns) < 0.3
        triggered = low_ic and chaotic
        return RedFlag(
            flag_id="12.3", description=RED_FLAG_DEFS["12.3"],
            triggered=triggered,
            detail=f"IC={m.ic_mean}, monotonicity={self._monotonicity(m.decile_returns):.2f}" if triggered else "",
        )

    def _rf_124_param_sensitive(self, spec: AlphaSpec, m: BacktestMetrics) -> RedFlag:
        triggered = len(spec.parameters) > 5
        return RedFlag(
            flag_id="12.4", description=RED_FLAG_DEFS["12.4"],
            triggered=triggered,
            detail=f"参数数量={len(spec.parameters)}" if triggered else "",
        )

    def _rf_125_recent_failure(self, m: BacktestMetrics) -> RedFlag:
        if m.recent_2y_return is None:
            return RedFlag(flag_id="12.5", description=RED_FLAG_DEFS["12.5"], triggered=False)
        bad_return = m.recent_2y_return < 0
        big_dd = m.recent_2y_max_drawdown is not None and m.recent_2y_max_drawdown < -0.3
        triggered = bad_return or big_dd
        return RedFlag(
            flag_id="12.5", description=RED_FLAG_DEFS["12.5"],
            triggered=triggered,
            detail=f"近2年收益={m.recent_2y_return:.3f}, 最大回撤={m.recent_2y_max_drawdown}" if triggered else "",
        )

    # ------------------------------------------------------------------
    # 汇总
    # ------------------------------------------------------------------

    def _compute_overall(self, scores: List[CriterionScore], flags: List[RedFlag]) -> float:
        if not scores:
            return 0.0
        weights = {1: 2.0, 2: 1.0, 3: 1.0, 4: 1.5, 5: 0.8,
                   6: 1.0, 7: 1.0, 8: 0.8, 9: 1.2, 10: 0.7}
        total_w = sum(weights.get(s.criterion_id, 1.0) for s in scores)
        weighted = sum(s.score * weights.get(s.criterion_id, 1.0) for s in scores)
        base = weighted / total_w
        penalty = sum(0.1 for f in flags if f.triggered)
        return round(max(0.0, base - penalty), 3)

    def _decide_verdict(self, overall: float, flags: List[RedFlag]) -> str:
        fatal_flags = {"12.1"}
        for f in flags:
            if f.triggered and f.flag_id in fatal_flags:
                return "fail"
        triggered_count = sum(1 for f in flags if f.triggered)
        if triggered_count >= 3:
            return "fail"
        if overall >= 0.65:
            return "pass"
        if overall >= 0.45:
            return "marginal"
        return "fail"

    def _ideal_template_summary(self, m: BacktestMetrics) -> str:
        parts = []
        if m.ic_mean is not None:
            parts.append(f"IC={m.ic_mean:.4f}")
        if m.sharpe is not None:
            parts.append(f"sharpe={m.sharpe:.2f}")
        if m.long_short_return is not None:
            parts.append(f"L/S={m.long_short_return:.3f}")
        if m.annual_returns:
            pos = sum(1 for r in m.annual_returns.values() if r > 0)
            parts.append(f"正收益年份={pos}/{len(m.annual_returns)}")
        return "理想模板对标: " + ", ".join(parts) if parts else "数据不足，无法对标理想模板"

    def _validation_protocol_summary(self, m: BacktestMetrics) -> str:
        parts = ["7:2:1 train/val/test"]
        if m.train_sharpe is not None:
            parts.append(f"train_sharpe={m.train_sharpe:.2f}")
        if m.val_sharpe is not None:
            parts.append(f"val_sharpe={m.val_sharpe:.2f}")
        if m.test_sharpe is not None:
            parts.append(f"test_sharpe={m.test_sharpe:.2f}")
        if m.train_sharpe is not None and m.val_sharpe is not None:
            ratio = m.val_sharpe / m.train_sharpe if m.train_sharpe != 0 else 0
            if ratio >= 0.7:
                parts.append("→ val/train 接近，初步通过")
            else:
                parts.append(f"→ val/train 比值={ratio:.2f}，衰减过大")
        return " | ".join(parts)

    def _build_summary(self, name: str, overall: float, verdict: str, flags: List[RedFlag]) -> str:
        triggered = [f for f in flags if f.triggered]
        lines = [f"因子 {name}: overall={overall:.3f}, verdict={verdict}"]
        if triggered:
            lines.append("触发否决条件: " + ", ".join(f"{f.flag_id} {f.description}" for f in triggered))
        return "; ".join(lines)

    # ------------------------------------------------------------------
    # 工具函数
    # ------------------------------------------------------------------

    @staticmethod
    def _monotonicity(returns: List[float]) -> float:
        """计算分组收益的单调性 (0~1)，1 表示完全单调。"""
        if len(returns) < 2:
            return 0.0
        n = len(returns) - 1
        increasing = sum(1 for i in range(n) if returns[i + 1] > returns[i])
        decreasing = sum(1 for i in range(n) if returns[i + 1] < returns[i])
        return max(increasing, decreasing) / n
