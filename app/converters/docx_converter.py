"""
app/converters/docx_converter.py
─────────────────────────────────────────────────────────────────────────────
Converts .docx → Markdown using python-docx.

Important behavior:
- Preserves document order by walking the Word body XML.
- Converts paragraphs, headings, lists and tables.
- Extracts embedded DOCX images and inserts Markdown image references exactly
  where the image appears in the document flow.
- Returns extracted image bytes in ConversionResult.figures so ZipBuilder can
  place them under figures/.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .base import AbstractConverter, ConversionError, ConversionResult

logger = logging.getLogger(__name__)

_W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"


@dataclass
class _ImageContext:
    doc: Any
    counter: int = 0
    figures: dict[str, bytes] = field(default_factory=dict)

    def add_from_rid(self, rid: str) -> str | None:
        """Store image bytes for a relationship id and return the filename."""
        try:
            part = self.doc.part.related_parts[rid]
        except KeyError:
            logger.warning("Image relationship %s not found in DOCX package.", rid)
            return None

        blob = getattr(part, "blob", None)
        if not blob:
            return None

        self.counter += 1
        ext = _extension_from_content_type(getattr(part, "content_type", ""))
        filename = f"figure-{self.counter}.{ext}"
        self.figures[filename] = blob
        return filename


class DocxConverter(AbstractConverter):
    supported_extensions = frozenset({".docx"})

    def convert(self, path: Path) -> ConversionResult:
        try:
            import docx as python_docx
        except ImportError as exc:
            raise ConversionError("python-docx is not installed.") from exc

        try:
            doc = python_docx.Document(str(path))
        except Exception as exc:
            raise ConversionError(f"Cannot open .docx: {exc}") from exc

        lines: list[str] = []
        warnings: list[str] = []
        image_ctx = _ImageContext(doc=doc)

        for block in doc.element.body:
            tag = _local_name(block.tag)

            if tag == "p":
                para = python_docx.text.paragraph.Paragraph(block, doc)
                line = _para_to_md(para, warnings, image_ctx)
                if line is not None:
                    lines.append(line)

            elif tag == "tbl":
                table = python_docx.table.Table(block, doc)
                table_lines = _table_to_md(table, warnings, image_ctx)
                if table_lines:
                    lines.append("")
                    lines.extend(table_lines)
                    lines.append("")

            elif tag == "sectPr":
                continue

        markdown = _collapse_blanks("\n".join(lines)).strip()

        return ConversionResult(
            markdown=markdown,
            warnings=warnings,
            figures=image_ctx.figures,
        )


# ── Paragraph ────────────────────────────────────────────────────────────────

def _para_to_md(para, warnings: list[str], image_ctx: _ImageContext) -> str | None:
    style_name = (para.style.name or "").strip()
    style_lower = style_name.lower()

    text = _paragraph_inline_to_md(para, warnings, image_ctx).strip()

    # Skip Word-generated table of contents lines. They are repeated metadata,
    # not real document body content. The real headings remain in the body.
    if style_lower.startswith("toc"):
        return None

    # Headings
    for level in range(1, 7):
        if style_lower == f"heading {level}":
            return f"{'#' * level} {text}" if text else ""

    if style_lower == "title":
        return f"# {text}" if text else ""

    if style_lower == "subtitle":
        return f"## {text}" if text else ""

    # Lists — simplified but stable.
    if "list" in style_lower or _has_num_pr(para):
        prefix = _list_prefix(para)
        return f"{prefix}{text}" if text else ""

    return text if text else ""


def _has_num_pr(para) -> bool:
    p_pr = para._p.find(f"{{{_W_NS}}}pPr")
    if p_pr is None:
        return False
    return p_pr.find(f"{{{_W_NS}}}numPr") is not None


def _list_prefix(para) -> str:
    style_lower = (para.style.name or "").lower()
    if "number" in style_lower or "ordered" in style_lower:
        return "1. "
    return "- "


# ── Runs → inline Markdown + inline images ───────────────────────────────────

def _paragraph_inline_to_md(para, warnings: list[str], image_ctx: _ImageContext) -> str:
    parts: list[str] = []

    for child in para._p:
        tag = _local_name(child.tag)
        if tag == "r":
            parts.append(_run_element_to_md(child, para, warnings, image_ctx))
        elif tag == "hyperlink":
            parts.append(_hyperlink_to_md(child, para, warnings, image_ctx))

    return "".join(parts).strip()


def _run_element_to_md(run_element, para, warnings: list[str], image_ctx: _ImageContext) -> str:
    from docx.text.run import Run

    run = Run(run_element, para)
    parts: list[str] = []

    # Images are represented as a:blip elements inside the run XML.
    image_refs = _image_refs_from_run(run, image_ctx)
    if image_refs:
        # Keep image markers in document order. Put them on their own line
        # when mixed with text to avoid broken Markdown.
        parts.append("\n")
        parts.extend(image_refs)
        parts.append("\n")

    chunk = run.text or ""
    if chunk:
        parts.append(_format_run_text(chunk, run))

    return "".join(parts)


def _hyperlink_to_md(hyperlink_element, para, warnings: list[str], image_ctx: _ImageContext) -> str:
    text_parts: list[str] = []
    for child in hyperlink_element:
        if _local_name(child.tag) == "r":
            text_parts.append(_run_element_to_md(child, para, warnings, image_ctx))

    text = "".join(text_parts).strip()
    target = _hyperlink_target(hyperlink_element, para)

    if not target:
        return text

    display = text or target
    return f"[{_escape_markdown_link_text(display)}]({_escape_markdown_link_target(target)})"


def _hyperlink_target(hyperlink_element, para) -> str | None:
    rid = hyperlink_element.get(f"{{{_R_NS}}}id")
    if rid:
        try:
            rel = para.part.rels[rid]
        except KeyError:
            return None
        return str(getattr(rel, "target_ref", "") or "").strip() or None

    anchor = str(hyperlink_element.get(f"{{{_W_NS}}}anchor") or "").strip()
    if anchor:
        return f"#{anchor}"
    return None


def _escape_markdown_link_text(text: str) -> str:
    return text.replace("\\", r"\\").replace("[", r"\[").replace("]", r"\]")


def _escape_markdown_link_target(target: str) -> str:
    return (
        target.replace("\\", "%5C")
        .replace(" ", "%20")
        .replace("(", "%28")
        .replace(")", "%29")
        .replace("<", "%3C")
        .replace(">", "%3E")
    )


def _image_refs_from_run(run, image_ctx: _ImageContext) -> list[str]:
    refs: list[str] = []

    # Iterate raw XML because python-docx does not expose images directly.
    for el in run._element.iter():
        if _local_name(el.tag) != "blip":
            continue

        rid = el.get(f"{{{_R_NS}}}embed") or el.get(f"{{{_R_NS}}}link")
        if not rid:
            continue

        filename = image_ctx.add_from_rid(rid)
        if filename:
            figure_number = _figure_number_from_filename(filename)
            refs.append(f"![Figure {figure_number}](figures/{filename})")

    return refs


def _format_run_text(text: str, run) -> str:
    # Normalize non-breaking spaces but preserve ordinary spacing.
    chunk = text.replace("\u00a0", " ")

    bold = bool(run.bold)
    italic = bool(run.italic)

    # Avoid wrapping pure whitespace in Markdown markers.
    if not chunk.strip():
        return chunk

    if bold and italic:
        return f"***{chunk}***"
    if bold:
        return f"**{chunk}**"
    if italic:
        return f"*{chunk}*"
    return chunk


# ── Table → GFM pipe table ───────────────────────────────────────────────────

def _table_to_md(table, warnings: list[str], image_ctx: _ImageContext) -> list[str]:
    rows = table.rows
    if not rows:
        return []

    result: list[str] = []
    expected_cols = max(len(row.cells) for row in rows)

    for i, row in enumerate(rows):
        cells = [_cell_text(cell, warnings, image_ctx) for cell in row.cells]

        # Normalize malformed Word rows so GFM table stays valid.
        if len(cells) < expected_cols:
            cells.extend([""] * (expected_cols - len(cells)))
        elif len(cells) > expected_cols:
            cells = cells[:expected_cols]

        result.append("| " + " | ".join(cells) + " |")
        if i == 0:
            result.append("| " + " | ".join(["---"] * expected_cols) + " |")

    return result


def _cell_text(cell, warnings: list[str], image_ctx: _ImageContext) -> str:
    parts: list[str] = []

    for p in cell.paragraphs:
        text = _paragraph_inline_to_md(p, warnings, image_ctx).strip()
        if text:
            parts.append(text)

    # Markdown tables cannot contain raw newlines in cells. Use <br>.
    return "<br>".join(parts).replace("|", "\\|")


# ── Utilities ────────────────────────────────────────────────────────────────

def _collapse_blanks(text: str) -> str:
    return re.sub(r"\n{3,}", "\n\n", text)


def _local_name(tag: str) -> str:
    return tag.split("}")[-1]


def _extension_from_content_type(content_type: str) -> str:
    content_type = (content_type or "").lower()
    if "jpeg" in content_type or "jpg" in content_type:
        return "jpg"
    if "png" in content_type:
        return "png"
    if "gif" in content_type:
        return "gif"
    if "bmp" in content_type:
        return "bmp"
    if "tiff" in content_type:
        return "tiff"
    if "webp" in content_type:
        return "webp"
    return "bin"


def _figure_number_from_filename(filename: str) -> int:
    try:
        return int(filename.split("-")[1].split(".")[0])
    except Exception:
        return 0
