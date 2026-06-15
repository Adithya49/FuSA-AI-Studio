from __future__ import annotations

import streamlit as st

from fusa_ai_studio.core.services import Services
from fusa_ai_studio.ui.components import data_table
from fusa_ai_studio.ui.genai import render_ai_response_with_chat, run_genai_action
from fusa_ai_studio.ui.workproduct_inputs import render_workproduct_inputs


def render(services: Services, project_id: str) -> None:
    repo = services.repo
    st.title("Item Definition")
    input_tab, scope_tab, interface_tab, ai_tab, records_tab = st.tabs(["Inputs", "Scope", "Interfaces", "AI Review", "Records"])
    with input_tab:
        render_workproduct_inputs(services, project_id, "Item Definition")
    with scope_tab:
        with st.form("item_form"):
            name = st.text_input("Item name", "Traction inverter torque supervision")
            purpose = st.text_area("Purpose", "Supervise and control propulsion torque delivery.")
            boundaries = st.text_area("Boundaries", "Control software, microcontroller, gate driver, sensors, and shutdown path.")
            assumptions = st.text_area("Assumptions", "Vehicle controller provides valid torque requests and contactors can support a safe state.")
            interfaces = st.text_area("Interfaces", "CAN torque request, phase currents, rotor position, DC-link voltage, PWM, shutdown line.")
            if st.form_submit_button("Save item"):
                item_id = repo.insert(
                    "items",
                    {
                        "project_id": project_id,
                        "name": name,
                        "purpose": purpose,
                        "boundaries": boundaries,
                        "interfaces": interfaces,
                        "assumptions": assumptions,
                    },
                )
                repo.add_memory(project_id, "item_definition", f"Item {name}: {purpose}", 3)
                repo.add_trace(project_id, "item", str(item_id), "knowledge_document", "project-context", "informed_by", "Item captured through item definition workflow.")
                services.knowledge.index_artifacts(project_id)
                st.success("Item saved and indexed.")
    with interface_tab:
        st.markdown("### Interface and Assumption Review")
        data_table([{k: row[k] for k in ("id", "name", "interfaces", "assumptions")} for row in repo.list_table("items", project_id)], "No interfaces recorded.")
    with ai_tab:
        if st.button("AI review item definition"):
            rows = repo.list_table("items", project_id)
            question = "Review the current item definition for missing boundaries, interfaces, assumptions, and traceability risks."
            answer = run_genai_action("Item Definition", lambda: services.rag.ask(project_id, "Item Definition", question + "\n\nItems:\n" + str(rows)))
            render_ai_response_with_chat(services, project_id, "Item Definition", answer, "item_definition_ai")
    with records_tab:
        data_table(repo.list_table("items", project_id), "No item definitions recorded.")
