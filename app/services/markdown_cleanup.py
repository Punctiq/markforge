"""Generic deterministic cleanup for Markdown converter artifacts."""

from __future__ import annotations

import re
from dataclasses import dataclass, field


_HEADING_RE = re.compile(r"^(#{1,6})(\s+)(.+?)(\s*)$")
_ITALIC_CAPTION_RE = re.compile(r"^(\s*)\*((?:Figure|Table).+?)\*(\s*)$", re.IGNORECASE)
_IMAGE_LINK_RE = re.compile(r"^\s*!\[[^\]]*]\([^)]+\)\s*$")
_MARKDOWN_LINK_RE = re.compile(r"!?\[[^\]]*]\([^)]+\)")
_TABLE_LINE_RE = re.compile(r"^\s*\|")
_ADJACENT_BOLD_SPANS_RE = re.compile(r"\*\*([^*\n]+?)\*\*\*\*([^*\n]+?)\*\*")
_WORD_START_BOLD_LETTER_RE = re.compile(r"\*\*([A-Za-z])\*\*(?=[A-Za-z])")
_WORD_END_BOLD_LETTER_RE = re.compile(r"(?<=[A-Za-z])\*\*([A-Za-z])\*\*")


@dataclass(frozen=True)
class MarkdownCleanupResult:
    markdown: str
    fixes: list[str] = field(default_factory=list)


def cleanup_markdown(markdown: str) -> MarkdownCleanupResult:
    """Clean safe DOCX-to-Markdown artifacts without rewriting content."""
    if not markdown:
        return MarkdownCleanupResult(markdown="")

    cleaned_lines: list[str] = []
    fixes: set[str] = set()
    in_code_block = False
    in_frontmatter = False
    frontmatter_checked = False
    in_html_comment = False

    for line in markdown.splitlines():
        stripped = line.strip()

        if not frontmatter_checked:
            frontmatter_checked = True
            if stripped == "---":
                in_frontmatter = True
                cleaned_lines.append(line)
                continue
        elif in_frontmatter:
            cleaned_lines.append(line)
            if stripped == "---":
                in_frontmatter = False
            continue

        if in_html_comment:
            cleaned_lines.append(line)
            if "-->" in line:
                in_html_comment = False
            continue
        if stripped.startswith("<!--"):
            cleaned_lines.append(line)
            if "-->" not in line:
                in_html_comment = True
            continue

        if stripped.startswith("```"):
            in_code_block = not in_code_block
            cleaned_lines.append(line)
            continue
        if in_code_block:
            cleaned_lines.append(line)
            continue

        cleaned = _cleanup_heading(line)
        if cleaned != line:
            fixes.add("Normalized broken emphasis markers in Markdown headings.")
            cleaned_lines.append(cleaned)
            continue

        cleaned = _cleanup_caption(line)
        if cleaned != line:
            fixes.add("Normalized broken emphasis markers in figure/table captions.")
            cleaned_lines.append(cleaned)
            continue

        cleaned = _cleanup_safe_inline_artifacts(line)
        if cleaned != line:
            fixes.add("Normalized obvious split-word emphasis artifacts.")

        cleaned_lines.append(cleaned)

    return MarkdownCleanupResult(markdown="\n".join(cleaned_lines), fixes=sorted(fixes))


def clean_broken_emphasis_artifacts(text: str) -> str:
    """Remove only obvious emphasis artifacts caused by DOCX run boundaries."""
    if "**" not in text:
        return text

    cleaned = text
    for _ in range(10):
        merged = _ADJACENT_BOLD_SPANS_RE.sub(r"\1\2", cleaned)
        if merged == cleaned:
            break
        cleaned = merged

    cleaned = _WORD_START_BOLD_LETTER_RE.sub(r"\1", cleaned)
    cleaned = _WORD_END_BOLD_LETTER_RE.sub(r"\1", cleaned)
    return cleaned


def _cleanup_heading(line: str) -> str:
    match = _HEADING_RE.match(line)
    if not match or "**" not in match.group(3):
        return line

    marker, spacing, text, trailing = match.groups()
    return f"{marker}{spacing}{_remove_emphasis_markers(text).strip()}{trailing}"


def _cleanup_caption(line: str) -> str:
    if _IMAGE_LINK_RE.match(line):
        return line

    match = _ITALIC_CAPTION_RE.match(line)
    if not match or "**" not in match.group(2):
        return line

    leading, caption, trailing = match.groups()
    caption = re.sub(r"\s+", " ", _remove_emphasis_markers(caption)).strip()
    return f"{leading}*{caption}*{trailing}"


def _cleanup_safe_inline_artifacts(line: str) -> str:
    if "**" not in line or _TABLE_LINE_RE.match(line) or _MARKDOWN_LINK_RE.search(line):
        return line
    return clean_broken_emphasis_artifacts(line)


def _remove_emphasis_markers(text: str) -> str:
    return text.replace("**", "")
