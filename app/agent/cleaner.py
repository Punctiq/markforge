"""
app/agent/cleaner.py
─────────────────────────────────────────────────────────────────────────────
AI cleanup pass — provider-agnostic.

Safety rules:
- Small documents can be cleaned in one LLM call.
- Large documents are cleaned in conservative chunks, not skipped entirely.
- The AI output is never trusted blindly. If a chunk is malformed, truncated,
  too short, missing image references, or missing the expected fixes JSON block,
  MarkForge keeps the original chunk.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any

from .base_llm import LLMError
from .llm_registry import get_llm_client
from .prompts import CLEANUP_USER, get_cleanup_system_prompt

logger = logging.getLogger(__name__)

DEFAULT_MAX_CHARS_FOR_FULL_AI_CLEANUP = 25_000
ALLOWED_CLEANUP_MODES = {"safe", "balanced", "aggressive"}

MODE_CONFIG = {
    "safe": {
        "min_word_retention_ratio_full": 0.92,
        "min_word_retention_ratio_chunk": 0.90,
        "max_chunk_chars": 10_000,
        "temperature": 0,
    },
    "balanced": {
        "min_word_retention_ratio_full": 0.90,
        "min_word_retention_ratio_chunk": 0.87,
        "max_chunk_chars": 12_000,
        "temperature": 0,
    },
    "aggressive": {
        "min_word_retention_ratio_full": 0.85,
        "min_word_retention_ratio_chunk": 0.80,
        "max_chunk_chars": 15_000,
        "temperature": 0,
    },
}




def _empty_token_usage() -> dict[str, int]:
    return {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "llm_calls": 0,
    }


def _get_last_token_usage(client: Any) -> dict[str, int]:
    usage = getattr(client, "last_usage", {}) or {}
    prompt_tokens = int(usage.get("prompt_tokens", 0) or 0)
    completion_tokens = int(usage.get("completion_tokens", 0) or 0)
    total_tokens = int(usage.get("total_tokens", 0) or 0)

    if total_tokens == 0 and (prompt_tokens or completion_tokens):
        total_tokens = prompt_tokens + completion_tokens

    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "llm_calls": 1 if total_tokens or prompt_tokens or completion_tokens else 0,
    }


def _add_token_usage(total: dict[str, int], item: dict[str, int]) -> dict[str, int]:
    for key in ("prompt_tokens", "completion_tokens", "total_tokens", "llm_calls"):
        total[key] = int(total.get(key, 0) or 0) + int(item.get(key, 0) or 0)
    return total

@dataclass
class CleanerResult:
    markdown: str
    fixes: list[str] = field(default_factory=list)
    ai_applied: bool = True
    token_usage: dict[str, int] = field(default_factory=dict)


@dataclass
class _ParsedCleanup:
    markdown: str
    fixes: list[str]
    ok: bool
    message: str = ""


class MarkdownCleaner:
    def __init__(self, config: dict, mode: str = "safe") -> None:
        self.config = config
        self.mode = (mode or "safe").strip().lower()
        if self.mode not in ALLOWED_CLEANUP_MODES:
            logger.warning("Unsupported AI cleanup mode '%s'; falling back to safe.", self.mode)
            self.mode = "safe"
        self.mode_config = MODE_CONFIG[self.mode]
        self.system_prompt = get_cleanup_system_prompt(self.mode)

    def clean(self, markdown: str) -> CleanerResult:
        if not self.config.get("LLM_API_KEY"):
            logger.warning("LLM_API_KEY not set — skipping AI cleanup.")
            return CleanerResult(markdown=markdown, fixes=[], ai_applied=False, token_usage=_empty_token_usage())

        try:
            client = get_llm_client(self.config)
        except LLMError as exc:
            logger.warning("LLM client init failed: %s — skipping cleanup.", exc)
            return CleanerResult(markdown=markdown, fixes=[], ai_applied=False, token_usage=_empty_token_usage())

        max_full_chars = int(
            self.config.get(
                "LLM_MAX_MARKDOWN_CHARS_FOR_FULL_CLEANUP",
                DEFAULT_MAX_CHARS_FOR_FULL_AI_CLEANUP,
            )
        )

        if len(markdown) <= max_full_chars:
            return self._clean_full_document(client=client, markdown=markdown)

        return self._clean_large_document(client=client, markdown=markdown)

    def _min_word_retention_ratio(self, full_document: bool) -> float:
        key = "min_word_retention_ratio_full" if full_document else "min_word_retention_ratio_chunk"
        return float(self.mode_config[key])

    def _max_chunk_chars(self) -> int:
        return int(
            self.config.get(
                "LLM_MAX_MARKDOWN_CHARS_PER_CHUNK",
                self.mode_config["max_chunk_chars"],
            )
        )

    def _clean_full_document(self, client: Any, markdown: str) -> CleanerResult:
        prompt = CLEANUP_USER.format(markdown=markdown)
        token_usage = _empty_token_usage()

        try:
            raw = client.complete(system=self.system_prompt, user=prompt)
            token_usage = _get_last_token_usage(client)
        except LLMError as exc:
            logger.error("LLM call failed: %s", exc)
            return CleanerResult(
                markdown=markdown,
                fixes=[],
                ai_applied=False,
                token_usage=token_usage,
            )

        parsed = _parse_response(
            raw=raw,
            original_markdown=markdown,
            min_word_retention_ratio=self._min_word_retention_ratio(full_document=True),
        )

        if not parsed.ok:
            logger.warning("AI cleanup discarded: %s", parsed.message)
            return CleanerResult(
                markdown=markdown,
                fixes=[parsed.message],
                ai_applied=False,
                token_usage=token_usage,
            )

        return CleanerResult(
            markdown=parsed.markdown,
            fixes=parsed.fixes,
            ai_applied=True,
            token_usage=token_usage,
        )


    def _clean_large_document(self, client: Any, markdown: str) -> CleanerResult:
        max_chunk_chars = self._max_chunk_chars()

        chunks = _split_markdown_into_chunks(markdown, max_chunk_chars=max_chunk_chars)
        logger.warning(
            "AI cleanup using %s chunked mode: document has %d chars, split into %d chunks.",
            self.mode,
            len(markdown),
            len(chunks),
        )

        cleaned_chunks: list[str] = []
        fixes: list[str] = []
        token_usage_total = _empty_token_usage()
        applied_chunks = 0

        for idx, chunk in enumerate(chunks, start=1):
            prompt = CLEANUP_USER.format(markdown=chunk)

            try:
                raw = client.complete(system=self.system_prompt, user=prompt)
                _add_token_usage(token_usage_total, _get_last_token_usage(client))
            except LLMError as exc:
                msg = f"AI cleanup chunk {idx}/{len(chunks)} failed: {exc}; original chunk kept."
                logger.error(msg)
                cleaned_chunks.append(chunk)
                fixes.append(msg)
                continue

            parsed = _parse_response(
                raw=raw,
                original_markdown=chunk,
                min_word_retention_ratio=self._min_word_retention_ratio(full_document=False),
            )

            if not parsed.ok:
                msg = f"AI cleanup chunk {idx}/{len(chunks)} discarded: {parsed.message}; original chunk kept."
                logger.warning(msg)
                cleaned_chunks.append(chunk)
                fixes.append(msg)
                continue

            cleaned_chunks.append(parsed.markdown)
            applied_chunks += 1

            if parsed.fixes:
                fixes.extend([f"chunk {idx}: {fix}" for fix in parsed.fixes])

        final_markdown = "\n\n".join(part.strip() for part in cleaned_chunks if part.strip()).strip()

        whole_doc_check = _validate_cleaned_markdown(
            original_markdown=markdown,
            cleaned_markdown=final_markdown,
            min_word_retention_ratio=self._min_word_retention_ratio(full_document=False),
        )

        if not whole_doc_check.ok:
            msg = f"AI chunked cleanup discarded: {whole_doc_check.message}"
            logger.warning(msg)
            return CleanerResult(markdown=markdown, fixes=[msg], ai_applied=False, token_usage=token_usage_total)

        if applied_chunks == 0:
            msg = "AI chunked cleanup did not safely apply to any chunk; original markdown kept."
            logger.warning(msg)
            return CleanerResult(markdown=markdown, fixes=[msg], ai_applied=False, token_usage=token_usage_total)

        fixes.insert(0, f"AI cleanup applied in {self.mode} chunked mode ({applied_chunks}/{len(chunks)} chunks).")
        return CleanerResult(markdown=final_markdown, fixes=fixes, ai_applied=True, token_usage=token_usage_total)


_JSON_FENCE_RE = re.compile(r"```json\s*(\{.*?\})\s*```", re.DOTALL | re.IGNORECASE)
_MD_FENCE_OPEN_RE = re.compile(r"^\s*```(?:markdown|md)?\s*\n", re.IGNORECASE)
_MD_FENCE_CLOSE_RE = re.compile(r"\n```\s*$")
_HEADING_RE = re.compile(r"(?m)^(#{1,6}\s+.+)$")
_IMAGE_RE = re.compile(r"!\[[^\]]*\]\([^)]+\)")


def _parse_response(raw: str, original_markdown: str, min_word_retention_ratio: float) -> _ParsedCleanup:
    """Parse and validate LLM cleanup response.

    Expected response:
        cleaned markdown
        ```json
        {"fixes": [...]}
        ```

    If invalid, return ok=False. The caller will keep the original Markdown.
    """
    text = raw.strip()
    json_blocks = list(_JSON_FENCE_RE.finditer(text))

    if not json_blocks:
        return _ParsedCleanup(
            markdown=original_markdown,
            fixes=[],
            ok=False,
            message="missing fixes JSON block; response may be truncated",
        )

    last_json_block = json_blocks[-1]
    json_text = last_json_block.group(1)
    cleaned = text[: last_json_block.start()].strip()
    cleaned = _strip_markdown_fence(cleaned)

    try:
        meta = json.loads(json_text)
        fixes_raw = meta.get("fixes", [])
        fixes = [str(item) for item in fixes_raw] if isinstance(fixes_raw, list) else []
    except json.JSONDecodeError as exc:
        return _ParsedCleanup(
            markdown=original_markdown,
            fixes=[],
            ok=False,
            message=f"invalid fixes JSON block: {exc}",
        )

    validation = _validate_cleaned_markdown(
        original_markdown=original_markdown,
        cleaned_markdown=cleaned,
        min_word_retention_ratio=min_word_retention_ratio,
    )

    if not validation.ok:
        return _ParsedCleanup(
            markdown=original_markdown,
            fixes=fixes,
            ok=False,
            message=validation.message,
        )

    return _ParsedCleanup(markdown=cleaned, fixes=fixes, ok=True)


def _validate_cleaned_markdown(
    original_markdown: str,
    cleaned_markdown: str,
    min_word_retention_ratio: float,
) -> _ParsedCleanup:
    original = original_markdown.strip()
    cleaned = cleaned_markdown.strip()

    if not cleaned:
        return _ParsedCleanup(markdown=original, fixes=[], ok=False, message="empty cleaned markdown")

    original_words = max(1, len(original.split()))
    cleaned_words = len(cleaned.split())
    ratio = cleaned_words / original_words

    if ratio < min_word_retention_ratio:
        return _ParsedCleanup(
            markdown=original,
            fixes=[],
            ok=False,
            message=(
                f"cleaned output retained only {ratio:.0%} "
                f"of original word count ({cleaned_words}/{original_words})"
            ),
        )

    original_images = _extract_markdown_images(original)
    cleaned_images = _extract_markdown_images(cleaned)

    if original_images != cleaned_images:
        return _ParsedCleanup(
            markdown=original,
            fixes=[],
            ok=False,
            message="image references changed, disappeared, or were reordered",
        )

    # The parser has already removed the final JSON block. Any remaining code
    # fences must be balanced.
    if cleaned.count("```") % 2 != 0:
        return _ParsedCleanup(
            markdown=original,
            fixes=[],
            ok=False,
            message="unbalanced Markdown code fences",
        )

    original_headings = _extract_headings(original)
    cleaned_headings = _extract_headings(cleaned)

    if original_headings and len(cleaned_headings) < len(original_headings) * 0.80:
        return _ParsedCleanup(
            markdown=original,
            fixes=[],
            ok=False,
            message="too many headings were removed",
        )

    return _ParsedCleanup(markdown=cleaned, fixes=[], ok=True)


def _extract_markdown_images(markdown: str) -> list[str]:
    return _IMAGE_RE.findall(markdown)


def _extract_headings(markdown: str) -> list[str]:
    headings: list[str] = []
    for line in markdown.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            headings.append(stripped)
    return headings


def _strip_markdown_fence(text: str) -> str:
    text = _MD_FENCE_OPEN_RE.sub("", text.strip())
    text = _MD_FENCE_CLOSE_RE.sub("", text.strip())
    return text.strip()


def _split_markdown_into_chunks(markdown: str, max_chunk_chars: int) -> list[str]:
    """Split Markdown into conservative chunks.

    Prefer splitting at headings. If a single section is too large, split at
    paragraph boundaries. If a paragraph is still too large, split at line
    boundaries. This avoids cutting most tables, image blocks, and captions.
    """
    markdown = markdown.strip()
    if len(markdown) <= max_chunk_chars:
        return [markdown]

    matches = list(_HEADING_RE.finditer(markdown))
    sections: list[str] = []

    if not matches:
        sections = _split_large_block(markdown, max_chunk_chars=max_chunk_chars)
    else:
        if matches[0].start() > 0:
            preface = markdown[: matches[0].start()].strip()
            if preface:
                sections.append(preface)

        for i, match in enumerate(matches):
            start = match.start()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(markdown)
            section = markdown[start:end].strip()
            if not section:
                continue

            if len(section) > max_chunk_chars:
                sections.extend(_split_large_block(section, max_chunk_chars=max_chunk_chars))
            else:
                sections.append(section)

    chunks: list[str] = []
    current = ""

    for section in sections:
        if not current:
            current = section
            continue

        if len(current) + len(section) + 2 <= max_chunk_chars:
            current = f"{current}\n\n{section}"
        else:
            chunks.append(current.strip())
            current = section

    if current.strip():
        chunks.append(current.strip())

    return chunks or [markdown]


def _split_large_block(text: str, max_chunk_chars: int) -> list[str]:
    paragraphs = re.split(r"\n\s*\n", text.strip())
    chunks: list[str] = []
    current = ""

    for paragraph in paragraphs:
        paragraph = paragraph.strip()
        if not paragraph:
            continue

        if len(paragraph) > max_chunk_chars:
            if current.strip():
                chunks.append(current.strip())
                current = ""
            chunks.extend(_split_very_large_paragraph(paragraph, max_chunk_chars=max_chunk_chars))
            continue

        if not current:
            current = paragraph
        elif len(current) + len(paragraph) + 2 <= max_chunk_chars:
            current = f"{current}\n\n{paragraph}"
        else:
            chunks.append(current.strip())
            current = paragraph

    if current.strip():
        chunks.append(current.strip())

    return chunks


def _split_very_large_paragraph(text: str, max_chunk_chars: int) -> list[str]:
    lines = text.splitlines()
    chunks: list[str] = []
    current = ""

    for line in lines:
        if not current:
            current = line
        elif len(current) + len(line) + 1 <= max_chunk_chars:
            current = f"{current}\n{line}"
        else:
            chunks.append(current.strip())
            current = line

    if current.strip():
        chunks.append(current.strip())

    return chunks
