import json
from datetime import datetime
from pathlib import Path
from typing import List
from astack.schemas import AlphaSpec, RankedAlpha, ValidationReport


class Exporter:
    def export(self, output_dir: Path, goal: str, specs: List[AlphaSpec], reports: List[ValidationReport], rankings: List[RankedAlpha]) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "goal": goal,
            "specs": [s.model_dump() for s in specs],
            "reports": [r.model_dump() for r in reports],
            "rankings": [r.model_dump() for r in rankings],
        }
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = output_dir / f"astack_report_{ts}.json"
        path.write_text(json.dumps(payload, indent=2))
        return path
