"""
因子迁移器 — 将旧因子统一为标准 AlphaSpec

Demo 实现：对已有 spec 做规范化。
真实场景应由 LLM 将非结构化的旧因子代码转成标准 AlphaSpec。
"""

from astack.schemas import AlphaSpec, FactorAuditReport


class FactorMigrator:

    def migrate(self, spec: AlphaSpec, audit: FactorAuditReport) -> AlphaSpec:
        """将旧因子规范化为标准 AlphaSpec。"""
        migrated = spec.model_copy(deep=True)

        # 补充方向
        if migrated.direction == "unknown":
            migrated.direction = "both"

        # 规范名称（去空格，小写）
        migrated.name = migrated.name.strip().lower().replace(" ", "_")

        # 补充描述
        if not migrated.description or len(migrated.description) < 10:
            migrated.description = audit.core_logic or f"Migrated factor: {migrated.name}"

        return migrated
