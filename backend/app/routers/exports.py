"""Exports router — bundle generation and download endpoints.

Endpoints:
  POST /export                        — generate a new export bundle
  GET  /export-runs                   — list all export run summaries
  GET  /export/download/{run_id}      — stream the manifest.json for a run
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse

from app.config import ENV, KOLKATA, get_supabase_client
from app.models.schemas import ExportRunSummary
from app.services.export_service import generate_export

logger = logging.getLogger(__name__)

router = APIRouter(tags=["exports"])

# Default export root — can be overridden via EXPORT_ROOT env var
_DEFAULT_EXPORT_ROOT = Path(__file__).resolve().parent.parent.parent / "exports"


def _export_root() -> str:
    return ENV.get("EXPORT_ROOT", str(_DEFAULT_EXPORT_ROOT))


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


@router.post("/export", status_code=status.HTTP_201_CREATED)
def create_export() -> dict:
    """Generate a new export bundle.

    Marks all prior export_runs as not-current, writes bundle files to disk,
    and inserts a new export_runs row. Returns metadata (no file content).
    """
    root = _export_root()
    os.makedirs(root, exist_ok=True)
    try:
        result = generate_export(root)
    except RuntimeError as exc:
        logger.error("Export generation failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected error during export generation")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Export generation failed",
        ) from exc
    return result


@router.get("/export-runs", response_model=list[ExportRunSummary])
def list_export_runs() -> list[dict]:
    """Return all export run summaries, most recent first."""
    client = get_supabase_client()
    try:
        resp = client.table("export_runs").select(
            "id, is_current, bundle_path, manifest_path, created_at"
        ).order("created_at", desc=True).execute()
    except Exception as exc:
        logger.exception("Error fetching export runs")
        raise HTTPException(status_code=500, detail="Failed to fetch export runs") from exc

    rows = resp.data or []
    return [
        {
            "id": row["id"],
            "is_current": row.get("is_current", False),
            "bundle_path": row.get("bundle_path"),
            "manifest_path": row.get("manifest_path"),
            "created_at": _to_kolkata(row.get("created_at")),
        }
        for row in rows
    ]


@router.get("/export/current")
def current_export() -> dict:
    """Return the current bundle's manifest (JSON) for in-app inspection."""
    root = Path(_export_root())
    marker = root / "CURRENT"
    if not marker.exists():
        raise HTTPException(status_code=404, detail="No export generated yet")
    name = marker.read_text(encoding="utf-8").strip()
    manifest = root / name / "manifest.json"
    if not manifest.exists():
        raise HTTPException(status_code=404, detail="Current manifest missing on disk")
    import json
    return json.loads(manifest.read_text(encoding="utf-8"))


@router.get("/export/current/zip")
def download_current_zip():
    """Download the current export bundle as a zip archive."""
    root = Path(_export_root())
    marker = root / "CURRENT"
    if not marker.exists():
        raise HTTPException(status_code=404, detail="No export generated yet")
    name = marker.read_text(encoding="utf-8").strip()
    zip_path = root / f"{name}.zip"
    if not zip_path.exists():
        raise HTTPException(status_code=404, detail="Current bundle zip missing on disk")
    return FileResponse(path=str(zip_path), media_type="application/zip", filename=f"{name}.zip")


@router.get("/export/download/{run_id}")
def download_manifest(run_id: str):
    """Stream the manifest.json for a given export run.

    Returns the manifest file as application/json for download.
    """
    client = get_supabase_client()
    try:
        resp = client.table("export_runs").select(
            "id, manifest_path"
        ).eq("id", run_id).limit(1).execute()
    except Exception as exc:
        logger.exception("Error fetching export run: %s", run_id)
        raise HTTPException(status_code=500, detail="Failed to fetch export run") from exc

    rows = resp.data or []
    if not rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Export run not found: {run_id}",
        )

    manifest_path = rows[0].get("manifest_path")
    if not manifest_path or not Path(manifest_path).exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Manifest file not found on disk",
        )

    return FileResponse(
        path=manifest_path,
        media_type="application/json",
        filename=f"manifest_{run_id[:8]}.json",
    )
