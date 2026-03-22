from alphastack.config import AlphaStackConfig
from alphastack.interfaces import EvaluationInterface
from alphastack.schemas import MemoryEntry
from alphastack.core.generator import Generator
from alphastack.core.formalizer import Formalizer
from alphastack.core.validator import Validator
from alphastack.core.deduper import Deduper
from alphastack.core.ranker import Ranker
from alphastack.core.memory import JsonMemoryStore
from alphastack.core.evolver import Evolver
from alphastack.core.exporter import Exporter


class AlphaPipeline:
    def __init__(self, config: AlphaStackConfig, adapter: EvaluationInterface) -> None:
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

    def run(self, goal: str, symbol_set: str):
        memory_priors = self.memory.retrieve(goal=goal)
        ideas = self.generator.generate(goal=goal, memory=memory_priors, max_ideas=self.config.max_ideas)
        specs = [self.formalizer.formalize(idea) for idea in ideas]
        reports = [self.validator.validate(spec, symbol_set=symbol_set) for spec in specs]
        filtered = [r for r in reports if r.quality_score >= self.config.min_quality_score]
        deduped = self.deduper.dedupe(filtered, threshold=self.config.correlation_threshold)

        survivor_names = {d.alpha_name for d in deduped}
        survivor_specs = [s for s in specs if s.name in survivor_names]
        evolved_specs = self.evolver.evolve(survivor_specs, self.config.max_evolved_children)
        evolved_reports = [self.validator.validate(spec, symbol_set=symbol_set) for spec in evolved_specs]

        all_specs = survivor_specs + evolved_specs
        all_reports = deduped + evolved_reports
        rankings = self.ranker.rank(all_reports)

        for report in all_reports:
            self.memory.add(
                MemoryEntry(
                    kind="success" if report.quality_score >= self.config.min_quality_score else "failure",
                    title=report.alpha_name,
                    content=report.critique or f"quality={report.quality_score}; warnings={report.warnings}",
                    tags=[report.turnover_risk, report.regime_risk],
                    metadata=report.metrics,
                )
            )

        return self.exporter.export(self.config.output_dir, goal, all_specs, all_reports, rankings)
