"""Brief router — the 21 August 2026 (Asia/Kolkata) manager brief.

GET /brief returns the prepared, human-reviewed brief (analysis/manager_brief.json)
together with live state for every record it cites, so the page can say when
a cited record has been manually re-routed or is awaiting analysis for a newer
source revision. The brief text itself is fixed to the date and is not
regenerated at runtime; activity numbers come from the current state.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.services.metric_service import get_dashboard_metrics
from app.services.record_service import load_state

logger = logging.getLogger(__name__)

router = APIRouter(tags=["brief"])

BRIEF_PATH = Path(__file__).resolve().parents[3] / "analysis" / "manager_brief.json"


def load_brief() -> dict:
    """The prepared brief enriched with live record state (keyed by identity)."""
    brief = json.loads(BRIEF_PATH.read_text(encoding="utf-8"))
    state = {(r["source_type"], r["source_id"]): r for r in load_state()}
    records = {}
    for ref, ident in brief.get("records", {}).items():
        live = state.get((ident["source_type"], ident["source_id"]))
        records[ref] = {
            **ident,
            "imported": live is not None,
            **({k: live[k] for k in (
                "revision", "review_state", "analysis_state", "has_manual_route",
                "manual_route_id", "effective_route_ids", "has_usable_text", "title", "person_name",
            )} if live else {}),
        }
    brief["records"] = records
    return brief


@router.get("/brief")
def get_brief() -> dict:
    try:
        brief = load_brief()
        metrics = get_dashboard_metrics()
    except Exception as exc:
        logger.exception("Error loading brief")
        raise HTTPException(status_code=500, detail="Failed to load the manager brief") from exc
    brief["activity"] = {
        "totals": metrics["totals"],
        "text_coverage": metrics["text_coverage"],
        "call_reps": metrics["call_reps"],
        "meeting_organisers": metrics["meeting_organisers"],
        "connection": metrics["connection"],
    }
    return brief
