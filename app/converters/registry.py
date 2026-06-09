"""
app/converters/registry.py
─────────────────────────────────────────────────────────────────────────────
Central registry that maps file extensions to converter classes.

ConversionService calls get_converter(extension) — it never hard-codes
format logic. Adding a new format = add one import + one entry here.

Example:
    from .registry import get_converter

    converter = get_converter(".pdf", config=app.config)
    result = converter.convert(path)
"""

from __future__ import annotations

from .base import AbstractConverter, ConversionError
from .doc_converter import DocConverter
from .docx_converter import DocxConverter
from .odt_converter import OdtConverter
from .pdf_converter import PdfConverter

# ── Registry ──────────────────────────────────────────────────────────────────
# Maps each supported extension to its converter class (not an instance —
# instances are created per-request so they are not shared across threads).
_REGISTRY: dict[str, type[AbstractConverter]] = {
    ".docx": DocxConverter,
    ".pdf": PdfConverter,
    ".odt": OdtConverter,
    ".doc": DocConverter,
}


def get_converter(extension: str, config: dict) -> AbstractConverter:
    """Return an initialised converter for the given file extension.

    Args:
        extension: Lowercased file extension including the dot, e.g. ".pdf".
        config:    Flask app.config dict passed through to the converter.

    Returns:
        An AbstractConverter instance ready to call .convert(path) on.

    Raises:
        ConversionError: If no converter is registered for this extension.
    """
    cls = _REGISTRY.get(extension.lower())
    if cls is None:
        supported = ", ".join(sorted(_REGISTRY))
        raise ConversionError(
            f"Unsupported format '{extension}'. Supported: {supported}"
        )
    return cls(config=config)


def supported_extensions() -> frozenset[str]:
    """Return the set of all currently registered extensions."""
    return frozenset(_REGISTRY.keys())