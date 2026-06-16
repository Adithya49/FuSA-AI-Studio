from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from datetime import date
import json
from typing import TypeVar

import streamlit as st

from fusa_ai_studio.ui.components import source_list
from fusa_ai_studio import logging_config
import traceback
import hashlib

logger = logging_config.get_logger(__name__)


def _log_exception(message: str, exc: BaseException) -> None:
    logger.exception(message)
    try:
        (logging_config.ERROR_DIR / "genai_last_error.log").write_text(
            f"{message}\n\n{traceback.format_exc()}", encoding="utf-8"
        )
    except Exception:
        logger.exception("Failed to write last error log")


T = TypeVar("T")


# Chat-based follow-ups removed per user request.

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


def _local_quick_suggestions(feature: str, current_output: str) -> list[dict]:
    """Generate quick-add suggestions without calling the LLM.

    This keeps suggestions deterministic and ensures the UI always has
    at least one actionable suggestion for common modules.
    """
    normalized_feature = (feature or "").lower()
    output_lines = [line.strip() for line in current_output.splitlines() if line.strip()]
    summary_line = output_lines[0] if output_lines else current_output.strip()
    if not summary_line:
        summary_line = f"Review the current {feature.lower()} output and extract a follow-up artifact."

    def make(title: str, artifact_type: str, summary: str, hint: str = "") -> dict:
        return {
            "artifact_type": artifact_type,
            "title": title,
            "summary": summary,
            "hint": hint,
        }

    suggestions: list[dict] = []

    if "hara" in normalized_feature:
        suggestions.append(
            make(
                "Add hazard candidate",
                "hazard",
                f"The HARA output suggests a traceable hazard based on: {summary_line[:180]}",
                "Prefill severity, exposure, controllability, and ASIL from the review text.",
            )
        )
        suggestions.append(
            make(
                "Add linked safety goal",
                "safety_goal",
                "Convert the hazard into a safety goal with a safe state and verification intent.",
                "Tie the goal directly to the hazard and preserve ASIL rationale.",
            )
        )
    elif "item" in normalized_feature:
        suggestions.append(
            make(
                "Refine item definition",
                "item",
                f"Turn the item review into a better item definition using: {summary_line[:180]}",
                "Use the generated output to improve purpose, boundaries, interfaces, and assumptions.",
            )
        )
        suggestions.append(
            make(
                "Add follow-up task",
                "workflow_task",
                "Capture the remaining item-definition work as a tracked task.",
                "Assign an owner and due date to close the gaps from the review.",
            )
        )
    elif "fsc" in normalized_feature or "functional safety concept" in normalized_feature:
        suggestions.append(
            make(
                "Add FSC requirement",
                "fsc_requirement",
                f"Promote the FSC review into a concrete requirement from: {summary_line[:180]}",
                "Prefill allocation, ASIL, rationale, and verification.",
            )
        )
        suggestions.append(
            make(
                "Add safety goal link",
                "safety_goal",
                "Ensure the FSC remains traceable to the governing safety goal.",
                "Link the requirement to the most relevant safety goal.",
            )
        )
    elif "tsc" in normalized_feature or "technical safety concept" in normalized_feature:
        suggestions.append(
            make(
                "Add TSC requirement",
                "tsc_requirement",
                f"Convert the TSC review into a component-level requirement from: {summary_line[:180]}",
                "Prefill the component, diagnostic mechanism, and verification fields.",
            )
        )
        suggestions.append(
            make(
                "Add implementation task",
                "workflow_task",
                "Track the implementation work needed to realize the TSC update.",
                "Assign the action to the relevant owner.",
            )
        )
    elif "safety goal" in normalized_feature or "safety" in normalized_feature:
        suggestions.append(
            make(
                "Refine safety goal",
                "safety_goal",
                f"Use the review text to strengthen the safety goal: {summary_line[:180]}",
                "Make the statement more verifiable and explicit.",
            )
        )
        suggestions.append(
            make(
                "Add traceability task",
                "workflow_task",
                "Record the remaining evidence and traceability work for this safety goal.",
                "Add owner, status, and due date.",
            )
        )
    else:
        suggestions.append(
            make(
                "Add follow-up task",
                "workflow_task",
                f"Track a follow-up derived from: {summary_line[:180]}",
                "Use this when the output does not map cleanly to a formal artifact.",
            )
        )

    return suggestions[:3]


