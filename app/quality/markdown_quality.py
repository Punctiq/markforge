"""
app/quality/markdown_quality.py
─────────────────────────────────────────────────────────────────────────────
Deterministic and AI-assisted quality reporting for Markdown cleanup.

The report compares the raw converter output with the final Markdown.
- AI cleanup ON  -> deterministic comparison + AI quality report
- AI cleanup OFF -> deterministic comparison only, no AI call
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any

from ..agent.base_llm import LLMError
from ..agent.llm_registry import get_llm_client

logger = logging.getLogger(__name__)

_HEADING_RE = re.compile(r"(?m)^(#{1,6})\s+(.+?)\s*$")
_IMAGE_RE = re.compile(r"!\[[^\]]*\]\([^)]+\)")
_LINK_RE = re.compile(r"(?<!!)\[[^\]]+\]\([^)]+\)")
_JSON_FENCE_RE = re.compile(r"```json\s*(\{.*?\})\s*```", re.DOTALL | re.IGNORECASE)
_TABLE_LINE_RE = re.compile(r"^\s*\|.+\|\s*$", re.MULTILINE)


def _empty_token_usage() -> dict[str, int]:
    return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "llm_calls": 0}


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


def _count_words(text: str) -> int:
    return len(re.findall(r"\b\S+\b", text or ""))


def _extract_headings(markdown: str) -> list[dict[str, Any]]:
    headings: list[dict[str, Any]] = []
    for match in _HEADING_RE.finditer(markdown or ""):
        headings.append({
            "level": len(match.group(1)),
            "text": match.group(2).strip(),
            "line": (markdown[:match.start()].count("\n") + 1),
        })
    return headings


def _normalize_heading(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip().lower()


def _severity_rank(value: str | None) -> int:
    return {"low": 1, "medium": 2, "high": 3}.get((value or "low").lower(), 1)


def _max_severity(*values: str | None) -> str:
    winner = "low"
    for value in values:
        if _severity_rank(value) > _severity_rank(winner):
            winner = (value or "low").lower()
    return winner


def _recommendation_for_risk(
    *,
    risk: str,
    content_risk: str,
    structure_risk: str,
    integrity_risk: str,
) -> str:
    if risk == "high" or content_risk == "high" or integrity_risk == "high":
        return "reject_cleanup"
    if content_risk == "medium" or integrity_risk == "medium":
        return "review_manually"
    if structure_risk == "medium":
        return "accept_after_heading_review"
    return "accept"


def _metrics(markdown: str) -> dict[str, Any]:
    headings = _extract_headings(markdown)
    images = _IMAGE_RE.findall(markdown or "")
    table_lines = _TABLE_LINE_RE.findall(markdown or "")
    code_fence_count = (markdown or "").count("```")
    return {
        "char_count": len(markdown or ""),
        "word_count": _count_words(markdown or ""),
        "heading_count": len(headings),
        "headings": headings,
        "image_count": len(images),
        "images": images,
        "table_line_count": len(table_lines),
        "link_count": len(_LINK_RE.findall(markdown or "")),
        "code_fence_count": code_fence_count,
        "code_fences_balanced": code_fence_count % 2 == 0,
    }


def _deterministic_findings(before: dict[str, Any], after: dict[str, Any]) -> tuple[list[dict[str, str]], str, str, dict[str, str]]:
    findings: list[dict[str, str]] = []

    content_risk = "low"
    structure_risk = "low"
    integrity_risk = "low"

    before_words = max(1, int(before["word_count"]))
    after_words = int(after["word_count"])
    retention_ratio = after_words / before_words

    if retention_ratio < 0.80:
        content_risk = "high"
        findings.append({
            "type": "possible_missing_content",
            "severity": "high",
            "topic": "Document level",
            "description": f"Final Markdown retained only {retention_ratio:.1%} of the original word count.",
        })
    elif retention_ratio < 0.92:
        content_risk = "medium"
        findings.append({
            "type": "possible_missing_content",
            "severity": "medium",
            "topic": "Document level",
            "description": f"Final Markdown retained {retention_ratio:.1%} of the original word count. Manual review is recommended.",
        })

    if before["images"] != after["images"]:
        integrity_risk = "high"
        findings.append({
            "type": "image_integrity",
            "severity": "high",
            "topic": "Figures / images",
            "description": "Image references changed, disappeared, or were reordered.",
        })

    before_heading_count = int(before["heading_count"])
    after_heading_count = int(after["heading_count"])

    if before_heading_count and after_heading_count < before_heading_count * 0.80:
        structure_risk = _max_severity(structure_risk, "medium")
        findings.append({
            "type": "heading_integrity",
            "severity": "medium",
            "topic": "Document structure",
            "description": "The final Markdown has significantly fewer headings than the original converted Markdown.",
        })

    before_heading_names = [_normalize_heading(h["text"]) for h in before["headings"]]
    after_heading_names = [_normalize_heading(h["text"]) for h in after["headings"]]

    missing = [h for h in before_heading_names if h and h not in after_heading_names]
    added = [h for h in after_heading_names if h and h not in before_heading_names]

    if missing:
        structure_risk = _max_severity(structure_risk, "medium")
        sample = ", ".join(missing[:8])
        findings.append({
            "type": "possible_missing_or_renamed_headings",
            "severity": "medium",
            "topic": "Document structure",
            "description": f"Some original headings are no longer present with the same text: {sample}",
        })

    if added:
        structure_risk = _max_severity(structure_risk, "medium")
        sample = ", ".join(added[:8])
        findings.append({
            "type": "new_or_reclassified_headings",
            "severity": "medium",
            "topic": "Document structure",
            "description": f"The final Markdown contains headings that were not detected before cleanup: {sample}",
        })

    if before_heading_count != after_heading_count:
        structure_risk = _max_severity(structure_risk, "medium")
        findings.append({
            "type": "heading_count_changed",
            "severity": "medium",
            "topic": "Document structure",
            "description": f"Heading count changed from {before_heading_count} to {after_heading_count}. Review heading hierarchy before accepting the cleanup.",
        })

    if int(after["table_line_count"]) < int(before["table_line_count"]) * 0.80 and int(before["table_line_count"]):
        integrity_risk = _max_severity(integrity_risk, "medium")
        findings.append({
            "type": "table_integrity",
            "severity": "medium",
            "topic": "Tables",
            "description": "The final Markdown has significantly fewer pipe-table lines than the original converted Markdown.",
        })

    if not after["code_fences_balanced"]:
        integrity_risk = "high"
        findings.append({
            "type": "markdown_syntax",
            "severity": "high",
            "topic": "Code blocks",
            "description": "The final Markdown has unbalanced fenced code blocks.",
        })

    risk = _max_severity(content_risk, structure_risk, integrity_risk)
    recommendation = _recommendation_for_risk(
        risk=risk,
        content_risk=content_risk,
        structure_risk=structure_risk,
        integrity_risk=integrity_risk,
    )

    if not findings:
        findings.append({
            "type": "deterministic_check",
            "severity": "low",
            "topic": "Document level",
            "description": "No obvious content-loss indicators were detected by deterministic checks.",
        })

    risk_breakdown = {
        "content_risk_level": content_risk,
        "structure_risk_level": structure_risk,
        "integrity_risk_level": integrity_risk,
    }

    return findings, risk, recommendation, risk_breakdown

def _sections_outline(headings: list[dict[str, Any]], limit: int = 80) -> list[str]:
    lines = []
    for h in headings[:limit]:
        indent = "  " * max(0, int(h["level"]) - 1)
        lines.append(f"{indent}- {h['text']}")
    if len(headings) > limit:
        lines.append(f"... {len(headings) - limit} more headings omitted from audit prompt")
    return lines


def _clip(text: str, max_chars: int) -> str:
    text = text or ""
    if len(text) <= max_chars:
        return text
    half = max_chars // 2
    return text[:half].rstrip() + "\n\n...[middle omitted for audit prompt safety]...\n\n" + text[-half:].lstrip()




def _estimate_tokens(text: str) -> int:
    """Cheap conservative token estimate used before sending audit prompts.

    This is intentionally simple. It avoids provider-specific tokenizers while
    still preventing obviously oversized prompts from being submitted.
    """
    return max(1, (len(text or "") + 3) // 4)


def _metric_summary(metrics: dict[str, Any]) -> dict[str, Any]:
    """Return a compact metrics object safe for LLM prompts.

    The full deterministic metrics can contain every heading and every image
    reference. In large PDFs this can become huge and can itself trigger a
    context-length error. The AI audit only needs counts and representative
    outlines, not the full raw lists.
    """
    headings = metrics.get("headings", []) or []
    images = metrics.get("images", []) or []
    return {
        "char_count": metrics.get("char_count", 0),
        "word_count": metrics.get("word_count", 0),
        "heading_count": metrics.get("heading_count", 0),
        "heading_outline_sample": _sections_outline(headings, limit=40),
        "image_count": metrics.get("image_count", 0),
        "image_reference_sample": images[:20],
        "table_line_count": metrics.get("table_line_count", 0),
        "link_count": metrics.get("link_count", 0),
        "code_fence_count": metrics.get("code_fence_count", 0),
        "code_fences_balanced": metrics.get("code_fences_balanced", True),
    }


def _compact_deterministic_report(report: dict[str, Any]) -> dict[str, Any]:
    metrics = report.get("metrics", {}) or {}
    before = metrics.get("before", {}) or {}
    after = metrics.get("after", {}) or {}
    findings = report.get("findings", []) or []
    return {
        "enabled": report.get("enabled", True),
        "risk_level": report.get("risk_level", "low"),
        "recommendation": report.get("recommendation", "accept"),
        "content_risk_level": report.get("content_risk_level", "low"),
        "structure_risk_level": report.get("structure_risk_level", "low"),
        "integrity_risk_level": report.get("integrity_risk_level", "low"),
        "metrics": {
            "before": _metric_summary(before),
            "after": _metric_summary(after),
            "retention_ratio": metrics.get("retention_ratio", 1),
            "word_count_delta": metrics.get("word_count_delta", 0),
            "heading_count_delta": metrics.get("heading_count_delta", 0),
            "image_count_delta": metrics.get("image_count_delta", 0),
            "table_line_count_delta": metrics.get("table_line_count_delta", 0),
        },
        "findings": findings[:30],
    }


def _sample_document(text: str, max_chars: int) -> str:
    """Create a beginning/middle/end sample for large-document AI audit."""
    text = text or ""
    if len(text) <= max_chars:
        return text

    part = max(500, max_chars // 3)
    middle_start = max(0, (len(text) // 2) - (part // 2))
    middle_end = min(len(text), middle_start + part)
    return "\n\n".join([
        text[:part].rstrip(),
        "...[middle sample]...",
        text[middle_start:middle_end].strip(),
        "...[end sample]...",
        text[-part:].lstrip(),
    ])

def _parse_ai_json(raw: str) -> dict[str, Any] | None:
    text = (raw or "").strip()
    match = list(_JSON_FENCE_RE.finditer(text))
    json_text = match[-1].group(1) if match else text
    try:
        parsed = json.loads(json_text)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        return None


def _ai_quality_report(
    *,
    config: dict,
    original_markdown: str,
    final_markdown: str,
    deterministic_report: dict[str, Any],
    mode: str,
) -> tuple[dict[str, Any] | None, dict[str, int], str | None]:
    token_usage = _empty_token_usage()

    if not config.get("LLM_API_KEY"):
        return None, token_usage, "LLM_API_KEY not set; AI quality report skipped."

    try:
        client = get_llm_client(config)
    except LLMError as exc:
        return None, token_usage, f"LLM client init failed; AI quality report skipped: {exc}"

    # AI audit must never submit the full document blindly. Large PDFs can
    # easily exceed model context limits, especially when the deterministic
    # report contains long heading/image lists. Use a compact report and a
    # bounded beginning/middle/end sample instead.
    safe_input_tokens = int(config.get("AI_QUALITY_SAFE_INPUT_TOKENS", 24_000))
    max_output_tokens = int(config.get("AI_QUALITY_MAX_OUTPUT_TOKENS", 2_048))
    sample_chars = int(config.get("AI_QUALITY_SAMPLE_CHARS", 16_000))

    combined = len(original_markdown or "") + len(final_markdown or "")
    scope = "full" if combined <= sample_chars else "sampled"
    per_doc_limit = max(2_000, sample_chars // 2)

    original_for_prompt = original_markdown if scope == "full" else _sample_document(original_markdown, per_doc_limit)
    final_for_prompt = final_markdown if scope == "full" else _sample_document(final_markdown, per_doc_limit)

    compact_report = _compact_deterministic_report(deterministic_report)
    before = compact_report["metrics"]["before"]
    after = compact_report["metrics"]["after"]

    system = """\
