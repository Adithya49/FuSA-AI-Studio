from __future__ import annotations

from fusa_ai_studio.database.repository import Repository
from fusa_ai_studio.vectorstores.base import SearchResult
from fusa_ai_studio.vectorstores.memory import InMemoryVectorStore


class SQLiteKeywordVectorStore:
    name = "SQLite"

    def __init__(self, repo: Repository):
        self.repo = repo
        self.memory = InMemoryVectorStore(name="SQLite")

    def upsert(self, ids: list[str], documents: list[str], metadatas: list[dict], embeddings: list[list[float]]) -> None:
        self.memory.upsert(ids, documents, metadatas, embeddings)

    def query(self, query_text: str, query_embedding: list[float], project_id: str, limit: int = 6) -> list[SearchResult]:
        memory_results = self.memory.query(query_text, query_embedding, project_id, limit)
        if memory_results:
            return memory_results
        tokens = [token.lower() for token in query_text.split() if len(token) > 2]
        rows = self.repo.list_table("knowledge_chunks", project_id)
        scored = []
        for row in rows:
            content = row["content"]
            score = sum(1 for token in tokens if token in content.lower())
            if score:
                scored.append(SearchResult(row["embedding_id"], content, {"project_id": project_id, "document_id": row["document_id"]}, float(score)))
        return sorted(scored, key=lambda item: item.score, reverse=True)[:limit]
