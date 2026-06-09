"""
app/services/file_service.py
─────────────────────────────────────────────────────────────────────────────
Upload validation, temp file lifecycle, MIME verification.
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path

from werkzeug.datastructures import FileStorage

logger = logging.getLogger(__name__)


class FileService:
    def __init__(self, config: dict) -> None:
        self.temp_dir = Path(config["UPLOAD_TEMP_DIR"])
        self.allowed_extensions: frozenset[str] = config.get(
            "ALLOWED_EXTENSIONS", frozenset({".docx", ".pdf", ".odt", ".doc"})
        )
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    # Maps extension → acceptable MIME prefixes
    _MIME_MAP: dict[str, tuple[str, ...]] = {
        ".docx": (
            "application/vnd.openxmlformats",
            "application/zip",          # some tools emit this for docx
        ),
        ".pdf":  ("application/pdf",),
        ".odt":  (
            "application/vnd.oasis",
            "application/zip",          # odt is also a zip
        ),
        ".doc":  (
            "application/msword",
            "application/vnd.ms-",
            "application/octet-stream", # old Word on some Linux libmagic
            "application/x-ole-storage",
        ),
    }

    def save_temp(self, upload: FileStorage) -> Path:
        original_name = upload.filename or ""
        extension = Path(original_name).suffix.lower()

        if extension not in self.allowed_extensions:
            raise ValueError(
                f"Unsupported format '{extension}'. "
                f"Allowed: {', '.join(sorted(self.allowed_extensions))}"
            )

        unique_name = f"{uuid.uuid4().hex}{extension}"
        tmp_path = self.temp_dir / unique_name
        upload.save(str(tmp_path))
        logger.debug("Saved upload → %s (%d bytes)", tmp_path, tmp_path.stat().st_size)

        self._verify_mime(tmp_path, extension)
        return tmp_path

    def cleanup(self, path: Path) -> None:
        try:
            if path and path.exists():
                path.unlink()
                logger.debug("Cleaned up %s", path)
        except OSError as exc:
            logger.warning("Could not delete %s: %s", path, exc)

    def _verify_mime(self, path: Path, extension: str) -> None:
        try:
            import magic
            detected: str = magic.from_file(str(path), mime=True)
            allowed = self._MIME_MAP.get(extension, ())
            if allowed and not any(detected.startswith(m) for m in allowed):
                path.unlink(missing_ok=True)
                raise ValueError(
                    f"MIME '{detected}' does not match extension '{extension}'. "
                    "File may be corrupted or misnamed."
                )
            logger.debug("MIME OK: %s → %s", extension, detected)
        except ImportError:
            logger.warning("python-magic not available — skipping MIME check.")