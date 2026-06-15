from __future__ import annotations

import json
from dataclasses import dataclass

from fusa_ai_studio.core.config import LLMConfig


LOCAL_MODEL_NAME = "fusa-local-deterministic"


@dataclass(frozen=True)
class LLMResponse:
    provider: str
    model: str
    text: str
    warning: str = ""


class LLMClient:
    def __init__(self, config: LLMConfig | None = None) -> None:
        self.config = config or LLMConfig()

    def generate(self, prompt: str, provider: str, model: str) -> LLMResponse:
        provider_key = provider.lower()
        try:
            if provider_key == "openai":
                return self._openai(prompt, model)
            if provider_key == "claude":
                return self._claude(prompt, model)
            if provider_key == "gemini":
                return self._gemini(prompt, model)
            if provider_key == "ollama":
                return self._ollama(prompt, model)
            if provider_key == "lm studio":
                selected = self._model(model, self.config.lm_studio.model or self.config.local_model)
                return self._openai_compatible(
                    selected,
                    prompt,
                    self.config.lm_studio.base_url or "http://localhost:1234/v1",
                    self.config.lm_studio.api_key or "lm-studio",
                    "LM Studio",
                )
            if provider_key == "openrouter":
                return self._openrouter(prompt, model)
        except Exception as exc:
            return LLMResponse(provider, model, self._local_response(prompt, f"Provider call failed: {exc}"), warning=str(exc))
        selected = self._model(model, self.config.local_model)
        return LLMResponse("Local", selected, self._local_response(prompt))

    def _openai(self, prompt: str, model: str) -> LLMResponse:
        from openai import OpenAI

        selected = self._model(model, self.config.openai.model or "gpt-4o-mini")
        client = OpenAI(api_key=self.config.openai.api_key, base_url=self.config.openai.base_url or "https://api.openai.com/v1")
        response = client.chat.completions.create(model=selected, messages=[{"role": "user", "content": prompt}], temperature=0.2)
        return LLMResponse("OpenAI", selected, response.choices[0].message.content or "")

    def _claude(self, prompt: str, model: str) -> LLMResponse:
        import anthropic

        selected = self._model(model, self.config.claude.model or "claude-3-5-sonnet-latest")
        client = anthropic.Anthropic(api_key=self.config.claude.api_key, base_url=self.config.claude.base_url or "https://api.anthropic.com")
        response = client.messages.create(model=selected, max_tokens=1400, temperature=0.2, messages=[{"role": "user", "content": prompt}])
        text = "\n".join(block.text for block in response.content if getattr(block, "type", "") == "text")
        return LLMResponse("Claude", selected, text)

    def _gemini(self, prompt: str, model: str) -> LLMResponse:
        from google import genai

        selected = self._model(model, self.config.gemini.model or "gemini-2.5-flash")
        client = genai.Client(api_key=self.config.gemini.api_key)
        response = client.models.generate_content(model=selected, contents=prompt)
        return LLMResponse("Gemini", selected, response.text or "")

    def _ollama(self, prompt: str, model: str) -> LLMResponse:
        import requests

        base_url = (self.config.ollama.base_url or "http://localhost:11434").rstrip("/")
        selected = self._model(model, self.config.ollama.model or "llama3.1")
        response = requests.post(f"{base_url}/api/generate", json={"model": selected, "prompt": prompt, "stream": False}, timeout=self._timeout())
        response.raise_for_status()
        return LLMResponse("Ollama", selected, response.json().get("response", ""))

    def _openrouter(self, prompt: str, model: str) -> LLMResponse:
        selected = self._model(model, self.config.openrouter.model or "openai/gpt-4o-mini")
        return self._openai_compatible(selected, prompt, self.config.openrouter.base_url or "https://openrouter.ai/api/v1", self.config.openrouter.api_key, "OpenRouter")

    def _openai_compatible(self, model: str, prompt: str, base_url: str, api_key: str, provider: str) -> LLMResponse:
        from openai import OpenAI

        client = OpenAI(api_key=api_key or "lm-studio", base_url=base_url)
        response = client.chat.completions.create(model=model, messages=[{"role": "user", "content": prompt}], temperature=0.2)
        return LLMResponse(provider, model, response.choices[0].message.content or "")

    def _model(self, configured: str, default: str) -> str:
        if configured and configured != self.config.local_model:
            return configured
        return default

    def _timeout(self) -> int:
        return self.config.timeout_seconds

    def _local_response(self, prompt: str, warning: str = "") -> str:
        if "Return JSON only" in prompt and "suggestions" in prompt:
            return self._local_additions_response(prompt, warning)
        context = prompt.split("Retrieved context:", 1)[-1].split("Question:", 1)[0].strip()
        question = prompt.split("Question:", 1)[-1].strip()
        context_lines = [line.strip("- ").strip() for line in context.splitlines() if line.strip()][:8]
        answer = [
            "AI assessment based on retrieved FuSA project context:",
            "",
            f"Question: {question[:500]}",
            "",
            "Recommended engineering response:",
            "- Preserve traceability from the originating item or hazard through the derived safety artifact.",
            "- State the safety intent in verifiable language with ASIL, safe state, timing, allocation, and verification evidence.",
            "- Record assumptions and rationale in project memory so future AI outputs reuse the same engineering basis.",
        ]
        if context_lines:
            answer.extend(["", "Retrieved sources considered:"])
            answer.extend(f"- {line[:220]}" for line in context_lines)
        if warning:
            answer.extend(["", f"Provider note: {warning}"])
        return "\n".join(answer)

    def _local_additions_response(self, prompt: str, warning: str = "") -> str:
        feature = prompt.split("Feature:", 1)[-1].split("Current generated output:", 1)[0].strip()
        current_output = prompt.split("Current generated output:", 1)[-1].split("Relevant source context:", 1)[0].strip()
        summary_line = current_output.splitlines()[0].strip() if current_output else f"Review the current {feature.lower()} output."

        suggestion = {
            "artifact_type": self._feature_artifact_type(feature),
            "title": self._feature_title(feature),
            "summary": summary_line[:220],
            "hint": "Use the current project context as the base and refine the prefilled fields before adding it.",
        }

        payload = {"suggestions": [suggestion]}
        if warning:
            payload["warning"] = warning
        return json.dumps(payload, indent=2)

    def _feature_artifact_type(self, feature: str) -> str:
        normalized = feature.lower()
        if "hara" in normalized:
            return "hazard"
        if "safety goal" in normalized:
            return "safety_goal"
        if normalized == "fsc" or "functional safety concept" in normalized:
            return "fsc_requirement"
        if normalized == "tsc" or "technical safety concept" in normalized:
            return "tsc_requirement"
        if "trace" in normalized:
            return "workflow_task"
        if "item" in normalized:
            return "item"
        return "workflow_task"

    def _feature_title(self, feature: str) -> str:
        normalized = feature.lower()
        if "hara" in normalized:
            return "Add hazard candidate"
        if "safety goal" in normalized:
            return "Add safety goal candidate"
        if normalized == "fsc" or "functional safety concept" in normalized:
            return "Add FSC improvement"
        if normalized == "tsc" or "technical safety concept" in normalized:
            return "Add TSC improvement"
        if "trace" in normalized:
            return "Add follow-up action"
        if "item" in normalized:
            return "Add item definition"
        return "Add follow-up action"
