"""Metric service — dashboard aggregation for the Revenue Intelligence Inbox.

DATA RULES enforced:
  4. Calls and meetings are NEVER merged: person_role='rep' (calls),
     person_role='organizer' (meetings) are always listed separately.
  5. No blending of call-rep metrics with meeting-organizer metrics.
  3. All timestamps displayed in Asia/Kolkata (UTC+05:30).
"""
from __future__ import annotations

import logging

from app.config import get_supabase_client

logger = logging.getLogger(__name__)


def get_dashboard_metrics() -> dict:
    """Return aggregated dashboard metrics.

    Returns a dict with:
      - activity_by_person: [{person_name, person_role, source_type, record_count}]
        (calls and meetings listed separately — never merged)
      - text_coverage: {total, usable, not_usable, pct_usable}
      - route_summary: {has_manual, has_analysis, pending_review, no_text}
      - definitions: MetricDefinitions-compatible dict
    """
    client = get_supabase_client()

    # Fetch all source_records (just the fields we need)
    sr_resp = client.table("source_records").select(
        "source_type, source_id, person_name, person_role, has_usable_text, activity_date"
    ).execute()
    all_records: list[dict] = sr_resp.data or []

    # Fetch all processing states
    ps_resp = client.table("record_processing_state").select(
        "source_type, source_id, analysis_state"
    ).execute()
    ps_map = {
        (r["source_type"], r["source_id"]): r for r in (ps_resp.data or [])
    }

    # Fetch active manual routes
    mr_resp = client.table("manual_route_decisions").select(
        "source_type, source_id"
    ).eq("is_active", True).execute()
    mr_set = {(r["source_type"], r["source_id"]) for r in (mr_resp.data or [])}

    # Fetch latest analyses per identity (to know if analysis exists)
    an_resp = client.table("analyses").select(
        "source_type, source_id, source_revision, created_at"
    ).order("created_at", desc=True).execute()
    an_map: dict[tuple, dict] = {}
    for a in (an_resp.data or []):
        key = (a["source_type"], a["source_id"])
        if key not in an_map:
            an_map[key] = a

    # --- activity_by_person (calls and meetings separate) ---
    # Group by (person_name, person_role, source_type)
    person_counts: dict[tuple, int] = {}
    for rec in all_records:
        group_key = (
            rec.get("person_name"),
            rec.get("person_role"),      # 'rep' | 'organizer'
            rec.get("source_type"),      # 'call' | 'meeting'
        )
        person_counts[group_key] = person_counts.get(group_key, 0) + 1

    activity_by_person = [
        {
            "person_name": k[0],
            "person_role": k[1],
            "source_type": k[2],
            "record_count": v,
        }
        for k, v in sorted(person_counts.items(), key=lambda x: -(x[1]))
    ]

    # --- text_coverage ---
    total = len(all_records)
    usable = sum(1 for r in all_records if r.get("has_usable_text", False))
    not_usable = total - usable
    pct_usable = round((usable / total * 100), 1) if total > 0 else 0.0

    text_coverage = {
        "total": total,
        "usable": usable,
        "not_usable": not_usable,
        "pct_usable": pct_usable,
    }

    # --- route_summary ---
    # Fetch also the source_records revision to match against analysis revision
    sr_rev_resp = client.table("source_records").select(
        "source_type, source_id, revision, has_usable_text"
    ).execute()
    sr_rev_map = {
        (r["source_type"], r["source_id"]): r for r in (sr_rev_resp.data or [])
    }

    counts = {"has_manual": 0, "has_analysis": 0, "pending_review": 0, "no_text": 0}
    for rec in all_records:
        key = (rec["source_type"], rec["source_id"])
        has_usable = rec.get("has_usable_text", False)

        if not has_usable:
            counts["no_text"] += 1
            continue

        if key in mr_set:
            counts["has_manual"] += 1
        elif key in an_map:
            counts["has_analysis"] += 1
        else:
            counts["pending_review"] += 1

    route_summary = {
        "has_manual": counts["has_manual"],
        "has_analysis": counts["has_analysis"],
        "pending_review": counts["pending_review"],
        "no_text": counts["no_text"],
    }

    # --- definitions ---
    definitions = {
        "scope": "All imported source records",
        "period": "All-time (no date filter applied)",
        "timezone": "Asia/Kolkata (UTC+05:30, fixed offset)",
        "denominator_note": "Percentages use total imported record count as denominator",
        "call_person_note": "Call metrics use person_role='rep' (rep_name field)",
        "meeting_person_note": "Meeting metrics use person_role='organizer' (organizer_email field)",
        "text_coverage_note": (
            "has_usable_text: calls require non-blank payload.transcript; "
            "meetings require >=1 non-blank turn.text in transcript_payload"
        ),
    }

    return {
        "activity_by_person": activity_by_person,
        "text_coverage": text_coverage,
        "route_summary": route_summary,
        "definitions": definitions,
    }
