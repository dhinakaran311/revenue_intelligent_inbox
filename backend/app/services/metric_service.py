"""Metric service — dashboard aggregation for the Revenue Intelligence Inbox.

Every number is computed from the current imported state (one row per
identity after revisions), so repeat imports can never inflate it. Filters
(source_type, person) narrow the selected records; every denominator is the
filtered selection unless a definition says otherwise.

DATA RULES enforced:
  4. Call reps (payload.rep_name) and meeting organisers (payload.organizer_email)
     are listed separately and never merged; an organiser is not assumed to be
     a salesperson or an attendee.
  5. Source-reported connection status is reported only over calls with a
     non-null is_connected, with unknowns shown, and is never combined with
     transcript-based judgements.
  3. Activity times are Asia/Kolkata (UTC+05:30).
"""
from __future__ import annotations

import logging
from collections import Counter, defaultdict

from app.analysis_contract import ROUTE_DEFINITIONS
from app.services.record_service import load_state

logger = logging.getLogger(__name__)

DEFINITIONS = [
    {"key": "selected_records", "label": "Selected records",
     "definition": "Distinct (source_type, source_id) identities in the current state that match the filters. "
                   "Repeat imports never add rows. This package is a selected sample, not a whole-team day."},
    {"key": "period", "label": "Period",
     "definition": "21 August 2026, Asia/Kolkata. Calls are dated by payload.started_at and meetings by payload.starts_at. "
                   "Every record falls on that one date, so the hour chart and the person filter carry the detail."},
    {"key": "usable_text", "label": "Usable supplied text",
     "definition": "A call with a non-blank payload.transcript, or a meeting with at least one non-blank transcript turn. "
                   "Coverage = usable ÷ selected records. A missing transcript does not mean the conversation did not happen."},
    {"key": "people", "label": "Call reps vs meeting organisers",
     "definition": "Calls are grouped by payload.rep_name and meetings by payload.organizer_email. An organiser is a calendar "
                   "field, not proof of attendance or a sales role, so the two lists are never merged."},
    {"key": "connection", "label": "Source-reported connection rate",
     "definition": "Calls with is_connected = true ÷ calls with non-null is_connected (unknowns shown separately). This is an upstream "
                   "classification, kept separate from transcript-based judgements, which can disagree with it."},
    {"key": "routes", "label": "Route assignments",
     "definition": "Effective routes: the manager's manual route when set, otherwise the suggested routes of an analysis of the "
                   "CURRENT source revision. One record can carry several routes, so assignments can exceed routed records."},
    {"key": "review_state", "label": "Review state",
     "definition": "no_text: nothing to analyse. awaiting_analysis: text exists but no analysis reflects the current revision. "
                   "needs_human_review: the suggestion includes Human review. manual_override: a manager chose the route. "
                   "suggested: an automated or prepared suggestion not yet overridden."},
    {"key": "label_conflicts", "label": "Source label conflicts",
     "definition": "Records where the stored upstream label (e.g. observed_outcome) or rep_name disagrees with what the transcript shows."},
]


def _pct(n: int, d: int) -> float | None:
    return round(n / d * 100, 1) if d else None


