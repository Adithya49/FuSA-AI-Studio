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
