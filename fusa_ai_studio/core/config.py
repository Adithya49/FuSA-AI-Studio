from __future__ import annotations

import json
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT_DIR / "config.json"


def _resolve_path(base_dir: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else base_dir / path


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


@dataclass(frozen=True)
class ProviderConfig:
    api_key: str = ""
    base_url: str = ""
    model: str = ""


@dataclass(frozen=True)
class LLMConfig:
    provider: str = "Local"
    model: str = "fusa-local-deterministic"
    timeout_seconds: int = 120
    local_model: str = "fusa-local-deterministic"
    openai: ProviderConfig = field(default_factory=lambda: ProviderConfig(base_url="https://api.openai.com/v1", model="gpt-4o-mini"))
    claude: ProviderConfig = field(default_factory=lambda: ProviderConfig(base_url="https://api.anthropic.com", model="claude-3-5-sonnet-latest"))
    gemini: ProviderConfig = field(default_factory=lambda: ProviderConfig(model="gemini-2.5-flash"))
    ollama: ProviderConfig = field(default_factory=lambda: ProviderConfig(base_url="http://localhost:11434", model="llama3.1"))
    openrouter: ProviderConfig = field(default_factory=lambda: ProviderConfig(base_url="https://openrouter.ai/api/v1", model="openai/gpt-4o-mini"))
    lm_studio: ProviderConfig = field(default_factory=lambda: ProviderConfig(api_key="lm-studio", base_url="http://localhost:1234/v1", model="local-model"))

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LLMConfig:
        def provider(name: str, default: ProviderConfig) -> ProviderConfig:
            values = data.get(name, {}) if isinstance(data.get(name, {}), dict) else {}
            return ProviderConfig(
                api_key=str(values.get("api_key", default.api_key)),
                base_url=str(values.get("base_url", default.base_url)),
                model=str(values.get("model", default.model)),
            )

        return cls(
            provider=str(data.get("provider", cls().provider)),
            model=str(data.get("model", cls().model)),
            timeout_seconds=int(data.get("timeout_seconds", cls().timeout_seconds)),
            local_model=str(data.get("local_model", cls().local_model)),
            openai=provider("openai", cls().openai),
            claude=provider("claude", cls().claude),
            gemini=provider("gemini", cls().gemini),
            ollama=provider("ollama", cls().ollama),
            openrouter=provider("openrouter", cls().openrouter),
            lm_studio=provider("lm_studio", cls().lm_studio),
        )


@dataclass(frozen=True)
class EmbeddingConfig:
    model: str = "deterministic-hash-384"
    openai: ProviderConfig = field(default_factory=lambda: ProviderConfig(api_key="", base_url="https://api.openai.com/v1", model="text-embedding-3-small"))

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EmbeddingConfig:
        values = data.get("openai", {}) if isinstance(data.get("openai", {}), dict) else {}
        return cls(
            model=str(data.get("model", cls().model)),
            openai=ProviderConfig(
                api_key=str(values.get("api_key", cls().openai.api_key)),
                base_url=str(values.get("base_url", cls().openai.base_url)),
                model=str(values.get("model", cls().openai.model)),
            ),
        )


@dataclass(frozen=True)
class AppConfig:
    root_dir: Path = ROOT_DIR
    config_path: Path = CONFIG_PATH
    data_dir: Path = ROOT_DIR / "data"
    export_dir: Path = ROOT_DIR / "data" / "exports"
    db_path: Path = ROOT_DIR / "data" / "fusa_ai_studio.db"
    chroma_path: Path = ROOT_DIR / "data" / "chroma"
    default_project_id: str = "demo-ev-inverter"
    vector_backend: str = "ChromaDB"
    embedding_model: str = "deterministic-hash-384"
    chunking_strategy: str = "section"
    llm: LLMConfig = field(default_factory=LLMConfig)
    embeddings: EmbeddingConfig = field(default_factory=EmbeddingConfig)

    @classmethod
    def from_file(cls, path: Path = CONFIG_PATH) -> AppConfig:
        payload = _load_json(path)
        paths = payload.get("paths", {}) if isinstance(payload.get("paths", {}), dict) else {}
        defaults = payload.get("defaults", {}) if isinstance(payload.get("defaults", {}), dict) else {}
        llm = LLMConfig.from_dict(payload.get("llm", {}) if isinstance(payload.get("llm", {}), dict) else {})
        embeddings = EmbeddingConfig.from_dict(payload.get("embeddings", {}) if isinstance(payload.get("embeddings", {}), dict) else {})
        return cls(
            config_path=path,
            data_dir=_resolve_path(ROOT_DIR, str(paths.get("data_dir", "data"))),
            export_dir=_resolve_path(ROOT_DIR, str(paths.get("export_dir", "data/exports"))),
            db_path=_resolve_path(ROOT_DIR, str(paths.get("db_path", "data/fusa_ai_studio.db"))),
            chroma_path=_resolve_path(ROOT_DIR, str(paths.get("chroma_path", "data/chroma"))),
            default_project_id=str(defaults.get("project_id", cls().default_project_id)),
            vector_backend=str(defaults.get("vector_backend", cls().vector_backend)),
            embedding_model=str(defaults.get("embedding_model", cls().embedding_model)),
            chunking_strategy=str(defaults.get("chunking_strategy", cls().chunking_strategy)),
            llm=llm,
            embeddings=embeddings,
        )

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.export_dir.mkdir(parents=True, exist_ok=True)
        self.chroma_path.mkdir(parents=True, exist_ok=True)


def get_config() -> AppConfig:
    config = AppConfig.from_file()
    config.ensure_dirs()
    return config


def detect_llm_provider() -> str:
    return get_config().llm.provider
