"""
FactorLibrary — 因子库管理

存储已入库因子的完整记录：
- spec, eval_report, status
- family / horizon / tags
- 相关性摘要
"""

import json
from pathlib import Path
from typing import List, Optional
from astack.schemas import AlphaSpec, FactorEvalReport, FactorRecord


class FactorLibrary:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.file = self.root / "factors.jsonl"
        if not self.file.exists():
            self.file.touch()

    def add(self, record: FactorRecord) -> None:
        with self.file.open("a") as f:
            f.write(record.model_dump_json() + "\n")

    def list_all(self) -> List[FactorRecord]:
        return self._read_all()

    def list_admitted(self) -> List[FactorRecord]:
        return [r for r in self._read_all() if r.status == "admitted"]

    def list_testing(self) -> List[FactorRecord]:
        return [r for r in self._read_all() if r.status == "testing"]

    def get(self, name: str) -> Optional[FactorRecord]:
        for r in self._read_all():
            if r.name == name:
                return r
        return None

    def admit(self, name: str) -> bool:
        return self._update_status(name, "admitted")

    def deprecate(self, name: str) -> bool:
        return self._update_status(name, "deprecated")

    def search_by_family(self, family: str) -> List[FactorRecord]:
        return [r for r in self._read_all() if r.family == family]

    def names(self) -> List[str]:
        return [r.name for r in self._read_all()]

    def summary(self) -> dict:
        records = self._read_all()
        by_status: dict = {}
        by_family: dict = {}
        for r in records:
            by_status[r.status] = by_status.get(r.status, 0) + 1
            if r.family:
                by_family[r.family] = by_family.get(r.family, 0) + 1
        return {
            "total": len(records),
            "by_status": by_status,
            "by_family": by_family,
        }

    def diagnostics(self) -> dict:
        """全局因子库诊断：family 分布、拥挤区域、空白区域、相关性聚类"""
        records = self._read_all()
        admitted = [r for r in records if r.status == "admitted"]

        # Family 分布
        family_counts: dict = {}
        for r in admitted:
            f = r.family or "unknown"
            family_counts[f] = family_counts.get(f, 0) + 1
        total = len(admitted) or 1
        family_pct = {f: round(c / total * 100, 1) for f, c in family_counts.items()}

        # 拥挤区域（占比 > 30%）
        overcrowded = [f for f, pct in family_pct.items() if pct > 30 and f != "unknown"]

        # 已知 factor space 维度
        KNOWN_FAMILIES = [
            "momentum", "mean_reversion", "microstructure", "volatility",
            "volume", "liquidity", "cross_sectional", "event_driven",
            "sentiment", "flow", "orderbook",
        ]
        covered = set(family_counts.keys())
        missing = [f for f in KNOWN_FAMILIES if f not in covered]

        # 相关性聚类（基于 correlated_with 字段）
        correlation_clusters: dict = {}
        for r in admitted:
            for corr in r.correlated_with:
                pair = tuple(sorted([r.name, corr]))
                correlation_clusters[str(pair)] = correlation_clusters.get(str(pair), 0) + 1

        # Horizon 分布
        horizon_counts: dict = {}
        for r in admitted:
            h = r.horizon or "unknown"
            horizon_counts[h] = horizon_counts.get(h, 0) + 1

        return {
            "total_admitted": len(admitted),
            "total_all": len(records),
            "family_distribution": family_pct,
            "overcrowded_families": overcrowded,
            "missing_families": missing,
            "horizon_distribution": horizon_counts,
            "correlation_clusters": dict(list(correlation_clusters.items())[:10]),
            "suggested_exploration": missing[:3] if missing else overcrowded[:1],
        }

    def _update_status(self, name: str, new_status: str) -> bool:
        records = self._read_all()
        found = False
        for r in records:
            if r.name == name:
                r.status = new_status
                found = True
        if found:
            self._write_all(records)
        return found

    def _read_all(self) -> List[FactorRecord]:
        records = []
        for line in self.file.read_text().splitlines():
            if not line.strip():
                continue
            records.append(FactorRecord.model_validate_json(line))
        return records

    def _write_all(self, records: List[FactorRecord]) -> None:
        self.file.write_text(
            "\n".join(r.model_dump_json() for r in records) + "\n"
        )
