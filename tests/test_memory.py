from alphastack.core.memory import JsonMemoryStore
from alphastack.schemas import MemoryEntry


def test_memory_roundtrip(tmp_path):
    store = JsonMemoryStore(tmp_path)
    store.add(MemoryEntry(kind="success", title="alpha1", content="volume alpha"))
    out = store.retrieve("volume", limit=5)
    assert len(out) == 1
