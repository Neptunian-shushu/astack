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

class QuantileResult(BaseModel):
    """单个分位数阈值的策略结果"""
    quantile: float = 0.0                   # 分位数 (0.999=0.1%, 0.99=1%, 0.95=5%, 0.9=10%)
    label: str = ""                         # "q10bp", "q100bp" 等
    ann_sharpe: Optional[float] = None
    ann_ret: Optional[float] = None
    cum_ret: Optional[float] = None
    avg_n_trades: Optional[float] = None
    win_rate: Optional[float] = None
    avg_holding_bars: Optional[float] = None
    long_pct: Optional[float] = None        # 多头占比
    short_pct: Optional[float] = None       # 空头占比


class BacktestMetrics(BaseModel):
    """adapter 回测返回的原始指标"""
    ic_mean: Optional[float] = None
    ic_std: Optional[float] = None
    icir: Optional[float] = None
    ic_series: List[float] = Field(default_factory=list)
    decile_returns: List[float] = Field(default_factory=list)

    # 各分位数的策略结果（核心）
    quantile_results: List[QuantileResult] = Field(default_factory=list)

    # 兼容旧字段（从最优分位数提取）
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


# ---------------------------------------------------------------------------
# Factor Governance（因子治理）
# ---------------------------------------------------------------------------

class FactorAuditReport(BaseModel):
    """因子审计报告 — 搞清楚旧因子在干什么、是否合格"""
    factor_name: str
    core_logic: str = ""                    # 核心逻辑描述
    factor_type: str = ""                   # 因子类型（成交量反转/动量/...）
    hypothesis_clarity: float = 0.0         # 假设清晰度 0~1
    implementation_clarity: float = 0.0     # 实现清晰度 0~1
    required_fields: List[str] = Field(default_factory=list)
    potential_issues: List[str] = Field(default_factory=list)
    lookahead_risk: bool = False
    turnover_estimate: Literal["low", "medium", "high", "unknown"] = "unknown"
    migratable: bool = True
    suggested_action: Literal["migrate", "rewrite", "deprecate", "keep_as_is"] = "migrate"
    notes: str = ""


class ImprovementSpec(BaseModel):
    """因子改进方案"""
    original_name: str
    improved_name: str
    improvements: List[str] = Field(default_factory=list)
    new_spec: Optional[AlphaSpec] = None
    expected_gains: str = ""                # 预期改进效果
    risk_notes: List[str] = Field(default_factory=list)


class FactorDecision(BaseModel):
    """因子最终决策"""
    factor_name: str
    decision: Literal["admit", "upgrade", "deprecate", "remove", "hold"]
    reason: str = ""
    replacement: Optional[str] = None       # 替代因子名称
    priority: Literal["high", "medium", "low"] = "medium"


class GovernanceSummary(BaseModel):
    """治理批量汇总报告 — 管理层视角"""
    total_audited: int = 0
    by_decision: Dict[str, int] = Field(default_factory=dict)
    top_issues: List[str] = Field(default_factory=list)
    most_redundant_family: str = ""
    most_missing_families: List[str] = Field(default_factory=list)
    library_before: Dict[str, Any] = Field(default_factory=dict)
    library_after: Dict[str, Any] = Field(default_factory=dict)
    decisions: List[FactorDecision] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
