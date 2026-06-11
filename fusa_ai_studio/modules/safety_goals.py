from __future__ import annotations

import streamlit as st

from fusa_ai_studio.core.services import Services
from fusa_ai_studio.ui.components import data_table, source_list
from fusa_ai_studio.ui.genai import run_genai_action
from fusa_ai_studio.ui.workproduct_inputs import render_workproduct_inputs


def render(services: Services, project_id: str) -> None:
    repo = services.repo
    st.title("Safety Goals")
    input_tab, derivation_tab, timing_tab, ai_tab, records_tab = st.tabs(["Inputs", "Goal Derivation", "Safe State & FTTI", "AI Review", "Records"])
    with input_tab:
        render_workproduct_inputs(services, project_id, "Safety Goals")
    with derivation_tab:
        hazards = repo.list_table("hazards", project_id)
        hazard_options = {f"{hazard['id']} · {hazard['malfunction']} · {hazard['asil']}": hazard for hazard in hazards}
        with st.form("safety_goal_form"):
            hazard_label = st.selectbox("Linked hazard", list(hazard_options.keys()) or ["No hazard"])
            hazard = hazard_options.get(hazard_label, {})
            goal_code = st.text_input("Goal code", f"SG-{len(repo.list_table('safety_goals', project_id)) + 1:03d}")
            statement = st.text_area("Statement", "The item shall prevent unintended torque above the calibrated safety threshold.")
            asil = st.selectbox("ASIL", ["QM", "A", "B", "C", "D"], index=["QM", "A", "B", "C", "D"].index(hazard.get("asil", "D") if hazard else "D"))
            safe_state = st.text_input("Safe state", "Torque inhibit and controlled transition to zero torque")
            ftt = st.text_input("Fault tolerant time", "100 ms")
            verification = st.text_area("Verification", "HIL fault injection and vehicle integration test.")
            if st.form_submit_button("Save safety goal"):
                sg_id = repo.insert(
                    "safety_goals",
                    {
                        "project_id": project_id,
                        "hazard_id": hazard.get("id"),
                        "goal_code": goal_code,
                        "statement": statement,
                        "asil": asil,
                        "safe_state": safe_state,
                        "fault_tolerant_time": ftt,
                        "verification": verification,
                    },
                )
                if hazard.get("id"):
                    repo.add_trace(project_id, "hazard", str(hazard["id"]), "safety_goal", str(sg_id), "mitigated_by", "Safety goal created from linked hazardous event.")
                repo.add_memory(project_id, "safety_goal", f"{goal_code}: {statement}", 4)
                services.knowledge.index_artifacts(project_id)
                st.success("Safety goal saved and traced.")
    with timing_tab:
        data_table([{k: row[k] for k in ("goal_code", "asil", "safe_state", "fault_tolerant_time", "verification")} for row in repo.list_table("safety_goals", project_id)], "No safe-state or FTTI data recorded.")
    with ai_tab:
        if st.button("AI review safety goals"):
            answer = run_genai_action(
                "Safety Goals",
                lambda: services.rag.ask(project_id, "Safety Goals", "Review safety goals for verifiability, ASIL consistency, safe state, and missing hazard links."),
            )
            st.markdown(answer.text)
            source_list(answer.sources)
    with records_tab:
        data_table(repo.list_table("safety_goals", project_id), "No safety goals recorded.")
