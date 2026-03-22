from pathlib import Path
from typing import List
from astack.interfaces import MemoryInterface
from astack.schemas import MemoryEntry


class JsonMemoryStore(MemoryInterface):
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.file = self.root / "memory.jsonl"
        if not self.file.exists():
            self.file.touch()

    def retrieve(self, goal: str, limit: int = 5) -> List[MemoryEntry]:
        tokens = [t for t in goal.lower().split() if len(t) > 2]
        entries: List[MemoryEntry] = []
        for line in self.file.read_text().splitlines():
            if not line.strip():
                continue
            entry = MemoryEntry.model_validate_json(line)
            text = (entry.content + " " + entry.title).lower()
            if any(t in text for t in tokens):
                entries.append(entry)
        return entries[-limit:]

    def add(self, entry: MemoryEntry) -> None:
        with self.file.open("a") as f:
            f.write(entry.model_dump_json() + "\n")
