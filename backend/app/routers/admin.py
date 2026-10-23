"""Admin router — reset and health-check endpoints.

Endpoints:
  POST /admin/reset  — truncate all app tables (403 in production)
  GET  /health       — service connectivity status (no credentials exposed)

DATA RULE 9: APP_ENV=production → admin reset must return 403 Forbidden.

Implementation note: the reset uses psycopg2 directly (DATABASE_URL) when
available, because PostgREST cannot execute the server-side DELETE statements
inside reset_app_data() without a row-filter — that limitation makes the RPC
path fail with "DELETE requires a WHERE clause".  psycopg2 is the same path
used by scripts/reset_db.py and scripts/apply_migrations.py.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, status

from app.config import ENV, app_env, get_supabase_client
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


@router.post("/admin/reset", status_code=status.HTTP_200_OK)
def admin_reset() -> dict:
    """Reset all application data (non-production only).

    Returns 403 Forbidden when APP_ENV=production (DATA RULE 9).
    Uses psycopg2 with DATABASE_URL when available; falls back to the
    Supabase RPC (which requires the reset_app_data function to exist).
    """
    if app_env() == "production":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Reset is not allowed in production environment",
        )

    dsn = ENV.get("DATABASE_URL", "").strip()
    try:
        if dsn:
            _reset_via_psycopg2(dsn)
        else:
            # Fallback: RPC path (requires Supabase reset_app_data function)
            client = get_supabase_client()
            client.rpc("reset_app_data", {}).execute()
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
