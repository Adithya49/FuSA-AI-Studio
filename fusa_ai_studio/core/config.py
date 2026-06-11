from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
try:
    from dotenv import load_dotenv

    load_dotenv(ROOT_DIR / ".env")
except Exception:
    pass


@dataclass(frozen=True)
class AppConfig:
    root_dir: Path = ROOT_DIR
    data_dir: Path = ROOT_DIR / "data"
    export_dir: Path = ROOT_DIR / "data" / "exports"
    db_path: Path = Path(os.getenv("FUSA_DB_PATH", str(ROOT_DIR / "data" / "fusa_ai_studio.db")))
    chroma_path: Path = Path(os.getenv("FUSA_CHROMA_PATH", str(ROOT_DIR / "data" / "chroma")))
    default_project_id: str = os.getenv("FUSA_DEFAULT_PROJECT", "demo-ev-inverter")
    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    lm_studio_base_url: str = os.getenv("LM_STUDIO_BASE_URL", "http://localhost:1234/v1")

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.export_dir.mkdir(parents=True, exist_ok=True)
        self.chroma_path.mkdir(parents=True, exist_ok=True)


def get_config() -> AppConfig:
    config = AppConfig()
    config.ensure_dirs()
    return config


def detect_llm_provider() -> str:
    explicit_provider = os.getenv("FUSA_LLM_PROVIDER", "").strip()
    if explicit_provider:
        return explicit_provider
    if os.getenv("GEMINI_API_KEY"):
        return "Gemini"
    if os.getenv("OPENAI_API_KEY"):
        return "OpenAI"
    if os.getenv("ANTHROPIC_API_KEY"):
        return "Claude"
    if os.getenv("OPENROUTER_API_KEY"):
        return "OpenRouter"
    return "Local"
