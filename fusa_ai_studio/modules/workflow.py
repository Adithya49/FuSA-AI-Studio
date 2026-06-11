from __future__ import annotations

from datetime import date, timedelta

import streamlit as st

from fusa_ai_studio.core.services import Services
from fusa_ai_studio.ui.components import data_table, source_list
from fusa_ai_studio.ui.genai import run_genai_action
from fusa_ai_studio.ui.workproduct_inputs import render_workproduct_inputs


def render(services: Services, project_id: str) -> None:
    repo = services.repo
    st.title("Workflow Automation")
    input_tab, planning_tab, evidence_tab, ai_tab, records_tab = st.tabs(["Inputs", "Planning", "Evidence", "AI Actions", "Records"])
    with input_tab:
        render_workproduct_inputs(services, project_id, "Workflow Automation")
    with planning_tab:
        with st.form("task_form"):
            title = st.text_input("Task", "Review generated traceability matrix")
            owner = st.text_input("Owner", "Safety Manager")
            status = st.selectbox("Status", ["Open", "In Progress", "Blocked", "Done"])
            due_date = st.date_input("Due date", date.today() + timedelta(days=14))
            evidence = st.text_area("Evidence", "Review notes, exported matrix, and approval record.")
            if st.form_submit_button("Create task"):
                repo.insert(
                    "workflow_tasks",
                    {
                        "project_id": project_id,
                        "title": title,
                        "owner": owner,
                        "status": status,
                        "due_date": due_date.isoformat(),
                        "evidence": evidence,
                    },
                )
                repo.add_memory(project_id, "workflow", f"{title} assigned to {owner} due {due_date.isoformat()}.", 2)
                st.success("Task created.")
    with evidence_tab:
        data_table([{k: row[k] for k in ("title", "owner", "status", "due_date", "evidence")} for row in repo.list_table("workflow_tasks", project_id)], "No workflow evidence recorded.")
    with ai_tab:
        if st.button("AI propose next workflow actions"):
            answer = run_genai_action(
                "Workflow Automation",
                lambda: services.rag.ask(project_id, "Workflow Automation", "Propose prioritized workflow actions based on current artifact and traceability gaps."),
            )
            st.markdown(answer.text)
            source_list(answer.sources)
    with records_tab:
        data_table(repo.list_table("workflow_tasks", project_id), "No workflow tasks recorded.")
