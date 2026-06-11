from __future__ import annotations

from fusa_ai_studio.vectorstores.base import SearchResult
from fusa_ai_studio.vectorstores.memory import InMemoryVectorStore


class ChromaVectorStore:
    name = "ChromaDB"

    def __init__(self, persist_path: str, collection_name: str):
        self.fallback = InMemoryVectorStore()
        self.collection = None
        try:
            import chromadb

            client = chromadb.PersistentClient(path=persist_path)
            self.collection = client.get_or_create_collection(name=collection_name)
        except Exception:
            self.collection = None

    def upsert(self, ids: list[str], documents: list[str], metadatas: list[dict], embeddings: list[list[float]]) -> None:
        self.fallback.upsert(ids, documents, metadatas, embeddings)
        if self.collection is None:
            return
        self.collection.upsert(ids=ids, documents=documents, metadatas=metadatas, embeddings=embeddings)

    def query(self, query_text: str, query_embedding: list[float], project_id: str, limit: int = 6) -> list[SearchResult]:
        if self.collection is None:
            return self.fallback.query(query_text, query_embedding, project_id, limit)
        result = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=limit,
            where={"project_id": project_id},
            include=["documents", "metadatas", "distances"],
        )
        ids = result.get("ids", [[]])[0]
        docs = result.get("documents", [[]])[0]
        metas = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0]
        return [
            SearchResult(str(item_id), doc, dict(meta or {}), 1.0 / (1.0 + float(distance)))
            for item_id, doc, meta, distance in zip(ids, docs, metas, distances)
        ]
