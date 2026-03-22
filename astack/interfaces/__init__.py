from abc import ABC, abstractmethod
from typing import Any, Iterable, List
from astack.schemas import AlphaSpec, ValidationReport, MemoryEntry


class DataInterface(ABC):
    @abstractmethod
    def fetch_data(self, fields: Iterable[str], symbol_set: str) -> Any:
        raise NotImplementedError


class EvaluationInterface(ABC):
    @abstractmethod
    def evaluate_alpha(self, alpha_spec: AlphaSpec, symbol_set: str) -> ValidationReport:
        raise NotImplementedError


class ExecutionInterface(ABC):
    @abstractmethod
    def export_signal(self, alpha_spec: AlphaSpec) -> str:
        raise NotImplementedError


class MemoryInterface(ABC):
    @abstractmethod
    def retrieve(self, goal: str, limit: int = 5) -> List[MemoryEntry]:
        raise NotImplementedError

    @abstractmethod
    def add(self, entry: MemoryEntry) -> None:
        raise NotImplementedError
