"""Verify Supabase state after import.

Checks:
  - row count in source_records
  - has_usable_text=true count
  - unique (source_type, source_id) holds (distinct identities == total rows)
  - recent import_runs log

Prints a summary. Works entirely through the Supabase REST API.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.config import get_supabase_client


def _safe_select(client, table: str, columns: str, order: str | None = None, limit: int = 1000):
    """Run a select, returning [] if the table is missing/unknown."""
    try:
        q = client.table(table).select(columns)
        if order:
            col, _, direction = order.partition(".")
            q = q.order(col, desc=(direction == "desc"))
        return q.limit(limit).execute().data or []
    except Exception as exc:  # noqa: BLE001
        msg = str(exc)
        if "PGRST205" in msg or "does not exist" in msg or "Could not find the table" in msg:
            return None
        raise


def main() -> int:
    print("=== Supabase state inspection ===")
    try:
        client = get_supabase_client()
    except Exception as exc:  # noqa: BLE001
        print(f"FAILED to build Supabase client: {str(exc)[:200]}")
        return 1

    rows = _safe_select(client, "source_records", "source_type,source_id,has_usable_text")
    if rows is None:
        print("source_records table not found. Apply migrations first:")
        print("  python scripts/apply_migrations.py")
        print("  (or paste backend/migrations/*.sql into the Supabase SQL editor)")
        return 1

    total = len(rows)
    usable = sum(1 for r in rows if r.get("has_usable_text") is True)
    identities = {(r["source_type"], r["source_id"]) for r in rows}
    distinct = len(identities)
    duplicates = total - distinct

    print(f"source_records rows:        {total}")
    print(f"  unique identities:        {distinct}")
    print(f"  duplicate identities:     {duplicates}")
    print(f"  has_usable_text=true:     {usable}")
    print(f"  identity constraint holds: {'YES' if duplicates == 0 else 'NO'}")

    print("\nimport_runs (most recent first):")
    runs = _safe_select(
        client, "import_runs",
        "filename,total_records,accepted,ignored,replaced,received_at",
        order="received_at.desc", limit=10,
    )
    if runs is None:
        print("  (import_runs table not found)")
    elif not runs:
        print("  (no import runs logged)")
    else:
        print(f"  {'filename':<28}{'total':>6}{'acc':>5}{'ign':>5}{'rep':>5}  received_at")
        for r in runs:
            fn = (r.get("filename") or "").split("\\")[-1].split("/")[-1] or "(none)"
            print(
                f"  {fn:<28}{r.get('total_records','')!s:>6}"
                f"{r.get('accepted','')!s:>5}{r.get('ignored','')!s:>5}"
                f"{r.get('replaced','')!s:>5}  {r.get('received_at','')}"
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
