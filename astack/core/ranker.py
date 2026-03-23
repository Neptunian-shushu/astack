from typing import Dict, List, Optional
from astack.schemas import RankedAlpha, ValidationReport

# Confidence 降权系数
CONFIDENCE_WEIGHT = {"high": 1.0, "medium": 0.85, "low": 0.6}


class Ranker:
    def rank(
        self,
        reports: List[ValidationReport],
        confidence_map: Optional[Dict[str, str]] = None,
    ) -> List[RankedAlpha]:
        """排序，支持 confidence 降权。

        confidence_map: {alpha_name: "high"|"medium"|"low"}
        """
        conf = confidence_map or {}
        scored = []
        for report in reports:
            base = report.quality_score
            c = conf.get(report.alpha_name, "high")
            weight = CONFIDENCE_WEIGHT.get(c, 1.0)
            adjusted = round(base * weight, 4)
            scored.append((report, adjusted, c))

        scored.sort(key=lambda x: x[1], reverse=True)
        ranked = []
        for report, adj_score, c in scored:
            conf_note = f" [confidence={c}, adjusted]" if c != "high" else ""
            ranked.append(
                RankedAlpha(
                    alpha_name=report.alpha_name,
                    rank_score=adj_score,
                    rationale=f"Quality={report.quality_score:.3f}; redundancy={report.redundancy_score:.3f}{conf_note}",
                    tags=[report.turnover_risk, report.regime_risk],
                )
            )
        return ranked
