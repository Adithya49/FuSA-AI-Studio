from __future__ import annotations

from dataclasses import dataclass

from fusa_ai_studio.ai.embeddings import EmbeddingEngine
from fusa_ai_studio.ai.llm import LLMClient
from fusa_ai_studio.ai.prompts import build_rag_prompt
from fusa_ai_studio.database.repository import Repository
from fusa_ai_studio.vectorstores.base import VectorStore


@dataclass(frozen=True)
class RAGAnswer:
    text: str
    sources: list[dict]
    provider: str
    model: str
    warning: str = ""


class RAGEngine:
    def __init__(self, repo: Repository, embeddings: EmbeddingEngine, vector_store: VectorStore, llm: LLMClient):
        self.repo = repo
        self.embeddings = embeddings
        self.vector_store = vector_store
        self.llm = llm

    def ask(self, project_id: str, feature: str, question: str) -> RAGAnswer:
        embedding_model = self.repo.get_setting("embedding_model", "deterministic-hash-384")
        provider = self.repo.get_setting("llm_provider", "Local")
        model = self.repo.get_setting("llm_model", "fusa-local-deterministic")
        query_embedding = self.embeddings.embed(question, embedding_model).vector
        results = self.vector_store.query(question, query_embedding, project_id, limit=6)
        sources = [
            {"id": item.id, "content": item.content, "metadata": item.metadata, "score": round(item.score, 4)}
            for item in results
        ]
        memory = self.repo.recent_memory(project_id)
        trace_context = self._trace_summary(project_id)
        prompt = build_rag_prompt(feature, question, memory, trace_context, sources)
        response = self.llm.generate(prompt, provider, model)
        self.repo.store_ai_interaction(project_id, feature, response.provider, response.model, question, sources, response.text)
        self.repo.add_memory(project_id, "ai_interaction", f"{feature}: {question[:160]}", 2)
        return RAGAnswer(response.text, sources, response.provider, response.model, response.warning)

    def _trace_summary(self, project_id: str) -> str:
        links = self.repo.list_table("trace_links", project_id)
        if not links:
            return "No trace links have been recorded."
        lines = [
            f"- {link['source_type']}:{link['source_id']} {link['link_type']} {link['target_type']}:{link['target_id']} ({link['rationale']})"
            for link in links[:20]
        ]
        return "\n".join(lines)
