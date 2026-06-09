"""
app/converters/doc_converter.py
─────────────────────────────────────────────────────────────────────────────
Converts legacy binary .doc → Markdown.

Pipeline:
    LibreOffice headless  →  .docx  →  DocxConverter
    (fallback: pandoc direct .doc → gfm)
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile
from pathlib import Path

from .base import AbstractConverter, ConversionError, ConversionResult
from .docx_converter import DocxConverter

logger = logging.getLogger(__name__)


class DocConverter(AbstractConverter):
    supported_extensions = frozenset({".doc"})

    def convert(self, path: Path) -> ConversionResult:
        soffice = self.config.get("LIBREOFFICE_BIN", "soffice")
        pandoc  = self.config.get("PANDOC_BIN", "pandoc")

        if shutil.which(soffice):
            return self._via_libreoffice(path, soffice)
        if shutil.which(pandoc):
            logger.warning("LibreOffice not found — falling back to pandoc for .doc")
            return self._via_pandoc(path, pandoc)

        raise ConversionError(
            "Cannot convert .doc: neither LibreOffice nor pandoc is available."
        )

    def _via_libreoffice(self, path: Path, soffice: str) -> ConversionResult:
        with tempfile.TemporaryDirectory(prefix="markforge-lo-") as tmp:
            cmd = [
                soffice, "--headless", "--norestore",
                "--convert-to", "docx",
                "--outdir", tmp,
                str(path),
            ]
            try:
                proc = subprocess.run(
                    cmd, capture_output=True, text=True, timeout=120, check=True,
                )
            except subprocess.CalledProcessError as exc:
                raise ConversionError(
                    f"LibreOffice failed (exit {exc.returncode}): {exc.stderr[:500]}"
                ) from exc
            except subprocess.TimeoutExpired as exc:
                raise ConversionError("LibreOffice timed out (120s).") from exc

            docx_path = Path(tmp) / (path.stem + ".docx")
            if not docx_path.exists():
                # LibreOffice sometimes names it differently
                candidates = list(Path(tmp).glob("*.docx"))
                if not candidates:
                    raise ConversionError(
                        f"LibreOffice produced no .docx. stderr: {proc.stderr[:300]}"
                    )
                docx_path = candidates[0]

            result = DocxConverter(config=self.config).convert(docx_path)

            for line in (proc.stderr or "").strip().splitlines():
                if line.strip():
                    result.warnings.append(f"libreoffice: {line.strip()}")

            return result

    def _via_pandoc(self, path: Path, pandoc: str) -> ConversionResult:
        cmd = [pandoc, str(path), "--from", "doc", "--to", "gfm", "--wrap", "none"]
        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=60, check=True,
            )
        except subprocess.CalledProcessError as exc:
            raise ConversionError(
                f"pandoc failed on .doc (exit {exc.returncode}): {exc.stderr[:500]}"
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise ConversionError("pandoc timed out (60s).") from exc

        warnings = [
            f"pandoc: {l.strip()}"
            for l in (proc.stderr or "").strip().splitlines() if l.strip()
        ]
        return ConversionResult(markdown=proc.stdout.strip(), warnings=warnings)