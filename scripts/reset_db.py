"""Clean reset of all app-owned data for replay testing.

Deletes (atomically via psycopg2 if DATABASE_URL is set, otherwise via
the Supabase RPC): manual_route_decisions, analyses,
record_processing_state, source_records, import_runs, export_runs.

Guarded by APP_ENV != 'production'.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.config import app_env, load_env, ENV


def _reset_via_psycopg2(dsn: str) -> bool:
    import psycopg2
    conn = psycopg2.connect(dsn)
    try:
        with conn:
            with conn.cursor() as cur:
                # FK-safe order: child tables first
                cur.execute("DELETE FROM manual_route_decisions")
                cur.execute("DELETE FROM analyses")
                cur.execute("DELETE FROM record_processing_state")
                cur.execute("DELETE FROM source_records")
                cur.execute("DELETE FROM import_runs")
                cur.execute("DELETE FROM export_runs")
        return True
    finally:
        conn.close()


def _reset_via_rpc() -> bool:
    from app.config import get_supabase_client
    client = get_supabase_client()
    client.rpc("reset_app_data", {}).execute()
    return True


def main() -> int:
    env = app_env()
    if env == "production":
        print(f"REFUSED: APP_ENV='{env}'. reset_db.py will not run in production.")
        return 1

    print(f"Resetting app-owned data (APP_ENV='{env}') ...")
    dsn = ENV.get("DATABASE_URL", "").strip()
    try:
        if dsn:
            _reset_via_psycopg2(dsn)
        else:
            _reset_via_rpc()
    except Exception as exc:  # noqa: BLE001
        print(f"FAILED: {str(exc)[:300]}")
        return 1

    print("OK: manual_route_decisions, analyses, record_processing_state,")
    print("    source_records, import_runs, export_runs cleared.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
