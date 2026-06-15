from __future__ import annotations

import streamlit as st

from fusa_ai_studio.core.asil import calculate_asil
from fusa_ai_studio.core.services import Services
from fusa_ai_studio.ui.components import data_table
from fusa_ai_studio.ui.genai import render_ai_response_with_chat, run_genai_action
from fusa_ai_studio.ui.workproduct_inputs import render_workproduct_inputs


def render(services: Services, project_id: str) -> None:
    repo = services.repo
    st.title("HARA")
    input_tab, situations_tab, rating_tab, ai_tab, records_tab = st.tabs(["Inputs", "Situations & Hazards", "S/E/C Rating", "AI Derivation", "Records"])
    with input_tab:
        render_workproduct_inputs(services, project_id, "HARA")
    with situations_tab:
        data_table(
            [
                {k: row[k] for k in ("id", "function_name", "malfunction", "operational_situation", "hazardous_event")}
                for row in repo.list_table("hazards", project_id)
            ],
            "No hazardous events recorded.",
        )
    with rating_tab:
        items = repo.list_table("items", project_id)
        item_options = {f"{item['id']} · {item['name']}": item["id"] for item in items}
        with st.form("hazard_form"):
            item_label = st.selectbox("Linked item", list(item_options.keys()) or ["No item"])
            function_name = st.text_input("Function", "Torque command execution")
            malfunction = st.text_input("Malfunction", "Unintended positive torque")
            situation = st.text_input("Operational situation", "Urban driving near pedestrians")
            event = st.text_area("Hazardous event", "Vehicle accelerates without driver intent")
            col1, col2, col3 = st.columns(3)
            severity = col1.slider("Severity", 0, 3, 3)
            exposure = col2.slider("Exposure", 0, 4, 4)
            controllability = col3.slider("Controllability", 0, 3, 3)
            asil = calculate_asil(severity, exposure, controllability)
            st.caption(f"Calculated ASIL: {asil}")
            rationale = st.text_area("Rationale", "Severity, exposure, and controllability rationale based on project context.")
            if st.form_submit_button("Save hazardous event"):
                hazard_id = repo.insert(
                    "hazards",
                    {
                        "project_id": project_id,
                        "item_id": item_options.get(item_label),
                        "function_name": function_name,
                        "malfunction": malfunction,
                        "operational_situation": situation,
                        "hazardous_event": event,
                        "severity": severity,
                        "exposure": exposure,
                        "controllability": controllability,
                        "asil": asil,
                        "rationale": rationale,
                    },
                )
                if item_options.get(item_label):
                    repo.add_trace(project_id, "item", str(item_options[item_label]), "hazard", str(hazard_id), "analyzed_by", "Hazard entered during HARA.")
                repo.add_memory(project_id, "hara", f"{malfunction} in {situation} classified {asil}.", 4)
                services.knowledge.index_artifacts(project_id)
                st.success("Hazard saved and indexed.")
    with ai_tab:
        if st.button("AI suggest safety goal candidates"):
            answer = run_genai_action(
                "HARA",
                lambda: services.rag.ask(project_id, "HARA", "Suggest safety goal candidates for the current HARA table. Include ASIL inheritance and safe-state hints."),
            )
            render_ai_response_with_chat(services, project_id, "HARA", answer, "hara_ai")
    with records_tab:
        data_table(repo.list_table("hazards", project_id), "No HARA rows recorded.")
