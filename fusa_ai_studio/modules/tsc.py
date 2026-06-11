from __future__ import annotations

import streamlit as st

from fusa_ai_studio.core.services import Services
from fusa_ai_studio.ui.components import data_table, source_list
from fusa_ai_studio.ui.genai import run_genai_action
from fusa_ai_studio.ui.workproduct_inputs import render_workproduct_inputs


def render(services: Services, project_id: str) -> None:
    repo = services.repo
    st.title("Technical Safety Concept")
    input_tab, technical_tab, diagnostics_tab, ai_tab, records_tab = st.tabs(["Inputs", "Technical Requirements", "Diagnostics & Verification", "AI Review", "Records"])
    with input_tab:
        render_workproduct_inputs(services, project_id, "TSC")
    with technical_tab:
        fsc_rows = repo.list_table("fsc_requirements", project_id)
        fsc_options = {f"{row['id']} · {row['req_code']} · {row['asil']}": row for row in fsc_rows}
        with st.form("tsc_form"):
            fsc_label = st.selectbox("Linked FSC requirement", list(fsc_options.keys()) or ["No FSC requirement"])
            fsc = fsc_options.get(fsc_label, {})
            req_code = st.text_input("Requirement code", f"TSC-{len(repo.list_table('tsc_requirements', project_id)) + 1:03d}")
            statement = st.text_area("Statement", "The safety task shall execute every 10 ms and assert hardware shutdown after confirmed torque deviation.")
            asil = st.selectbox("ASIL", ["QM", "A", "B", "C", "D"], index=["QM", "A", "B", "C", "D"].index(fsc.get("asil", "D") if fsc else "D"))
            component = st.text_input("Component", "Microcontroller safety task and gate driver shutdown")
            diagnostic = st.text_area("Diagnostic mechanism", "Program-flow monitoring, watchdog supervision, ADC plausibility, and shutdown readback.")
            verification = st.text_area("Verification", "Timing analysis, software unit tests, HIL test, and electrical shutdown test.")
            if st.form_submit_button("Save TSC requirement"):
                req_id = repo.insert(
                    "tsc_requirements",
                    {
                        "project_id": project_id,
                        "fsc_requirement_id": fsc.get("id"),
                        "req_code": req_code,
                        "statement": statement,
                        "asil": asil,
                        "component": component,
                        "diagnostic_mechanism": diagnostic,
                        "verification": verification,
                    },
                )
                if fsc.get("id"):
                    repo.add_trace(project_id, "fsc_requirement", str(fsc["id"]), "tsc_requirement", str(req_id), "refined_by", "TSC requirement implements FSC requirement.")
                repo.add_memory(project_id, "tsc", f"{req_code}: {statement}", 3)
                services.knowledge.index_artifacts(project_id)
                st.success("TSC requirement saved and traced.")
    with diagnostics_tab:
        data_table([{k: row[k] for k in ("req_code", "component", "diagnostic_mechanism", "verification")} for row in repo.list_table("tsc_requirements", project_id)], "No diagnostics or verification data recorded.")
    with ai_tab:
        if st.button("AI review technical allocation"):
            answer = run_genai_action(
                "TSC",
                lambda: services.rag.ask(project_id, "TSC", "Review technical safety concept for component allocation, diagnostic coverage, timing, and verification gaps."),
            )
            st.markdown(answer.text)
            source_list(answer.sources)
    with records_tab:
        data_table(repo.list_table("tsc_requirements", project_id), "No TSC requirements recorded.")
