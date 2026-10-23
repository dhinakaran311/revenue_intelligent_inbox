"""Metrics router — dashboard KPI and definitions endpoints.

Endpoints:
  GET /metrics/dashboard?source_type=&person=  — aggregated dashboard metrics
  GET /definitions                             — metric definition reference
  GET /routes                                  — route taxonomy (ids, labels, definitions, folders)
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.analysis_contract import ROUTE_DEFINITIONS
from app.services import metric_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["metrics"])


@router.get("/metrics/dashboard")
def dashboard_metrics(
    source_type: Optional[str] = Query(None, pattern="^(call|meeting)$"),
    person: Optional[str] = Query(None, description="Exact rep_name or organizer_email"),
) -> dict:
    """Return aggregated dashboard metrics for the filtered selection.

    Call reps and meeting organisers are always listed separately (DATA RULE 4).
    Activity is grouped in Asia/Kolkata (DATA RULE 3).
    """
    try:
        return metric_service.get_dashboard_metrics(source_type=source_type, person=person)
    except Exception as exc:
        logger.exception("Error computing dashboard metrics")
        raise HTTPException(status_code=500, detail="Failed to compute dashboard metrics") from exc


@router.get("/definitions")
def metric_definitions() -> list[dict]:
    """Return the metric definitions shown beside every headline number."""
    return metric_service.DEFINITIONS


@router.get("/routes")
def route_taxonomy() -> list[dict]:
    """Return the routing taxonomy used by analysis, manual correction and export."""
    return [{"route_id": rid, **d} for rid, d in ROUTE_DEFINITIONS.items()]
