"""Build ZIP output containing Markdown, extracted figures and metadata."""

from __future__ import annotations

import json
import zipfile
from io import BytesIO
from typing import Any

from ..quality import build_quality_report_markdown


def build_zip(
    markdown: str,
    result: Any,
    figures: dict[str, bytes],
    stem: str,
    converter_version: str,
    ai_applied: bool = False,
    ai_fixes: list[str] | None = None,
    conversion_warnings: list[str] | None = None,
    quality_report: dict[str, Any] | None = None,
) -> bytes:
    ai_fixes = ai_fixes or []
    conversion_warnings = conversion_warnings or []

    meta = {
        "title": result.title,
        "doc_type": result.doc_type_code,
        "doc_type_label": result.doc_type_label,
        "language": result.language,
        "source_filename": result.source_filename,
        "source_format": result.source_format,
        "word_count": result.word_count,
        "estimated_pages": result.estimated_pages,
        "table_count": result.table_count,
        "figure_count": result.figure_count,
        "sections": result.sections,
        "subsections": result.subsections,
        "converter_version": converter_version,
        "ai_applied": ai_applied,
        "ai_fixes": ai_fixes,
        "warnings": conversion_warnings,
        "quality_report": quality_report,
        "figures": [
            {
                "index": fig.index,
                "caption": fig.caption,
                "filename": fig.filename,
                "page_hint": fig.page_hint,
            }
            for fig in result.figures
        ],
    }

    buffer = BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"{stem}.md", markdown)
        zf.writestr("markforge-meta.json", json.dumps(meta, indent=2, ensure_ascii=False))
        if quality_report:
            zf.writestr("markforge-quality-report.json", json.dumps(quality_report, indent=2, ensure_ascii=False))
            zf.writestr("markforge-quality-report.md", build_quality_report_markdown(quality_report))
        for filename, data in sorted(figures.items()):
            zf.writestr(f"figures/{filename}", data)

    buffer.seek(0)
    return buffer.getvalue()
