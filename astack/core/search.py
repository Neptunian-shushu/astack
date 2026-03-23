"""
SearchStrategy — 引导式因子搜索

不是 brute-force + LLM imagination，而是：
  exploration = f(library_diagnostics, pattern_constraints, correlation_gaps)

将 PatternMemory 的搜索约束 + FactorLibrary 的全局诊断
融合成一个 SearchContext，让 generator 知道：
- 往哪个方向探索
- 避免什么模式
- 填补什么空白
"""

from dataclasses import dataclass, field
from typing import Dict, List

from astack.core.experience import ExperienceMemory
from astack.core.factor_library import FactorLibrary
from astack.core.pattern_memory import PatternMemory


@dataclass
class SearchContext:
    """generator 直接使用的搜索上下文"""
    # 应该探索的方向
    explore_directions: List[str] = field(default_factory=list)
    # 应该避免的模式
    avoid_patterns: List[str] = field(default_factory=list)
    # 偏好的模式（历史成功率高）
    prefer_patterns: List[str] = field(default_factory=list)
    # 因子库空白区域
    missing_spaces: List[str] = field(default_factory=list)
    # 因子库拥挤区域（低优先级）
    overcrowded_areas: List[str] = field(default_factory=list)
    # 已有因子名（避免重复）
    existing_names: List[str] = field(default_factory=list)
    # 汇总 prompt hint（可直接拼入 LLM prompt）
    prompt_hint: str = ""

    def to_prompt(self) -> str:
        """生成可直接嵌入 LLM prompt 的搜索指令"""
        parts = []
        if self.missing_spaces:
            parts.append(f"重点探索以下空白领域: {', '.join(self.missing_spaces)}")
        if self.explore_directions:
            parts.append(f"推荐探索方向: {', '.join(self.explore_directions)}")
        if self.prefer_patterns:
            parts.append(f"历史成功模式: {', '.join(self.prefer_patterns)}")
        if self.avoid_patterns:
            parts.append(f"避免以下模式: {', '.join(self.avoid_patterns)}")
        if self.overcrowded_areas:
            parts.append(f"以下领域已拥挤，低优先级: {', '.join(self.overcrowded_areas)}")
        if self.existing_names:
            parts.append(f"已有因子({len(self.existing_names)}个)，避免重复")
        return "\n".join(parts) if parts else "无特定搜索约束，自由探索"


class SearchStrategy:
    """融合 library diagnostics + pattern memory 生成搜索策略"""

    def __init__(self, library: FactorLibrary, experience: ExperienceMemory):
        self.library = library
        self.experience = experience
        self.pattern_memory = PatternMemory()

    def build_context(self) -> SearchContext:
        # 1. Library 全局诊断
        lib_diag = self.library.diagnostics()

        # 2. Pattern Memory 搜索约束
        successes = self.experience.get_successes(limit=50)
        failures = self.experience.get_failures(limit=50)
        constraints = self.pattern_memory.get_search_constraints(successes, failures)

        # 3. 融合
        ctx = SearchContext(
            explore_directions=constraints.get("explore_directions", [])
                + lib_diag.get("suggested_exploration", []),
            avoid_patterns=constraints.get("avoid_patterns", []),
            prefer_patterns=constraints.get("prefer_patterns", []),
            missing_spaces=lib_diag.get("missing_families", []),
            overcrowded_areas=lib_diag.get("overcrowded_families", []),
            existing_names=self.library.names(),
        )
        ctx.prompt_hint = ctx.to_prompt()
        return ctx
