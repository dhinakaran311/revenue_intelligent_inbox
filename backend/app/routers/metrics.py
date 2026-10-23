"""Metrics router — dashboard KPI and definitions endpoints.

Endpoints:
  GET /metrics/dashboard  — aggregated dashboard metrics
  GET /definitions        — metric definition reference
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from app.models.schemas import DashboardMetrics, MetricDefinitions
from app.services import metric_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["metrics"])


@router.get("/metrics/dashboard", response_model=DashboardMetrics)
def dashboard_metrics() -> dict:
    """Return aggregated dashboard metrics.

    Calls and meetings are always listed separately (DATA RULE 4).
    Counts are derived from Asia/Kolkata activity dates (DATA RULE 3).
    """
    try:
        return metric_service.get_dashboard_metrics()
    except Exception as exc:
        logger.exception("Error computing dashboard metrics")
        raise HTTPException(status_code=500, detail="Failed to compute dashboard metrics") from exc


@router.get("/definitions", response_model=MetricDefinitions)
def metric_definitions() -> dict:
    """Return metric definition reference (scope, period, timezone notes, person-role notes)."""
    return MetricDefinitions().model_dump()
