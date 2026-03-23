"""
ResearchAgent — astack 的主控 workflow 编排器

两条核心 workflow：
1. Alpha Research: generate → formalize → validate → dedupe → rank → evolve
2. Factor Governance: audit → migrate → evaluate → improve → decide

支持完整 loop 或单独调用某个 skill。
"""

import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from astack.config import AStackConfig
from astack.interfaces import EvaluationInterface
from astack.schemas import (
    AlphaIdea,
    AlphaSpec,
    FactorAuditReport,
    FactorDecision,
    FactorRecord,
    GovernanceSummary,
    ImprovementSpec,
    MemoryEntry,
    RankedAlpha,
    ValidationReport,
)
from astack.core.generator import Generator
from astack.core.formalizer import Formalizer
from astack.core.validator import Validator
from astack.core.deduper import Deduper
from astack.core.ranker import Ranker
from astack.core.memory import JsonMemoryStore
from astack.core.evolver import Evolver
from astack.core.exporter import Exporter
from astack.core.criteria import CriteriaEvaluator
from astack.core.experience import ExperienceMemory
from astack.core.factor_library import FactorLibrary
from astack.core.search import SearchStrategy
from astack.core.auditor import FactorAuditor
from astack.core.migrator import FactorMigrator
from astack.core.improver import FactorImprover
from astack.core.decider import FactorDecider


@dataclass
class RunResult:
    """一轮完整 research loop 的结果"""
    goal: str
    ideas: List[AlphaIdea] = field(default_factory=list)
    specs: List[AlphaSpec] = field(default_factory=list)
    reports: List[ValidationReport] = field(default_factory=list)
    survivors: List[AlphaSpec] = field(default_factory=list)
    evolved: List[AlphaSpec] = field(default_factory=list)
    rankings: List[RankedAlpha] = field(default_factory=list)
    export_path: Optional[str] = None


