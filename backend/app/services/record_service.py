"""Record service — DB query layer for source_records.

All queries use the Supabase Python client (service-role key).
Secrets are never returned in any output dict.

Timestamp serialisation:
  - Every TIMESTAMPTZ coming from Supabase is UTC; we convert to
    Asia/Kolkata (KOLKATA fixed offset) before returning.

State derivation lives here, in one place, so the inbox, dashboard, brief and
export can never disagree:

  analysis_freshness  no_text  — no usable supplied text (no analysis allowed)
                      current  — latest analysis reflects the current revision
                      stale    — only an older revision has been analysed
                      pending  — usable text, never analysed
  effective_routes    the manual route when one is active, else the suggested
                      routes of the CURRENT-revision analysis, else [].
                      A stale analysis's routes are never presented as current.
  review_state        no_text | awaiting_analysis | manual_override |
                      needs_human_review | suggested

DATA RULES enforced:
  1. Identity = exact case-sensitive (source_type, source_id).
  4. person_role='rep' for calls, 'organizer' for meetings — never merged.
  7. has_usable_text=false → no substantive analysis is returned.
  8. analysis_source labelled 'prepared' or 'runtime' in every response.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.config import KOLKATA, get_supabase_client

logger = logging.getLogger(__name__)

NO_TEXT_MESSAGE = "No usable supplied text — analysis unavailable"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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
        return ts  # return as-is if unparseable


def analysis_extras(an: dict | None) -> dict:
    """Return the schema-1.1 extras stored in the analyses.evidence_refs jsonb.

    Schema 1.0 rows stored a plain list of reference strings there; schema 1.1
    rows store {"evidence": [...], "headline", "priority", "label_check",
    "label_agrees", "record_ref"}. Both shapes are read safely.
    """
    raw = (an or {}).get("evidence_refs")
    if isinstance(raw, dict):
        return raw
    return {"evidence": [], "legacy_refs": raw if isinstance(raw, list) else []}


def _text_status(rec: dict) -> str:
    """Human-readable reason a record does or does not have usable text."""
    if rec.get("has_usable_text"):
        return "Usable supplied text"
    payload = rec.get("source_payload") or {}
    if rec["source_type"] == "call":
        return "No transcript supplied for this call (background call)"
    reason = (rec.get("transcript_payload") or {}).get("unavailable_reason")
    if reason:
        return reason
    return f"No usable turns (recording_status={payload.get('recording_status')})"


def _source_label(rec: dict) -> str | None:
    """The stored upstream label shown next to our own judgement."""
    payload = rec.get("source_payload") or {}
    if rec["source_type"] == "call":
        return payload.get("observed_outcome")
    return payload.get("recording_status")


def _activity_at(rec: dict) -> str | None:
    payload = rec.get("source_payload") or {}
    ts = payload.get("started_at") if rec["source_type"] == "call" else payload.get("starts_at")
    return _to_kolkata(ts)


def _route_ids(an: dict | None) -> list[str]:
    routes = (an or {}).get("suggested_routes") or []
    return [r["route_id"] for r in routes if isinstance(r, dict) and r.get("route_id")]


def derive_state(rec: dict, latest: dict | None, current: dict | None, manual: dict | None) -> dict:
    """Derive freshness, routes and review state for one record.

    ``latest`` is the newest analysis for any revision; ``current`` is the
    newest analysis whose source_revision equals the record's revision.
    """
    has_text = bool(rec.get("has_usable_text"))
    if not has_text:
        freshness = "no_text"
    elif current:
        freshness = "current"
    elif latest:
        freshness = "stale"
    else:
        freshness = "pending"

    suggested = _route_ids(current) if has_text else []
    manual_id = manual["route_id"] if manual else None
    effective = [manual_id] if manual_id else suggested

    if not has_text:
        review_state = "no_text"
    elif manual_id:
        review_state = "manual_override"
    elif freshness != "current":
        review_state = "awaiting_analysis"
    elif "human_review" in suggested:
        review_state = "needs_human_review"
    else:
        review_state = "suggested"

    extras = analysis_extras(current)
    return {
        "analysis_state": freshness,
        "analysis_source": (current or {}).get("analysis_source"),
        "analysis_revision": (latest or {}).get("source_revision"),
        "has_manual_route": manual_id is not None,
        "manual_route_id": manual_id,
        "suggested_route_ids": suggested,
        "effective_route_ids": effective,
        "review_state": review_state,
        "priority": extras.get("priority") if current else None,
        "headline": extras.get("headline") if current else None,
        "label_agrees": extras.get("label_agrees") if current else None,
    }


def load_state(client=None) -> list[dict]:
    """Load every record with its derived state, in one round of queries.

    Returns list rows (no transcript text) sorted by activity time, newest first.
    """
    client = client or get_supabase_client()
    records = client.table("source_records").select(
        "source_type, source_id, record_ref, revision, activity_date, person_name, "
        "person_role, has_usable_text, source_payload, transcript_payload"
    ).execute().data or []

    ps_map = {
        (r["source_type"], r["source_id"]): r
        for r in (client.table("record_processing_state").select(
            "source_type, source_id, intake_state").execute().data or [])
    }
    mr_map = {
        (r["source_type"], r["source_id"]): r
        for r in (client.table("manual_route_decisions").select(
            "source_type, source_id, route_id, rationale, author, created_at"
        ).eq("is_active", True).execute().data or [])
    }
    analyses = client.table("analyses").select(
        "source_type, source_id, source_revision, analysis_source, suggested_routes, "
        "evidence_refs, created_at"
    ).order("created_at", desc=True).execute().data or []

    latest_map: dict[tuple, dict] = {}
    by_key_rev: dict[tuple, dict] = {}
    for a in analyses:
        key = (a["source_type"], a["source_id"])
        latest_map.setdefault(key, a)
        by_key_rev.setdefault((*key, a["source_revision"]), a)

    rows = []
    for rec in records:
        key = (rec["source_type"], rec["source_id"])
        payload = rec.get("source_payload") or {}
        row = {
            "source_type": rec["source_type"],
            "source_id": rec["source_id"],
            "record_ref": rec.get("record_ref"),
            "revision": rec["revision"],
            "activity_date": rec.get("activity_date"),
            "activity_at": _activity_at(rec),
            "person_name": rec.get("person_name"),
            "person_role": rec.get("person_role"),
            "title": payload.get("title") if rec["source_type"] == "meeting" else None,
            "has_usable_text": bool(rec.get("has_usable_text")),
            "text_status": _text_status(rec),
            "source_label": _source_label(rec),
            "is_connected": payload.get("is_connected") if rec["source_type"] == "call" else None,
            "intake_state": ps_map.get(key, {}).get("intake_state", "pending"),
        }
        row.update(derive_state(
            rec,
            latest_map.get(key),
            by_key_rev.get((*key, rec["revision"])),
            mr_map.get(key),
        ))
        # Back-compat field used by older clients/scripts.
        row["route_state"] = {
            "no_text": "no_text", "manual_override": "has_manual",
            "awaiting_analysis": "pending_review",
        }.get(row["review_state"], "has_analysis")
        rows.append(row)

    rows.sort(key=lambda r: r.get("activity_at") or "", reverse=True)
    return rows


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_all_records(filters: dict) -> list[dict]:
    """Return all records with derived state, filtered.

    Supported filter keys:
      - source_type: 'call' | 'meeting'
      - has_usable_text: bool
      - person_name: partial case-insensitive match
      - route_id: matches any effective route
      - review_state: exact match
    """
    rows = load_state()
    if filters.get("source_type"):
        rows = [r for r in rows if r["source_type"] == filters["source_type"]]
    if filters.get("has_usable_text") is not None:
        rows = [r for r in rows if r["has_usable_text"] == filters["has_usable_text"]]
    if filters.get("person_name"):
        needle = filters["person_name"].lower()
        rows = [r for r in rows if needle in (r.get("person_name") or "").lower()]
    if filters.get("route_id"):
        rows = [r for r in rows if filters["route_id"] in r["effective_route_ids"]]
    if filters.get("review_state"):
        rows = [r for r in rows if r["review_state"] == filters["review_state"]]
    return rows


def _fetch(client, table: str, source_type: str, source_id: str):
    return client.table(table).select("*").eq("source_type", source_type).eq("source_id", source_id)


def get_record_detail(source_type: str, source_id: str) -> dict | None:
    """Return full record detail including payloads, analysis, and manual route.

    Returns None when the identity is not found.
    """
    client = get_supabase_client()

    rows = _fetch(client, "source_records", source_type, source_id).limit(1).execute().data or []
    if not rows:
        return None
    rec = rows[0]

    ps = (_fetch(client, "record_processing_state", source_type, source_id)
          .limit(1).execute().data or [{}])[0]
    analyses = (_fetch(client, "analyses", source_type, source_id)
                .order("created_at", desc=True).execute().data or [])
    latest = analyses[0] if analyses else None
    current = next((a for a in analyses if a["source_revision"] == rec["revision"]), None)
    mr_rows = (_fetch(client, "manual_route_decisions", source_type, source_id)
               .eq("is_active", True).limit(1).execute().data or [])
    manual = mr_rows[0] if mr_rows else None
    history = (_fetch(client, "manual_route_decisions", source_type, source_id)
               .order("created_at", desc=True).execute().data or [])

    has_text = bool(rec.get("has_usable_text"))
    payload = rec.get("source_payload") or {}
    row: dict = {
        "source_type": rec["source_type"],
        "source_id": rec["source_id"],
        "record_ref": rec.get("record_ref"),
        "revision": rec["revision"],
        "activity_date": rec.get("activity_date"),
        "activity_at": _activity_at(rec),
        "person_name": rec.get("person_name"),
        "person_role": rec.get("person_role"),
        "title": payload.get("title") if source_type == "meeting" else None,
        "has_usable_text": has_text,
        "text_status": _text_status(rec),
        "source_label": _source_label(rec),
        "is_connected": payload.get("is_connected") if source_type == "call" else None,
        "intake_state": ps.get("intake_state", "pending"),
        "source_payload": payload,
        "transcript_payload": rec.get("transcript_payload"),
        "source_updated_at": _to_kolkata(rec.get("updated_at")),
        "current_analysis": _build_analysis_summary(current, rec["revision"]) if (current and has_text) else None,
        "stale_analysis": (
            _build_analysis_summary(latest, rec["revision"])
            if (has_text and latest and not current) else None
        ),
        "manual_route": _build_manual_route(manual) if manual else None,
        "manual_route_history": [_build_manual_route(m) for m in history],
    }
    row.update(derive_state(rec, latest, current, manual))
    row["route_state"] = {
        "no_text": "no_text", "manual_override": "has_manual",
        "awaiting_analysis": "pending_review",
    }.get(row["review_state"], "has_analysis")
    return row


def get_record_analysis(source_type: str, source_id: str) -> dict | None:
    """Return the latest analysis for the record's current revision.

    Returns None if no analysis exists or the record does not exist.
    """
    client = get_supabase_client()

    sr_rows = client.table("source_records").select(
        "revision, has_usable_text"
    ).eq("source_type", source_type).eq("source_id", source_id).limit(1).execute().data or []
    if not sr_rows:
        return None

    rec = sr_rows[0]
    if not rec.get("has_usable_text", False):
        return {"analysis_state": "no_text", "concise_output": NO_TEXT_MESSAGE}

    an_rows = client.table("analyses").select("*").eq(
        "source_type", source_type
    ).eq("source_id", source_id).eq(
        "source_revision", rec["revision"]
    ).order("created_at", desc=True).limit(1).execute().data or []
    if not an_rows:
        return None
    return _build_analysis_summary(an_rows[0], rec["revision"])


def get_record_evidence(source_type: str, source_id: str) -> dict:
    """Return the readable source text plus the analysis's cited passages.

    - Calls: the full adapted transcript (no invented turns or timings) and
      each cited quote with its character offset so the UI can highlight it.
    - Meetings: every supplied turn with its 1-based number, and the cited
      turn numbers.
    Only evidence from the CURRENT-revision analysis is returned as cited.
    """
    client = get_supabase_client()

    sr_rows = client.table("source_records").select(
        "source_type, source_id, record_ref, revision, has_usable_text, source_payload, transcript_payload"
    ).eq("source_type", source_type).eq("source_id", source_id).limit(1).execute().data or []
    if not sr_rows:
        return {"found": False, "evidence": []}

    rec = sr_rows[0]
    if not rec.get("has_usable_text", False):
        return {
            "found": True,
            "has_usable_text": False,
            "analysis_state": "no_text",
            "message": NO_TEXT_MESSAGE,
            "text_status": _text_status(rec),
            "evidence": [],
            "turns": [],
            "transcript": None,
        }

    an_rows = client.table("analyses").select("evidence_refs").eq(
        "source_type", source_type
    ).eq("source_id", source_id).eq("source_revision", rec["revision"]).order(
        "created_at", desc=True
    ).limit(1).execute().data or []
    cited = analysis_extras(an_rows[0] if an_rows else None).get("evidence") or []

    transcript = None
    turns: list[dict] = []
    evidence: list[dict] = []
    if source_type == "call":
        transcript = (rec.get("source_payload") or {}).get("transcript") or ""
        for e in cited:
            q = e.get("quote", "")
            evidence.append({**e, "type": "call_quote", "offset": transcript.find(q)})
    else:
        raw_turns = (rec.get("transcript_payload") or {}).get("turns") or []
        turns = [
            {
                "turn_number": i + 1,
                "speaker": t.get("speaker"),
                "timecode": t.get("timecode"),
                "text": t.get("text", ""),
            }
            for i, t in enumerate(raw_turns)
        ]
        for e in cited:
            evidence.append({**e, "type": "meeting_turn", "turn_number": e.get("turn")})

    return {
        "found": True,
        "has_usable_text": True,
        "source_type": source_type,
        "source_id": source_id,
        "record_ref": rec.get("record_ref"),
        "revision": rec["revision"],
        "transcript": transcript,
        "turns": turns,
        "evidence": evidence,
    }


# ---------------------------------------------------------------------------
# Internal builders
# ---------------------------------------------------------------------------

def _build_analysis_summary(an: dict, current_revision: int) -> dict:
    """Build analysis summary dict from an analyses row."""
    source_revision = an.get("source_revision", 0)
    freshness = "current" if source_revision == current_revision else "stale"
    extras = analysis_extras(an)

    routes = []
    for r in an.get("suggested_routes") or []:
        if isinstance(r, dict):
            routes.append({
                "route_id": r.get("route_id", ""),
                "label": r.get("label", r.get("route_id", "")),
                "rationale": r.get("rationale"),
                "evidence_ref": r.get("evidence_ref"),
                "priority": r.get("priority"),
                "output": r.get("output"),
                "owner": r.get("owner"),
                "is_manual": False,
            })

    return {
        "analysis_id": an.get("id", ""),
        "headline": extras.get("headline"),
        "priority": extras.get("priority"),
        "suggested_routes": routes,
        "evidence": extras.get("evidence") or [],
        "concise_output": an.get("concise_output"),
        "what_established": an.get("what_established"),
        "what_not_established": an.get("what_not_established"),
        "next_action": an.get("next_action"),
        "owner": an.get("owner"),
        "confidence": an.get("confidence"),
        "uncertainty": an.get("uncertainty"),
        "label_check": extras.get("label_check"),
        "label_agrees": extras.get("label_agrees"),
        "analysis_source": an.get("analysis_source", "prepared"),
        "source_revision": source_revision,
        "freshness_label": freshness,
        "created_at": _to_kolkata(an.get("created_at")),
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
