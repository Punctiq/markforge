"""
app/converters/odt_converter.py
─────────────────────────────────────────────────────────────────────────────
Converts .odt → Markdown via pandoc subprocess (GFM output).
pandoc 3.x handles ODT very well natively.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from .base import AbstractConverter, ConversionError, ConversionResult


class OdtConverter(AbstractConverter):
    supported_extensions = frozenset({".odt"})

    def convert(self, path: Path) -> ConversionResult:
        pandoc_bin: str = self.config.get("PANDOC_BIN", "pandoc")

        if not shutil.which(pandoc_bin):
            raise ConversionError(
                f"pandoc not found at '{pandoc_bin}'. "
                "Install: https://pandoc.org/installing.html"
            )

        cmd = [
            pandoc_bin,
            str(path),
            "--from", "odt",
            "--to", "gfm",
            "--wrap", "none",
        ]

        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=60, check=True,
            )
        except subprocess.CalledProcessError as exc:
            raise ConversionError(
                f"pandoc failed (exit {exc.returncode}): {exc.stderr[:500]}"
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise ConversionError("pandoc timed out (60s).") from exc

        warnings: list[str] = []
        for line in (result.stderr or "").strip().splitlines():
            if line.strip():
                warnings.append(f"pandoc: {line.strip()}")

        return ConversionResult(markdown=result.stdout.strip(), warnings=warnings)