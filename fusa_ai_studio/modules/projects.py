from __future__ import annotations

import re

import streamlit as st

from fusa_ai_studio.core.sample_data import seed_sample_data
from fusa_ai_studio.core.services import Services
from fusa_ai_studio.ui.components import data_table
from fusa_ai_studio.ui.workproduct_inputs import SAMPLE_INPUTS


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "new-project"


def render(services: Services, project_id: str) -> None:
    repo = services.repo
    st.title("Projects")
    st.caption("Create a project, choose the active project, and load sample FuSA data before starting work products.")

    projects = repo.list_projects()
    labels = {f"{project['name']} ({project['id']})": project["id"] for project in projects}
    if labels:
        selected = st.selectbox(
            "Active project",
            list(labels.keys()),
            index=max(0, list(labels.values()).index(project_id) if project_id in labels.values() else 0),
        )
        if st.button("Use selected project", type="primary"):
            repo.set_setting("active_project_id", labels[selected])
            st.success(f"Active project set to {labels[selected]}.")

    st.markdown("### Sample Inputs")
    if st.button("Create sample input packs for all work products"):
        for workproduct, content in SAMPLE_INPUTS.items():
            services.knowledge.add_document(project_id, f"{workproduct} sample input pack", "Generated project sample input", content, workproduct)
        repo.add_memory(project_id, "sample_input", "Generated sample input packs for all FuSA work products.", 3)
        st.success("Sample input packs created and indexed for every work product.")

    st.markdown("### Create Project")
    with st.form("create_project"):
        name = st.text_input("Project name", "New FuSA Project")
        generated_id = _slug(name)
        new_id = st.text_input("Project ID", generated_id)
        description = st.text_area("Description", "Functional safety project for an automotive E/E item.")
        standard = st.text_input("Safety standard", "ISO 26262:2018")
        load_sample = st.checkbox("Load full EV inverter sample data", value=True)
        if st.form_submit_button("Create project"):
            if load_sample:
                seed_sample_data(repo, new_id)
                repo.upsert_project(new_id, name, description, standard)
            else:
                repo.upsert_project(new_id, name, description, standard)
                repo.add_memory(new_id, "project_context", f"{name}: {description}", 3)
            repo.set_setting("active_project_id", new_id)
            services.knowledge.index_project(new_id)
            st.success(f"Created and selected project {new_id}.")

    st.markdown("### Existing Projects")
    data_table(repo.list_projects(), "No projects found.")
