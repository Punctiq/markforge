"""
app/converters/base.py — AbstractConverter + ConversionResult.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ConversionResult:
    """Raw output from a format-specific converter."""
    markdown: str
    warnings: list[str] = field(default_factory=list)
    figures: dict[str, bytes] = field(default_factory=dict)
    # figures: {filename → image_bytes}, e.g. {"figure-1.png": b"..."}


class AbstractConverter(ABC):
    def __init__(self, config: dict) -> None:
        self.config = config

    @abstractmethod
    def convert(self, path: Path) -> ConversionResult: ...

    @property
    @abstractmethod
    def supported_extensions(self) -> frozenset[str]: ...


class ConversionError(Exception):
    """Raised when a converter cannot process the given file."""