def get_dashboard_metrics(source_type: str | None = None, person: str | None = None) -> dict:
    all_rows = load_state()
    people = {
        "call_reps": sorted({r["person_name"] for r in all_rows if r["source_type"] == "call" and r["person_name"]}),
        "meeting_organisers": sorted({r["person_name"] for r in all_rows if r["source_type"] == "meeting" and r["person_name"]}),
    }

    rows = all_rows
    if source_type:
        rows = [r for r in rows if r["source_type"] == source_type]
    if person:
        rows = [r for r in rows if r["person_name"] == person]

    calls = [r for r in rows if r["source_type"] == "call"]
    meetings = [r for r in rows if r["source_type"] == "meeting"]
    usable = [r for r in rows if r["has_usable_text"]]

    # Activity by day and hour (Asia/Kolkata)
    by_day: dict[str, Counter] = defaultdict(Counter)
    by_hour: dict[str, Counter] = defaultdict(Counter)
    for r in rows:
        by_day[r["activity_date"] or "unknown"][r["source_type"]] += 1
        hour = (r.get("activity_at") or "")[11:13]
        if hour:
            by_hour[f"{hour}:00"][r["source_type"]] += 1

    def person_rows(items: list[dict]) -> list[dict]:
        grouped: dict[str, list[dict]] = defaultdict(list)
        for r in items:
            grouped[r["person_name"] or "(not supplied)"].append(r)
        out = []
        for name, rs in grouped.items():
            known = [r for r in rs if r.get("is_connected") is not None]
            out.append({
                "person": name,
                "records": len(rs),
                "with_text": sum(r["has_usable_text"] for r in rs),
                "needs_attention": sum(
                    r["review_state"] in ("needs_human_review", "awaiting_analysis") or r.get("priority") == "high"
                    for r in rs
                ),
                "connected_source_reported": sum(r.get("is_connected") is True for r in known),
                "connection_known": len(known),
            })
        return sorted(out, key=lambda x: (-x["records"], x["person"]))

    # Text coverage and no-text reasons
    reasons = Counter(r["text_status"] for r in rows if not r["has_usable_text"])

    # Source-reported connection (calls only)
    known = [r for r in calls if r.get("is_connected") is not None]
    connected = sum(r["is_connected"] is True for r in known)

    # Routes
    route_counts = Counter(rid for r in rows for rid in r["effective_route_ids"])
    routed_records = sum(1 for r in rows if r["effective_route_ids"])

    attention = sorted(
        [r for r in rows if r["has_usable_text"] and (
            r.get("priority") == "high" or r["review_state"] in ("needs_human_review", "awaiting_analysis"))],
        key=lambda r: ({"awaiting_analysis": 0}.get(r["review_state"], 1),
                       {"high": 0, "medium": 1, "low": 2}.get(r.get("priority") or "low", 3),
                       r["record_ref"] or ""),
    )

    return {
        "filters": {"source_type": source_type, "person": person},
        "people": people,
        "totals": {"records": len(rows), "calls": len(calls), "meetings": len(meetings)},
        "activity_by_day": [
            {"date": d, "calls": c["call"], "meetings": c["meeting"], "total": c["call"] + c["meeting"]}
            for d, c in sorted(by_day.items())
        ],
        "activity_by_hour": [
            {"hour": h, "calls": c["call"], "meetings": c["meeting"]} for h, c in sorted(by_hour.items())
        ],
        "call_reps": person_rows(calls),
        "meeting_organisers": person_rows(meetings),
        "text_coverage": {
            "usable": len(usable),
            "total": len(rows),
            "pct": _pct(len(usable), len(rows)),
            "calls": {"usable": sum(r["has_usable_text"] for r in calls), "total": len(calls)},
            "meetings": {"usable": sum(r["has_usable_text"] for r in meetings), "total": len(meetings)},
            "no_text_reasons": [{"reason": k, "count": v} for k, v in reasons.most_common()],
        },
        "connection": {
            "connected": connected,
            "known": len(known),
            "unknown": len(calls) - len(known),
            "pct": _pct(connected, len(known)),
        },
        "review_states": dict(Counter(r["review_state"] for r in rows)),
        "freshness": dict(Counter(r["analysis_state"] for r in rows)),
        "manual_overrides": sum(r["has_manual_route"] for r in rows),
        "routes": [
            {"route_id": rid, "label": d["label"], "definition": d["definition"], "records": route_counts.get(rid, 0)}
            for rid, d in ROUTE_DEFINITIONS.items()
        ],
        "route_assignments": sum(route_counts.values()),
        "routed_records": routed_records,
        "label_conflicts": [
            {"record_ref": r["record_ref"], "source_type": r["source_type"], "source_id": r["source_id"],
             "source_label": r["source_label"]}
            for r in rows if r.get("label_agrees") is False
        ],
        "attention": [
            {k: r[k] for k in ("record_ref", "source_type", "source_id", "person_name", "headline",
                               "priority", "review_state", "effective_route_ids", "has_manual_route")}
            for r in attention
        ],
        "definitions": DEFINITIONS,
    }
