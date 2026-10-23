"""Apply the SQL migrations in backend/migrations/*.sql to Supabase.

Tries, in order:
  1. DATABASE_URL            -> psycopg2 direct Postgres (transactional DDL)
  2. SUPABASE_ACCESS_TOKEN   -> Supabase Management API /database/query
  3. Otherwise prints instructions and exits non-zero.

DATABASE_URL (psycopg2) is preferred: it applies DDL over one connection and
reports 'already exists' for re-runs. The Management API path needs a Supabase
personal access token (SUPABASE_ACCESS_TOKEN), NOT the service role key, because
the REST API the service role key unlocks (PostgREST) cannot run DDL such as
CREATE TABLE. If neither credential is present, paste the migration files into
the Supabase SQL editor in the dashboard.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MIGRATIONS_DIR = ROOT / "backend" / "migrations"
ENV_KEYS = ("DATABASE_URL", "SUPABASE_ACCESS_TOKEN", "SUPABASE_URL")


def _load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    p = ROOT / "backend" / ".env"
    if p.exists():
        for raw in p.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.split("#")[0].strip()
    for k in ENV_KEYS:  # real environment variables override .env
        if os.environ.get(k):
            env[k] = os.environ[k]
    return env


def apply_via_psycopg2(dsn: str) -> bool:
    import psycopg2
    from psycopg2 import errors as pg_errors

    conn = psycopg2.connect(dsn)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            for f in sorted(MIGRATIONS_DIR.glob("*.sql")):
                sql = f.read_text(encoding="utf-8")
                try:
                    cur.execute(sql)
                    print(f"  [applied] {f.name}")
                except pg_errors.DuplicateTable:
                    print(f"  [exists]  {f.name}")
                except pg_errors.DuplicateFunction:
                    print(f"  [exists]  {f.name}")
        return True
    finally:
        conn.close()


def apply_via_management_api(token: str, supabase_url: str) -> bool:
    import httpx

    ref = re.sub(r"^https?://([^.]+).*", r"\1", supabase_url)
    base = f"https://api.supabase.com/v1/projects/{ref}/database/query"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    with httpx.Client(timeout=120) as c:
        for f in sorted(MIGRATIONS_DIR.glob("*.sql")):
            sql = f.read_text(encoding="utf-8")
            r = c.post(base, headers=headers, json={"query": sql})
            if r.status_code == 200:
                print(f"  [applied] {f.name}")
            else:
                print(f"  [fail {r.status_code}] {f.name}: {r.text[:150]}")
                return False
    return True


def main() -> int:
    env = _load_env()
    print(f"Applying migrations from {MIGRATIONS_DIR}")

    dsn = env.get("DATABASE_URL")
    if dsn:
        print("[path] psycopg2 (DATABASE_URL)")
        try:
            ok = apply_via_psycopg2(dsn)
            print("Done." if ok else "Failed.")
            return 0 if ok else 1
        except ImportError:
            print("[path] psycopg2 not installed; cannot use DATABASE_URL.")
        except Exception as exc:  # noqa: BLE001
            print(f"[path] psycopg2 failed: {str(exc)[:200]}")
            return 1

    token = env.get("SUPABASE_ACCESS_TOKEN")
    url = env.get("SUPABASE_URL")
    if token and url:
        print("[path] Supabase Management API (SUPABASE_ACCESS_TOKEN)")
        try:
            ok = apply_via_management_api(token, url)
            print("Done." if ok else "Failed.")
            return 0 if ok else 1
        except Exception as exc:  # noqa: BLE001
            print(f"[path] management API failed: {str(exc)[:200]}")
            return 1

    print("[path] no usable DDL credential available.")
    print("To apply migrations, do ONE of:")
    print("  1. Paste backend/migrations/*.sql into the Supabase SQL editor (dashboard).")
    print("  2. Set DATABASE_URL (pooler/direct Postgres URL) in backend/.env and re-run")
    print("     (requires psycopg2-binary installed).")
    print("  3. Set SUPABASE_ACCESS_TOKEN (personal access token) in backend/.env and re-run.")
    print("The service role key alone cannot run DDL via the REST (PostgREST) API.")
    return 2


if __name__ == "__main__":
    sys.exit(main())
