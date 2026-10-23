"""Imports router — delivery ingestion endpoints.

Endpoints:
  POST /import        — JSON body or multipart file upload
  GET  /import-runs   — list all import run summaries

POST /import accepts:
  1. JSON body: {"revision": int, "records": [...]}
  2. Multipart file upload: file field containing the delivery JSON

SHA-256 checksum is computed from raw bytes before parsing.
No raw source data is included in error messages.

Implementation note:
  FastAPI does not allow a File() parameter and a Pydantic body model in the
  same endpoint signature.  We therefore use a raw Request body path for the
  JSON branch and a separate /import/upload endpoint alias for the multipart
  branch — both resolve to the same import_delivery() call.
"""
from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, File, HTTPException, Request, UploadFile, status
from pydantic import ValidationError

from app.config import KOLKATA, get_supabase_client
from app.importer import import_delivery
from app.models.schemas import ImportRequest, ImportRunSummary

logger = logging.getLogger(__name__)

router = APIRouter(tags=["imports"])


def _to_kolkata(ts: str | None) -> str | None:
    if not ts:
        return None
    try:
        s = ts.strip()
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(KOLKATA).isoformat()
    except (ValueError, TypeError):
        return ts


def _sanitise_errors(errors: list) -> list:
    """Strip raw source data from error dicts; truncate long detail strings."""
    result = []
    for err in errors:
        if not isinstance(err, dict):
            result.append(err)
            continue
        sanitised = {k: v for k, v in err.items() if k not in ("source_payload", "transcript")}
        if "detail" in sanitised and len(str(sanitised.get("detail", ""))) > 300:
            sanitised["detail"] = str(sanitised["detail"])[:300] + "…"
        result.append(sanitised)
    return result


def _run_import(raw_bytes: bytes, filename: str | None) -> dict:
    """Shared import execution: parse, checksum, call import_delivery."""
    checksum = hashlib.sha256(raw_bytes).hexdigest()

    try:
        payload = json.loads(raw_bytes.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "invalid_json", "message": "Body is not valid JSON"},
        ) from exc

    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "invalid_structure", "message": "Root must be a JSON object"},
        )

    try:
        req = ImportRequest(**payload)
    except (ValidationError, TypeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "validation_error", "message": "Missing or invalid revision/records fields"},
        ) from exc

    result = import_delivery(
        records=req.records,
        revision=req.revision,
        filename=filename,
        checksum=checksum,
    )

    errors = _sanitise_errors(result.get("errors", []))
    return {
        "total": result.get("total", len(req.records)),
        "accepted": result.get("accepted", 0),
        "ignored": result.get("ignored", 0),
        "replaced": result.get("replaced", 0),
        "error_count": len(errors),
        "errors": errors,
        "checksum": checksum,
        "filename": filename,
    }


@router.post("/import", status_code=status.HTTP_200_OK)
async def import_json(request: Request) -> dict:
    """Import a delivery from a JSON request body.

    Body: {"revision": int, "records": [...]}
    Checksum is computed from the raw request bytes.
    Error messages never include raw source data.
    """
    raw_bytes = await request.body()
    if not raw_bytes:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "empty_body", "message": "Request body is empty"},
        )
    return _run_import(raw_bytes, filename=None)


@router.post("/import/upload", status_code=status.HTTP_200_OK)
async def import_file(file: UploadFile = File(...)) -> dict:
    """Import a delivery from a multipart file upload.

    The uploaded file must contain the delivery JSON:
      {"revision": int, "records": [...]}
    Checksum is computed from the raw file bytes.
    Error messages never include raw source data.
    """
    raw_bytes = await file.read()
    return _run_import(raw_bytes, filename=file.filename)


@router.get("/import-runs", response_model=list[ImportRunSummary])
def list_import_runs() -> list[dict]:
    """Return all import run summaries, most recent first."""
    client = get_supabase_client()
    try:
        resp = client.table("import_runs").select(
            "id, filename, received_at, total_records, accepted, ignored, replaced, errors"
        ).order("received_at", desc=True).execute()
    except Exception as exc:
        logger.exception("Error fetching import runs")
        raise HTTPException(status_code=500, detail="Failed to fetch import runs") from exc

    rows = resp.data or []
    result = []
    for row in rows:
        errors = row.get("errors") or []
        error_count = len(errors) if isinstance(errors, list) else 0
        result.append({
            "id": row["id"],
            "filename": row.get("filename"),
            "received_at": _to_kolkata(row.get("received_at")),
            "total_records": row.get("total_records"),
            "accepted": row.get("accepted"),
            "ignored": row.get("ignored"),
            "replaced": row.get("replaced"),
            "error_count": error_count,
        })
    return result
