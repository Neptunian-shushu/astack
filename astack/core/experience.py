"""
ExperienceMemory — 研究经验积累

存储并检索：
- 成功的 alpha 模式
- 失败的 alpha 模式及 rejection reason
- 高相关的因子 family
- 推荐的探索方向
"""

import json
from pathlib import Path
from typing import List
from astack.schemas import MemoryEntry


class ExperienceMemory:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.successes_file = self.root / "successes.jsonl"
        self.failures_file = self.root / "failures.jsonl"
        self.insights_file = self.root / "insights.jsonl"
        for f in [self.successes_file, self.failures_file, self.insights_file]:
            if not f.exists():
                f.touch()

    def record(self, entry: MemoryEntry) -> None:
        target = {
            "success": self.successes_file,
            "failure": self.failures_file,
            "insight": self.insights_file,
        }[entry.kind]
        with target.open("a") as f:
            f.write(entry.model_dump_json() + "\n")

    def get_successes(self, limit: int = 20) -> List[MemoryEntry]:
        return self._read(self.successes_file, limit)

    def get_failures(self, limit: int = 20) -> List[MemoryEntry]:
        return self._read(self.failures_file, limit)

    def get_insights(self, limit: int = 20) -> List[MemoryEntry]:
        return self._read(self.insights_file, limit)

    def search(self, query: str, limit: int = 10) -> List[MemoryEntry]:
        tokens = [t for t in query.lower().split() if len(t) > 2]
        results = []
        for f in [self.successes_file, self.failures_file, self.insights_file]:
            for entry in self._read(f, limit=999):
                text = (entry.title + " " + entry.content).lower()
                if any(t in text for t in tokens):
                    results.append(entry)
        return results[-limit:]

    def summary(self) -> dict:
        successes = self._read(self.successes_file, limit=999)
        failures = self._read(self.failures_file, limit=999)
        # 提取常见 rejection reasons
        rejection_reasons: dict = {}
        for f in failures:
            for tag in f.tags:
                rejection_reasons[tag] = rejection_reasons.get(tag, 0) + 1
        # 提取成功 family 分布
        success_families: dict = {}
        for s in successes:
            for tag in s.tags:
                success_families[tag] = success_families.get(tag, 0) + 1
        return {
            "total_successes": len(successes),
            "total_failures": len(failures),
            "top_rejection_reasons": sorted(rejection_reasons.items(), key=lambda x: -x[1])[:5],
            "top_success_families": sorted(success_families.items(), key=lambda x: -x[1])[:5],
        }

    @staticmethod
    def _read(path: Path, limit: int) -> List[MemoryEntry]:
        entries = []
        for line in path.read_text().splitlines():
            if not line.strip():
                continue
            entries.append(MemoryEntry.model_validate_json(line))
        return entries[-limit:]
