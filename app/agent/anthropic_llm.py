"""
app/agent/anthropic_llm.py
─────────────────────────────────────────────────────────────────────────────
Anthropic Claude provider.

Config keys:
    LLM_API_KEY   — Anthropic API key (sk-ant-...)
    LLM_MODEL     — e.g. claude-sonnet-4-20250514
"""

from __future__ import annotations

import logging

from .base_llm import AbstractLLMClient, LLMError

logger = logging.getLogger(__name__)


class AnthropicClient(AbstractLLMClient):
    """Wraps the anthropic SDK."""

    def __init__(self, config: dict) -> None:
        super().__init__(config)
        self._client = None
        self.last_usage: dict[str, int] = {}

    @property
    def _sdk(self):
        if self._client is None:
            try:
                import anthropic
            except ImportError as exc:
                raise LLMError("anthropic SDK not installed: pip install anthropic") from exc
            self._client = anthropic.Anthropic(
                api_key=self.config["LLM_API_KEY"]
            )
        return self._client

    def complete(self, system: str, user: str, max_tokens: int | None = None) -> str:
        model = self.model or "claude-sonnet-4-20250514"
        logger.debug("Anthropic request: model=%s", model)
        try:
            msg = self._sdk.messages.create(
                model=model,
                max_tokens=int(max_tokens or self.config.get("LLM_MAX_OUTPUT_TOKENS", 8192)),
                temperature=float(self.config.get("LLM_TEMPERATURE", 0)),
                system=system,
                messages=[{"role": "user", "content": user}],
            )

            usage = getattr(msg, "usage", None)
            if usage is not None:
                input_tokens = int(getattr(usage, "input_tokens", 0) or 0)
                output_tokens = int(getattr(usage, "output_tokens", 0) or 0)
                self.last_usage = {
                    "prompt_tokens": input_tokens,
                    "completion_tokens": output_tokens,
                    "total_tokens": input_tokens + output_tokens,
                }
            else:
                self.last_usage = {}

            return msg.content[0].text
        except Exception as exc:
            raise LLMError(f"Anthropic API error: {exc}") from exc