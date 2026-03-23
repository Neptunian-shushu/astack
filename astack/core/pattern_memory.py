"""
PatternMemory — 从历史因子中提取抽象模式

不只是存储 success/failure 条目，而是提炼出：
- 成功模式（什么类型的因子容易成功）
- 失败模式（什么组合容易失败）
- 约束条件（generator 应该避免什么、探索什么）
"""

from collections import Counter
from typing import Dict, List, Tuple
from astack.schemas import MemoryEntry


class FactorPattern:
    """一个抽象的因子模式"""
    def __init__(self, pattern_type: str, description: str, confidence: float, examples: List[str]):
        self.pattern_type = pattern_type  # "success" | "failure" | "risk"
        self.description = description
        self.confidence = confidence       # 0~1, 出现频率越高越 confident
        self.examples = examples


class PatternMemory:
    """从 ExperienceMemory 的原始条目中提取可复用的抽象模式"""

    def extract_patterns(
        self,
        successes: List[MemoryEntry],
        failures: List[MemoryEntry],
    ) -> List[FactorPattern]:
        patterns = []
        patterns.extend(self._extract_success_patterns(successes))
        patterns.extend(self._extract_failure_patterns(failures))
        patterns.extend(self._extract_risk_patterns(successes, failures))
        return patterns

    def get_search_constraints(
        self,
        successes: List[MemoryEntry],
        failures: List[MemoryEntry],
    ) -> Dict:
        """生成 generator 可直接使用的搜索约束"""
        patterns = self.extract_patterns(successes, failures)

        avoid = []
        explore = []
        prefer = []

        for p in patterns:
            if p.pattern_type == "failure" and p.confidence >= 0.3:
                avoid.append(p.description)
            elif p.pattern_type == "success" and p.confidence >= 0.3:
                prefer.append(p.description)
            elif p.pattern_type == "risk":
                avoid.append(p.description)

        # 从成功模式中推导探索方向
        success_tags = self._count_tags(successes)
        failure_tags = self._count_tags(failures)
        for tag, count in success_tags.most_common(5):
            if tag and failure_tags.get(tag, 0) < count:
                explore.append(f"{tag} 方向（历史成功率高）")

        return {
            "avoid_patterns": avoid[:5],
            "explore_directions": explore[:5],
            "prefer_patterns": prefer[:5],
        }

    def _extract_success_patterns(self, successes: List[MemoryEntry]) -> List[FactorPattern]:
        if not successes:
            return []
        patterns = []
        tag_counts = self._count_tags(successes)
        total = len(successes)

        for tag, count in tag_counts.most_common(5):
            if not tag or count < 2:
                continue
            confidence = count / total
            examples = [s.title for s in successes if tag in s.tags][:3]
            patterns.append(FactorPattern(
                pattern_type="success",
                description=f"{tag} 类因子成功率较高 ({count}/{total})",
                confidence=confidence,
                examples=examples,
            ))

        # 内容关键词模式
        keyword_patterns = self._extract_keyword_patterns(successes, "success")
        patterns.extend(keyword_patterns)
        return patterns

    def _extract_failure_patterns(self, failures: List[MemoryEntry]) -> List[FactorPattern]:
        if not failures:
            return []
        patterns = []
        tag_counts = self._count_tags(failures)
        total = len(failures)

        for tag, count in tag_counts.most_common(5):
            if not tag or count < 2:
                continue
            confidence = count / total
            examples = [f.title for f in failures if tag in f.tags][:3]
            patterns.append(FactorPattern(
                pattern_type="failure",
                description=f"{tag} 类因子失败率较高 ({count}/{total})",
                confidence=confidence,
                examples=examples,
            ))

        keyword_patterns = self._extract_keyword_patterns(failures, "failure")
        patterns.extend(keyword_patterns)
        return patterns

    def _extract_risk_patterns(
        self, successes: List[MemoryEntry], failures: List[MemoryEntry]
    ) -> List[FactorPattern]:
        """交叉分析：哪些 tag 在成功和失败中都出现"""
        patterns = []
        success_tags = self._count_tags(successes)
        failure_tags = self._count_tags(failures)

        for tag in set(success_tags) & set(failure_tags):
            if not tag:
                continue
            s_count = success_tags[tag]
            f_count = failure_tags[tag]
            if f_count > s_count:
                patterns.append(FactorPattern(
                    pattern_type="risk",
                    description=f"{tag} 方向不稳定（成功{s_count}次 vs 失败{f_count}次）",
                    confidence=f_count / (s_count + f_count),
                    examples=[],
                ))
        return patterns

    def _extract_keyword_patterns(
        self, entries: List[MemoryEntry], pattern_type: str
    ) -> List[FactorPattern]:
        """从内容中提取高频关键词模式"""
        keywords: Counter = Counter()
        for e in entries:
            words = e.content.lower().split()
            for w in words:
                if len(w) > 3 and w.isalpha():
                    keywords[w] += 1
        patterns = []
        total = len(entries)
        for word, count in keywords.most_common(3):
            if count >= 2:
                confidence = count / total
                patterns.append(FactorPattern(
                    pattern_type=pattern_type,
                    description=f"关键词 '{word}' 在{pattern_type}中频繁出现 ({count}/{total})",
                    confidence=confidence,
                    examples=[],
                ))
        return patterns

    @staticmethod
    def _count_tags(entries: List[MemoryEntry]) -> Counter:
        tags: Counter = Counter()
        for e in entries:
            for t in e.tags:
                if t:
                    tags[t] += 1
        return tags
