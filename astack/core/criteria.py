"""
单因子评价标准 skill

8 个评分维度（标准 1-8）：每项 0~1 分
理想模板匹配（标准 9）：综合描述
5 个否决条件（标准 10.1-10.5）：触发任一则 verdict 降级
验证协议（标准 11）：7:2:1 train/val/test 结果对比

所有收益类指标基于分位数突破策略（多分位数加权）：
  信号突破前/后 x% 分位数时开仓，回落到 50% 分位数时平仓。
  分位数级别：0.1%, 0.5%, 1%, 5%, 10%

分位数权重逻辑：
  10% 分位数权重最高（交易量大、最可靠、包含所有更严格分位数的交易）
  0.1% 权重最低（交易极少、统计意义弱）
  10% 有效但 1% 无效 → 仍有价值
  1% 有效但 10% 无效 → 可疑
"""

from typing import Dict, List, Optional
from astack.schemas import (
    AlphaSpec,
    BacktestMetrics,
    CriterionScore,
    FactorEvalReport,
    QuantileResult,
    RedFlag,
)

# ---------------------------------------------------------------------------
# 标准定义
# ---------------------------------------------------------------------------

CRITERIA = {
    1: "预测能力（IC/多分位数策略收益/夏普）",
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

# 分位数权重：宽松分位数（交易多）权重高，严格分位数（交易少）权重低
# quantile 值越小 = 分位数越宽松（10% = 0.9）
QUANTILE_WEIGHTS = {
    0.9: 3.0,    # 10% — 最重要
    0.95: 2.0,   # 5%
    0.99: 1.0,   # 1%
    0.995: 0.5,  # 0.5%
    0.999: 0.3,  # 0.1%
}


def _quantile_weight(quantile: float) -> float:
    """根据分位数阈值返回权重。越宽松权重越高。"""
    # 找最接近的已知权重
    best_key = min(QUANTILE_WEIGHTS.keys(), key=lambda k: abs(k - quantile))
    if abs(best_key - quantile) < 0.02:
        return QUANTILE_WEIGHTS[best_key]
    # 插值：quantile 越低（越宽松）权重越高
    return max(0.3, 3.0 * (1 - quantile))


def _weighted_quantile_score(
    qr: List[QuantileResult],
    value_fn,
    default: float = 0.0,
) -> tuple:
    """多分位数加权评分。

    value_fn: QuantileResult → Optional[float] (单个分位数的得分 0~1)
    返回: (加权分数, detail_str)
    """
    if not qr:
        return default, "无分位数数据"
    total_w = 0.0
    weighted_sum = 0.0
    parts = []
    for q in qr:
        val = value_fn(q)
        if val is None:
            continue
        w = _quantile_weight(q.quantile)
        weighted_sum += val * w
        total_w += w
        pct = round((1 - q.quantile) * 100, 1)
        parts.append(f"{pct}%={val:.2f}(w={w:.1f})")
    if total_w == 0:
        return default, "无有效数据"
    score = weighted_sum / total_w
    return round(score, 3), "; ".join(parts)


class CriteriaEvaluator:
    """基于多分位数策略加权评分。"""

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
        """核心评分：多分位数加权的策略收益。

        子项：
        1. IC 水平 + ICIR
        2. 多分位数加权夏普（10% 权重最高）
        3. 多分位数加权收益正负
        4. 多分位数加权胜率
        5. 收益单调性（10% > 5% > 1% 的总收益）
        """
        sub_scores = []
        details = []
        qr = m.quantile_results

        # IC
        if m.ic_mean is not None:
            sub_scores.append(min(abs(m.ic_mean) / 0.05, 1.0))
            details.append(f"IC={m.ic_mean:.4f}")
        if m.icir is not None:
            sub_scores.append(min(abs(m.icir) / 1.5, 1.0))
            details.append(f"ICIR={m.icir:.2f}")

        if qr:
            # 多分位数加权夏普
            sharpe_score, sharpe_detail = _weighted_quantile_score(
                qr, lambda q: max(0, min(q.ann_sharpe / 2.0, 1.0)) if q.ann_sharpe is not None else None
            )
            sub_scores.append(sharpe_score)
            details.append(f"加权sharpe={sharpe_score}({sharpe_detail})")

            # 多分位数加权收益正负
            ret_score, ret_detail = _weighted_quantile_score(
                qr, lambda q: (1.0 if q.ann_ret > 0 else 0.0) if q.ann_ret is not None else None
            )
            sub_scores.append(ret_score)
            details.append(f"加权正收益={ret_score}")

            # 多分位数加权胜率
            wr_score, wr_detail = _weighted_quantile_score(
                qr, lambda q: min(max(0, (q.win_rate - 50) / 30), 1.0) if q.win_rate is not None else None
            )
            sub_scores.append(wr_score)
            details.append(f"加权胜率={wr_score}")

            # 收益单调性检查：宽松分位数总收益 ≥ 严格分位数
            # qr 按 quantile 从高到低排（0.999 最严, 0.9 最宽松在后）
            cum_rets = [(q.quantile, q.cum_ret) for q in qr if q.cum_ret is not None]
            if len(cum_rets) >= 2:
                # 按 quantile 从低到高（宽松到严格）
                cum_rets.sort(key=lambda x: x[0])
                mono = self._monotonicity([r for _, r in cum_rets])
                sub_scores.append(mono)
                details.append(f"收益单调性={mono:.2f}")
        else:
            if m.sharpe is not None:
                sub_scores.append(max(0, min(m.sharpe / 2.0, 1.0)))
                details.append(f"sharpe={m.sharpe:.2f}(fallback)")

        score = sum(sub_scores) / max(len(sub_scores), 1)
        return CriterionScore(
            criterion_id=1, name=CRITERIA[1],
            score=round(score, 3), passed=score >= 0.4,
            detail="; ".join(details),
        )

    def _c2_holding_period_robustness(self, spec: AlphaSpec, m: BacktestMetrics, q: dict) -> CriterionScore:
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
        """年度一致性：多分位数加权的逐年收益。"""
        qr = m.quantile_results
        if qr:
            # 收集所有分位数的年度数据，加权计算"每年是否正收益"
            all_years: set = set()
            for qres in qr:
                all_years.update(qres.annual_returns.keys())
            if all_years:
                year_scores = {}
                for yr in sorted(all_years):
                    # 对该年份，多分位数加权判断是否正收益
                    yr_score, _ = _weighted_quantile_score(
                        qr,
                        lambda q, y=yr: (
                            1.0 if q.annual_returns.get(y) and q.annual_returns[y].ann_ret is not None and q.annual_returns[y].ann_ret > 0
                            else 0.0 if q.annual_returns.get(y) and q.annual_returns[y].ann_ret is not None
                            else None
                        ),
                    )
                    year_scores[yr] = yr_score
                avg = sum(year_scores.values()) / len(year_scores) if year_scores else 0
                positive_yrs = sum(1 for s in year_scores.values() if s > 0.5)
                return CriterionScore(
                    criterion_id=3, name=CRITERIA[3],
                    score=round(avg, 3), passed=avg >= 0.6,
                    detail=f"多分位数加权正收益年份={positive_yrs}/{len(year_scores)}, years={list(year_scores.keys())}",
                )
        # fallback
        if m.annual_returns:
            returns = list(m.annual_returns.values())
            ratio = sum(1 for r in returns if r > 0) / len(returns)
            return CriterionScore(
                criterion_id=3, name=CRITERIA[3],
                score=round(ratio, 3), passed=ratio >= 0.6,
                detail=f"正收益年份占比={ratio:.0%}",
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
        """跨品种稳健性：多分位数加权的分品种收益。"""
        qr = m.quantile_results
        if qr:
            # 收集所有分位数的品种数据
            all_symbols: set = set()
            for qres in qr:
                all_symbols.update(qres.per_symbol_returns.keys())
            if all_symbols:
                sym_scores = {}
                for sym in sorted(all_symbols):
                    sym_score, _ = _weighted_quantile_score(
                        qr,
                        lambda q, s=sym: (
                            1.0 if q.per_symbol_returns.get(s, 0) > 0
                            else 0.0 if s in q.per_symbol_returns
                            else None
                        ),
                    )
                    sym_scores[sym] = sym_score
                avg = sum(sym_scores.values()) / len(sym_scores) if sym_scores else 0
                positive_syms = sum(1 for s in sym_scores.values() if s > 0.5)
                return CriterionScore(
                    criterion_id=6, name=CRITERIA[6],
                    score=round(avg, 3), passed=avg >= 0.5,
                    detail=f"多分位数加权正收益品种={positive_syms}/{len(sym_scores)}, symbols={list(sym_scores.keys())}",
                )
        # fallback
        per_sym = m.per_symbol_returns
        if per_sym:
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
                detail=f"正收益品种占比={positive_ratio:.0%}",
            )
        return CriterionScore(
            criterion_id=6, name=CRITERIA[6],
            score=0.5, passed=True, detail="无分品种数据（需 AlphaGPT 导出 per_symbol_returns）",
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
        """多分位数加权检查多空均衡。"""
        qr = m.quantile_results
        if qr:
            # 加权检查各分位数的多空占比
            skew_score, _ = _weighted_quantile_score(
                qr,
                lambda q: (
                    1.0 if q.long_pct is not None and q.short_pct is not None and (q.long_pct > 80 or q.short_pct > 80)
                    else 0.0 if q.long_pct is not None
                    else None
                ),
            )
            triggered = skew_score > 0.5  # 多数分位数策略都偏向单方向
            return RedFlag(
                flag_id="10.2", description=RED_FLAG_DEFS["10.2"],
                triggered=triggered,
                detail=f"加权方向偏度={skew_score:.2f}" if triggered else "",
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
        if m.quantile_results:
            # 按分位数从宽松到严格报告
            for qr in sorted(m.quantile_results, key=lambda q: q.quantile):
                pct = round((1 - qr.quantile) * 100, 1)
                if qr.ann_sharpe is not None:
                    parts.append(f"{pct}%: sharpe={qr.ann_sharpe:.2f}, ret={qr.ann_ret}")
        elif m.sharpe is not None:
            parts.append(f"sharpe={m.sharpe:.2f}")
        return "理想模板对标: " + ", ".join(parts) if parts else "数据不足"

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
