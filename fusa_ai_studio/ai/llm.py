from __future__ import annotations

import json
import time
from dataclasses import dataclass, replace

from fusa_ai_studio.core.config import LLMConfig
from fusa_ai_studio import logging_config

logger = logging_config.get_logger(__name__)


LOCAL_MODEL_NAME = "fusa-local-deterministic"


@dataclass(frozen=True)
class LLMResponse:
    provider: str
    model: str
    text: str
    warning: str = ""
    tokens_in: int | None = None
    tokens_out: int | None = None
    tokens_total: int | None = None
    latency_seconds: float | None = None
    gpu: str = ""


class LLMClient:
    def __init__(self, config: LLMConfig | None = None) -> None:
        self.config = config or LLMConfig()

    def generate(self, prompt: str, provider: str, model: str) -> LLMResponse:
        start = time.perf_counter()
        provider_key = provider.lower()
        try:
            if provider_key == "openai":
                result = self._openai(prompt, model)
            elif provider_key == "claude":
                result = self._claude(prompt, model)
            elif provider_key == "gemini":
                result = self._gemini(prompt, model)
            elif provider_key == "ollama":
                result = self._ollama(prompt, model)
            elif provider_key == "lm studio":
                selected = self._model(model, self.config.lm_studio.model or self.config.local_model)
                result = self._openai_compatible(
                    selected,
                    prompt,
                    self.config.lm_studio.base_url or "http://localhost:1234/v1",
                    self.config.lm_studio.api_key or "lm-studio",
                    "LM Studio",
                )
            elif provider_key == "openrouter":
                result = self._openrouter(prompt, model)
            else:
                selected = self._model(model, self.config.local_model)
                result = LLMResponse("Local", selected, self._local_response(prompt))
        except Exception as exc:
            latency = time.perf_counter() - start
            logger.exception("LLM generate failed")
            return replace(
                LLMResponse(provider, model, self._local_response(prompt, f"Provider call failed: {exc}"), warning=str(exc)),
                latency_seconds=latency,
            )

        latency = time.perf_counter() - start
        if isinstance(result, LLMResponse) and result.latency_seconds is None:
            result = replace(result, latency_seconds=latency)
        return result

    def _openai(self, prompt: str, model: str) -> LLMResponse:
        from openai import OpenAI

        selected = self._model(model, self.config.openai.model or "gpt-4o-mini")
        client = OpenAI(api_key=self.config.openai.api_key, base_url=self.config.openai.base_url or "https://api.openai.com/v1")
        response = client.chat.completions.create(model=selected, messages=[{"role": "user", "content": prompt}], temperature=0.2)
        usage = getattr(response, "usage", None)
        tokens_in = getattr(usage, "prompt_tokens", None) if usage is not None else None
        tokens_out = getattr(usage, "completion_tokens", None) if usage is not None else None
        tokens_total = getattr(usage, "total_tokens", None) if usage is not None else None
        return LLMResponse("OpenAI", selected, response.choices[0].message.content or "", tokens_in=tokens_in, tokens_out=tokens_out, tokens_total=tokens_total)

    def _claude(self, prompt: str, model: str) -> LLMResponse:
        import anthropic

        selected = self._model(model, self.config.claude.model or "claude-3-5-sonnet-latest")
        client = anthropic.Anthropic(api_key=self.config.claude.api_key, base_url=self.config.claude.base_url or "https://api.anthropic.com")
        response = client.messages.create(model=selected, max_tokens=1400, temperature=0.2, messages=[{"role": "user", "content": prompt}])
        text = "\n".join(block.text for block in response.content if getattr(block, "type", "") == "text")
        usage = getattr(response, "usage", None)
        tokens_in = getattr(usage, "prompt_tokens", None) if usage is not None else None
        tokens_out = getattr(usage, "completion_tokens", None) if usage is not None else None
        tokens_total = getattr(usage, "total_tokens", None) if usage is not None else None
        return LLMResponse("Claude", selected, text, tokens_in=tokens_in, tokens_out=tokens_out, tokens_total=tokens_total)

    def _gemini(self, prompt: str, model: str) -> LLMResponse:
        from google import genai

        selected = self._model(model, self.config.gemini.model or "gemini-2.5-flash")
        client = genai.Client(api_key=self.config.gemini.api_key)
        response = client.models.generate_content(model=selected, contents=prompt)
        tokens_in = getattr(response, "request_tokens", None) or getattr(response, "prompt_tokens", None)
        tokens_out = getattr(response, "response_tokens", None) or getattr(response, "completion_tokens", None)
        tokens_total = getattr(response, "total_tokens", None)
        return LLMResponse("Gemini", selected, response.text or "", tokens_in=tokens_in, tokens_out=tokens_out, tokens_total=tokens_total)

    def _ollama(self, prompt: str, model: str) -> LLMResponse:
        import requests

        base_url = (self.config.ollama.base_url or "http://localhost:11434").rstrip("/")
        selected = self._model(model, self.config.ollama.model or "llama3.1")
        response = requests.post(f"{base_url}/api/generate", json={"model": selected, "prompt": prompt, "stream": False}, timeout=self._timeout())
        response.raise_for_status()
        payload = response.json()
        tokens_total = payload.get("usage", {}).get("total_tokens") if isinstance(payload.get("usage"), dict) else None
        return LLMResponse("Ollama", selected, payload.get("response", ""), tokens_total=tokens_total)

    def _openrouter(self, prompt: str, model: str) -> LLMResponse:
        selected = self._model(model, self.config.openrouter.model or "openai/gpt-4o-mini")
        return self._openai_compatible(selected, prompt, self.config.openrouter.base_url or "https://openrouter.ai/api/v1", self.config.openrouter.api_key, "OpenRouter")

    def _openai_compatible(self, model: str, prompt: str, base_url: str, api_key: str, provider: str) -> LLMResponse:
        from openai import OpenAI

        client = OpenAI(api_key=api_key or "lm-studio", base_url=base_url)
        response = client.chat.completions.create(model=model, messages=[{"role": "user", "content": prompt}], temperature=0.2)
        usage = getattr(response, "usage", None)
        tokens_in = getattr(usage, "prompt_tokens", None) if usage is not None else None
        tokens_out = getattr(usage, "completion_tokens", None) if usage is not None else None
        tokens_total = getattr(usage, "total_tokens", None) if usage is not None else None
        gpu = ""
        try:
            if provider.lower() == "lm studio":
                gpu = self._query_lm_studio_gpu(base_url, api_key)
        except Exception:
            logger.exception("Failed to query LM Studio GPU status")
            gpu = ""
        return LLMResponse(provider, model, response.choices[0].message.content or "", tokens_in=tokens_in, tokens_out=tokens_out, tokens_total=tokens_total, gpu=gpu)

    def _model(self, configured: str, default: str) -> str:
        if configured and configured != self.config.local_model:
            return configured
        return default

    def _timeout(self) -> int:
        return self.config.timeout_seconds

    def _query_lm_studio_gpu(self, base_url: str, api_key: str) -> str:
        import requests

        status_url = f"{base_url.rstrip('/')}/api/status"
        response = requests.get(status_url, headers={"Authorization": f"Bearer {api_key}"}, timeout=self._timeout())
        response.raise_for_status()
        payload = response.json()
        gpu_info = payload.get("gpu", {})
        if isinstance(gpu_info, dict):
            name = gpu_info.get("name") or "GPU"
            memory = gpu_info.get("memory_used")
            memory_total = gpu_info.get("memory_total")
            utilization = gpu_info.get("utilization")
            parts = []
            if memory is not None and memory_total is not None:
                parts.append(f"{memory} / {memory_total} GB")
            elif memory is not None:
                parts.append(f"{memory} GB")
            if utilization is not None:
                parts.append(f"{utilization}%")
            if parts:
                return f"{name} @ {' · '.join(parts)}"
        return ""

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
