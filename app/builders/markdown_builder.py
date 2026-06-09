"""
app/builders/markdown_builder.py
─────────────────────────────────────────────────────────────────────────────
Assembles final Markdown document.

Important:
- DOCX images are inserted by the converter at their original positions.
- This builder no longer blindly appends every image at the end.
- It only appends an "Unreferenced figures" section for images that exist in
  the ZIP but were not referenced in the Markdown body.
"""

from __future__ import annotations

import re
from typing import Any


_MD_FENCE_OPEN_RE = re.compile(r"^\s*```(?:markdown|md)?\s*\n", re.IGNORECASE)
_MD_FENCE_CLOSE_RE = re.compile(r"\n```\s*$")


def build_markdown(
    body: str,
    frontmatter: str,
    result: Any,
) -> str:
    body = _strip_markdown_fence(body).strip()
    frontmatter = frontmatter.strip()

    parts = [
        frontmatter,
        "",
        _build_llm_hint(result),
        "",
        body,
    ]

    unreferenced = _build_unreferenced_figures_block(body, result)
    if unreferenced:
        parts.extend(["", unreferenced])

    return "\n".join(parts).strip() + "\n"


def _build_llm_hint(result: Any) -> str:
    parts = [
        "<!-- markforge:llm-hint",
        f"Document type: {result.doc_type_label} ({result.doc_type_code})",
        f"Language: {result.language}",
        f"Estimated pages: {result.estimated_pages}",
        f"Word count: {result.word_count}",
        f"Tables: {result.table_count}",
        f"Figures: {result.figure_count}",
    ]

    if getattr(result, "sections", None):
        parts.append("Main sections: " + ", ".join(result.sections[:10]))

    parts.append("Technical or business document.")
    parts.append("markforge:llm-hint -->")

    return "\n".join(parts)


def _build_unreferenced_figures_block(body: str, result: Any) -> str:
    figures = getattr(result, "figures", None) or []
    if not figures:
        return ""

    referenced = set(re.findall(r"figures/([^\)\s]+)", body))
    missing = [fig for fig in figures if fig.filename not in referenced]

    if not missing:
        return ""

    lines = ["## Unreferenced figures", ""]
    for fig in missing:
        caption = fig.caption or f"Figure {fig.index}"
        lines.append(f"![{caption}](figures/{fig.filename})")

    return "\n".join(lines)


def _strip_markdown_fence(text: str) -> str:
    text = _MD_FENCE_OPEN_RE.sub("", text.strip())
    text = _MD_FENCE_CLOSE_RE.sub("", text.strip())
    return text.strip()
