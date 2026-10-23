"""Route service — manual route decision management.

DATA RULES enforced:
  2. Manual route decisions are NEVER overwritten by import or analysis;
     only explicit API calls (set / reset) mutate this table.
  1. Identity = exact case-sensitive (source_type, source_id).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.analysis_contract import ROUTE_DEFINITIONS
from app.config import KOLKATA, get_supabase_client

logger = logging.getLogger(__name__)

# All allowed route identifiers — one taxonomy shared with analysis and export.
VALID_ROUTE_IDS: list[str] = list(ROUTE_DEFINITIONS)


def _to_kolkata(ts: str | None) -> str | None:
    """Convert a UTC ISO-8601 string (from Supabase) to Asia/Kolkata ISO string."""
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


def set_manual_route(
    source_type: str,
    source_id: str,
    route_id: str,
    rationale: str | None,
    author: str | None,
) -> dict:
    """Deactivate any existing active manual route, then insert a new active one.

    Returns the newly inserted manual route dict.
    Raises ValueError if route_id is not in VALID_ROUTE_IDS.
    """
    if route_id not in VALID_ROUTE_IDS:
        raise ValueError(
            f"Invalid route_id '{route_id}'. "
            f"Must be one of: {', '.join(VALID_ROUTE_IDS)}"
        )

    client = get_supabase_client()

    # Deactivate existing active routes for this identity (DATA RULE 2: only
    # explicit API calls mutate this table).
    now_utc = datetime.now(tz=timezone.utc).isoformat()
    client.table("manual_route_decisions").update(
        {"is_active": False, "reset_at": now_utc}
    ).eq("source_type", source_type).eq("source_id", source_id).eq(
        "is_active", True
    ).execute()

    # Insert the new active route
    insert_resp = client.table("manual_route_decisions").insert({
        "source_type": source_type,
        "source_id": source_id,
        "route_id": route_id,
        "rationale": rationale,
        "author": author,
        "is_active": True,
    }).execute()

    inserted = (insert_resp.data or [{}])[0]
    return {
        "route_id": inserted.get("route_id", route_id),
        "rationale": inserted.get("rationale", rationale),
        "author": inserted.get("author", author),
        "is_active": inserted.get("is_active", True),
        "created_at": _to_kolkata(inserted.get("created_at")),
        "reset_at": _to_kolkata(inserted.get("reset_at")),
    }


def reset_manual_route(source_type: str, source_id: str) -> dict:
    """Deactivate all active manual routes for this identity.

    Sets is_active=false and reset_at=now() (UTC).
    Returns count of deactivated routes.
    """
    client = get_supabase_client()

    now_utc = datetime.now(tz=timezone.utc).isoformat()
    resp = client.table("manual_route_decisions").update(
        {"is_active": False, "reset_at": now_utc}
    ).eq("source_type", source_type).eq("source_id", source_id).eq(
        "is_active", True
    ).execute()

    deactivated = len(resp.data or [])
    return {
        "deactivated_count": deactivated,
        "message": (
            f"Deactivated {deactivated} manual route(s) for "
            f"{source_type}/{source_id}."
        ),
    }


def get_active_manual_route(source_type: str, source_id: str) -> dict | None:
    """Return the active manual route for the identity, or None if none exists."""
    client = get_supabase_client()

    resp = client.table("manual_route_decisions").select("*").eq(
        "source_type", source_type
    ).eq("source_id", source_id).eq("is_active", True).limit(1).execute()

    rows = resp.data or []
    if not rows:
        return None
    mr = rows[0]
    return {
        "route_id": mr.get("route_id", ""),
        "rationale": mr.get("rationale"),
        "author": mr.get("author"),
        "is_active": mr.get("is_active", True),
        "created_at": _to_kolkata(mr.get("created_at")),
        "reset_at": _to_kolkata(mr.get("reset_at")),
    }
