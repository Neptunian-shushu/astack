import json
from pathlib import Path
from typing import List
from alphastack.schemas import AlphaSpec, RankedAlpha, ValidationReport


class Exporter:
    def export(self, output_dir: Path, goal: str, specs: List[AlphaSpec], reports: List[ValidationReport], rankings: List[RankedAlpha]) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "goal": goal,
            "specs": [s.model_dump() for s in specs],
            "reports": [r.model_dump() for r in reports],
            "rankings": [r.model_dump() for r in rankings],
        }
        path = output_dir / "alphastack_report.json"
        path.write_text(json.dumps(payload, indent=2))
        return path
