"""
tests/unit/test_converters.py
─────────────────────────────────────────────────────────────────────────────
Unit tests for the converter registry and abstract base.
These tests do NOT perform real file conversion — they verify the
dispatch logic and error paths.
"""

import pytest

from app.converters import ConversionError, get_converter, supported_extensions


def test_supported_extensions_returns_all_four():
    exts = supported_extensions()
    assert {".docx", ".pdf", ".odt", ".doc"} == exts


def test_get_converter_returns_correct_class():
    from app.converters.docx_converter import DocxConverter
    from app.converters.pdf_converter import PdfConverter

    assert isinstance(get_converter(".docx", config={}), DocxConverter)
    assert isinstance(get_converter(".pdf", config={}), PdfConverter)


def test_get_converter_case_insensitive():
    from app.converters.docx_converter import DocxConverter

    assert isinstance(get_converter(".DOCX", config={}), DocxConverter)


def test_get_converter_unsupported_raises():
    with pytest.raises(ConversionError, match="Unsupported format"):
        get_converter(".xyz", config={})