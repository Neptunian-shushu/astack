"""
因子决策器 — 决定因子在库中的命运

基于审计报告、评估结果和改进方案，给出最终决策。
"""

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
    ) -> FactorDecision:

        # 未来数据 → 直接移除
        if audit.lookahead_risk:
            return FactorDecision(
                factor_name=spec.name,
                decision="remove",
                reason="存在未来数据风险",
                priority="high",
            )

        # 不可迁移 → 重写或移除
        if not audit.migratable:
            return FactorDecision(
                factor_name=spec.name,
                decision="remove",
                reason="无法迁移为标准格式",
                priority="medium",
            )

        # 质量很好 → 直接入库
        if report.quality_score >= 0.75 and report.redundancy_score < 0.5:
            return FactorDecision(
                factor_name=spec.name,
                decision="admit",
                reason=f"质量评分={report.quality_score:.2f}，冗余度低",
                priority="high",
            )

        # 质量可以但有改进空间 → 升级
        if report.quality_score >= 0.5:
            return FactorDecision(
                factor_name=spec.name,
                decision="upgrade",
                reason=f"质量={report.quality_score:.2f}，有改进空间: {'; '.join(improvement.improvements)}",
                replacement=improvement.improved_name,
                priority="medium",
            )

        # 质量太差 → 弃用
        if report.quality_score < 0.4:
            return FactorDecision(
                factor_name=spec.name,
                decision="deprecate",
                reason=f"质量评分={report.quality_score:.2f}，低于阈值",
                priority="low",
            )

        # 中间地带 → 暂时保留
        return FactorDecision(
            factor_name=spec.name,
            decision="hold",
            reason=f"质量={report.quality_score:.2f}，暂不决策，需更多数据",
            priority="low",
        )
