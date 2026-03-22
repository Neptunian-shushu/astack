"""
因子审计器 — 解析旧因子，输出审计报告

Demo 实现：基于 spec 的字段做简单分析。
真实场景应由 LLM 审查因子代码和文档。
"""

from astack.schemas import AlphaSpec, FactorAuditReport


class FactorAuditor:

    def audit(self, spec: AlphaSpec) -> FactorAuditReport:
        issues = []
        # 检查参数数量
        if len(spec.parameters) > 3:
            issues.append(f"参数过多({len(spec.parameters)}个)，过拟合风险")
        # 检查实现
        impl_clarity = 0.8 if spec.implementation_stub.strip() else 0.2
        if not spec.implementation_stub.strip():
            issues.append("缺少实现代码")
        # 检查公式
        hyp_clarity = 0.7 if spec.description and len(spec.description) > 10 else 0.3
        if not spec.description:
            issues.append("缺少因子描述/假设")
        # 检查方向
        if spec.direction == "unknown":
            issues.append("方向未定义")
        # 猜测 factor type
        expr_lower = spec.formula_expression.lower()
        if "volume" in expr_lower:
            ftype = "成交量相关"
        elif "return" in expr_lower or "momentum" in expr_lower:
            ftype = "动量/反转"
        elif "volatil" in expr_lower:
            ftype = "波动率"
        else:
            ftype = "其他"
        # 换手率估计
        if "rank" in expr_lower or "zscore" in expr_lower:
            turnover = "medium"
        else:
            turnover = "unknown"
        # 可迁移性
        migratable = bool(spec.formula_expression.strip() and spec.required_fields)
        if not migratable:
            issues.append("公式或字段缺失，无法迁移")
        # 建议操作
        if not migratable:
            action = "rewrite"
        elif len(issues) >= 3:
            action = "rewrite"
        elif issues:
            action = "migrate"
        else:
            action = "migrate"

        return FactorAuditReport(
            factor_name=spec.name,
            core_logic=spec.description[:200] if spec.description else "",
            factor_type=ftype,
            hypothesis_clarity=hyp_clarity,
            implementation_clarity=impl_clarity,
            required_fields=spec.required_fields,
            potential_issues=issues,
            lookahead_risk=False,
            turnover_estimate=turnover,
            migratable=migratable,
            suggested_action=action,
        )
