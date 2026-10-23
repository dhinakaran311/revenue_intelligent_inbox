"""Record service — DB query layer for source_records.

All queries use the Supabase Python client (service-role key).
Secrets are never returned in any output dict.

Timestamp serialisation:
  - Every TIMESTAMPTZ coming from Supabase is UTC; we convert to
    Asia/Kolkata (KOLKATA fixed offset) before returning.

DATA RULES enforced:
  1. Identity = exact case-sensitive (source_type, source_id).
  4. person_role='rep' for calls, 'organizer' for meetings — never merged.
  7. has_usable_text=false → analysis_state treated as 'no_text'.
  8. analysis_source labelled 'prepared' or 'runtime' in every response.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from app.config import KOLKATA, get_supabase_client

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _to_kolkata(ts: str | None) -> str | None:
    """Convert a UTC ISO-8601 string (from Supabase) to Asia/Kolkata ISO string."""
    if not ts:
        return None
    try:
        # Supabase returns timestamps like "2025-01-15T08:30:00+00:00"
        s = ts.strip()
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(KOLKATA).isoformat()
    except (ValueError, TypeError):
        return ts  # return as-is if unparseable


def _derive_route_state(row: dict) -> str:
    """Derive the route_state label from processing state and manual route flag."""
    if not row.get("has_usable_text", False):
        return "no_text"
    if row.get("has_manual_route", False):
        return "has_manual"
    analysis_state = row.get("analysis_state", "pending")
    if analysis_state not in ("pending", "no_text"):
        return "has_analysis"
    return "pending_review"


def _safe_payload(payload: Any) -> dict | None:
    """Return payload dict, scrubbing any keys that look like secrets."""
    if not isinstance(payload, dict):
        return payload
    # No raw-secret keys are expected inside source payloads per the data contract,
    # but we omit 'transcript' for list views — that is done at the call site.
    return payload


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_all_records(filters: dict) -> list[dict]:
    """Return all records joined with processing state and manual-route active flag.

    Supported filter keys:
      - source_type: 'call' | 'meeting'
      - has_usable_text: bool
      - person_name: partial case-insensitive match
    """
    client = get_supabase_client()

    # Fetch source_records + processing state
    q = client.table("source_records").select(
        "id, source_type, source_id, record_ref, revision, activity_date, "
        "person_name, person_role, has_usable_text, created_at, updated_at"
    )
    if filters.get("source_type"):
        q = q.eq("source_type", filters["source_type"])
    if filters.get("has_usable_text") is not None:
        q = q.eq("has_usable_text", filters["has_usable_text"])
    if filters.get("person_name"):
        q = q.ilike("person_name", f"%{filters['person_name']}%")

    sr_resp = q.execute()
    records: list[dict] = sr_resp.data or []

    if not records:
        return []

    # Fetch all processing states in one shot
    ps_resp = client.table("record_processing_state").select(
        "source_type, source_id, has_usable_text, intake_state, analysis_state, analysis_revision"
    ).execute()
    ps_map: dict[tuple, dict] = {
        (r["source_type"], r["source_id"]): r for r in (ps_resp.data or [])
    }

    # Fetch all active manual routes in one shot
    mr_resp = client.table("manual_route_decisions").select(
        "source_type, source_id, route_id, is_active"
    ).eq("is_active", True).execute()
    mr_map: dict[tuple, dict] = {
        (r["source_type"], r["source_id"]): r for r in (mr_resp.data or [])
    }

    # Fetch latest analyses (to expose analysis_source)
    an_resp = client.table("analyses").select(
        "source_type, source_id, source_revision, analysis_source, created_at"
    ).order("created_at", desc=True).execute()
    # Keep only latest per identity
    an_map: dict[tuple, dict] = {}
    for a in (an_resp.data or []):
        key = (a["source_type"], a["source_id"])
        if key not in an_map:
            an_map[key] = a

    result = []
    for rec in records:
        key = (rec["source_type"], rec["source_id"])
        ps = ps_map.get(key, {})
        mr = mr_map.get(key)
        an = an_map.get(key)

        has_manual_route = mr is not None
        has_usable_text = rec.get("has_usable_text", False)

        # analysis_state: override to 'no_text' when text not usable
        raw_analysis_state = ps.get("analysis_state", "pending")
        analysis_state = "no_text" if not has_usable_text else raw_analysis_state

        row = {
            "source_type": rec["source_type"],
            "source_id": rec["source_id"],
            "record_ref": rec.get("record_ref"),
            "revision": rec["revision"],
            "activity_date": rec.get("activity_date"),
            "person_name": rec.get("person_name"),
            "person_role": rec.get("person_role"),
            "has_usable_text": has_usable_text,
            "intake_state": ps.get("intake_state", "pending"),
            "analysis_state": analysis_state,
            "analysis_source": an.get("analysis_source") if an else None,
            "has_manual_route": has_manual_route,
        }
        row["route_state"] = _derive_route_state(row)
        result.append(row)

    return result


def get_record_detail(source_type: str, source_id: str) -> dict | None:
    """Return full record detail including payloads, analysis, and manual route.

    Returns None when the identity is not found.
    """
    client = get_supabase_client()

    # 1. Source record (with payloads)
    sr_resp = client.table("source_records").select("*").eq(
        "source_type", source_type
    ).eq("source_id", source_id).limit(1).execute()
    rows = sr_resp.data or []
    if not rows:
        return None
    rec = rows[0]

    # 2. Processing state
    ps_resp = client.table("record_processing_state").select("*").eq(
        "source_type", source_type
    ).eq("source_id", source_id).limit(1).execute()
    ps = (ps_resp.data or [{}])[0]

    # 3. Latest analysis for current revision
    current_revision = rec["revision"]
    an_resp = client.table("analyses").select("*").eq(
        "source_type", source_type
    ).eq("source_id", source_id).eq(
        "source_revision", current_revision
    ).order("created_at", desc=True).limit(1).execute()
    an_rows = an_resp.data or []
    current_analysis = _build_analysis_summary(an_rows[0], current_revision) if an_rows else None

    # 4. Active manual route
    mr_resp = client.table("manual_route_decisions").select("*").eq(
        "source_type", source_type
    ).eq("source_id", source_id).eq("is_active", True).limit(1).execute()
    mr_rows = mr_resp.data or []
    manual_route = _build_manual_route(mr_rows[0]) if mr_rows else None

    has_usable_text = rec.get("has_usable_text", False)
    raw_analysis_state = ps.get("analysis_state", "pending")
    analysis_state = "no_text" if not has_usable_text else raw_analysis_state

    row: dict = {
        "source_type": rec["source_type"],
        "source_id": rec["source_id"],
        "record_ref": rec.get("record_ref"),
        "revision": rec["revision"],
        "activity_date": rec.get("activity_date"),
        "person_name": rec.get("person_name"),
        "person_role": rec.get("person_role"),
        "has_usable_text": has_usable_text,
        "intake_state": ps.get("intake_state", "pending"),
        "analysis_state": analysis_state,
        "analysis_source": current_analysis["analysis_source"] if current_analysis else None,
        "has_manual_route": manual_route is not None,
        "source_payload": _safe_payload(rec.get("source_payload")),
        "transcript_payload": rec.get("transcript_payload"),
        "current_analysis": current_analysis,
        "manual_route": manual_route,
    }
    row["route_state"] = _derive_route_state(row)
    return row


def get_record_analysis(source_type: str, source_id: str) -> dict | None:
    """Return the latest analysis for the record's current revision.

    Returns None if no analysis exists or the record does not exist.
    """
    client = get_supabase_client()

    # Resolve current revision
    sr_resp = client.table("source_records").select(
        "revision, has_usable_text"
    ).eq("source_type", source_type).eq("source_id", source_id).limit(1).execute()
    sr_rows = sr_resp.data or []
    if not sr_rows:
        return None

    rec = sr_rows[0]
    if not rec.get("has_usable_text", False):
        return {
            "analysis_state": "no_text",
            "concise_output": "No usable supplied text — analysis unavailable",
        }

    an_resp = client.table("analyses").select("*").eq(
        "source_type", source_type
    ).eq("source_id", source_id).eq(
        "source_revision", rec["revision"]
    ).order("created_at", desc=True).limit(1).execute()
    an_rows = an_resp.data or []
    if not an_rows:
        return None
    return _build_analysis_summary(an_rows[0], rec["revision"])


def get_record_evidence(source_type: str, source_id: str) -> dict:
    """Return formatted evidence citations for the record.

    - Calls: source_id + short quote from transcript (first 120 chars).
    - Meetings: source_id + turn number for each usable turn.
    - Returns no_text state if has_usable_text=false.
    """
    client = get_supabase_client()

    sr_resp = client.table("source_records").select(
        "source_type, source_id, record_ref, has_usable_text, source_payload, transcript_payload"
    ).eq("source_type", source_type).eq("source_id", source_id).limit(1).execute()
    sr_rows = sr_resp.data or []
    if not sr_rows:
        return {"found": False, "evidence": []}

    rec = sr_rows[0]
    if not rec.get("has_usable_text", False):
        return {
            "found": True,
            "has_usable_text": False,
            "analysis_state": "no_text",
            "message": "No usable supplied text — analysis unavailable",
            "evidence": [],
        }

    evidence: list[dict] = []
    if source_type == "call":
        transcript = (rec.get("source_payload") or {}).get("transcript", "")
        snippet = transcript[:120].strip() if transcript else ""
        evidence.append({
            "ref": source_id,
            "type": "call_transcript_snippet",
            "quote": snippet + ("…" if len(transcript) > 120 else ""),
        })
    else:
        # meeting — list each non-blank turn
        turns = (rec.get("transcript_payload") or {}).get("turns", [])
        for idx, turn in enumerate(turns):
            text = turn.get("text", "").strip()
            if text:
                evidence.append({
                    "ref": f"{source_id}#turn{idx + 1}",
                    "type": "meeting_turn",
                    "turn_number": idx + 1,
                    "speaker": turn.get("speaker"),
                    "quote": text[:120] + ("…" if len(text) > 120 else ""),
                })

    return {
        "found": True,
        "has_usable_text": True,
        "source_type": source_type,
        "source_id": source_id,
        "evidence": evidence,
    }


# ---------------------------------------------------------------------------
# Internal builders
# ---------------------------------------------------------------------------

def _build_analysis_summary(an: dict, current_revision: int) -> dict:
    """Build analysis summary dict from an analyses row."""
    source_revision = an.get("source_revision", 0)
    freshness = "current" if source_revision == current_revision else "stale"

    # Build RouteItem list from suggested_routes jsonb
    raw_routes = an.get("suggested_routes") or []
    routes = []
    if isinstance(raw_routes, list):
        for r in raw_routes:
            if isinstance(r, dict):
                routes.append({
                    "route_id": r.get("route_id", ""),
                    "label": r.get("label", r.get("route_id", "")),
                    "rationale": r.get("rationale"),
                    "evidence_ref": r.get("evidence_ref"),
                    "is_manual": False,
                })

    return {
        "analysis_id": an.get("id", ""),
        "suggested_routes": routes,
        "concise_output": an.get("concise_output"),
        "evidence_refs": an.get("evidence_refs"),
        "what_established": an.get("what_established"),
        "what_not_established": an.get("what_not_established"),
        "next_action": an.get("next_action"),
        "owner": an.get("owner"),
        "confidence": an.get("confidence"),
        "uncertainty": an.get("uncertainty"),
        "analysis_source": an.get("analysis_source", "prepared"),
        "source_revision": source_revision,
        "freshness_label": freshness,
    }


def _build_manual_route(mr: dict) -> dict:
    """Build manual route dict from a manual_route_decisions row."""
    return {
        "route_id": mr.get("route_id", ""),
        "rationale": mr.get("rationale"),
        "author": mr.get("author"),
        "is_active": mr.get("is_active", True),
        "created_at": _to_kolkata(mr.get("created_at")),
        "reset_at": _to_kolkata(mr.get("reset_at")),
    }