class ResearchAgent:
    """Alpha research workflow 主控。"""

    def __init__(self, config: AStackConfig, adapter: EvaluationInterface) -> None:
        self.config = config
        self.adapter = adapter
        self.generator = Generator()
        self.formalizer = Formalizer()
        self.validator = Validator(adapter)
        self.deduper = Deduper()
        self.ranker = Ranker()
        self.memory = JsonMemoryStore(config.memory_dir)
        self.evolver = Evolver()
        self.exporter = Exporter()
        self.criteria = CriteriaEvaluator()
        self.experience = ExperienceMemory(config.memory_dir / "experience")
        self.library = FactorLibrary(config.memory_dir / "factor_library")
        self.search = SearchStrategy(self.library, self.experience)
        # Governance
        self.auditor = FactorAuditor()
        self.migrator = FactorMigrator()
        self.improver = FactorImprover()
        self.decider = FactorDecider()

    # ------------------------------------------------------------------
    # 完整 loop
    # ------------------------------------------------------------------

    def run(self, goal: str, symbol_set: str = "default") -> RunResult:
        """执行完整的 research loop。"""
        result = RunResult(goal=goal)

        # 1. generate
        result.ideas = self.generate(goal)

        # 2. formalize
        result.specs = self.formalize(result.ideas)

        # 3. validate
        result.reports = self.validate(result.specs, symbol_set)

        # 4. filter + dedupe
        filtered = [r for r in result.reports if r.quality_score >= self.config.min_quality_score]
        deduped = self.dedupe(filtered)

        # 5. identify survivors
        survivor_names = {d.alpha_name for d in deduped}
        result.survivors = [s for s in result.specs if s.name in survivor_names]

        # 6. evolve
        result.evolved = self.evolve(result.survivors)

        # 7. validate evolved
        evolved_reports = self.validate(result.evolved, symbol_set)

        # 8. rank all
        all_reports = deduped + evolved_reports
        result.rankings = self.rank(all_reports)

        # 9. update experience memory
        self._update_experience(all_reports)

        # 10. add to factor library as testing
        all_specs = result.survivors + result.evolved
        self._add_to_library(all_specs, all_reports)

        # 11. export (structured artifact directory)
        research_dir = self.config.output_dir / "research"
        research_dir.mkdir(parents=True, exist_ok=True)
        self._write_json(research_dir / "ideas.json", result.ideas)
        self._write_json(research_dir / "specs.json", all_specs)
        self._write_json(research_dir / "reports.json", all_reports)
        self._write_json(research_dir / "ranked.json", result.rankings)

        path = self.exporter.export(
            self.config.output_dir, goal, all_specs, all_reports, result.rankings
        )
        result.export_path = str(path)

        return result

    # ------------------------------------------------------------------
    # 单独 skill 调用
    # ------------------------------------------------------------------

    def generate(self, goal: str) -> List[AlphaIdea]:
        memory_priors = self.memory.retrieve(goal=goal)
        search_ctx = self.search.build_context()
        return self.generator.generate(
            goal=goal, memory=memory_priors, max_ideas=self.config.max_ideas,
            search_context=search_ctx,
        )

    def formalize(self, ideas: List[AlphaIdea]) -> List[AlphaSpec]:
        return [self.formalizer.formalize(idea) for idea in ideas]

    def validate(self, specs: List[AlphaSpec], symbol_set: str = "default") -> List[ValidationReport]:
        return [self.validator.validate(spec, symbol_set=symbol_set) for spec in specs]

    def dedupe(self, reports: List[ValidationReport]) -> List[ValidationReport]:
        return self.deduper.dedupe(reports, threshold=self.config.correlation_threshold)

    def rank(self, reports: List[ValidationReport]) -> List[RankedAlpha]:
        return self.ranker.rank(reports)

    def evolve(self, specs: List[AlphaSpec]) -> List[AlphaSpec]:
        return self.evolver.evolve(specs, self.config.max_evolved_children)

    # ------------------------------------------------------------------
    # Factor Governance
    # ------------------------------------------------------------------

    def audit(self, specs: List[AlphaSpec]) -> List[FactorAuditReport]:
        return [self.auditor.audit(s) for s in specs]

    def migrate(self, specs: List[AlphaSpec], audits: Optional[List[FactorAuditReport]] = None) -> List[AlphaSpec]:
        if audits is None:
            audits = self.audit(specs)
        return [self.migrator.migrate(s, a) for s, a in zip(specs, audits)]

    def improve(self, specs: List[AlphaSpec], reports: List[ValidationReport]) -> List[ImprovementSpec]:
        return [self.improver.improve(s, r) for s, r in zip(specs, reports)]

    def decide(
        self, specs: List[AlphaSpec], audits: List[FactorAuditReport],
        reports: List[ValidationReport], improvements: List[ImprovementSpec],
    ) -> List[FactorDecision]:
        lib_diag = self.library.diagnostics()
        return [
            self.decider.decide(s, a, r, i, library_diagnostics=lib_diag)
            for s, a, r, i in zip(specs, audits, reports, improvements)
        ]

    def govern(self, specs: List[AlphaSpec], symbol_set: str = "default") -> GovernanceSummary:
        """完整治理 loop: audit → migrate → evaluate → improve → decide → summary"""
        lib_before = self.library.diagnostics()

        # 1. audit
        audits = self.audit(specs)
        # 2. migrate
        migrated = self.migrate(specs, audits)
        # 3. evaluate
        reports = self.validate(migrated, symbol_set)
        # 4. improve
        improvements = self.improve(migrated, reports)
        # 5. decide (with library global awareness)
        decisions = self.decide(migrated, audits, reports, improvements)
        # 6. update library
        for spec, dec in zip(migrated, decisions):
            if dec.decision == "admit":
                self.library.add(FactorRecord(name=spec.name, spec=spec, status="admitted"))
            elif dec.decision == "upgrade" and dec.replacement:
                imp = next((i for i in improvements if i.improved_name == dec.replacement), None)
                if imp and imp.new_spec:
                    self.library.add(FactorRecord(name=imp.improved_name, spec=imp.new_spec, status="testing"))
                self.library.deprecate(spec.name)
            elif dec.decision in ("deprecate", "remove"):
                self.library.deprecate(spec.name)

        lib_after = self.library.diagnostics()

        # 7. build summary
        by_decision = Counter(d.decision for d in decisions)
        all_issues: list = []
        for a in audits:
            all_issues.extend(a.potential_issues)
        top_issues = [issue for issue, _ in Counter(all_issues).most_common(5)]

        recommendations = []
        if lib_after.get("missing_families"):
            recommendations.append(f"建议探索空白领域: {', '.join(lib_after['missing_families'][:3])}")
        if lib_after.get("overcrowded_families"):
            recommendations.append(f"以下领域已拥挤: {', '.join(lib_after['overcrowded_families'])}")
        if by_decision.get("deprecate", 0) + by_decision.get("remove", 0) > len(specs) * 0.5:
            recommendations.append("超过半数因子被弃用，建议重新审视因子库构建策略")
        if by_decision.get("upgrade", 0) > 0:
            recommendations.append(f"{by_decision['upgrade']}个因子建议升级，优先处理 high priority 项")

        summary = GovernanceSummary(
            total_audited=len(specs),
            by_decision=dict(by_decision),
            top_issues=top_issues,
            most_redundant_family=lib_after.get("overcrowded_families", [""])[0] if lib_after.get("overcrowded_families") else "",
            most_missing_families=lib_after.get("missing_families", [])[:3],
            library_before=lib_before,
            library_after=lib_after,
            decisions=decisions,
            recommendations=recommendations,
        )

        # 8. write governance artifacts
        gov_dir = self.config.output_dir / "governance"
        gov_dir.mkdir(parents=True, exist_ok=True)
        self._write_json(gov_dir / "audits.json", audits)
        self._write_json(gov_dir / "migrated.json", migrated)
        self._write_json(gov_dir / "reports.json", reports)
        self._write_json(gov_dir / "improvements.json", improvements)
        self._write_json(gov_dir / "decisions.json", decisions)
        self._write_json(gov_dir / "summary.json", summary)

        return summary

    # ------------------------------------------------------------------
    # 内部
    # ------------------------------------------------------------------

    def _update_experience(self, reports: List[ValidationReport]) -> None:
        for report in reports:
            entry = MemoryEntry(
                kind="success" if report.quality_score >= self.config.min_quality_score else "failure",
                title=report.alpha_name,
                content=report.critique or f"quality={report.quality_score}; warnings={report.warnings}",
                tags=[report.turnover_risk, report.regime_risk],
                metadata=report.metrics,
            )
            self.experience.record(entry)
            self.memory.add(entry)

    @staticmethod
    def _write_json(path: Path, data) -> None:
        if hasattr(data, "model_dump"):
            payload = data.model_dump()
        elif isinstance(data, list) and data and hasattr(data[0], "model_dump"):
            payload = [d.model_dump() for d in data]
        else:
            payload = data
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False))

    def _add_to_library(self, specs: List[AlphaSpec], reports: List[ValidationReport]) -> None:
        report_map = {r.alpha_name: r for r in reports}
        existing = set(self.library.names())
        for spec in specs:
            if spec.name in existing:
                continue
            report = report_map.get(spec.name)
            self.library.add(FactorRecord(
                name=spec.name,
                spec=spec,
                status="testing",
                family=spec.parameters.get("family", ""),
                horizon=spec.parameters.get("horizon", ""),
            ))
