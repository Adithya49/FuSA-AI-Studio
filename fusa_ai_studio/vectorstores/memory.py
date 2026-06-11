from __future__ import annotations

import math
from dataclasses import dataclass, field

from fusa_ai_studio.vectorstores.base import SearchResult


def cosine(a: list[float], b: list[float]) -> float:
    size = min(len(a), len(b))
    if size == 0:
        return 0.0
    dot = sum(a[i] * b[i] for i in range(size))
    na = math.sqrt(sum(value * value for value in a[:size])) or 1.0
    nb = math.sqrt(sum(value * value for value in b[:size])) or 1.0
    return dot / (na * nb)


@dataclass
class InMemoryVectorStore:
    name: str = "In-Memory"
    entries: dict[str, tuple[str, dict, list[float]]] = field(default_factory=dict)

    def upsert(self, ids: list[str], documents: list[str], metadatas: list[dict], embeddings: list[list[float]]) -> None:
        for item_id, document, metadata, embedding in zip(ids, documents, metadatas, embeddings):
            self.entries[item_id] = (document, metadata, embedding)

    def query(self, query_text: str, query_embedding: list[float], project_id: str, limit: int = 6) -> list[SearchResult]:
        scored: list[SearchResult] = []
        for item_id, (document, metadata, embedding) in self.entries.items():
            if metadata.get("project_id") != project_id:
                continue
            keyword_bonus = sum(1 for token in query_text.lower().split() if token and token in document.lower()) * 0.02
            scored.append(SearchResult(item_id, document, metadata, cosine(query_embedding, embedding) + keyword_bonus))
        return sorted(scored, key=lambda item: item.score, reverse=True)[:limit]
