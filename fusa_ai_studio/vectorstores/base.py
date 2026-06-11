from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class SearchResult:
    id: str
    content: str
    metadata: dict
    score: float


class VectorStore(Protocol):
    name: str

    def upsert(self, ids: list[str], documents: list[str], metadatas: list[dict], embeddings: list[list[float]]) -> None:
        ...

    def query(self, query_text: str, query_embedding: list[float], project_id: str, limit: int = 6) -> list[SearchResult]:
        ...
