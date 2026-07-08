"""
app/config.py — Config class hierarchy Dev / Prod / Test.
"""

from __future__ import annotations

import os
from pathlib import Path


def _int_env(name: str, default: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


class BaseConfig:
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-secret-change-in-prod")
    JSON_SORT_KEYS: bool = False

    # File handling
    MAX_UPLOAD_SIZE_MB: int = int(os.getenv("MAX_UPLOAD_SIZE_MB", "50"))
    MAX_CONTENT_LENGTH: int = MAX_UPLOAD_SIZE_MB * 1024 * 1024
    UPLOAD_TEMP_DIR: Path = Path(os.getenv("UPLOAD_TEMP_DIR", "/tmp/markforge"))
    ALLOWED_EXTENSIONS: frozenset[str] = frozenset({".docx", ".pdf", ".odt", ".doc"})

    # ── LLM — provider-agnostic ─────────────────────────────────────────────
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "")        # anthropic | openai | groq | ollama | ...
    LLM_API_KEY:  str = os.getenv("LLM_API_KEY", "")         # provider API key
    LLM_MODEL:    str = os.getenv("LLM_MODEL", "")           # model name
    LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", "")        # optional — Azure / Groq / Ollama endpoint

    # LLM output limits
    # General cleanup can still use a larger completion budget, while
    # quality audit uses a smaller budget to avoid context overflow.
    LLM_MAX_OUTPUT_TOKENS: int = _int_env("LLM_MAX_OUTPUT_TOKENS", 8192)
    LLM_CLEANUP_CONTEXT_WINDOW_TOKENS: int = _int_env("LLM_CLEANUP_CONTEXT_WINDOW_TOKENS", 32000)
    AI_QUALITY_MAX_OUTPUT_TOKENS: int = int(os.getenv("AI_QUALITY_MAX_OUTPUT_TOKENS", "2048"))
    AI_QUALITY_SAFE_INPUT_TOKENS: int = int(os.getenv("AI_QUALITY_SAFE_INPUT_TOKENS", "24000"))
    AI_QUALITY_SAMPLE_CHARS: int = int(os.getenv("AI_QUALITY_SAMPLE_CHARS", "16000"))

    # Conversion backends
    PANDOC_BIN:      str = os.getenv("PANDOC_BIN", "pandoc")
    LIBREOFFICE_BIN: str = os.getenv("LIBREOFFICE_BIN", "soffice")

    # Rate limiting
    RATELIMIT_DEFAULT:     str = os.getenv("RATELIMIT_DEFAULT", "60 per minute")
    RATELIMIT_STORAGE_URI: str = "memory://"

    # CORS
    CORS_ORIGINS: list[str] = os.getenv(
        "CORS_ORIGINS", "http://localhost:5173,http://localhost:3000"
    ).split(",")


class DevelopmentConfig(BaseConfig):
    DEBUG: bool = True
    TESTING: bool = False


class ProductionConfig(BaseConfig):
    DEBUG: bool = False
    TESTING: bool = False
    SECRET_KEY: str = os.getenv("SECRET_KEY", "")


class TestingConfig(BaseConfig):
    DEBUG: bool = True
    TESTING: bool = True
    UPLOAD_TEMP_DIR: Path = Path("/tmp/markforge-test")
    RATELIMIT_ENABLED: bool = False
    LLM_API_KEY: str = "test-key"


config_by_name: dict[str, type[BaseConfig]] = {
    "development": DevelopmentConfig,
    "production":  ProductionConfig,
    "testing":     TestingConfig,
}