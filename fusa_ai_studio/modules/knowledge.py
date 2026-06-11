from __future__ import annotations

import streamlit as st

from fusa_ai_studio.core.services import Services
from fusa_ai_studio.ui.components import data_table


def render(services: Services, project_id: str) -> None:
    repo = services.repo
    st.title("Knowledge Base")
    st.caption("Documents are chunked, embedded, and added to the selected vector database.")
    uploaded = st.file_uploader("Import text, Markdown, CSV, or log file", type=["txt", "md", "csv", "log"])
    title = st.text_input("Document title", "Imported Safety Evidence")
    doc_type = st.selectbox("Document type", ["guidance", "evidence", "requirements", "analysis", "artifact-index"])
    if uploaded and st.button("Ingest document"):
        content = uploaded.read().decode("utf-8", errors="replace")
        services.knowledge.add_document(project_id, title, uploaded.name, content, doc_type)
        repo.add_memory(project_id, "knowledge", f"Ingested {title} from {uploaded.name}.", 3)
        st.success("Document ingested, chunked, embedded, and indexed.")

    manual = st.text_area("Manual knowledge entry", "Paste safety notes, review minutes, or external guidance here.")
    if st.button("Save manual knowledge"):
        services.knowledge.add_document(project_id, title, "Manual entry", manual, doc_type)
        st.success("Manual knowledge indexed.")

    data_table(repo.list_table("knowledge_documents", project_id), "No knowledge documents recorded.")
    data_table(repo.list_table("knowledge_chunks", project_id), "No chunks recorded.")
