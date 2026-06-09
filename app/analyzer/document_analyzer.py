"""
app/analyzer/document_analyzer.py
─────────────────────────────────────────────────────────────────────────────
Analyzes converted Markdown to extract structured metadata:
    - title (from first H1 or docx core properties)
    - document type (HLD / LLD / SOP / ...)
    - language (detected from content)
    - section skeleton (H1 + H2 headings)
    - figure count and references
    - table count
    - word count / estimated pages

All logic is deterministic — no LLM calls. Fast, free, offline.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class FigureRef:
    """A figure found in the document."""
    index: int
    caption: str
    filename: str        # e.g. "figure-1.png"
    page_hint: int = 0   # 0 = unknown


@dataclass
class AnalysisResult:
    """All metadata extracted from a converted document."""

    # Identity
    title: str = ""
    doc_type_code: str = "UNKNOWN"
    doc_type_label: str = "Document"
    language: str = "en"

    # Structure
    sections: list[str] = field(default_factory=list)   # H1 headings
    subsections: list[str] = field(default_factory=list) # H2 headings

    # Content stats
    word_count: int = 0
    estimated_pages: int = 0
    table_count: int = 0
    figure_count: int = 0
    figures: list[FigureRef] = field(default_factory=list)

    # Source info (filled by caller)
    source_filename: str = ""
    source_format: str = ""

    def llm_hint(self, doc_type_context: str) -> str:
        """Generate a factual, template-based LLM hint string."""
        parts: list[str] = [doc_type_context]

        if self.figure_count:
            parts.append(
                f"Contains {self.figure_count} figure(s) referenced as [Figure N] "
                f"with image files in the figures/ directory."
            )
        if self.table_count:
            parts.append(f"Contains {self.table_count} table(s).")

        if self.sections:
            top = self.sections[:6]
            more = len(self.sections) - len(top)
            section_list = ", ".join(f'"{s}"' for s in top)
            if more > 0:
                section_list += f" and {more} more"
            parts.append(f"Main sections: {section_list}.")

        if self.language != "en":
            parts.append(f"Document language: {self.language}.")

        return " ".join(parts)


# ── Regex patterns ─────────────────────────────────────────────────────────────
_H1 = re.compile(r"^# (.+)$", re.MULTILINE)
_H2 = re.compile(r"^## (.+)$", re.MULTILINE)
_TABLE_ROW = re.compile(r"^\|.+\|$", re.MULTILINE)
_TABLE_SEP = re.compile(r"^\|[-| :]+\|$", re.MULTILINE)

# Figure references: "Figure N: Caption" or "Figure N - Caption" or just "Figure N"
_FIGURE_REF = re.compile(
    r"\bfigure\s+(\d+)\s*[:\-–]?\s*([^\n\r]{0,120})",
    re.IGNORECASE,
)

# Language detection — simple heuristic on common stopwords
_LANG_HINTS: dict[str, list[str]] = {
    "ro": ["și", "sau", "pentru", "care", "este", "sunt", "cu", "de", "în", "la"],
    "de": ["und", "oder", "für", "die", "der", "das", "ist", "sind", "mit", "von"],
    "fr": ["et", "ou", "pour", "qui", "est", "sont", "avec", "de", "le", "la"],
    "es": ["y", "o", "para", "que", "es", "son", "con", "de", "el", "la"],
}


def analyze(
    markdown: str,
    source_filename: str = "",
    source_format: str = "",
    figures: list[FigureRef] | None = None,
) -> AnalysisResult:
    """Extract structured metadata from converted Markdown.

    Args:
        markdown:        The converted Markdown string.
        source_filename: Original uploaded filename.
        source_format:   File extension e.g. ".docx".
        figures:         Pre-extracted FigureRef list from the converter
                         (if available). If None, figures are detected
                         from Markdown text references only.

    Returns:
        AnalysisResult with all detected metadata populated.
    """
    result = AnalysisResult(
        source_filename=source_filename,
        source_format=source_format,
    )

    # ── Title ──────────────────────────────────────────────────────────────
    h1_matches = _H1.findall(markdown)
    result.title = h1_matches[0].strip() if h1_matches else Path(source_filename).stem

    # ── Sections ───────────────────────────────────────────────────────────
    result.sections    = [h.strip() for h in h1_matches]
    result.subsections = [h.strip() for h in _H2.findall(markdown)]

    # ── Document type ───────────────────────────────────────────────────────
    from .doc_types import detect_doc_type
    all_headings = result.sections + result.subsections
    doc_type = detect_doc_type(result.title, all_headings)
    result.doc_type_code  = doc_type.code
    result.doc_type_label = doc_type.label

    # ── Table count ─────────────────────────────────────────────────────────
    # Count separator rows — each GFM table has exactly one separator
    result.table_count = len(_TABLE_SEP.findall(markdown))

    # ── Figures ─────────────────────────────────────────────────────────────
    if figures is not None:
        result.figures = figures
        result.figure_count = len(figures)
    else:
        # Detect from text references only (PDF / ODT path)
        seen: set[int] = set()
        for m in _FIGURE_REF.finditer(markdown):
            idx = int(m.group(1))
            if idx not in seen:
                seen.add(idx)
                caption = m.group(2).strip().rstrip(".,;")
                result.figures.append(FigureRef(
                    index=idx,
                    caption=caption,
                    filename=f"figure-{idx}.png",
                ))
        result.figure_count = len(result.figures)

    # ── Word count & estimated pages ────────────────────────────────────────
    words = len(markdown.split())
    result.word_count = words
    result.estimated_pages = max(1, words // 300)  # ~300 words/page

    # ── Language ────────────────────────────────────────────────────────────
    result.language = _detect_language(markdown)

    return result


def _detect_language(text: str) -> str:
    """Heuristic language detection based on stopword frequency."""
    sample = text[:3000].lower()
    words  = set(re.findall(r"\b\w+\b", sample))

    scores: dict[str, int] = {}
    for lang, stopwords in _LANG_HINTS.items():
        scores[lang] = sum(1 for w in stopwords if w in words)

    best_lang = max(scores, key=lambda l: scores[l])
    return best_lang if scores[best_lang] >= 3 else "en"