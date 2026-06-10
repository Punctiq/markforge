"""
app/agent/openai_llm.py
─────────────────────────────────────────────────────────────────────────────
OpenAI-compatible provider — works with:
    - OpenAI            (LLM_BASE_URL not set)
    - Azure OpenAI      (LLM_BASE_URL=https://<resource>.openai.azure.com/)
    - Groq              (LLM_BASE_URL=https://api.groq.com/openai/v1)
    - Ollama            (LLM_BASE_URL=http://localhost:11434/v1)
    - LM Studio         (LLM_BASE_URL=http://localhost:1234/v1)
    - Any OpenAI-compat (LLM_BASE_URL=<endpoint>)

Config keys:
    LLM_API_KEY    — API key (use "ollama" for Ollama, any string for LM Studio)
    LLM_MODEL      — e.g. gpt-4o, llama3, mistral, gemma2
    LLM_BASE_URL   — optional custom endpoint
"""

from __future__ import annotations

import logging

from .base_llm import AbstractLLMClient, LLMError

logger = logging.getLogger(__name__)


class OpenAIClient(AbstractLLMClient):
    """Wraps the openai SDK with optional base_url override."""

    def __init__(self, config: dict) -> None:
        super().__init__(config)
        self._client = None
        self.last_usage: dict[str, int] = {}

    @property
    def _sdk(self):
        if self._client is None:
            try:
                from openai import OpenAI
            except ImportError as exc:
                raise LLMError("openai SDK not installed: pip install openai") from exc

            kwargs: dict = {"api_key": self.config.get("LLM_API_KEY", "ollama")}
            base_url = self.config.get("LLM_BASE_URL", "").strip()
            if base_url:
                kwargs["base_url"] = base_url

            self._client = OpenAI(**kwargs)
        return self._client

    def complete(self, system: str, user: str, max_tokens: int | None = None) -> str:
        model = self.model or "gpt-4o"
        logger.debug("OpenAI-compat request: model=%s base_url=%s",
                     model, self.config.get("LLM_BASE_URL", "default"))
        try:
            resp = self._sdk.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user",   "content": user},
                ],
                max_tokens=int(max_tokens or self.config.get("LLM_MAX_OUTPUT_TOKENS", 8192)),
                temperature=float(self.config.get("LLM_TEMPERATURE", 0)),
            )

            usage = getattr(resp, "usage", None)
            if usage is not None:
                self.last_usage = {
                    "prompt_tokens": int(getattr(usage, "prompt_tokens", 0) or 0),
                    "completion_tokens": int(getattr(usage, "completion_tokens", 0) or 0),
                    "total_tokens": int(getattr(usage, "total_tokens", 0) or 0),
                }
            else:
                self.last_usage = {}

            return resp.choices[0].message.content or ""
        except Exception as exc:
            raise LLMError(f"OpenAI-compat API error: {exc}") from exc