You are a strict document conversion QA auditor for MarkForge.

Compare raw converted Markdown against final Markdown after cleanup.
Your job is to identify possible content loss, reordering, grammar/text edits, formatting-only changes, and integrity concerns.

Be conservative:
- Do not claim certainty unless evidence is clear.
- Use phrases like "possible" or "no obvious issue detected".
- Never invent sections that are not visible in the provided text or metrics.
- Do not rewrite the document.
- Output JSON only, no Markdown prose.
"""

    user = f"""\
AI cleanup mode: {mode}
Audit scope: {scope}

Compact deterministic comparison JSON:
{json.dumps(compact_report, ensure_ascii=False, indent=2)}

Original heading outline:
{chr(10).join(before.get('heading_outline_sample', []))}

Final heading outline:
{chr(10).join(after.get('heading_outline_sample', []))}

Original Markdown sample:
--- ORIGINAL START ---
{original_for_prompt}
--- ORIGINAL END ---

Final Markdown sample:
--- FINAL START ---
{final_for_prompt}
--- FINAL END ---

Return exactly this JSON structure:
{{
  "risk_level": "low | medium | high",
  "recommendation": "accept | review_manually | reject_cleanup",
  "summary": "short audit summary",
  "possible_missing_content": [
    {{"severity": "low | medium | high", "topic": "topic or section", "description": "what may be missing and why"}}
  ],
  "possible_reordered_content": [
    {{"severity": "low | medium | high", "topic": "topic or section", "description": "what may have moved"}}
  ],
  "grammar_text_changes": [
    {{"severity": "low | medium | high", "topic": "topic or section", "description": "possible grammar/text change"}}
  ],
  "formatting_changes": [
    {{"severity": "low | medium | high", "topic": "topic or section", "description": "formatting-only change"}}
  ],
  "integrity_concerns": [
    {{"severity": "low | medium | high", "topic": "topic or section", "description": "image/table/code/link concern"}}
  ]
}}
"""

    # Final guardrail: if the prompt is still too large after compacting,
    # shrink the document samples once more. If it remains too large, skip AI
    # audit gracefully and keep the deterministic report.
    estimated_input_tokens = _estimate_tokens(system) + _estimate_tokens(user)
    if estimated_input_tokens + max_output_tokens > safe_input_tokens:
        reduced_limit = max(1_000, per_doc_limit // 3)
        original_for_prompt = _sample_document(original_markdown, reduced_limit)
        final_for_prompt = _sample_document(final_markdown, reduced_limit)
        scope = "sampled-reduced"
        user = f"""\
