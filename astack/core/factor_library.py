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
        by_status = {}
        by_family = {}
        for r in records:
            by_status[r.status] = by_status.get(r.status, 0) + 1
            if r.family:
                by_family[r.family] = by_family.get(r.family, 0) + 1
        return {
            "total": len(records),
            "by_status": by_status,
            "by_family": by_family,
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
