from __future__ import annotations

from fusa_ai_studio.ai.chunking import ChunkingEngine
from fusa_ai_studio.ai.embeddings import EmbeddingEngine
from fusa_ai_studio.ai.prompts import build_rag_prompt
from fusa_ai_studio.core.asil import calculate_asil
from fusa_ai_studio.core.config import detect_llm_provider
from fusa_ai_studio.ui.genai import _split_think_sections


def test_asil_calculation() -> None:
    assert calculate_asil(3, 4, 3) == "D"
    assert calculate_asil(0, 4, 3) == "QM"


def test_chunking_and_embeddings() -> None:
    chunks = ChunkingEngine().chunk("# Heading\n\nA safety goal shall be verifiable.", "section")
    assert chunks
    vector = EmbeddingEngine().embed(chunks[0].content).vector
    assert len(vector) == 384


def test_detect_llm_provider_prefers_explicit_setting(monkeypatch) -> None:
    monkeypatch.setenv("FUSA_LLM_PROVIDER", "Local")
    monkeypatch.setenv("GEMINI_API_KEY", "abc")
    assert detect_llm_provider() == "Local"


def test_detect_llm_provider_falls_back_to_gemini(monkeypatch) -> None:
    monkeypatch.delenv("FUSA_LLM_PROVIDER", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "abc")
    assert detect_llm_provider() == "Gemini"


def test_split_think_sections_removes_reasoning_from_visible_output() -> None:
    visible, reasoning = _split_think_sections(
        "<think>First think through the problem.</think>\n\nFinal answer."
    )

    assert reasoning == ["First think through the problem."]
    assert visible == "Final answer."


def test_rag_prompt_scopes_answers_to_fusa_context() -> None:
    prompt = build_rag_prompt(
        "HARA",
        "Can you explain the weather?",
        [],
        "",
        [],
    )

    assert "Do not answer questions that are unrelated to functional safety" in prompt
    assert "only using the retrieved project context" in prompt
