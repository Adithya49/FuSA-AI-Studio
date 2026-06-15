from __future__ import annotations

from collections.abc import Callable
import json
from typing import TypeVar

import streamlit as st

from fusa_ai_studio.ai.prompts import build_additions_prompt, build_follow_up_prompt
from fusa_ai_studio.ui.components import source_list
import hashlib


T = TypeVar("T")


FOLLOW_UP_OPTIONS = {
    "Explain this output": "Explain the current output in plain language and call out the most important safety implications.",
    "Suggest edits": "Suggest concrete edits that would improve clarity, traceability, and ISO 26262 rigor. Return a revised version and a short change log.",
    "Rewrite for clarity": "Rewrite the current output so it reads like a concise safety engineering artifact while preserving meaning and traceability.",
    "Highlight gaps": "Identify missing evidence, ambiguities, assumptions, and traceability gaps in the current output.",
    "Custom question": "Ask a follow-up question about the current output.",
}

REVISION_MODES = {"Suggest edits", "Rewrite for clarity"}

ADD_DIALOG_FIELDS = {
    "item": ["name", "purpose", "boundaries", "interfaces", "assumptions"],
    "hazard": ["item_id", "function_name", "malfunction", "operational_situation", "hazardous_event", "severity", "exposure", "controllability", "asil", "rationale"],
    "safety_goal": ["hazard_id", "goal_code", "statement", "asil", "safe_state", "fault_tolerant_time", "verification"],
    "fsc_requirement": ["safety_goal_id", "req_code", "statement", "asil", "allocation", "rationale", "verification"],
    "tsc_requirement": ["fsc_requirement_id", "req_code", "statement", "asil", "component", "diagnostic_mechanism", "verification"],
    "workflow_task": ["title", "owner", "status", "due_date", "evidence"],
}

ADD_DIALOG_TITLES = {
    "item": "Item Definition",
    "hazard": "HARA Hazard",
    "safety_goal": "Safety Goal",
    "fsc_requirement": "FSC Requirement",
    "tsc_requirement": "TSC Requirement",
    "workflow_task": "Workflow Task",
}


def _safe_dialog(title: str):
    dialog = getattr(st, "dialog", None)
    if dialog is None:
        def passthrough(func):
            return func

        return passthrough
    return dialog(title)


def run_genai_action(label: str, action: Callable[[], T]) -> T:
    with st.status(f"{label}: preparing request", expanded=True) as status:
        status.write("Collecting project context and building prompt.")
        status.update(label=f"{label}: sending request", state="running")
        status.write("Request sent. Waiting for GenAI response.")
        try:
            result = action()
        except Exception as exc:
            status.update(label=f"{label}: error", state="error")
            status.write(f"Error: {exc}")
            raise

        warning = getattr(result, "warning", "") or ""
        if warning:
            status.update(label=f"{label}: provider error", state="error")
            status.write(warning)
        else:
            status.update(label=f"{label}: response received", state="complete")
            status.write("GenAI response received successfully.")
        return result


