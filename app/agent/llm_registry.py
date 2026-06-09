"""
app/agent/llm_registry.py
─────────────────────────────────────────────────────────────────────────────
Returns the correct LLM client based on LLM_PROVIDER in config.

Supported values for LLM_PROVIDER:
    anthropic           → AnthropicClient
    openai              → OpenAIClient (api.openai.com)
    azure               → OpenAIClient + LLM_BASE_URL
    groq                → OpenAIClient + LLM_BASE_URL=https://api.groq.com/openai/v1
    ollama              → OpenAIClient + LLM_BASE_URL=http://localhost:11434/v1
    lmstudio            → OpenAIClient + LLM_BASE_URL=http://localhost:1234/v1
    openai-compatible   → OpenAIClient + LLM_BASE_URL (custom)
"""

from __future__ import annotations

import logging

from .base_llm import AbstractLLMClient, LLMError

logger = logging.getLogger(__name__)

# Providers that auto-set base_url if not explicitly provided
_AUTO_BASE_URLS: dict[str, str] = {
    "groq":     "https://api.groq.com/openai/v1",
    "ollama":   "http://localhost:11434/v1",
    "lmstudio": "http://localhost:1234/v1",
}

# Providers that use the OpenAI-compatible SDK
_OPENAI_COMPAT = {"openai", "azure", "groq", "ollama", "lmstudio", "openai-compatible"}


def get_llm_client(config: dict) -> AbstractLLMClient:
    """Instantiate and return the appropriate LLM client.

    Args:
        config: Flask app.config dict. Must contain LLM_PROVIDER and LLM_API_KEY.

    Returns:
        A concrete AbstractLLMClient ready to call .complete() on.

    Raises:
        LLMError: If LLM_PROVIDER is missing or unknown.
    """
    provider = config.get("LLM_PROVIDER", "").lower().strip()

    if not provider:
        raise LLMError(
            "LLM_PROVIDER is not set. "
            "Add it to .env: anthropic | openai | groq | ollama | lmstudio | azure"
        )

    # Inject auto base_url for known shorthand providers
    if provider in _AUTO_BASE_URLS and not config.get("LLM_BASE_URL", "").strip():
        config = {**config, "LLM_BASE_URL": _AUTO_BASE_URLS[provider]}
        logger.debug("Auto base_url for %s: %s", provider, config["LLM_BASE_URL"])

    if provider == "anthropic":
        from .anthropic_llm import AnthropicClient
        return AnthropicClient(config)

    if provider in _OPENAI_COMPAT:
        from .openai_llm import OpenAIClient
        return OpenAIClient(config)

    raise LLMError(
        f"Unknown LLM_PROVIDER '{provider}'. "
        f"Supported: anthropic, openai, azure, groq, ollama, lmstudio, openai-compatible"
    )