from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel


class AlphaIdea(BaseModel):
    name: str
    hypothesis: str
    intuition: str
    family: str
    expected_horizon: str
    required_fields: List[str]
    constraints: List[str] = []


class AlphaSpec(BaseModel):
    name: str
    description: str
    formula_expression: str
    required_fields: List[str]
    parameters: Dict[str, Any] = {}
    output_type: Literal["signal", "score", "rank"] = "signal"
    direction: Literal["long", "short", "both", "unknown"] = "unknown"
    implementation_stub: str = ""


class ValidationReport(BaseModel):
    alpha_name: str
    implementable: bool
    lookahead_safe: bool
    data_available: bool
    redundancy_score: float
    quality_score: float
    turnover_risk: str
    regime_risk: str
    metrics: Dict[str, Any] = {}
    warnings: List[str] = []
    critique: Optional[str] = None


class RankedAlpha(BaseModel):
    alpha_name: str
    rank_score: float
    rationale: str
    tags: List[str] = []


class MemoryEntry(BaseModel):
    kind: Literal["success", "failure", "insight"]
    title: str
    content: str
    tags: List[str] = []
    metadata: Dict[str, Any] = {}
