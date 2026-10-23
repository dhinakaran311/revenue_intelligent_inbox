"""Admin router — reset, replay controls and health-check endpoints.

Endpoints:
  POST /admin/reset                    — delete all app-owned rows (403 in production)
  POST /admin/import-sample/{name}     — import a supplied delivery from data/
                                         (name: initial | update; ?reorder=true reverses record order)
  POST /admin/apply-prepared           — apply reviewed analyses whose revision matches the record
  POST /admin/demo-load                — reset → initial → update → apply prepared (final state)
  GET  /health                         — service connectivity status (no credentials exposed)

DATA RULE 9: APP_ENV=production → admin reset must return 403 Forbidden.

Implementation note: the reset uses psycopg2 directly (DATABASE_URL) when
available, because PostgREST cannot execute the server-side DELETE statements
inside reset_app_data() without a row-filter — that limitation makes the RPC
path fail with "DELETE requires a WHERE clause".  psycopg2 is the same path
used by scripts/reset_db.py and scripts/apply_migrations.py.
"""
from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, status

from app.config import BACKEND_DIR, ENV, app_env, get_supabase_client
from app.importer import import_delivery
from app.models.schemas import HealthResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["admin"])

# FK-safe deletion order (child tables first)
_RESET_TABLES = [
    "manual_route_decisions",
    "analyses",
    "record_processing_state",
    "source_records",
    "import_runs",
    "export_runs",
]


def _reset_via_psycopg2(dsn: str) -> None:
    """Atomically delete all app-owned rows via a direct Postgres connection."""
    import psycopg2  # type: ignore

    conn = psycopg2.connect(dsn)
    try:
        with conn:
            with conn.cursor() as cur:
                for table in _RESET_TABLES:
                    cur.execute(f"DELETE FROM {table}")  # noqa: S608
    finally:
        conn.close()


def _reset_via_rest(client) -> None:
    """Delete all rows via PostgREST using a WHERE clause workaround.

    PostgREST refuses bare DELETE (no filter). We filter on primary key
    columns. Tables with UUID `id` pk use neq with nil UUID. The
    `record_processing_state` table uses a composite (source_type, source_id)
    pk — we filter on source_type neq an impossible value instead.
    """
    NIL_UUID = "00000000-0000-0000-0000-000000000000"
    for table in _RESET_TABLES:
        try:
            if table == "record_processing_state":
                # composite PK, no id column — filter on source_type
                client.table(table).delete().neq("source_type", "__never__").execute()
            else:
                client.table(table).delete().neq("id", NIL_UUID).execute()
        except Exception as exc:
            logger.warning("REST reset failed for %s: %s", table, exc)
            raise


SAMPLE_FILES = {"initial": "01_initial.json", "update": "02_update.json"}


def _data_dir() -> Path:
    return Path(ENV.get("DATA_DIR") or (BACKEND_DIR.parent / "data"))


def _forbid_in_production() -> None:
    if app_env() == "production":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Replay controls are disabled in production",
        )


def _import_sample(name: str, reorder: bool) -> dict:
    import json

    if name not in SAMPLE_FILES:
        raise HTTPException(status_code=404, detail=f"Unknown sample '{name}' (use initial or update)")
    path = _data_dir() / SAMPLE_FILES[name]
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"{SAMPLE_FILES[name]} not found in the data directory")
    raw = path.read_bytes()
    delivery = json.loads(raw.decode("utf-8"))
    records = delivery.get("records", [])
    if reorder:
        records = list(reversed(records))
    result = import_delivery(
        records,
        delivery.get("revision"),
        filename=SAMPLE_FILES[name] + (" (reordered)" if reorder else ""),
        checksum=hashlib.sha256(raw).hexdigest(),
    )
    return {"file": SAMPLE_FILES[name], "reordered": reorder, **result}


def _reset_all() -> None:
    dsn = ENV.get("DATABASE_URL", "").strip()
    if dsn:
        try:
            _reset_via_psycopg2(dsn)
            return
        except Exception as psyco_exc:
            logger.warning(
                "psycopg2 reset failed (%s), falling back to REST client",
                type(psyco_exc).__name__,
            )
    _reset_via_rest(get_supabase_client())


@router.post("/admin/import-sample/{name}")
def import_sample(name: str, reorder: bool = Query(False)) -> dict:
    """Import a supplied delivery file (the replay steps, without a file picker)."""
    _forbid_in_production()
    return _import_sample(name, reorder)


@router.post("/admin/apply-prepared")
def apply_prepared_all() -> dict:
    """Apply every reviewed analysis whose revision equals its record's revision.

    Records whose text changed (e.g. M07 before its revision-2 analysis is
    applied) stay 'awaiting analysis' until this runs or a manager applies the
    reviewed analysis from the record page. Manual routes are never touched.
    """
    from app.services.analysis_service import apply_all_prepared

    return {"results": apply_all_prepared()}


@router.post("/admin/demo-load")
def demo_load() -> dict:
    """One action to reach the final post-update state from a clean start."""
    from app.services.analysis_service import apply_all_prepared

    _forbid_in_production()
    try:
        _reset_all()
    except Exception as exc:
        logger.exception("Error during demo-load reset")
        raise HTTPException(status_code=500, detail="Reset failed — database error") from exc
    steps = [_import_sample("initial", False), _import_sample("update", False)]
    return {"imports": steps, "prepared": apply_all_prepared()}


@router.post("/admin/reset", status_code=status.HTTP_200_OK)
def admin_reset() -> dict:
    """Reset all application data (non-production only).

    Returns 403 Forbidden when APP_ENV=production (DATA RULE 9).
    Tries psycopg2 (DATABASE_URL) first; falls back to PostgREST REST
    client when the direct Postgres connection is unavailable (e.g. port
    5432 blocked by network or DNS not resolving).
    """
    if app_env() == "production":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Reset is not allowed in production environment",
        )

    try:
        _reset_all()
    except Exception as exc:
        logger.exception("Error during admin reset")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Reset failed — database error",
        ) from exc

    logger.warning("admin/reset executed in env=%s", app_env())
    return {"status": "ok", "message": "All application data has been reset"}


@router.get("/health", response_model=HealthResponse)
def health_check() -> dict:
    """Return service health status.

    Tests Supabase connectivity with a minimal query.
    Never exposes credentials or connection strings in the response.
    """
    supabase_status = "connected"
    detail: str | None = None

    try:
        client = get_supabase_client()
        # Minimal connectivity test — just count rows in import_runs
        client.table("import_runs").select("id", count="exact").limit(1).execute()
    except RuntimeError as exc:
        # Configuration error (missing env vars)
        supabase_status = "error"
        detail = "Supabase configuration error — check server environment"
        logger.error("Health check: Supabase config error: %s", type(exc).__name__)
    except Exception as exc:
        supabase_status = "error"
        detail = "Supabase connectivity error"
        logger.error("Health check: Supabase error: %s", type(exc).__name__)

    overall = "ok" if supabase_status == "connected" else "degraded"

    return {
        "status": overall,
        "supabase": supabase_status,
        "app_env": app_env(),
        "detail": detail,
    }
