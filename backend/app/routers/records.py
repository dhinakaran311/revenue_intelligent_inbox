"""Records router — CRUD + analysis + evidence + manual route endpoints.

Endpoints:
  GET  /records                              — list all records (with filters)
  GET  /records/{source_type}/{source_id}   — full record detail
  GET  /records/{source_type}/{source_id}/analysis
  GET  /records/{source_type}/{source_id}/evidence
  POST /records/{source_type}/{source_id}/route
  DELETE /records/{source_type}/{source_id}/route

DATA RULES enforced by the service layer; router enforces:
  - 404 for unknown (source_type, source_id)
  - 422 for invalid route_id (raised as ValueError by route_service)
  - 501 stub for analysis/refresh (Phase 4)
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status

from app.models.schemas import (
    ManualRouteRequest,
    RecordDetail,
    RecordListFilters,
    RecordSummary,
    ResetRouteResponse,
)
from app.services import record_service, route_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/records", tags=["records"])


@router.get("", response_model=list[RecordSummary])
def list_records(
    source_type: Optional[str] = Query(None, description="Filter by source_type: 'call' | 'meeting'"),
    has_usable_text: Optional[bool] = Query(None, description="Filter by has_usable_text flag"),
    person: Optional[str] = Query(None, description="Partial match on person_name (case-insensitive)"),
) -> list[dict]:
    """Return all records matching the given filters.

    Calls and meetings are always returned as separate entries — never merged.
    Transcript content is NOT included in the list view.
    """
    filters = RecordListFilters(
        source_type=source_type,
        has_usable_text=has_usable_text,
        person_name=person,
    )
    try:
        records = record_service.get_all_records(filters.model_dump(exclude_none=True))
    except Exception as exc:
        logger.exception("Error fetching records list")
        raise HTTPException(status_code=500, detail="Failed to fetch records") from exc
    return records


@router.get("/{source_type}/{source_id}", response_model=RecordDetail)
def get_record(source_type: str, source_id: str) -> dict:
    """Return full record detail including transcript, analysis, and manual route."""
    try:
        detail = record_service.get_record_detail(source_type, source_id)
    except Exception as exc:
        logger.exception("Error fetching record detail: %s/%s", source_type, source_id)
        raise HTTPException(status_code=500, detail="Failed to fetch record detail") from exc

    if detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Record not found: source_type='{source_type}', source_id='{source_id}'",
        )
    return detail


@router.get("/{source_type}/{source_id}/analysis")
def get_analysis(source_type: str, source_id: str) -> dict:
    """Return the latest analysis for the record's current revision.

    Returns 404 if the record does not exist.
    Returns a no_text response if has_usable_text=false.
    """
    # First verify the record exists
    try:
        detail = record_service.get_record_detail(source_type, source_id)
    except Exception as exc:
        logger.exception("Error fetching record for analysis: %s/%s", source_type, source_id)
        raise HTTPException(status_code=500, detail="Failed to fetch record") from exc

    if detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Record not found: source_type='{source_type}', source_id='{source_id}'",
        )

    if not detail.get("has_usable_text", False):
        return {
            "source_type": source_type,
            "source_id": source_id,
            "analysis_state": "no_text",
            "concise_output": "No usable supplied text — analysis unavailable",
        }

    try:
        analysis = record_service.get_record_analysis(source_type, source_id)
    except Exception as exc:
        logger.exception("Error fetching analysis: %s/%s", source_type, source_id)
        raise HTTPException(status_code=500, detail="Failed to fetch analysis") from exc

    if analysis is None:
        return {
            "source_type": source_type,
            "source_id": source_id,
            "analysis_state": "pending",
            "concise_output": None,
            "message": "No analysis available yet for this record",
        }
    return {"source_type": source_type, "source_id": source_id, **analysis}


@router.get("/{source_type}/{source_id}/evidence")
def get_evidence(source_type: str, source_id: str) -> dict:
    """Return formatted evidence citations for the record."""
    try:
        evidence = record_service.get_record_evidence(source_type, source_id)
    except Exception as exc:
        logger.exception("Error fetching evidence: %s/%s", source_type, source_id)
        raise HTTPException(status_code=500, detail="Failed to fetch evidence") from exc

    if not evidence.get("found", False):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Record not found: source_type='{source_type}', source_id='{source_id}'",
        )
    return evidence


@router.post("/{source_type}/{source_id}/route", status_code=status.HTTP_201_CREATED)
def set_route(source_type: str, source_id: str, body: ManualRouteRequest) -> dict:
    """Set a manual route decision for a record.

    Deactivates any existing active manual route before inserting the new one.
    Manual routes are NEVER overwritten by import or analysis.
    """
    # Verify the record exists
    try:
        detail = record_service.get_record_detail(source_type, source_id)
    except Exception as exc:
        logger.exception("Error verifying record for route: %s/%s", source_type, source_id)
        raise HTTPException(status_code=500, detail="Failed to verify record") from exc

    if detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Record not found: source_type='{source_type}', source_id='{source_id}'",
        )

    try:
        new_route = route_service.set_manual_route(
            source_type=source_type,
            source_id=source_id,
            route_id=body.route_id,
            rationale=body.rationale,
            author=body.author,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.exception("Error setting manual route: %s/%s", source_type, source_id)
        raise HTTPException(status_code=500, detail="Failed to set manual route") from exc

    return {
        "source_type": source_type,
        "source_id": source_id,
        "manual_route": new_route,
    }


@router.delete("/{source_type}/{source_id}/route", response_model=ResetRouteResponse)
def reset_route(source_type: str, source_id: str) -> dict:
    """Deactivate all active manual routes for this record."""
    # Verify the record exists
    try:
        detail = record_service.get_record_detail(source_type, source_id)
    except Exception as exc:
        logger.exception("Error verifying record for route reset: %s/%s", source_type, source_id)
        raise HTTPException(status_code=500, detail="Failed to verify record") from exc

    if detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Record not found: source_type='{source_type}', source_id='{source_id}'",
        )

    try:
        result = route_service.reset_manual_route(source_type, source_id)
    except Exception as exc:
        logger.exception("Error resetting manual route: %s/%s", source_type, source_id)
        raise HTTPException(status_code=500, detail="Failed to reset manual route") from exc

    return result


@router.post("/{source_type}/{source_id}/analysis/refresh")
def refresh_analysis(source_type: str, source_id: str) -> dict:
    """Trigger runtime analysis refresh using Pinecone retrieval and Groq LLM.

    Tied to the current source revision. Never mutates manual routes.
    """
    from app.services.analysis_service import run_analysis_for_record

    try:
        res = run_analysis_for_record(source_type, source_id, analysis_source="runtime")
    except Exception as exc:
        logger.exception("Error running analysis for %s/%s", source_type, source_id)
        raise HTTPException(status_code=500, detail="Analysis service encountered an internal error") from exc

    status_code = res.get("status")
    if status_code == "not_found":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Record not found: source_type='{source_type}', source_id='{source_id}'",
        )
    if status_code == "no_text":
        return {
            "source_type": source_type,
            "source_id": source_id,
            "status": "no_text",
            "message": "No usable supplied text — analysis unavailable",
        }
    if status_code == "groq_failed":
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Language analysis service failed to generate structured output",
        )
    return {
        "source_type": source_type,
        "source_id": source_id,
        "status": "ok",
        "analysis": res.get("analysis"),
    }

