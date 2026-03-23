"""
单因子评价标准 skill

8 个评分维度（标准 1-8）：每项 0~1 分
理想模板匹配（标准 9）：综合描述
5 个否决条件（标准 10.1-10.5）：触发任一则 verdict 降级
验证协议（标准 11）：7:2:1 train/val/test 结果对比

所有收益类指标基于分位数突破策略：
  信号突破前/后 x% 分位数时开仓，回落到 50% 分位数时平仓。
  分位数级别：0.1%, 0.5%, 1%, 5%, 10%
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
    1: "预测能力（IC/分位数策略收益/夏普）",
    2: "多持仓周期稳健性",
    3: "年度一致性",
    4: "经济含义与交易逻辑",
    5: "参数简洁性（≤3个）",
    6: "跨时间/跨品种稳健性",
    7: "创新性（非旧因子机械变形）",
    8: "表达简洁可审查",
}

RED_FLAG_DEFS = {
    "10.1": "存在未来数据",
    "10.2": "多空收益严重不均衡",
    "10.3": "IC接近零且分组混乱",
    "10.4": "参数敏感/过拟合嫌疑",
    "10.5": "近两年表现差或巨大回撤",
}


class CriteriaEvaluator:
    """基于分位数突破策略的量化评分。"""

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
    # 标准 1-8 评分
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
            self._c6_cross_robustness,
            self._c7_novelty,
            self._c8_expression_clarity,
        ]
        return [fn(spec, m, q) for fn in scorers]

    def _c1_predictive_power(self, spec: AlphaSpec, m: BacktestMetrics, q: dict) -> CriterionScore:
        """核心评分：基于分位数突破策略的真实开仓收益。

        子项：
        1. IC 水平
        2. ICIR
        3. 头部分位数收益是否为正（关键！）
        4. 头部分位数夏普
        5. 多分位数一致性（宽松→严格分位数收益是否单调）
        6. 头部分位数胜率
        """
        sub_scores = []
        details = []

        # IC
        if m.ic_mean is not None:
            ic_score = min(abs(m.ic_mean) / 0.05, 1.0)
            sub_scores.append(ic_score)
            details.append(f"IC={m.ic_mean:.4f}")

        # ICIR
        if m.icir is not None:
            icir_score = min(abs(m.icir) / 1.5, 1.0)
            sub_scores.append(icir_score)
            details.append(f"ICIR={m.icir:.2f}")

        # --- 分位数策略指标 ---
        qr = m.quantile_results
        if qr:
            # 头部分位数（最严格的）收益是否为正
            top_q = qr[0]  # 排序后第一个是最严格分位数
            if top_q.ann_ret is not None:
                positive = 1.0 if top_q.ann_ret > 0 else 0.0
                sub_scores.append(positive)
                details.append(f"top_q({top_q.label})_ret={'正' if positive else '负'}({top_q.ann_ret:.4f})")

            # 头部分位数夏普
            if top_q.ann_sharpe is not None:
                sharpe_score = max(0, min(top_q.ann_sharpe / 2.0, 1.0))
                sub_scores.append(sharpe_score)
                details.append(f"top_q_sharpe={top_q.ann_sharpe:.2f}")

            # 头部分位数胜率
            if top_q.win_rate is not None:
                wr_score = max(0, (top_q.win_rate - 50) / 30)  # 50%=0, 80%=1
                sub_scores.append(min(wr_score, 1.0))
                details.append(f"top_q_winrate={top_q.win_rate:.1f}%")

            # 多分位数一致性：有多少个分位数的收益为正
            positive_count = sum(1 for r in qr if r.ann_ret is not None and r.ann_ret > 0)
            consistency = positive_count / len(qr) if qr else 0
            sub_scores.append(consistency)
            details.append(f"正收益分位数={positive_count}/{len(qr)}")
        else:
            # 无分位数数据时 fallback 到旧逻辑
            if m.sharpe is not None:
                sub_scores.append(max(0, min(m.sharpe / 2.0, 1.0)))
                details.append(f"sharpe={m.sharpe:.2f}(fallback)")
            if m.long_short_return is not None:
                sub_scores.append(min(m.long_short_return / 0.3, 1.0) if m.long_short_return > 0 else 0.0)
                details.append(f"L/S={m.long_short_return:.4f}(fallback)")

        score = sum(sub_scores) / max(len(sub_scores), 1)
        return CriterionScore(
            criterion_id=1, name=CRITERIA[1],
            score=round(score, 3), passed=score >= 0.4,
            detail="; ".join(details),
        )

    def _c2_holding_period_robustness(self, spec: AlphaSpec, m: BacktestMetrics, q: dict) -> CriterionScore:
        """多持仓周期：各 horizon 的头部分位数夏普是否为正。"""
        if not m.holding_period_sharpes:
            return CriterionScore(
                criterion_id=2, name=CRITERIA[2],
                score=0.5, passed=True, detail="无多周期数据，待补充",
            )
        sharpes = list(m.holding_period_sharpes.values())
        positive_ratio = sum(1 for s in sharpes if s > 0) / len(sharpes)
        return CriterionScore(
            criterion_id=2, name=CRITERIA[2],
            score=round(positive_ratio, 3), passed=positive_ratio >= 0.6,
            detail=f"正夏普周期占比={positive_ratio:.0%}, periods={list(m.holding_period_sharpes.keys())}",
        )

    def _c3_annual_consistency(self, spec: AlphaSpec, m: BacktestMetrics, q: dict) -> CriterionScore:
        """年度一致性：基于头部分位数策略的逐年收益。"""
        # 优先用分位数策略的年度收益
        if m.quantile_results:
            top_q = m.quantile_results[0]
            if top_q.annual_returns:
                years = list(top_q.annual_returns.keys())
                positive = sum(
                    1 for yr in top_q.annual_returns.values()
                    if yr.ann_ret is not None and yr.ann_ret > 0
                )
                ratio = positive / len(years)
                return CriterionScore(
                    criterion_id=3, name=CRITERIA[3],
                    score=round(ratio, 3), passed=ratio >= 0.6,
                    detail=f"分位数策略正收益年份={positive}/{len(years)}, years={years}",
                )
        # fallback 旧字段
        if m.annual_returns:
            returns = list(m.annual_returns.values())
            ratio = sum(1 for r in returns if r > 0) / len(returns)
            return CriterionScore(
                criterion_id=3, name=CRITERIA[3],
                score=round(ratio, 3), passed=ratio >= 0.6,
                detail=f"正收益年份占比={ratio:.0%}, years={list(m.annual_returns.keys())}",
            )
        return CriterionScore(
            criterion_id=3, name=CRITERIA[3],
            score=0.5, passed=True, detail="无年度数据（需 AlphaGPT 导出 annual_returns）",
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

    def _c6_cross_robustness(self, spec: AlphaSpec, m: BacktestMetrics, q: dict) -> CriterionScore:
        """跨品种稳健性：基于头部分位数策略的分品种收益。"""
        # 优先用分位数策略的分品种收益
        per_sym = {}
        if m.quantile_results:
            top_q = m.quantile_results[0]
            if top_q.per_symbol_returns:
                per_sym = top_q.per_symbol_returns
        if not per_sym:
            per_sym = m.per_symbol_returns
        if not per_sym:
            return CriterionScore(
                criterion_id=6, name=CRITERIA[6],
                score=0.5, passed=True, detail="无分品种数据（需 AlphaGPT 导出 per_symbol_returns）",
            )
        returns = list(per_sym.values())
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
            criterion_id=6, name=CRITERIA[6],
            score=round(score, 3), passed=score >= 0.5,
            detail=f"分位数策略正收益品种={sum(1 for r in returns if r > 0)}/{len(returns)}, symbols={list(per_sym.keys())}",
        )

    def _c7_novelty(self, spec: AlphaSpec, m: BacktestMetrics, q: dict) -> CriterionScore:
        score = q.get("novelty_score", 0.5)
        return CriterionScore(
            criterion_id=7, name=CRITERIA[7],
            score=score, passed=score >= 0.4,
            detail=q.get("novelty_detail", "待 LLM 或人工评估"),
        )

    def _c8_expression_clarity(self, spec: AlphaSpec, m: BacktestMetrics, q: dict) -> CriterionScore:
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
            criterion_id=8, name=CRITERIA[8],
            score=score, passed=score >= 0.4,
            detail=f"formula_len={expr_len}",
        )

    # ------------------------------------------------------------------
    # 标准 10：否决条件
    # ------------------------------------------------------------------

    def _check_red_flags(self, spec: AlphaSpec, m: BacktestMetrics) -> List[RedFlag]:
        return [
            self._rf_101_lookahead(m),
            self._rf_102_unbalanced_ls(m),
            self._rf_103_low_ic_chaotic(m),
            self._rf_104_param_sensitive(spec, m),
            self._rf_105_recent_failure(m),
        ]

    def _rf_101_lookahead(self, m: BacktestMetrics) -> RedFlag:
        suspicious = m.ic_mean is not None and abs(m.ic_mean) > 0.15
        return RedFlag(
            flag_id="10.1", description=RED_FLAG_DEFS["10.1"],
            triggered=suspicious,
            detail=f"IC={m.ic_mean}，异常高可能存在未来数据" if suspicious else "",
        )

    def _rf_102_unbalanced_ls(self, m: BacktestMetrics) -> RedFlag:
        """基于分位数策略：头部分位数的多空占比是否严重偏向一方。"""
        qr = m.quantile_results
        if qr:
            top = qr[0]
            if top.long_pct is not None and top.short_pct is not None:
                # 如果收益为正但几乎全是单方向 → 不均衡
                if top.ann_ret and top.ann_ret > 0:
                    heavily_skewed = top.long_pct > 85 or top.short_pct > 85
                    return RedFlag(
                        flag_id="10.2", description=RED_FLAG_DEFS["10.2"],
                        triggered=heavily_skewed,
                        detail=f"long_pct={top.long_pct:.1f}%, short_pct={top.short_pct:.1f}%" if heavily_skewed else "",
                    )
        # fallback
        if m.long_return is None or m.short_return is None:
            return RedFlag(flag_id="10.2", description=RED_FLAG_DEFS["10.2"], triggered=False)
        both_positive = m.long_return > 0.05 and m.short_return > 0.05
        both_negative = m.long_return < -0.05 and m.short_return < -0.05
        triggered = both_positive or both_negative
        return RedFlag(
            flag_id="10.2", description=RED_FLAG_DEFS["10.2"],
            triggered=triggered,
            detail=f"long={m.long_return:.3f}, short={m.short_return:.3f}" if triggered else "",
        )

    def _rf_103_low_ic_chaotic(self, m: BacktestMetrics) -> RedFlag:
        low_ic = m.ic_mean is not None and abs(m.ic_mean) < 0.01
        chaotic = len(m.decile_returns) >= 5 and self._monotonicity(m.decile_returns) < 0.3
        triggered = low_ic and chaotic
        return RedFlag(
            flag_id="10.3", description=RED_FLAG_DEFS["10.3"],
            triggered=triggered,
            detail=f"IC={m.ic_mean}, monotonicity={self._monotonicity(m.decile_returns):.2f}" if triggered else "",
        )

    def _rf_104_param_sensitive(self, spec: AlphaSpec, m: BacktestMetrics) -> RedFlag:
        triggered = len(spec.parameters) > 5
        return RedFlag(
            flag_id="10.4", description=RED_FLAG_DEFS["10.4"],
            triggered=triggered,
            detail=f"参数数量={len(spec.parameters)}" if triggered else "",
        )

    def _rf_105_recent_failure(self, m: BacktestMetrics) -> RedFlag:
        if m.recent_2y_return is None:
            return RedFlag(flag_id="10.5", description=RED_FLAG_DEFS["10.5"], triggered=False)
        bad_return = m.recent_2y_return < 0
        big_dd = m.recent_2y_max_drawdown is not None and m.recent_2y_max_drawdown < -0.3
        triggered = bad_return or big_dd
        return RedFlag(
            flag_id="10.5", description=RED_FLAG_DEFS["10.5"],
            triggered=triggered,
            detail=f"近2年收益={m.recent_2y_return:.3f}, 最大回撤={m.recent_2y_max_drawdown}" if triggered else "",
        )

    # ------------------------------------------------------------------
    # 汇总
    # ------------------------------------------------------------------

    def _compute_overall(self, scores: List[CriterionScore], flags: List[RedFlag]) -> float:
        if not scores:
            return 0.0
        # 标准 1 权重最高（3.0），因为它直接反映分位数策略的真实收益
        weights = {1: 3.0, 2: 1.0, 3: 1.0, 4: 1.5, 5: 0.8,
                   6: 1.0, 7: 0.8, 8: 0.7}
        total_w = sum(weights.get(s.criterion_id, 1.0) for s in scores)
        weighted = sum(s.score * weights.get(s.criterion_id, 1.0) for s in scores)
        base = weighted / total_w
        penalty = sum(0.1 for f in flags if f.triggered)
        return round(max(0.0, base - penalty), 3)

    def _decide_verdict(self, overall: float, flags: List[RedFlag]) -> str:
        fatal_flags = {"10.1"}
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
        # 用头部分位数策略指标
        if m.quantile_results:
            top = m.quantile_results[0]
            if top.ann_sharpe is not None:
                parts.append(f"top_q_sharpe={top.ann_sharpe:.2f}")
            if top.ann_ret is not None:
                parts.append(f"top_q_ret={top.ann_ret:.4f}")
            if top.win_rate is not None:
                parts.append(f"top_q_winrate={top.win_rate:.1f}%")
        elif m.sharpe is not None:
            parts.append(f"sharpe={m.sharpe:.2f}")
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

    @staticmethod
    def _monotonicity(returns: List[float]) -> float:
        if len(returns) < 2:
            return 0.0
        n = len(returns) - 1
        increasing = sum(1 for i in range(n) if returns[i + 1] > returns[i])
        decreasing = sum(1 for i in range(n) if returns[i + 1] < returns[i])
        return max(increasing, decreasing) / n
