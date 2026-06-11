from __future__ import annotations

import streamlit as st

from fusa_ai_studio.core.services import Services
from fusa_ai_studio.ui.components import data_table


def render(services: Services, project_id: str) -> None:
    repo = services.repo
    project = repo.get_project(project_id)
    st.title("FuSA AI Studio")
    if project:
        st.subheader(project["name"])
        st.caption(f"{project['standard']} · {project['description']}")

    metrics = repo.metrics(project_id)
    cols = st.columns(4)
    labels = [
        ("Items", "items"),
        ("Hazards", "hazards"),
        ("Safety Goals", "safety_goals"),
        ("Trace Links", "trace_links"),
    ]
    for col, (label, key) in zip(cols, labels):
        col.metric(label, metrics[key])

    cols = st.columns(4)
    for col, (label, key) in zip(cols, [("FSC", "fsc_requirements"), ("TSC", "tsc_requirements"), ("Knowledge", "knowledge_documents"), ("Tasks", "workflow_tasks")]):
        col.metric(label, metrics[key])

    st.markdown("### Open Work")
    data_table(repo.due_tasks(project_id), "No overdue or due workflow tasks.")

    st.markdown("### Recent AI Interactions")
    data_table(repo.list_table("ai_interactions", project_id)[:5], "AI interactions will appear after assistant or generation features run.")
