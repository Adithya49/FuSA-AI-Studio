from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass

from fusa_ai_studio.core.config import EmbeddingConfig


@dataclass(frozen=True)
class EmbeddingResult:
    model: str
    vector: list[float]


class EmbeddingEngine:
    def __init__(self, config: EmbeddingConfig | None = None) -> None:
        self._sentence_models: dict[str, object] = {}
        self.config = config or EmbeddingConfig()

    def embed(self, text: str, model: str = "deterministic-hash-384") -> EmbeddingResult:
        if model.startswith("sentence-transformers/"):
            return EmbeddingResult(model, self._sentence_transformer(text, model.split("/", 1)[1]))
        if model.startswith("openai/"):
            return EmbeddingResult(model, self._openai(text, model.split("/", 1)[1]))
        return EmbeddingResult("deterministic-hash-384", self._deterministic_hash(text))

    def embed_many(self, texts: list[str], model: str) -> list[list[float]]:
        return [self.embed(text, model).vector for text in texts]

    def _deterministic_hash(self, text: str, dimensions: int = 384) -> list[float]:
        vector = [0.0] * dimensions
        tokens = re.findall(r"[A-Za-z0-9_+-]+", text.lower())
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            idx = int.from_bytes(digest[:4], "big") % dimensions
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[idx] += sign
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]

    def _sentence_transformer(self, text: str, name: str) -> list[float]:
        try:
            from sentence_transformers import SentenceTransformer
        except Exception:
            return self._deterministic_hash(text)
        if name not in self._sentence_models:
            self._sentence_models[name] = SentenceTransformer(name)
        model = self._sentence_models[name]
        vector = model.encode([text], normalize_embeddings=True)[0]
        return [float(value) for value in vector]

    def _openai(self, text: str, name: str) -> list[float]:
        api_key = self.config.openai.api_key
        if not api_key:
            return self._deterministic_hash(text)
        try:
            from openai import OpenAI

            client = OpenAI(api_key=api_key, base_url=self.config.openai.base_url or "https://api.openai.com/v1")
            response = client.embeddings.create(model=name, input=text)
            return [float(value) for value in response.data[0].embedding]
        except Exception:
            return self._deterministic_hash(text)
