"""Build YAML frontmatter for converted documents."""

from __future__ import annotations

from datetime import datetime
from typing import Any


def _yaml_escape(value: object) -> str:
    return str(value or "").replace("\\", "\\\\").replace('"', '\\"')


def _yaml_list(values: list[str] | tuple[str, ...] | None) -> str:
    values = list(values or [])
    if not values:
        return "[]"
    return "\n".join(f'  - "{_yaml_escape(value)}"' for value in values)


def build_frontmatter(
    result: Any,
    converted_at: datetime,
    converter_version: str,
    ai_applied: bool = False,
    ai_fixes: list[str] | None = None,
) -> str:
    ai_fixes = ai_fixes or []

    return f'''---
title: "{_yaml_escape(result.title or "Untitled")}"
doc_type: "{_yaml_escape(result.doc_type_code or "UNKNOWN")}"
doc_type_label: "{_yaml_escape(result.doc_type_label or "Document")}"
language: "{_yaml_escape(result.language or "en")}"
source_filename: "{_yaml_escape(result.source_filename)}"
source_format: "{_yaml_escape(result.source_format)}"
converted_at: "{converted_at.isoformat()}"
converter_version: "{_yaml_escape(converter_version)}"
ai_applied: {str(ai_applied).lower()}
word_count: {int(result.word_count or 0)}
estimated_pages: {int(result.estimated_pages or 0)}
table_count: {int(result.table_count or 0)}
figure_count: {int(result.figure_count or 0)}
sections:
{_yaml_list(result.sections)}
subsections:
{_yaml_list(result.subsections)}
ai_fixes:
{_yaml_list(ai_fixes)}
---
'''