def _direct_quick_add(services, project_id: str, feature: str, answer, suggestion: dict) -> tuple[str, str]:
    """Create an artifact immediately from a quick suggestion."""
    artifact_type = suggestion.get("artifact_type", "workflow_task")
    summary = suggestion.get("summary", "").strip()
    hint = suggestion.get("hint", "").strip()
    title = suggestion.get("title", "").strip()

    if artifact_type == "item":
        item_id = services.repo.insert(
            "items",
            {
                "project_id": project_id,
                "name": title or "New item definition",
                "purpose": summary or hint or "Created from quick suggestion.",
                "boundaries": "Derived from the generated review output.",
                "interfaces": "Derived from the generated review output.",
                "assumptions": hint or "To be validated during review.",
            },
        )
        services.repo.add_memory(project_id, "item_definition", f"Item {title or item_id}: {summary or hint}", 3)
        services.knowledge.index_artifacts(project_id)
        metadata = {
            "tokens_in": getattr(answer, "tokens_in", None),
            "tokens_out": getattr(answer, "tokens_out", None),
            "tokens_total": getattr(answer, "tokens_total", None),
            "latency_seconds": getattr(answer, "latency_seconds", None),
            "gpu": getattr(answer, "gpu", None),
        }
        services.repo.store_ai_interaction(
            project_id,
            f"{feature} quick-add",
            answer.provider,
            answer.model,
            title or "Add item definition",
            [{"id": "suggestion", "content": json.dumps(suggestion)}],
            f"Added item {item_id}",
            metadata=metadata,
        )
        return "item", str(item_id)

    if artifact_type == "hazard":
        items = services.repo.list_table("items", project_id)
        item_id = items[0]["id"] if items else None
        hazard_id = services.repo.insert(
            "hazards",
            {
                "project_id": project_id,
                "item_id": item_id,
                "function_name": title or "Hazard candidate",
                "malfunction": summary or hint or "Derived from HARA output.",
                "operational_situation": "Derived from the generated review output.",
                "hazardous_event": summary or hint or "Potential hazardous event identified by quick suggestion.",
                "severity": 3,
                "exposure": 4,
                "controllability": 3,
                "asil": "D",
                "rationale": hint or "Added directly from quick suggestion.",
            },
        )
        if item_id:
            services.repo.add_trace(project_id, "item", str(item_id), "hazard", str(hazard_id), "analyzed_by", "Added from quick suggestion.")
        services.repo.add_memory(project_id, "hara", f"{summary or hint} classified D.", 4)
        services.knowledge.index_artifacts(project_id)
        metadata = {
            "tokens_in": getattr(answer, "tokens_in", None),
            "tokens_out": getattr(answer, "tokens_out", None),
            "tokens_total": getattr(answer, "tokens_total", None),
            "latency_seconds": getattr(answer, "latency_seconds", None),
            "gpu": getattr(answer, "gpu", None),
        }
        services.repo.store_ai_interaction(
            project_id,
            f"{feature} quick-add",
            answer.provider,
            answer.model,
            title or "Add hazard",
            [{"id": "suggestion", "content": json.dumps(suggestion)}],
            f"Added hazard {hazard_id}",
            metadata=metadata,
        )
        return "hazard", str(hazard_id)

    if artifact_type == "safety_goal":
        hazards = services.repo.list_table("hazards", project_id)
        hazard_id = hazards[0]["id"] if hazards else None
        goal_code = f"SG-AUTO-{len(services.repo.list_table('safety_goals', project_id)) + 1:03d}"
        sg_id = services.repo.insert(
            "safety_goals",
            {
                "project_id": project_id,
                "hazard_id": hazard_id,
                "goal_code": goal_code,
                "statement": summary or hint or "Derived from the generated review output.",
                "asil": "D",
                "safe_state": "To be defined",
                "fault_tolerant_time": "To be defined",
                "verification": "To be defined",
            },
        )
        if hazard_id:
            services.repo.add_trace(project_id, "hazard", str(hazard_id), "safety_goal", str(sg_id), "mitigated_by", "Added from quick suggestion.")
        services.repo.add_memory(project_id, "safety_goal", f"{goal_code}: {summary or hint}", 4)
        services.knowledge.index_artifacts(project_id)
        metadata = {
            "tokens_in": getattr(answer, "tokens_in", None),
            "tokens_out": getattr(answer, "tokens_out", None),
            "tokens_total": getattr(answer, "tokens_total", None),
            "latency_seconds": getattr(answer, "latency_seconds", None),
            "gpu": getattr(answer, "gpu", None),
        }
        services.repo.store_ai_interaction(
            project_id,
            f"{feature} quick-add",
            answer.provider,
            answer.model,
            title or "Add safety goal",
            [{"id": "suggestion", "content": json.dumps(suggestion)}],
            f"Added safety goal {sg_id}",
            metadata=metadata,
        )
        return "safety_goal", str(sg_id)

    if artifact_type == "fsc_requirement":
        goals = services.repo.list_table("safety_goals", project_id)
        goal_id = goals[0]["id"] if goals else None
        req_code = f"FSC-AUTO-{len(services.repo.list_table('fsc_requirements', project_id)) + 1:03d}"
        req_id = services.repo.insert(
            "fsc_requirements",
            {
                "project_id": project_id,
                "safety_goal_id": goal_id,
                "req_code": req_code,
                "statement": summary or hint or "Derived from the generated review output.",
                "asil": "D",
                "allocation": "To be defined",
                "rationale": hint or "Added directly from quick suggestion.",
                "verification": "To be defined",
            },
        )
        if goal_id:
            services.repo.add_trace(project_id, "safety_goal", str(goal_id), "fsc_requirement", str(req_id), "refined_by", "Added from quick suggestion.")
        services.repo.add_memory(project_id, "fsc", f"{req_code}: {summary or hint}", 3)
        services.knowledge.index_artifacts(project_id)
        metadata = {
            "tokens_in": getattr(answer, "tokens_in", None),
            "tokens_out": getattr(answer, "tokens_out", None),
            "tokens_total": getattr(answer, "tokens_total", None),
            "latency_seconds": getattr(answer, "latency_seconds", None),
            "gpu": getattr(answer, "gpu", None),
        }
        services.repo.store_ai_interaction(
            project_id,
            f"{feature} quick-add",
            answer.provider,
            answer.model,
            title or "Add FSC requirement",
            [{"id": "suggestion", "content": json.dumps(suggestion)}],
            f"Added FSC requirement {req_id}",
            metadata=metadata,
        )
        return "fsc_requirement", str(req_id)

    if artifact_type == "tsc_requirement":
        fsc_rows = services.repo.list_table("fsc_requirements", project_id)
        fsc_id = fsc_rows[0]["id"] if fsc_rows else None
        req_code = f"TSC-AUTO-{len(services.repo.list_table('tsc_requirements', project_id)) + 1:03d}"
        req_id = services.repo.insert(
            "tsc_requirements",
            {
                "project_id": project_id,
                "fsc_requirement_id": fsc_id,
                "req_code": req_code,
                "statement": summary or hint or "Derived from the generated review output.",
                "asil": "D",
                "component": "To be defined",
                "diagnostic_mechanism": hint or "Added directly from quick suggestion.",
                "verification": "To be defined",
            },
        )
        if fsc_id:
            services.repo.add_trace(project_id, "fsc_requirement", str(fsc_id), "tsc_requirement", str(req_id), "refined_by", "Added from quick suggestion.")
        services.repo.add_memory(project_id, "tsc", f"{req_code}: {summary or hint}", 3)
        services.knowledge.index_artifacts(project_id)
        metadata = {
            "tokens_in": getattr(answer, "tokens_in", None),
            "tokens_out": getattr(answer, "tokens_out", None),
            "tokens_total": getattr(answer, "tokens_total", None),
            "latency_seconds": getattr(answer, "latency_seconds", None),
            "gpu": getattr(answer, "gpu", None),
        }
        services.repo.store_ai_interaction(
            project_id,
            f"{feature} quick-add",
            answer.provider,
            answer.model,
            title or "Add TSC requirement",
            [{"id": "suggestion", "content": json.dumps(suggestion)}],
            f"Added TSC requirement {req_id}",
            metadata=metadata,
        )
        return "tsc_requirement", str(req_id)

    task_id = services.repo.insert(
        "workflow_tasks",
        {
            "project_id": project_id,
            "title": title or "Follow-up task",
            "owner": "Safety Manager",
            "status": "Open",
            "due_date": date.today().isoformat(),
            "evidence": summary or hint or "Added from quick suggestion.",
        },
    )
    services.repo.add_memory(project_id, "workflow", f"{title or 'Follow-up task'} added from quick suggestion.", 2)
    metadata = {
        "tokens_in": getattr(answer, "tokens_in", None),
        "tokens_out": getattr(answer, "tokens_out", None),
        "tokens_total": getattr(answer, "tokens_total", None),
        "latency_seconds": getattr(answer, "latency_seconds", None),
        "gpu": getattr(answer, "gpu", None),
    }
    services.repo.store_ai_interaction(
        project_id,
        f"{feature} quick-add",
        answer.provider,
        answer.model,
        title or "Add follow-up task",
        [{"id": "suggestion", "content": json.dumps(suggestion)}],
        f"Added task {task_id}",
        metadata=metadata,
    )
    return "workflow_task", str(task_id)


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
            _log_exception(f"GenAI action failed for {label}", exc)
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
        draft = st.session_state.get(draft_key)
        if draft is None or draft == prev_source:
            st.session_state[draft_key] = answer_text
        st.session_state[source_key] = answer_text
        st.session_state[source_hash_key] = answer_hash
        suggestions_key = f"{panel_key}_suggestions"
        st.session_state[suggestions_key] = _local_quick_suggestions(feature, answer_text)

    # Ensure draft key exists to avoid KeyError on widget-driven reruns
    st.session_state.setdefault(draft_key, answer_text)

    st.markdown(st.session_state[draft_key])
    try:
        caption_items = [f"Provider: {answer.provider}", f"Model: {answer.model}"]
        if getattr(answer, "tokens_in", None) is not None or getattr(answer, "tokens_out", None) is not None or getattr(answer, "tokens_total", None) is not None:
            tokens_in = getattr(answer, "tokens_in", None) or 0
            tokens_out = getattr(answer, "tokens_out", None) or 0
            tokens_total = getattr(answer, "tokens_total", None) or tokens_in + tokens_out
            caption_items.append(f"Tokens (In/Out/Total): {tokens_in:,} / {tokens_out:,} / {tokens_total:,}")
        if getattr(answer, "latency_seconds", None) is not None:
            caption_items.append(f"Latency: {answer.latency_seconds:.2f}s")
        if getattr(answer, "gpu", ""):
            caption_items.append(f"GPU: {answer.gpu}")
    except Exception as exc:
        _log_exception("Error formatting AI response caption", exc)
        caption_items = [
            f"Provider: {getattr(answer, 'provider', 'unknown')}",
            f"Model: {getattr(answer, 'model', 'unknown')}"
        ]
    st.caption(" • ".join(caption_items))
    source_list(answer.sources)
    # Chat UI removed — users interact with the displayed draft directly.

    render_ai_addition_suggestions(services, project_id, feature, answer, panel_key)


def render_ai_addition_suggestions(services, project_id: str, feature: str, answer, panel_key: str) -> None:
    suggestions_key = f"{panel_key}_suggestions"
    answer_text = getattr(answer, "text", "") or ""

    # Render the suggestions already generated from the output/feature.
    if st.session_state.get(suggestions_key) is None:
        st.session_state[suggestions_key] = _local_quick_suggestions(feature, answer_text) if answer_text else []

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
            if st.button("Add", key=f"{panel_key}_add_{index}"):
                added_type, added_id = _direct_quick_add(services, project_id, feature, answer, suggestion)
                st.success(f"Added {added_type} {added_id}.")
                st.rerun()
    # No secondary form is shown. Suggestions create artifacts immediately.