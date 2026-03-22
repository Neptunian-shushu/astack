from pathlib import Path
from pydantic import BaseModel, Field

class AStackConfig(BaseModel):
    max_ideas: int = 10
    max_evolved_children: int = 8
    correlation_threshold: float = 0.7
    min_quality_score: float = 0.55
    output_dir: Path = Field(default=Path("outputs"))
    memory_dir: Path = Field(default=Path("memory_store"))
    export_format: str = "json"
