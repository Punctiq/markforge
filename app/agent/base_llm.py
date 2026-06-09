"""
app/agent/base_llm.py
─────────────────────────────────────────────────────────────────────────────
Abstract LLM client. Every provider implementation must subclass this.

The interface is intentionally minimal — one method: complete().
All provider-specific auth, retries, and SDK details stay inside
the concrete implementation; the rest of the codebase never sees them.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class AbstractLLMClient(ABC):
    """Common interface for all LLM providers."""

    def __init__(self, config: dict) -> None:
        self.config = config

    @abstractmethod
    def complete(self, system: str, user: str) -> str:
        """Send a system + user prompt and return the model's text response.

        Args:
            system: System prompt string.
            user:   User message string.

        Returns:
            The model's text response as a plain string.

        Raises:
            LLMError: On any unrecoverable API or network error.
        """
        ...

    @property
    def model(self) -> str:
        return self.config.get("LLM_MODEL", "")


class LLMError(Exception):
    """Raised when an LLM provider call fails unrecoverably."""