AI cleanup mode: {mode}
Audit scope: {scope}

Compact deterministic comparison JSON:
{json.dumps(compact_report, ensure_ascii=False, indent=2)}

Original heading outline:
{chr(10).join(before.get('heading_outline_sample', []))}

Final heading outline:
{chr(10).join(after.get('heading_outline_sample', []))}

Original Markdown sample:
--- ORIGINAL START ---
{original_for_prompt}
--- ORIGINAL END ---

Final Markdown sample:
--- FINAL START ---
{final_for_prompt}
--- FINAL END ---

Return exactly this JSON structure:
{{
  "risk_level": "low | medium | high",
  "recommendation": "accept | review_manually | reject_cleanup",
  "summary": "short audit summary",
  "possible_missing_content": [
    {{"severity": "low | medium | high", "topic": "topic or section", "description": "what may be missing and why"}}
  ],
  "possible_reordered_content": [
    {{"severity": "low | medium | high", "topic": "topic or section", "description": "what may have moved"}}
  ],
  "grammar_text_changes": [
    {{"severity": "low | medium | high", "topic": "topic or section", "description": "possible grammar/text change"}}
  ],
  "formatting_changes": [
    {{"severity": "low | medium | high", "topic": "topic or section", "description": "formatting-only change"}}
  ],
  "integrity_concerns": [
    {{"severity": "low | medium | high", "topic": "topic or section", "description": "image/table/code/link concern"}}
  ]
}}
"""
        estimated_input_tokens = _estimate_tokens(system) + _estimate_tokens(user)

    if estimated_input_tokens + max_output_tokens > safe_input_tokens:
        return (
            None,
            token_usage,
            "AI quality report skipped: document is too large for the configured AI audit token budget. "
            "Deterministic quality checks completed successfully.",
        )

    try:
        raw = client.complete(system=system, user=user, max_tokens=max_output_tokens)
        token_usage = _get_last_token_usage(client)
    except LLMError as exc:
        msg = str(exc)
        if "context_length_exceeded" in msg or "maximum context length" in msg:
            return (
                None,
                token_usage,
                "AI quality report skipped: provider context limit exceeded. "
                "Deterministic quality checks completed successfully.",
            )
        return None, token_usage, f"AI quality report failed: {exc}"

    parsed = _parse_ai_json(raw)
    if not parsed:
        return None, token_usage, "AI quality report returned invalid JSON."

    parsed.setdefault("risk_level", deterministic_report["risk_level"])
    parsed.setdefault("recommendation", deterministic_report["recommendation"])
    parsed.setdefault("summary", "AI quality audit completed.")
    for key in (
        "possible_missing_content",
        "possible_reordered_content",
        "grammar_text_changes",
        "formatting_changes",
        "integrity_concerns",
    ):
        if not isinstance(parsed.get(key), list):
            parsed[key] = []

    parsed["scope"] = scope
    return parsed, token_usage, None


def build_quality_report(
    *,
    original_markdown: str,
    final_markdown: str,
    mode: str,
    ai_cleanup_requested: bool,
    ai_applied: bool,
    config: dict | None = None,
) -> dict[str, Any]:
    before = _metrics(original_markdown)
    after = _metrics(final_markdown)
    findings, risk, recommendation, risk_breakdown = _deterministic_findings(before, after)

    before_words = max(1, int(before["word_count"]))
    after_words = int(after["word_count"])

    deterministic = {
        "enabled": True,
        "risk_level": risk,
        "recommendation": recommendation,
        **risk_breakdown,
        "metrics": {
            "before": before,
            "after": after,
            "retention_ratio": after_words / before_words,
            "word_count_delta": after_words - before_words,
            "heading_count_delta": int(after["heading_count"]) - int(before["heading_count"]),
            "image_count_delta": int(after["image_count"]) - int(before["image_count"]),
            "table_line_count_delta": int(after["table_line_count"]) - int(before["table_line_count"]),
        },
        "findings": findings,
    }

    report: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
        "ai_cleanup_requested": ai_cleanup_requested,
        "ai_applied": ai_applied,
        "risk_level": risk,
        "recommendation": recommendation,
        **risk_breakdown,
        "deterministic_report": deterministic,
        "ai_report": None,
        "ai_report_error": None,
        "token_usage": _empty_token_usage(),
    }

    if ai_cleanup_requested and config is not None:
        ai_report, token_usage, error = _ai_quality_report(
            config=config,
            original_markdown=original_markdown,
            final_markdown=final_markdown,
            deterministic_report=deterministic,
            mode=mode,
        )
        report["ai_report"] = ai_report
        report["ai_report_error"] = error
        report["token_usage"] = token_usage

        if ai_report:
            ai_risk = str(ai_report.get("risk_level") or risk).lower()
            combined_risk = _max_severity(risk, ai_risk)
            report["risk_level"] = combined_risk

            # The AI audit may notice additional issues, but it must not downgrade
            # deterministic structure/content/integrity warnings.
            ai_recommendation = str(ai_report.get("recommendation") or recommendation).lower()
            if recommendation != "accept":
                report["recommendation"] = recommendation
            elif ai_recommendation != "accept":
                report["recommendation"] = ai_recommendation
            else:
                report["recommendation"] = _recommendation_for_risk(
                    risk=combined_risk,
                    content_risk=report.get("content_risk_level", "low"),
                    structure_risk=report.get("structure_risk_level", "low"),
                    integrity_risk=report.get("integrity_risk_level", "low"),
                )

    return report


def build_quality_report_markdown(report: dict[str, Any]) -> str:
    deterministic = report.get("deterministic_report") or {}
    metrics = deterministic.get("metrics") or {}
    before = metrics.get("before") or {}
    after = metrics.get("after") or {}
    ai_report = report.get("ai_report") or {}

    lines = [
        "# MarkForge Quality Report",
        "",
        f"- Generated at: `{report.get('generated_at', '')}`",
        f"- AI cleanup requested: `{report.get('ai_cleanup_requested')}`",
        f"- AI cleanup applied: `{report.get('ai_applied')}`",
        f"- AI mode: `{report.get('mode')}`",
        f"- Risk level: **{report.get('risk_level', 'unknown')}**",
        f"- Content risk: **{report.get('content_risk_level', 'unknown')}**",
        f"- Structure risk: **{report.get('structure_risk_level', 'unknown')}**",
        f"- Integrity risk: **{report.get('integrity_risk_level', 'unknown')}**",
        f"- Recommendation: **{report.get('recommendation', 'unknown')}**",
        "",
        "## Deterministic comparison",
        "",
        f"- Word count before: `{before.get('word_count', 0)}`",
        f"- Word count after: `{after.get('word_count', 0)}`",
        f"- Retention ratio: `{metrics.get('retention_ratio', 0):.2%}`",
        f"- Headings before/after: `{before.get('heading_count', 0)}` / `{after.get('heading_count', 0)}`",
        f"- Images before/after: `{before.get('image_count', 0)}` / `{after.get('image_count', 0)}`",
        f"- Table lines before/after: `{before.get('table_line_count', 0)}` / `{after.get('table_line_count', 0)}`",
        f"- Code fences balanced: `{after.get('code_fences_balanced')}`",
        "",
        "### Deterministic findings",
        "",
    ]

    for finding in deterministic.get("findings", []):
        lines.append(
            f"- **{finding.get('severity', 'info')}** / `{finding.get('type', 'finding')}` / "
            f"{finding.get('topic', 'Document level')}: {finding.get('description', '')}"
        )

    if ai_report:
        lines.extend([
            "",
            "## AI quality audit",
            "",
            f"- Scope: `{ai_report.get('scope', 'unknown')}`",
            f"- Summary: {ai_report.get('summary', '')}",
            "",
        ])
        groups = [
            ("Possible missing content", "possible_missing_content"),
            ("Possible reordered content", "possible_reordered_content"),
            ("Grammar/text changes", "grammar_text_changes"),
            ("Formatting changes", "formatting_changes"),
            ("Integrity concerns", "integrity_concerns"),
        ]
        for title, key in groups:
            lines.extend([f"### {title}", ""])
            items = ai_report.get(key) or []
            if not items:
                lines.append("- No obvious issue detected.")
            else:
                for item in items:
                    lines.append(
                        f"- **{item.get('severity', 'info')}** / {item.get('topic', 'Document level')}: "
                        f"{item.get('description', '')}"
                    )
            lines.append("")
    else:
        lines.extend([
            "",
            "## AI quality audit",
            "",
            "- Not run.",
        ])
        if report.get("ai_report_error"):
            lines.append(f"- Reason: {report['ai_report_error']}")

    return "\n".join(lines).strip() + "\n"
