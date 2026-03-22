"""
ResearchAgent — astack 的主控 workflow 编排器

将各个 skill 串联成完整的 alpha research loop：
generate → formalize → validate/critique → dedupe → rank → evolve → export

支持两种使用方式：
1. agent.run(goal) — 跑完整 loop
2. agent.generate(goal) / agent.formalize(ideas) / ... — 单独调用某个 skill
"""

from dataclasses import dataclass, field
from typing import List, Optional

from astack.config import AStackConfig
from astack.interfaces import EvaluationInterface
from astack.schemas import (
    AlphaIdea,
    AlphaSpec,
    FactorRecord,
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

        # 11. export
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
        library_context = self._build_library_context()
        return self.generator.generate(
            goal=goal, memory=memory_priors, max_ideas=self.config.max_ideas,
            library_context=library_context,
        )

    def _build_library_context(self) -> dict:
        lib_summary = self.library.summary()
        exp_summary = self.experience.summary()
        return {
            "existing_names": self.library.names(),
            "family_distribution": lib_summary.get("by_family", {}),
            "total_admitted": lib_summary.get("by_status", {}).get("admitted", 0),
            "total_testing": lib_summary.get("by_status", {}).get("testing", 0),
            "top_rejection_reasons": exp_summary.get("top_rejection_reasons", []),
            "top_success_families": exp_summary.get("top_success_families", []),
        }

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
