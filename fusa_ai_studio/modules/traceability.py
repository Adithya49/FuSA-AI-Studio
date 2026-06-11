from __future__ import annotations

import pandas as pd
import streamlit as st

from fusa_ai_studio.core.services import Services
from fusa_ai_studio.ui.components import data_table, source_list
from fusa_ai_studio.ui.genai import run_genai_action
from fusa_ai_studio.ui.workproduct_inputs import render_workproduct_inputs


def render(services: Services, project_id: str) -> None:
    repo = services.repo
    st.title("Traceability")
    input_tab, links_tab, coverage_tab, matrix_tab, ai_tab = st.tabs(["Inputs", "Links", "Coverage", "Matrix", "AI Review"])
    with input_tab:
        render_workproduct_inputs(services, project_id, "Traceability")
    links = repo.list_table("trace_links", project_id)
    with links_tab:
        data_table(links, "No trace links recorded.")
    hazards = repo.list_table("hazards", project_id)
    goals = repo.list_table("safety_goals", project_id)
    fsc = repo.list_table("fsc_requirements", project_id)
    tsc = repo.list_table("tsc_requirements", project_id)
    linked_hazards = {link["source_id"] for link in links if link["source_type"] == "hazard" and link["target_type"] == "safety_goal"}
    linked_goals = {link["source_id"] for link in links if link["source_type"] == "safety_goal" and link["target_type"] == "fsc_requirement"}
    linked_fsc = {link["source_id"] for link in links if link["source_type"] == "fsc_requirement" and link["target_type"] == "tsc_requirement"}
    gaps = []
    gaps.extend({"artifact": f"Hazard {row['id']}", "gap": "No linked safety goal"} for row in hazards if str(row["id"]) not in linked_hazards)
    gaps.extend({"artifact": row["goal_code"], "gap": "No linked FSC requirement"} for row in goals if str(row["id"]) not in linked_goals)
    gaps.extend({"artifact": row["req_code"], "gap": "No linked TSC requirement"} for row in fsc if str(row["id"]) not in linked_fsc)
    with coverage_tab:
        data_table(gaps, "Traceability coverage is complete for hazard -> SG -> FSC -> TSC.")
    with matrix_tab:
        matrix = []
        for goal in goals:
            related_hazards = [link["source_id"] for link in links if link["target_type"] == "safety_goal" and link["target_id"] == str(goal["id"])]
            related_fsc = [row["req_code"] for row in fsc if row["safety_goal_id"] == goal["id"]]
            related_tsc = [row["req_code"] for row in tsc if row["fsc_requirement_id"] in [f["id"] for f in fsc if f["safety_goal_id"] == goal["id"]]]
            matrix.append({"Safety Goal": goal["goal_code"], "Hazards": ", ".join(related_hazards), "FSC": ", ".join(related_fsc), "TSC": ", ".join(related_tsc)})
        if matrix:
            st.dataframe(pd.DataFrame(matrix), use_container_width=True, hide_index=True)
        else:
            st.info("No matrix rows yet.")
    with ai_tab:
        if st.button("AI analyze trace gaps"):
            answer = run_genai_action(
                "Traceability",
                lambda: services.rag.ask(project_id, "Traceability", "Analyze traceability gaps and recommend the next links or evidence to create."),
            )
            st.markdown(answer.text)
            source_list(answer.sources)
