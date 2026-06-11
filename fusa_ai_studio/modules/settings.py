from __future__ import annotations

import streamlit as st

from fusa_ai_studio.core.services import Services
from fusa_ai_studio.ui.components import data_table


def render(services: Services, project_id: str) -> None:
    repo = services.repo
    st.title("Settings")
    st.caption("Changes are applied immediately. Restart Streamlit after changing vector backend to rebuild the service container.")
    with st.form("settings_form"):
        provider = st.selectbox("LLM provider", ["Local", "OpenAI", "Claude", "Gemini", "Ollama", "LM Studio", "OpenRouter"], index=["Local", "OpenAI", "Claude", "Gemini", "Ollama", "LM Studio", "OpenRouter"].index(repo.get_setting("llm_provider", "Local")))
        model = st.text_input("LLM model", repo.get_setting("llm_model", "fusa-local-deterministic"))
        vector_backend = st.selectbox("Vector database", ["ChromaDB", "SQLite", "In-Memory"], index=["ChromaDB", "SQLite", "In-Memory"].index(repo.get_setting("vector_backend", "ChromaDB")))
        embedding = st.selectbox("Embedding model", ["deterministic-hash-384", "sentence-transformers/all-MiniLM-L6-v2", "openai/text-embedding-3-small"], index=["deterministic-hash-384", "sentence-transformers/all-MiniLM-L6-v2", "openai/text-embedding-3-small"].index(repo.get_setting("embedding_model", "deterministic-hash-384")))
        chunking = st.selectbox("Chunking strategy", ["section", "recursive", "fixed"], index=["section", "recursive", "fixed"].index(repo.get_setting("chunking_strategy", "section")))
        if st.form_submit_button("Save settings"):
            repo.set_setting("llm_provider", provider)
            repo.set_setting("llm_model", model)
            repo.set_setting("vector_backend", vector_backend)
            repo.set_setting("embedding_model", embedding)
            repo.set_setting("chunking_strategy", chunking)
            services.knowledge.index_project(project_id)
            st.success("Settings saved and knowledge re-index requested.")

    st.markdown("### Vector Collections")
    data_table(repo.list_table("vector_collections", project_id), "No vector collections recorded.")
    st.markdown("### Raw Settings")
    data_table(repo.list_table("doc_templates"), "No templates recorded.")
