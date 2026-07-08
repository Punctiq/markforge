"""
app/services/conversion_service.py
─────────────────────────────────────────────────────────────────────────────
Full pipeline:
    1. Converter          → raw Markdown + extracted figures
    2. DocumentAnalyzer   → metadata (title, doc_type, sections, ...)
    3. FrontmatterBuilder → Obsidian-compatible YAML
    4. MarkdownBuilder    → LLM-ready Markdown with figure tags injected
    5. AI cleanup         → optional cleanup pass
    6. ZipBuilder         → .zip with .md + figures/ + markforge-meta.json

Returns either:
    - dict with "markdown" key   (ai_cleanup only, no ZIP — legacy/simple mode)
    - dict with "zip" key        (full LLM-ready output)

The endpoint decides which mode based on the "output_format" request param.
Default is "zip" for full output.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from pathlib import Path

from ..analyzer.document_analyzer import FigureRef, analyze
from ..builders.frontmatter import build_frontmatter
from ..builders.markdown_builder import build_markdown
from ..builders.zip_builder import build_zip
from ..quality import build_quality_report
from ..converters.base import ConversionError
from ..converters.registry import get_converter
from .markdown_cleanup import cleanup_markdown

logger = logging.getLogger(__name__)

MARKFORGE_VERSION = "0.1.0"


class ConversionService:
    def __init__(self, config: dict) -> None:
        self.config = config

    def convert(
        self,
        path: Path,
        original_name: str,
        ai_cleanup: bool = True,
        ai_cleanup_mode: str = "safe",
        output_format: str = "zip",   # "zip" | "markdown" | "both"
    ) -> dict:
        """Run the full conversion pipeline.

        Returns dict with keys depending on output_format:
            zip:      {"zip": bytes, "filename": "stem.zip", "stats": {...}}
            markdown: {"markdown": str, "filename": "stem.md", "stats": {...}}
            both:     {"markdown": str, "zip": bytes, "filename": "stem.zip", "stats": {...}}
        """
        t0 = time.monotonic()
        ext = path.suffix.lower()
        stem = Path(original_name).stem
        converted_at = datetime.now(timezone.utc)

        logger.info("Converting '%s' (ext=%s ai=%s mode=%s out=%s)",
                    original_name, ext, ai_cleanup, ai_cleanup_mode, output_format)

        # ── 1. Format-specific conversion ───────────────────────────────────
        try:
            converter = get_converter(ext, config=self.config)
            raw = converter.convert(path)
        except ConversionError:
            raise
        except Exception as exc:
            raise ConversionError(f"Unexpected error: {exc}") from exc

        original_markdown = raw.markdown
        deterministic_cleanup = cleanup_markdown(original_markdown)
        markdown = deterministic_cleanup.markdown
        figures_bytes = raw.figures   # {filename: bytes}

        # ── 2. AI cleanup (optional) ─────────────────────────────────────────
        fixes: list[str] = list(deterministic_cleanup.fixes)
        ai_applied = False
        token_usage: dict[str, int] = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "llm_calls": 0,
        }

        if ai_cleanup and self.config.get("LLM_API_KEY"):
            from ..agent.cleaner import MarkdownCleaner
            cleaned = MarkdownCleaner(config=self.config, mode=ai_cleanup_mode).clean(markdown)
            markdown = cleaned.markdown
            fixes.extend(cleaned.fixes)
            ai_applied = cleaned.ai_applied
            token_usage = cleaned.token_usage or token_usage

        # ── 3. Quality report ───────────────────────────────────────────────
        quality_report = build_quality_report(
            original_markdown=original_markdown,
            final_markdown=markdown,
            mode=ai_cleanup_mode,
            ai_cleanup_requested=ai_cleanup,
            ai_applied=ai_applied,
            config=self.config if ai_cleanup else None,
        )

        quality_token_usage = quality_report.get("token_usage", {}) or {}
        for key in ("prompt_tokens", "completion_tokens", "total_tokens", "llm_calls"):
            token_usage[key] = int(token_usage.get(key, 0) or 0) + int(quality_token_usage.get(key, 0) or 0)

        # ── 4. Analyze document ──────────────────────────────────────────────
        # Build FigureRef list from extracted images
        figure_refs: list[FigureRef] = []
        for filename in sorted(figures_bytes.keys()):
            # Parse index from filename: "figure-3.png" → 3
            try:
                idx = int(filename.split("-")[1].split(".")[0])
            except (IndexError, ValueError):
                idx = len(figure_refs) + 1
            figure_refs.append(FigureRef(
                index=idx,
                caption="",      # filled by markdown_builder from context
                filename=filename,
            ))

        result = analyze(
            markdown=markdown,
            source_filename=original_name,
            source_format=ext,
            figures=figure_refs if figure_refs else None,
        )

        # ── 5. Build frontmatter ─────────────────────────────────────────────
        frontmatter = build_frontmatter(
            result=result,
            converted_at=converted_at,
            converter_version=MARKFORGE_VERSION,
            ai_applied=ai_applied,
            ai_fixes=fixes,
        )

        # ── 6. Assemble LLM-ready Markdown ───────────────────────────────────
        final_markdown = build_markdown(
            body=markdown,
            frontmatter=frontmatter,
            result=result,
        )

        duration_ms = int((time.monotonic() - t0) * 1000)

        stats = {
            "duration_ms":     duration_ms,
            "ai_applied":      ai_applied,
            "ai_cleanup_mode": ai_cleanup_mode,
            "token_usage":     token_usage,
            "fixes":           fixes,
            "warnings":        raw.warnings,
            "doc_type":        result.doc_type_code,
            "doc_type_label":  result.doc_type_label,
            "title":           result.title,
            "figure_count":    result.figure_count,
            "table_count":     result.table_count,
            "estimated_pages": result.estimated_pages,
            "word_count":      result.word_count,
            "language":        result.language,
            "quality_report":  quality_report,
        }

        logger.info(
            "Done: '%s' → %s | %dms | type=%s figures=%d tables=%d ai=%s tokens=%s",
            original_name, stem, duration_ms,
            result.doc_type_code, result.figure_count,
            result.table_count, ai_applied, token_usage.get("total_tokens", 0),
        )

        # ── 7. Output ────────────────────────────────────────────────────────
        zip_bytes = build_zip(
            markdown=final_markdown,
            result=result,
            figures=figures_bytes,
            stem=stem,
            converter_version=MARKFORGE_VERSION,
            ai_applied=ai_applied,
            ai_fixes=fixes,
            conversion_warnings=raw.warnings,
            quality_report=quality_report,
        )

        if output_format == "markdown":
            return {
                "markdown": final_markdown,
                "filename": f"{stem}.md",
                "stats": stats,
            }

        if output_format == "both":
            return {
                "markdown": final_markdown,
                "markdown_filename": f"{stem}.md",
                "zip": zip_bytes,
                "zip_filename": f"{stem}.zip",
                "filename": f"{stem}.zip",
                "stats": stats,
            }

        # Default: ZIP
        return {
            "zip": zip_bytes,
            "filename": f"{stem}.zip",
            "stats": stats,
        }
