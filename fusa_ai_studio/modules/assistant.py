from __future__ import annotations

import streamlit as st

from fusa_ai_studio.core.services import Services
from fusa_ai_studio.ui.components import data_table, source_list
from fusa_ai_studio.ui.genai import render_ai_response_with_chat, run_genai_action


def render(services: Services, project_id: str) -> None:
    st.title("AI Assistant")
    st.caption("All assistant responses use RAG, project memory, and traceability context.")
    question = st.text_area("Question", "What are the most important gaps in the current safety case?")
    feature = st.selectbox("Feature context", ["General", "Item Definition", "HARA", "Safety Goals", "FSC", "TSC", "Traceability", "Document Factory"])
    if st.button("Ask with RAG", type="primary"):
        answer = run_genai_action(feature, lambda: services.rag.ask(project_id, feature, question))
        render_ai_response_with_chat(services, project_id, feature, answer, "assistant_ai")

    st.markdown("### Project Memory")
    with st.form("memory_form"):
        memory_type = st.selectbox("Memory type", ["decision", "assumption", "constraint", "open_issue", "rationale"])
        content = st.text_area("Content", "Record a project decision or assumption for future AI context.")
        importance = st.slider("Importance", 1, 5, 3)
        if st.form_submit_button("Add memory"):
            services.repo.add_memory(project_id, memory_type, content, importance)
            st.success("Memory recorded.")
    data_table(services.repo.recent_memory(project_id, 20), "No project memory recorded.")
