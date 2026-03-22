from typing import List
from astack.schemas import RankedAlpha, ValidationReport


class Ranker:
    def rank(self, reports: List[ValidationReport]) -> List[RankedAlpha]:
        ranked = []
        for report in sorted(reports, key=lambda x: x.quality_score, reverse=True):
            ranked.append(
                RankedAlpha(
                    alpha_name=report.alpha_name,
                    rank_score=report.quality_score,
                    rationale=f"Quality={report.quality_score:.3f}; redundancy={report.redundancy_score:.3f}; implementable={report.implementable}",
                    tags=[report.turnover_risk, report.regime_risk],
                )
            )
        return ranked
