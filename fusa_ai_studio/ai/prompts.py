from __future__ import annotations


SYSTEM_PROMPT = """You are FuSA AI Studio, an ISO 26262 functional safety assistant.
Use only the retrieved project context, project memory, and traceability evidence supplied in the prompt.
When information is missing, state what evidence is needed instead of inventing it.
Return concise, auditable engineering output with assumptions, rationale, and verification considerations."""


def build_rag_prompt(feature: str, question: str, memory: list[dict], trace_context: str, retrieved: list[dict]) -> str:
    memory_text = "\n".join(f"- {row['memory_type']}: {row['content']}" for row in memory) or "- No memory recorded."
    retrieved_text = "\n".join(
        f"- Source {idx + 1} [{item.get('metadata', {}).get('title', item.get('id', 'chunk'))}]: {item.get('content', '')}"
        for idx, item in enumerate(retrieved)
    ) or "- No relevant chunks retrieved."
    return f"""{SYSTEM_PROMPT}

Feature: {feature}

Project memory:
{memory_text}

Traceability context:
{trace_context}

Retrieved context:
{retrieved_text}

Question:
{question}
"""


def build_follow_up_prompt(feature: str, current_output: str, user_request: str, mode: str, sources: list[dict]) -> str:
    source_text = "\n".join(
        f"- Source {idx + 1} [{item.get('metadata', {}).get('title', item.get('id', 'chunk'))}]: {item.get('content', '')}"
        for idx, item in enumerate(sources)
    ) or "- No source context was supplied."
    return f"""{SYSTEM_PROMPT}

Feature: {feature}

Chat mode:
{mode}

Current generated output:
{current_output}

Relevant source context:
{source_text}

User request:
{user_request}

Instructions:
- If the user asks for explanation, explain the current output clearly and reference the most relevant lines.
- If the user asks for modification, return a revised version first, then a short change summary.
- Preserve traceability, ISO 26262 terminology, and explicit safety rationale.
- Do not invent evidence or claim a revision is validated unless the supplied context supports it.
"""


def build_additions_prompt(feature: str, current_output: str, sources: list[dict]) -> str:
    source_text = "\n".join(
        f"- Source {idx + 1} [{item.get('metadata', {}).get('title', item.get('id', 'chunk'))}]: {item.get('content', '')}"
        for idx, item in enumerate(sources)
    ) or "- No source context was supplied."
    return f"""{SYSTEM_PROMPT}

Feature: {feature}

Current generated output:
{current_output}

Relevant source context:
{source_text}

Task:
Suggest up to 3 addable project artifacts that the user can quickly create from this output.

Return JSON only using this schema:
{{
    "suggestions": [
        {{
            "artifact_type": "item|hazard|safety_goal|fsc_requirement|tsc_requirement|workflow_task",
            "title": "Short card title",
            "summary": "One-sentence reason the artifact should be added",
            "hint": "Optional short guidance for the prefilled form"
        }}
    ]
}}

Rules:
- Choose the artifact type that best matches the feature and current output.
- Keep each suggestion concise and actionable.
- Prefer suggestions that can be added immediately with a prefilled form.
- If no safe suggestion is available, return an empty suggestions array.
"""