def render_ai_response_with_chat(services, project_id: str, feature: str, answer, panel_key: str) -> None:
    draft_key = f"{panel_key}_draft"
    source_key = f"{panel_key}_source_text"
    messages_key = f"{panel_key}_messages"

    # Track a stable hash of the original answer so we can detect when
    # a genuinely new AI-generated output appears. When a new original
    # answer appears, update the source; but only overwrite the user's
    # draft/messages if the draft still matches the previous source
    # (meaning the user hasn't edited or applied a follow-up revision).
    source_hash_key = f"{panel_key}_source_hash"
    prev_source = st.session_state.get(source_key)
    prev_hash = st.session_state.get(source_hash_key)
    answer_text = getattr(answer, "text", "") or ""

    # If the current answer is empty/blank, avoid changing session state.
    # This prevents widget-driven reruns (e.g. selecting a follow-up mode)
    # from clearing the draft when the top-level answer variable isn't set.
    if not answer_text:
        answer_hash = None
    else:
        answer_hash = hashlib.sha256(answer_text.encode("utf-8")).hexdigest()

    if answer_text and prev_hash != answer_hash:
        # New original answer detected
        draft = st.session_state.get(draft_key)
        if draft is None or draft == prev_source:
            st.session_state[draft_key] = answer_text
            st.session_state[messages_key] = [{"role": "assistant", "content": answer_text}]
        # Always update the canonical source and stored hash when we have a real answer
        st.session_state[source_key] = answer_text
        st.session_state[source_hash_key] = answer_hash

    st.markdown(st.session_state[draft_key])
    st.caption(f"Provider: {answer.provider} · Model: {answer.model}")
    source_list(answer.sources)

    with st.expander("Chat about this output", expanded=False):
        st.caption("Use a preset or ask a custom question to explain or revise the current draft.")
        mode = st.selectbox("Chat option", list(FOLLOW_UP_OPTIONS.keys()), key=f"{panel_key}_mode")
        user_request = st.text_area(
            "Message to the LLM",
            value=FOLLOW_UP_OPTIONS[mode],
            key=f"{panel_key}_request",
            height=120,
        )

        for message in st.session_state.get(messages_key, []):
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        col1, col2 = st.columns(2)
        if col1.button("Send to LLM", key=f"{panel_key}_send"):
            current_output = st.session_state[draft_key]
            prompt = build_follow_up_prompt(feature, current_output, user_request, mode, answer.sources)
            provider = services.repo.get_setting("llm_provider", "Local")
            model = services.repo.get_setting("llm_model", "fusa-local-deterministic")
            response = services.rag.llm.generate(prompt, provider, model)
            st.session_state[messages_key].append({"role": "user", "content": user_request})
            st.session_state[messages_key].append({"role": "assistant", "content": response.text})
            services.repo.store_ai_interaction(
                project_id,
                f"{feature} follow-up",
                response.provider,
                response.model,
                user_request,
                [{"id": "current_output", "content": current_output, "metadata": {"feature": feature, "mode": mode}}, *answer.sources],
                response.text,
            )
            if mode in REVISION_MODES:
                st.session_state[draft_key] = response.text
            st.rerun()

        if col2.button("Reset draft", key=f"{panel_key}_reset"):
            st.session_state[draft_key] = st.session_state[source_key]
            st.session_state[messages_key] = [{"role": "assistant", "content": st.session_state[source_key]}]
            st.rerun()

    render_ai_addition_suggestions(services, project_id, feature, answer, panel_key)


def render_ai_addition_suggestions(services, project_id: str, feature: str, answer, panel_key: str) -> None:
    suggestions_key = f"{panel_key}_suggestions"
    suggestion_state_key = f"{panel_key}_suggestion_state"
    dialog_request_key = f"{panel_key}_dialog_request"

    if st.session_state.get(suggestions_key) is None:
        prompt = build_additions_prompt(feature, answer.text, answer.sources)
        response = services.rag.llm.generate(prompt, services.repo.get_setting("llm_provider", "Local"), services.repo.get_setting("llm_model", "fusa-local-deterministic"))
        try:
            payload = json.loads(response.text)
            st.session_state[suggestions_key] = payload.get("suggestions", [])
        except json.JSONDecodeError:
            st.session_state[suggestions_key] = []

    suggestions = st.session_state.get(suggestions_key, [])
    if not suggestions:
        st.caption("No quick-add suggestions were generated for this output.")
        return

    st.markdown("### Quick Add Suggestions")
    for index, suggestion in enumerate(suggestions):
        artifact_type = suggestion.get("artifact_type", "workflow_task")
        title = suggestion.get("title", "Add item")
        summary = suggestion.get("summary", "")
        hint = suggestion.get("hint", "")
        columns = st.columns([0.85, 0.15])
        with columns[0]:
            st.markdown(f"**{title}**")
            st.caption(summary)
            if hint:
                st.caption(hint)
        with columns[1]:
            if st.button("+", key=f"{panel_key}_add_{index}"):
                st.session_state[suggestion_state_key] = suggestion
                st.session_state[dialog_request_key] = True
                st.rerun()

    if st.session_state.get(dialog_request_key):
        _render_add_dialog(services, project_id, feature, panel_key, answer, st.session_state[suggestion_state_key], dialog_request_key, suggestion_state_key)


