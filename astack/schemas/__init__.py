from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


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


# ---------------------------------------------------------------------------
# 单因子评价体系（对应 15 条评价标准）
# ---------------------------------------------------------------------------

class BacktestMetrics(BaseModel):
    """adapter 回测返回的原始指标"""
    ic_mean: Optional[float] = None
    ic_std: Optional[float] = None
    icir: Optional[float] = None
    ic_series: List[float] = Field(default_factory=list)
    decile_returns: List[float] = Field(default_factory=list)
    long_return: Optional[float] = None
    short_return: Optional[float] = None
    long_short_return: Optional[float] = None
    sharpe: Optional[float] = None
    annual_returns: Dict[str, float] = Field(default_factory=dict)
    holding_period_sharpes: Dict[str, float] = Field(default_factory=dict)
    per_symbol_returns: Dict[str, float] = Field(default_factory=dict)
    max_drawdown: Optional[float] = None
    recent_2y_return: Optional[float] = None
    recent_2y_max_drawdown: Optional[float] = None
    train_sharpe: Optional[float] = None
    val_sharpe: Optional[float] = None
    test_sharpe: Optional[float] = None
    extra: Dict[str, Any] = Field(default_factory=dict)


class CriterionScore(BaseModel):
    """单项评价标准的得分"""
    criterion_id: int
    name: str
    score: float = Field(ge=0, le=1)
    passed: bool
    detail: str = ""


class RedFlag(BaseModel):
    """否决条件（对应标准 14）"""
    flag_id: str
    description: str
    triggered: bool
    detail: str = ""


class FactorEvalReport(BaseModel):
    """完整的单因子评价报告"""
    alpha_name: str
    backtest_metrics: BacktestMetrics = Field(default_factory=BacktestMetrics)

    # 各维度评分（对应标准 1-12）
    criteria_scores: List[CriterionScore] = Field(default_factory=list)

    # 否决条件（对应标准 14）
    red_flags: List[RedFlag] = Field(default_factory=list)

    # 汇总
    overall_score: float = 0.0
    verdict: Literal["pass", "marginal", "fail"] = "fail"
    ideal_template_match: str = ""        # 对应标准 13
    validation_protocol: str = ""         # 对应标准 15

    summary: str = ""


# ---------------------------------------------------------------------------
# 原有兼容类型（pipeline 其他环节使用）
# ---------------------------------------------------------------------------

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
    eval_report: Optional[FactorEvalReport] = None


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


# ---------------------------------------------------------------------------
# Factor Library
# ---------------------------------------------------------------------------

class FactorRecord(BaseModel):
    """入库因子的完整记录"""
    name: str
    spec: AlphaSpec
    eval_report: Optional[FactorEvalReport] = None
    status: Literal["admitted", "deprecated", "testing"] = "testing"
    family: str = ""
    horizon: str = ""
    tags: List[str] = Field(default_factory=list)
    correlated_with: List[str] = Field(default_factory=list)
    notes: str = ""
