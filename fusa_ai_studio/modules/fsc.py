from __future__ import annotations

import streamlit as st

from fusa_ai_studio.core.services import Services
from fusa_ai_studio.ui.components import data_table
from fusa_ai_studio.ui.genai import render_ai_response_with_chat, run_genai_action
from fusa_ai_studio.ui.workproduct_inputs import render_workproduct_inputs


def render(services: Services, project_id: str) -> None:
    repo = services.repo
    st.title("Functional Safety Concept")
    input_tab, function_tab, allocation_tab, ai_tab, records_tab = st.tabs(["Inputs", "Functional Requirements", "Allocation & Verification", "AI Review", "Records"])
    with input_tab:
        render_workproduct_inputs(services, project_id, "FSC")
    with function_tab:
        goals = repo.list_table("safety_goals", project_id)
        goal_options = {f"{goal['id']} · {goal['goal_code']} · {goal['asil']}": goal for goal in goals}
        with st.form("fsc_form"):
            goal_label = st.selectbox("Linked safety goal", list(goal_options.keys()) or ["No safety goal"])
            goal = goal_options.get(goal_label, {})
            req_code = st.text_input("Requirement code", f"FSC-{len(repo.list_table('fsc_requirements', project_id)) + 1:03d}")
            statement = st.text_area("Statement", "The system shall detect torque deviation and command torque inhibit within the fault tolerant time.")
            asil = st.selectbox("ASIL", ["QM", "A", "B", "C", "D"], index=["QM", "A", "B", "C", "D"].index(goal.get("asil", "D") if goal else "D"))
            allocation = st.text_input("Allocation", "Inverter control software and independent monitor")
            rationale = st.text_area("Rationale", "Independent monitoring reduces dependency on the primary torque control path.")
            verification = st.text_area("Verification", "Requirements-based test, HIL fault injection, and analysis.")
            if st.form_submit_button("Save FSC requirement"):
                req_id = repo.insert(
                    "fsc_requirements",
                    {
                        "project_id": project_id,
                        "safety_goal_id": goal.get("id"),
                        "req_code": req_code,
                        "statement": statement,
                        "asil": asil,
                        "allocation": allocation,
                        "rationale": rationale,
                        "verification": verification,
                    },
                )
                if goal.get("id"):
                    repo.add_trace(project_id, "safety_goal", str(goal["id"]), "fsc_requirement", str(req_id), "refined_by", "FSC requirement refines linked safety goal.")
                repo.add_memory(project_id, "fsc", f"{req_code}: {statement}", 3)
                services.knowledge.index_artifacts(project_id)
                st.success("FSC requirement saved and traced.")
    with allocation_tab:
        data_table([{k: row[k] for k in ("req_code", "asil", "allocation", "verification", "rationale")} for row in repo.list_table("fsc_requirements", project_id)], "No FSC allocation data recorded.")
    with ai_tab:
        if st.button("AI derive FSC improvements"):
            answer = run_genai_action(
                "FSC",
                lambda: services.rag.ask(project_id, "FSC", "Suggest improvements to the functional safety concept, including allocation, diagnostics, and verification evidence."),
            )
            render_ai_response_with_chat(services, project_id, "FSC", answer, "fsc_ai")
    with records_tab:
        data_table(repo.list_table("fsc_requirements", project_id), "No FSC requirements recorded.")
