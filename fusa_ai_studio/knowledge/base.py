from __future__ import annotations

import json

from fusa_ai_studio.ai.chunking import ChunkingEngine
from fusa_ai_studio.ai.embeddings import EmbeddingEngine
from fusa_ai_studio.database.repository import Repository
from fusa_ai_studio.vectorstores.base import VectorStore


class KnowledgeBase:
    def __init__(self, repo: Repository, chunking: ChunkingEngine, embeddings: EmbeddingEngine, vector_store: VectorStore):
        self.repo = repo
        self.chunking = chunking
        self.embeddings = embeddings
        self.vector_store = vector_store

    def add_document(self, project_id: str, title: str, source: str, content: str, doc_type: str = "project") -> int:
        document_id = self.repo.insert(
            "knowledge_documents",
            {
                "project_id": project_id,
                "title": title,
                "source": source,
                "content": content,
                "doc_type": doc_type,
            },
        )
        self.index_document(project_id, document_id)
        return document_id

    def index_project(self, project_id: str) -> None:
        for document in self.repo.list_table("knowledge_documents", project_id):
            self.index_document(project_id, int(document["id"]))

    def index_artifacts(self, project_id: str) -> None:
        parts: list[str] = []
        for table, title in [
            ("items", "Item Definitions"),
            ("hazards", "HARA"),
            ("safety_goals", "Safety Goals"),
            ("fsc_requirements", "Functional Safety Concept"),
            ("tsc_requirements", "Technical Safety Concept"),
        ]:
            rows = self.repo.list_table(table, project_id)
            if rows:
                parts.append(f"## {title}")
                for row in rows:
                    parts.append("; ".join(f"{key}: {value}" for key, value in row.items() if key not in {"created_at", "updated_at"}))
        if parts:
            existing = [doc for doc in self.repo.list_table("knowledge_documents", project_id) if doc["title"] == "Generated Artifact Index"]
            content = "\n\n".join(parts)
            if not existing:
                self.add_document(project_id, "Generated Artifact Index", "FuSA AI Studio artifacts", content, "artifact-index")

    def index_document(self, project_id: str, document_id: int) -> None:
        documents = [doc for doc in self.repo.list_table("knowledge_documents", project_id) if int(doc["id"]) == document_id]
        if not documents:
            return
        document = documents[0]
        strategy = self.repo.get_setting("chunking_strategy", "section")
        embedding_model = self.repo.get_setting("embedding_model", "deterministic-hash-384")
        chunks = self.chunking.chunk(document["content"], strategy)
        ids: list[str] = []
        contents: list[str] = []
        metadatas: list[dict] = []
        existing_ids = {row["embedding_id"] for row in self.repo.list_table("knowledge_chunks", project_id)}
        for chunk in chunks:
            embedding_id = f"{project_id}-doc-{document_id}-chunk-{chunk.index}"
            metadata = {
                "project_id": project_id,
                "document_id": document_id,
                "title": document["title"],
                "source": document["source"],
                "doc_type": document["doc_type"],
                **chunk.metadata,
            }
            if embedding_id not in existing_ids:
                self.repo.insert(
                    "knowledge_chunks",
                    {
                        "project_id": project_id,
                        "document_id": document_id,
                        "chunk_index": chunk.index,
                        "content": chunk.content,
                        "metadata": json.dumps(metadata),
                        "embedding_id": embedding_id,
                    },
                )
            ids.append(embedding_id)
            contents.append(chunk.content)
            metadatas.append(metadata)
        if ids:
            vectors = self.embeddings.embed_many(contents, embedding_model)
            self.vector_store.upsert(ids, contents, metadatas, vectors)
