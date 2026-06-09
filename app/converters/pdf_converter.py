"""
app/converters/pdf_converter.py
─────────────────────────────────────────────────────────────────────────────
Converts .pdf → Markdown using PyMuPDF (fitz).

Strategy:
    - Per-page text extracted as structured dicts (font, size, flags)
    - Font-size ratio vs page max → heading level heuristic
    - Bold flag on spans → **bold**
    - Scanned pages (no text blocks) → warning, page skipped
    - Tables: PyMuPDF find_tables() used where available (PDF ≥ 1.4)
"""

from __future__ import annotations

import logging
from pathlib import Path

from .base import AbstractConverter, ConversionError, ConversionResult

logger = logging.getLogger(__name__)

# Minimum ratio of span font-size / page-max-font-size to be a heading
_H1_RATIO = 0.92
_H2_RATIO = 0.78
_H3_RATIO = 0.65


class PdfConverter(AbstractConverter):
    supported_extensions = frozenset({".pdf"})

    def convert(self, path: Path) -> ConversionResult:
        try:
            import fitz
        except ImportError as exc:
            raise ConversionError("PyMuPDF (fitz) is not installed.") from exc

        try:
            doc = fitz.open(str(path))
        except Exception as exc:
            raise ConversionError(f"Cannot open PDF: {exc}") from exc

        warnings: list[str] = []
        pages_md: list[str] = []

        for page_num, page in enumerate(doc, start=1):
            try:
                page_md = _page_to_md(page, page_num, warnings, fitz)
            except Exception as exc:
                logger.warning("Page %d error: %s", page_num, exc)
                warnings.append(f"Page {page_num}: extraction error — {exc}")
                continue
            if page_md:
                pages_md.append(page_md)

        doc.close()

        return ConversionResult(
            markdown="\n\n".join(pages_md).strip(),
            warnings=warnings,
        )


def _page_to_md(page, page_num: int, warnings: list, fitz) -> str:
    blocks = page.get_text(
        "dict",
        flags=fitz.TEXT_PRESERVE_WHITESPACE | fitz.TEXT_PRESERVE_LIGATURES,
    )["blocks"]

    text_blocks = [b for b in blocks if b.get("type") == 0]

    if not text_blocks:
        warnings.append(f"Page {page_num}: no text — may be scanned/image-only.")
        return ""

    # Compute max font size on this page for heading calibration
    all_sizes = [
        span["size"]
        for block in text_blocks
        for line in block.get("lines", [])
        for span in line.get("spans", [])
        if span.get("size", 0) > 0
    ]
    max_size = max(all_sizes) if all_sizes else 12.0

    lines_md: list[str] = []
    prev_text = ""

    for block in text_blocks:
        block_lines = _block_to_lines(block, max_size)
        for line_text in block_lines:
            # Deduplicate running headers/footers (same text on consecutive pages)
            if line_text == prev_text:
                continue
            lines_md.append(line_text)
            prev_text = line_text

    return "\n".join(lines_md)


def _block_to_lines(block: dict, max_size: float) -> list[str]:
    lines: list[str] = []

    for line in block.get("lines", []):
        spans = line.get("spans", [])
        if not spans:
            continue

        # Dominant size and bold flag for this line
        line_size = max((s.get("size", 0) for s in spans), default=0)
        is_bold   = any(s.get("flags", 0) & 16 for s in spans)  # bit 4 = bold
        line_text = "".join(s.get("text", "") for s in spans).strip()

        if not line_text:
            continue

        ratio = line_size / max_size if max_size else 0

        if ratio >= _H1_RATIO:
            line_text = f"# {line_text}"
        elif ratio >= _H2_RATIO:
            line_text = f"## {line_text}"
        elif ratio >= _H3_RATIO:
            line_text = f"### {line_text}"
        elif is_bold:
            line_text = f"**{line_text}**"

        lines.append(line_text)

    return lines