from pathlib import Path
from typing import List
from alphastack.interfaces import MemoryInterface
from alphastack.schemas import MemoryEntry


class JsonMemoryStore(MemoryInterface):
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.file = self.root / "memory.jsonl"
        if not self.file.exists():
            self.file.touch()

    def retrieve(self, goal: str, limit: int = 5) -> List[MemoryEntry]:
        entries: List[MemoryEntry] = []
        token = goal.lower().split()[0] if goal.split() else ""
        for line in self.file.read_text().splitlines():
            if not line.strip():
                continue
            entry = MemoryEntry.model_validate_json(line)
            if token and (token in entry.content.lower() or token in entry.title.lower()):
                entries.append(entry)
        return entries[-limit:]

    def add(self, entry: MemoryEntry) -> None:
        with self.file.open("a") as f:
            f.write(entry.model_dump_json() + "\n")