@_safe_dialog("Add suggested artifact")
def _render_add_dialog(services, project_id: str, feature: str, panel_key: str, answer, suggestion: dict, dialog_request_key: str, suggestion_state_key: str) -> None:
    artifact_type = suggestion.get("artifact_type", "workflow_task")
    hint = suggestion.get("hint", "")
    st.subheader(ADD_DIALOG_TITLES.get(artifact_type, "Suggested addition"))
    st.caption(suggestion.get("summary", ""))
    if hint:
        st.caption(hint)

    if artifact_type == "item":
        name = st.text_input("Item name", suggestion.get("title", "New item"), key=f"{panel_key}_item_name")
        purpose = st.text_area("Purpose", suggestion.get("summary", ""), key=f"{panel_key}_item_purpose")
        boundaries = st.text_area("Boundaries", "", key=f"{panel_key}_item_boundaries")
        interfaces = st.text_area("Interfaces", "", key=f"{panel_key}_item_interfaces")
        assumptions = st.text_area("Assumptions", "", key=f"{panel_key}_item_assumptions")

        if st.button("Proceed / Add", key=f"{panel_key}_item_add"):
            item_id = services.repo.insert(
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
            services.repo.add_memory(project_id, "item_definition", f"Item {name}: {purpose}", 3)
            services.knowledge.index_artifacts(project_id)
            services.repo.store_ai_interaction(project_id, f"{feature} quick-add", answer.provider, answer.model, suggestion.get("summary", ""), [{"id": "suggestion", "content": json.dumps(suggestion)}], f"Added item {item_id}")
            st.session_state[dialog_request_key] = False
            st.session_state.pop(suggestion_state_key, None)
            st.success("Item added.")
            st.rerun()
        return

    if artifact_type == "hazard":
        hazards = services.repo.list_table("hazards", project_id)
        items = services.repo.list_table("items", project_id)
        item_options = {f"{item['id']} · {item['name']}": item["id"] for item in items}
        item_label = st.selectbox("Linked item", list(item_options.keys()) or ["No item"], key=f"{panel_key}_hazard_item")
        function_name = st.text_input("Function", suggestion.get("title", "Hazard function"), key=f"{panel_key}_hazard_function")
        malfunction = st.text_input("Malfunction", suggestion.get("summary", ""), key=f"{panel_key}_hazard_malfunction")
        situation = st.text_input("Operational situation", "", key=f"{panel_key}_hazard_situation")
        event = st.text_area("Hazardous event", "", key=f"{panel_key}_hazard_event")
        col1, col2, col3 = st.columns(3)
        severity = col1.slider("Severity", 0, 3, 3, key=f"{panel_key}_hazard_severity")
        exposure = col2.slider("Exposure", 0, 4, 4, key=f"{panel_key}_hazard_exposure")
        controllability = col3.slider("Controllability", 0, 3, 3, key=f"{panel_key}_hazard_controllability")
        asil = st.selectbox("ASIL", ["QM", "A", "B", "C", "D"], index=4, key=f"{panel_key}_hazard_asil")
        rationale = st.text_area("Rationale", suggestion.get("hint", ""), key=f"{panel_key}_hazard_rationale")
        if st.button("Proceed / Add", key=f"{panel_key}_hazard_add"):
            hazard_id = services.repo.insert(
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
                services.repo.add_trace(project_id, "item", str(item_options[item_label]), "hazard", str(hazard_id), "analyzed_by", "Added from AI suggestion dialog.")
            services.repo.add_memory(project_id, "hara", f"{malfunction} in {situation} classified {asil}.", 4)
            services.knowledge.index_artifacts(project_id)
            st.session_state[dialog_request_key] = False
            st.session_state.pop(suggestion_state_key, None)
            st.success("Hazard added.")
            st.rerun()
        return

    if artifact_type == "safety_goal":
        hazards = services.repo.list_table("hazards", project_id)
        hazard_options = {f"{hazard['id']} · {hazard['malfunction']} · {hazard['asil']}": hazard for hazard in hazards}
        hazard_label = st.selectbox("Linked hazard", list(hazard_options.keys()) or ["No hazard"], key=f"{panel_key}_sg_hazard")
        hazard = hazard_options.get(hazard_label, {})
        goal_code = st.text_input("Goal code", suggestion.get("title", "SG-NEW"), key=f"{panel_key}_sg_code")
        statement = st.text_area("Statement", suggestion.get("summary", ""), key=f"{panel_key}_sg_statement")
        asil = st.selectbox("ASIL", ["QM", "A", "B", "C", "D"], index=4, key=f"{panel_key}_sg_asil")
        safe_state = st.text_input("Safe state", "", key=f"{panel_key}_sg_safe_state")
        ftt = st.text_input("Fault tolerant time", "", key=f"{panel_key}_sg_ftt")
        verification = st.text_area("Verification", "", key=f"{panel_key}_sg_verification")
        if st.button("Proceed / Add", key=f"{panel_key}_sg_add"):
            sg_id = services.repo.insert(
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
                services.repo.add_trace(project_id, "hazard", str(hazard["id"]), "safety_goal", str(sg_id), "mitigated_by", "Added from AI suggestion dialog.")
            services.repo.add_memory(project_id, "safety_goal", f"{goal_code}: {statement}", 4)
            services.knowledge.index_artifacts(project_id)
            st.session_state[dialog_request_key] = False
            st.session_state.pop(suggestion_state_key, None)
            st.success("Safety goal added.")
            st.rerun()
        return

    if artifact_type == "fsc_requirement":
        goals = services.repo.list_table("safety_goals", project_id)
        goal_options = {f"{goal['id']} · {goal['goal_code']} · {goal['asil']}": goal for goal in goals}
        goal_label = st.selectbox("Linked safety goal", list(goal_options.keys()) or ["No safety goal"], key=f"{panel_key}_fsc_goal")
        goal = goal_options.get(goal_label, {})
        req_code = st.text_input("Requirement code", suggestion.get("title", "FSC-NEW"), key=f"{panel_key}_fsc_code")
        statement = st.text_area("Statement", suggestion.get("summary", ""), key=f"{panel_key}_fsc_statement")
        asil = st.selectbox("ASIL", ["QM", "A", "B", "C", "D"], index=4, key=f"{panel_key}_fsc_asil")
        allocation = st.text_input("Allocation", "", key=f"{panel_key}_fsc_allocation")
        rationale = st.text_area("Rationale", suggestion.get("hint", ""), key=f"{panel_key}_fsc_rationale")
        verification = st.text_area("Verification", "", key=f"{panel_key}_fsc_verification")
        if st.button("Proceed / Add", key=f"{panel_key}_fsc_add"):
            req_id = services.repo.insert(
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
                services.repo.add_trace(project_id, "safety_goal", str(goal["id"]), "fsc_requirement", str(req_id), "refined_by", "Added from AI suggestion dialog.")
            services.repo.add_memory(project_id, "fsc", f"{req_code}: {statement}", 3)
            services.knowledge.index_artifacts(project_id)
            st.session_state[dialog_request_key] = False
            st.session_state.pop(suggestion_state_key, None)
            st.success("FSC requirement added.")
            st.rerun()
        return

    if artifact_type == "tsc_requirement":
        fsc_rows = services.repo.list_table("fsc_requirements", project_id)
        fsc_options = {f"{row['id']} · {row['req_code']} · {row['asil']}": row for row in fsc_rows}
        fsc_label = st.selectbox("Linked FSC requirement", list(fsc_options.keys()) or ["No FSC requirement"], key=f"{panel_key}_tsc_fsc")
        fsc = fsc_options.get(fsc_label, {})
        req_code = st.text_input("Requirement code", suggestion.get("title", "TSC-NEW"), key=f"{panel_key}_tsc_code")
        statement = st.text_area("Statement", suggestion.get("summary", ""), key=f"{panel_key}_tsc_statement")
        asil = st.selectbox("ASIL", ["QM", "A", "B", "C", "D"], index=4, key=f"{panel_key}_tsc_asil")
        component = st.text_input("Component", "", key=f"{panel_key}_tsc_component")
        diagnostic = st.text_area("Diagnostic mechanism", "", key=f"{panel_key}_tsc_diagnostic")
        verification = st.text_area("Verification", "", key=f"{panel_key}_tsc_verification")
        if st.button("Proceed / Add", key=f"{panel_key}_tsc_add"):
            req_id = services.repo.insert(
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
                services.repo.add_trace(project_id, "fsc_requirement", str(fsc["id"]), "tsc_requirement", str(req_id), "refined_by", "Added from AI suggestion dialog.")
            services.repo.add_memory(project_id, "tsc", f"{req_code}: {statement}", 3)
            services.knowledge.index_artifacts(project_id)
            st.session_state[dialog_request_key] = False
            st.session_state.pop(suggestion_state_key, None)
            st.success("TSC requirement added.")
            st.rerun()
        return

    title = st.text_input("Task title", suggestion.get("title", "Follow-up task"), key=f"{panel_key}_task_title")
    owner = st.text_input("Owner", "Safety Manager", key=f"{panel_key}_task_owner")
    status = st.selectbox("Status", ["Open", "In Progress", "Blocked", "Done"], key=f"{panel_key}_task_status")
    due_date = st.date_input("Due date", key=f"{panel_key}_task_due")
    evidence = st.text_area("Evidence", suggestion.get("hint", ""), key=f"{panel_key}_task_evidence")
    if st.button("Proceed / Add", key=f"{panel_key}_task_add"):
        services.repo.insert(
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
        services.repo.add_memory(project_id, "workflow", f"{title} assigned to {owner} due {due_date.isoformat()}.", 2)
        st.session_state[dialog_request_key] = False
        st.session_state.pop(suggestion_state_key, None)
        st.success("Task added.")
        st.rerun()