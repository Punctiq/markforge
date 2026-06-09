"""
app/models/schemas.py
─────────────────────────────────────────────────────────────────────────────
Data contracts for API request/response structures.

Using plain dataclasses (stdlib) keeps things lightweight — marshmallow is
available for full serialisation/validation when needed (see imports below).

These are used for:
    - Type-checking in service methods
    - Unit testing without spinning up Flask
    - Documentation (type hints are self-documenting)
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ConversionStats:
    """Metadata produced by the conversion pipeline."""

    duration_ms: int
    ai_applied: bool
    fixes: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class ConversionResponse:
    """Full response returned by POST /api/v1/convert."""

    markdown: str
    filename: str
    stats: ConversionStats

    def to_dict(self) -> dict:
        """Serialise to a plain dict suitable for jsonify()."""
        return {
            "markdown": self.markdown,
            "filename": self.filename,
            "stats": {
                "duration_ms": self.stats.duration_ms,
                "ai_applied": self.stats.ai_applied,
                "fixes": self.stats.fixes,
                "warnings": self.stats.warnings,
            },
        }