"""
因子决策器 — 决定因子在库中的命运

不只是 threshold-based，而是综合考虑：
- 审计结果
- 评估质量
- 冗余度（是否和已有因子高度相关）
- 改进潜力
- 因子库全局状态（是否填补空白）

决策类型：admit / upgrade / evolve / combine / deprecate / remove / hold
"""

from typing import Optional
from astack.schemas import (
    AlphaSpec,
    FactorAuditReport,
    FactorDecision,
    ImprovementSpec,
    ValidationReport,
)


class FactorDecider:

    def decide(
        self,
        spec: AlphaSpec,
        audit: FactorAuditReport,
        report: ValidationReport,
        improvement: ImprovementSpec,
        library_diagnostics: Optional[dict] = None,
    ) -> FactorDecision:

        # === 一票否决 ===

        if audit.lookahead_risk:
            return FactorDecision(
                factor_name=spec.name,
                decision="remove",
                reason="存在未来数据风险",
                priority="high",
            )

        if not audit.migratable:
            return FactorDecision(
                factor_name=spec.name,
                decision="remove",
                reason="无法迁移为标准格式",
                priority="medium",
            )

        # === 综合评分 ===
        q = report.quality_score
        r = report.redundancy_score
        fills_gap = self._fills_library_gap(spec, library_diagnostics)

        # 高质量 + 低冗余 → 直接入库
        if q >= 0.75 and r < 0.5:
            return FactorDecision(
                factor_name=spec.name,
                decision="admit",
                reason=f"质量={q:.2f}，冗余度={r:.2f}，达到入库标准",
                priority="high",
            )

        # 高质量但高冗余 → 尝试正交化
        if q >= 0.7 and r >= 0.5:
            return FactorDecision(
                factor_name=spec.name,
                decision="upgrade",
                reason=f"质量好({q:.2f})但冗余高({r:.2f})，建议正交化后入库",
                replacement=improvement.improved_name,
                priority="medium",
            )

        # 中等质量 + 填补空白 → 优先升级
        if q >= 0.5 and fills_gap:
            return FactorDecision(
                factor_name=spec.name,
                decision="upgrade",
                reason=f"质量={q:.2f}，填补因子库空白领域，值得改进",
                replacement=improvement.improved_name,
                priority="high",
            )

        # 中等质量 → 标准升级流程
        if q >= 0.5:
            return FactorDecision(
                factor_name=spec.name,
                decision="upgrade",
                reason=f"质量={q:.2f}，改进方向: {'; '.join(improvement.improvements)}",
                replacement=improvement.improved_name,
                priority="medium",
            )

        # 低质量但有某些可取之处 → 保留观察
        if q >= 0.4 and audit.hypothesis_clarity >= 0.6:
            return FactorDecision(
                factor_name=spec.name,
                decision="hold",
                reason=f"质量偏低({q:.2f})但经济逻辑清晰，暂保留待进一步研究",
                priority="low",
            )

        # 质量差 → 弃用
        return FactorDecision(
            factor_name=spec.name,
            decision="deprecate",
            reason=f"质量={q:.2f}，低于阈值，建议弃用",
            priority="low",
        )

    def _fills_library_gap(self, spec: AlphaSpec, diagnostics: Optional[dict]) -> bool:
        """判断该因子是否填补因子库空白"""
        if not diagnostics:
            return False
        missing = diagnostics.get("missing_families", [])
        # 检查 spec 的描述/公式是否涉及缺失 family
        text = (spec.description + " " + spec.formula_expression).lower()
        return any(m.lower() in text for m in missing)
