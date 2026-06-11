from __future__ import annotations

import streamlit as st

from fusa_ai_studio.core.services import Services, build_services
from fusa_ai_studio.modules import assistant, dashboard, document_factory, fsc, hara, item_definition, knowledge, projects, safety_goals, settings, traceability, tsc, workflow


@st.cache_resource(show_spinner="Starting FuSA AI Studio")
def services() -> Services:
    return build_services()


def main() -> None:
    st.set_page_config(page_title="FuSA AI Studio", page_icon="FS", layout="wide")
    svc = services()
    repo = svc.repo
    active_project = repo.get_setting("active_project_id", svc.config.default_project_id)
    project_rows = repo.list_projects()
    project_labels = {f"{project['name']} ({project['id']})": project["id"] for project in project_rows}

    with st.sidebar:
        st.header("FuSA AI Studio")
        if project_labels:
            st.markdown("**Select active project**")
            selected_label = st.selectbox("Project", list(project_labels.keys()), index=max(0, list(project_labels.values()).index(active_project) if active_project in project_labels.values() else 0))
            active_project = project_labels[selected_label]
            repo.set_setting("active_project_id", active_project)
        else:
            st.warning("No project exists. Open Projects to create one.")
        page = st.radio(
            "Workspace",
            [
                "Projects",
                "Dashboard",
                "Item Definition",
                "HARA",
                "Safety Goals",
                "FSC",
                "TSC",
                "Traceability",
                "AI Assistant",
                "Workflow Automation",
                "Knowledge Base",
                "Document Factory",
                "Settings",
            ],
        )
        st.divider()
        st.caption(f"LLM: {repo.get_setting('llm_provider', 'Local')} | {repo.get_setting('llm_model', 'fusa-local-deterministic')}")
        st.caption(f"Vector: {repo.get_setting('vector_backend', 'ChromaDB')} | Embedding: {repo.get_setting('embedding_model', 'deterministic-hash-384')}")

    routes = {
        "Projects": projects.render,
        "Dashboard": dashboard.render,
        "Item Definition": item_definition.render,
        "HARA": hara.render,
        "Safety Goals": safety_goals.render,
        "FSC": fsc.render,
        "TSC": tsc.render,
        "Traceability": traceability.render,
        "AI Assistant": assistant.render,
        "Workflow Automation": workflow.render,
        "Knowledge Base": knowledge.render,
        "Document Factory": document_factory.render,
        "Settings": settings.render,
    }
    routes[page](svc, active_project)


if __name__ == "__main__":
    main()
