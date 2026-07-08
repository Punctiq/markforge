"""
app/api/v1/convert.py
─────────────────────────────────────────────────────────────────────────────
POST /api/v1/convert

Form fields:
    file          (required)  — document to convert
    ai_cleanup    (optional)  — "true" | "false" (default: "true")
    output_format (optional)  — "zip" | "markdown" | "both" (default: "zip")

Responses:
    output_format=zip       → application/zip binary download
    output_format=markdown  → application/json with markdown string
    output_format=both      → application/json with markdown preview + base64 ZIP
"""

from __future__ import annotations

from flask import current_app, jsonify, request, send_file
import base64
import io

from ...auth.guards import login_required_api
from ...services.conversion_service import ConversionService
from ...services.file_service import FileService
from . import bp


@bp.get("/ai/status")
@login_required_api
def ai_status() -> tuple:
    """Return the active AI cleanup configuration for the web UI.

    Never expose the API key itself. The UI only needs to know whether
    AI cleanup is configured and which provider/model will be used.
    """
    provider = str(current_app.config.get("LLM_PROVIDER", "") or "").strip()
    model = str(current_app.config.get("LLM_MODEL", "") or "").strip()
    base_url = str(current_app.config.get("LLM_BASE_URL", "") or "").strip()
    api_key_configured = bool(str(current_app.config.get("LLM_API_KEY", "") or "").strip())

    return jsonify({
        "configured": bool(provider and model and api_key_configured),
        "provider": provider,
        "model": model,
        "base_url": base_url,
        "api_key_configured": api_key_configured,
        "supported_modes": ["safe", "balanced", "aggressive"],
        "default_mode": "safe",
    }), 200


@bp.post("/convert")
@login_required_api
def convert() -> tuple:
    # ── Validate file presence ──────────────────────────────────────────────
    if "file" not in request.files:
        return jsonify({"error": "No file field in request."}), 400

    upload = request.files["file"]
    if not upload.filename:
        return jsonify({"error": "Empty filename."}), 400

    # ── Parse options ────────────────────────────────────────────────────────
    ai_cleanup = request.form.get("ai_cleanup", "true").lower() != "false"
    ai_cleanup_mode = request.form.get("ai_cleanup_mode", "safe").lower()
    if ai_cleanup_mode not in ("safe", "balanced", "aggressive"):
        ai_cleanup_mode = "safe"

    output_format = request.form.get("output_format", "zip").lower()

    # Supported modes:
    #   zip      -> binary ZIP download, useful for API usage
    #   markdown -> JSON preview only
    #   both     -> JSON preview + ZIP as base64, useful for the web UI
    if output_format not in ("zip", "markdown", "both"):
        output_format = "zip"

    # ── Save temp file ───────────────────────────────────────────────────────
    file_service = FileService(config=current_app.config)
    tmp_path = None
    try:
        tmp_path = file_service.save_temp(upload)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 422

    # ── Convert ──────────────────────────────────────────────────────────────
    try:
        result = ConversionService(config=current_app.config).convert(
            path=tmp_path,
            original_name=upload.filename,
            ai_cleanup=ai_cleanup,
            ai_cleanup_mode=ai_cleanup_mode,
            output_format=output_format,
        )
    except Exception as exc:
        current_app.logger.exception("Conversion failed: %s", exc)
        return jsonify({"error": "Conversion failed. See server logs."}), 500
    finally:
        if tmp_path:
            file_service.cleanup(tmp_path)

    # ── Respond ──────────────────────────────────────────────────────────────
    if output_format == "zip":
        return send_file(
            io.BytesIO(result["zip"]),
            mimetype="application/zip",
            as_attachment=True,
            download_name=result["filename"],
        )

    if output_format == "both":
        zip_base64 = base64.b64encode(result["zip"]).decode("ascii")

        return jsonify({
            "markdown": result["markdown"],
            "markdown_filename": result["markdown_filename"],
            "zip_base64": zip_base64,
            "zip_filename": result["zip_filename"],
            "filename": result["zip_filename"],
            "stats": result["stats"],
        }), 200

    # markdown mode — JSON response (backward compatible)
    return jsonify({
        "markdown": result["markdown"],
        "filename": result["filename"],
        "stats": result["stats"],
    }), 200
