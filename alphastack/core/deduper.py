from typing import List
from alphastack.schemas import ValidationReport


class Deduper:
    """Simple deduper. Replace with true signal/factor correlation logic."""

    def dedupe(self, reports: List[ValidationReport], threshold: float) -> List[ValidationReport]:
        seen = set()
        kept = []
        for report in sorted(reports, key=lambda x: x.quality_score, reverse=True):
            key = report.alpha_name.split("_")[0]
            if key in seen and report.redundancy_score >= threshold:
                continue
            kept.append(report)
            seen.add(key)
        return kept
