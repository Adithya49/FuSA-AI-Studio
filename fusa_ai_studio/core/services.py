from __future__ import annotations

import os
from dataclasses import dataclass

from fusa_ai_studio.ai.chunking import ChunkingEngine
from fusa_ai_studio.ai.embeddings import EmbeddingEngine
from fusa_ai_studio.ai.llm import LLMClient
from fusa_ai_studio.ai.rag import RAGEngine
from fusa_ai_studio.core.config import AppConfig, detect_llm_provider, get_config
from fusa_ai_studio.core.sample_data import seed_sample_data
from fusa_ai_studio.database.connection import initialize_database
from fusa_ai_studio.database.repository import Repository
from fusa_ai_studio.knowledge.base import KnowledgeBase
from fusa_ai_studio.vectorstores.chroma_store import ChromaVectorStore
from fusa_ai_studio.vectorstores.memory import InMemoryVectorStore
from fusa_ai_studio.vectorstores.sqlite_store import SQLiteKeywordVectorStore


@dataclass
class Services:
    config: AppConfig
    repo: Repository
    chunking: ChunkingEngine
    embeddings: EmbeddingEngine
    knowledge: KnowledgeBase
    rag: RAGEngine


def build_services() -> Services:
    config = get_config()
    schema_path = config.root_dir / "fusa_ai_studio" / "database" / "schema.sql"
    initialize_database(config.db_path, schema_path)
    repo = Repository(config.db_path)
    seed_sample_data(repo, config.default_project_id)

    if not os.getenv("FUSA_LLM_PROVIDER"):
        current_provider = repo.get_setting("llm_provider", "Local")
        detected_provider = detect_llm_provider()
        if current_provider == "Local" and detected_provider != "Local":
            repo.set_setting("llm_provider", detected_provider)

    backend = repo.get_setting("vector_backend", "ChromaDB")
    collection_name = f"fusa_{config.default_project_id.replace('-', '_')}"
    if backend == "SQLite":
        vector_store = SQLiteKeywordVectorStore(repo)
    elif backend == "In-Memory":
        vector_store = InMemoryVectorStore()
    else:
        vector_store = ChromaVectorStore(str(config.chroma_path), collection_name)
        backend = "ChromaDB"
    repo.insert(
        "vector_collections",
        {
            "project_id": config.default_project_id,
            "backend": backend,
            "collection_name": collection_name,
            "embedding_model": repo.get_setting("embedding_model", "deterministic-hash-384"),
            "chunking_strategy": repo.get_setting("chunking_strategy", "section"),
        },
    ) if not repo.list_table("vector_collections", config.default_project_id) else None

    chunking = ChunkingEngine()
    embeddings = EmbeddingEngine()
    llm = LLMClient()
    knowledge = KnowledgeBase(repo, chunking, embeddings, vector_store)
    knowledge.index_artifacts(config.default_project_id)
    knowledge.index_project(config.default_project_id)
    rag = RAGEngine(repo, embeddings, vector_store, llm)
    return Services(config, repo, chunking, embeddings, knowledge, rag)
