"""Pydantic v2 schemas for the Revenue Intelligence Inbox API.

All timestamps are stored in UTC by Supabase but serialised as Asia/Kolkata
(UTC+05:30) strings before being included in any response. The serialisation
happens in the service layer; the schemas just carry ``str`` or ``datetime``
fields so that FastAPI can validate outgoing data correctly.

DATA_RULES enforced:
  - ``person_role`` is always 'rep' (calls) or 'organizer' (meetings); never merged.
  - ``has_manual_route`` / ``manual_route`` fields are always present (never omitted).
  - ``analysis_source`` distinguishes 'prepared' vs 'runtime' labels.
"""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Shared / primitive
# ---------------------------------------------------------------------------

class RouteItem(BaseModel):
    """A single suggested route entry (from analysis or manual override)."""

    model_config = ConfigDict(populate_by_name=True)

    route_id: str
    label: str
    rationale: Optional[str] = None
    evidence_ref: Optional[str] = None
    is_manual: bool = False


class ManualRoute(BaseModel):
    """An active (or recently reset) manual route decision."""

    model_config = ConfigDict(populate_by_name=True)

    route_id: str
    rationale: Optional[str] = None
    author: Optional[str] = None
    is_active: bool
    created_at: str  # ISO-8601 in Asia/Kolkata
    reset_at: Optional[str] = None  # ISO-8601 in Asia/Kolkata when deactivated


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

class AnalysisSummary(BaseModel):
    """The latest analysis for a record."""

    model_config = ConfigDict(populate_by_name=True)

    analysis_id: str
    suggested_routes: list[RouteItem] = Field(default_factory=list)
    concise_output: Optional[str] = None
    evidence_refs: Optional[Any] = None          # jsonb — pass through as-is
    what_established: Optional[str] = None
    what_not_established: Optional[str] = None
    next_action: Optional[str] = None
    owner: Optional[str] = None
    confidence: Optional[str] = None
    uncertainty: Optional[str] = None
    analysis_source: str                          # 'prepared' | 'runtime'
    source_revision: int
    freshness_label: str                          # e.g. "current" | "stale"


# ---------------------------------------------------------------------------
# Record list / detail
# ---------------------------------------------------------------------------

class RecordSummary(BaseModel):
    """Lightweight record entry — no transcript content."""

    model_config = ConfigDict(populate_by_name=True)

    source_type: str
    source_id: str
    record_ref: Optional[str] = None
    revision: int
    activity_date: Optional[str] = None          # YYYY-MM-DD (Asia/Kolkata)
    person_name: Optional[str] = None
    person_role: Optional[str] = None            # 'rep' | 'organizer'
    has_usable_text: bool
    intake_state: str
    analysis_state: str
    analysis_source: Optional[str] = None        # 'prepared' | 'runtime' | None
    route_state: str                              # 'has_manual' | 'has_analysis' | 'pending_review' | 'no_text'
    has_manual_route: bool


class RecordDetail(RecordSummary):
    """Full record entry including payloads, analysis, and manual route."""

    # source_payload is included for detail view; secrets must be scrubbed upstream
    source_payload: Optional[dict[str, Any]] = None
    transcript_payload: Optional[dict[str, Any]] = None
    current_analysis: Optional[AnalysisSummary] = None
    manual_route: Optional[ManualRoute] = None


# ---------------------------------------------------------------------------
# Dashboard metrics
# ---------------------------------------------------------------------------

class ActivityByPerson(BaseModel):
    """Per-person-per-source-type activity row (calls and meetings are separate)."""

    model_config = ConfigDict(populate_by_name=True)

    person_name: Optional[str] = None
    person_role: str                             # 'rep' | 'organizer'
    source_type: str                             # 'call' | 'meeting'
    record_count: int


class TextCoverage(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    total: int
    usable: int
    not_usable: int
    pct_usable: float


class RouteSummary(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    has_manual: int
    has_analysis: int
    pending_review: int
    no_text: int


class MetricDefinitions(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    scope: str = "All imported source records"
    period: str = "All-time (no date filter applied)"
    timezone: str = "Asia/Kolkata (UTC+05:30, fixed offset)"
    denominator_note: str = "Percentages use total imported record count as denominator"
    call_person_note: str = "Call metrics use person_role='rep' (rep_name field)"
    meeting_person_note: str = "Meeting metrics use person_role='organizer' (organizer_email field)"
    text_coverage_note: str = (
        "has_usable_text: calls require non-blank payload.transcript; "
        "meetings require >=1 non-blank turn.text in transcript_payload"
    )


class DashboardMetrics(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    activity_by_person: list[ActivityByPerson]
    text_coverage: TextCoverage
    route_summary: RouteSummary
    definitions: MetricDefinitions


# ---------------------------------------------------------------------------
# Import
# ---------------------------------------------------------------------------

class ImportRequest(BaseModel):
    """JSON body for POST /import."""

    model_config = ConfigDict(populate_by_name=True)

    revision: int = Field(..., gt=0, description="Delivery revision (positive integer)")
    records: list[dict[str, Any]] = Field(..., min_length=1)


class ImportRunSummary(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    filename: Optional[str] = None
    received_at: str                             # ISO-8601 in Asia/Kolkata
    total_records: Optional[int] = None
    accepted: Optional[int] = None
    ignored: Optional[int] = None
    replaced: Optional[int] = None
    error_count: int = 0


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

class ExportRunSummary(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    is_current: bool
    bundle_path: Optional[str] = None
    manifest_path: Optional[str] = None
    created_at: str                              # ISO-8601 in Asia/Kolkata


# ---------------------------------------------------------------------------
# Request bodies
# ---------------------------------------------------------------------------

class ManualRouteRequest(BaseModel):
    """Body for POST /records/{source_type}/{source_id}/route."""

    model_config = ConfigDict(populate_by_name=True)

    route_id: str = Field(..., description="Must be one of the VALID_ROUTE_IDS")
    rationale: Optional[str] = None
    author: Optional[str] = None


# ---------------------------------------------------------------------------
# Query-parameter filter bag (used in /records list)
# ---------------------------------------------------------------------------

class RecordListFilters(BaseModel):
    """Optional filters for GET /records."""

    model_config = ConfigDict(populate_by_name=True)

    source_type: Optional[str] = None           # 'call' | 'meeting'
    has_usable_text: Optional[bool] = None
    person: Optional[str] = None                # partial match on person_name


# ---------------------------------------------------------------------------
# Generic API responses
# ---------------------------------------------------------------------------

class ResetRouteResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    deactivated_count: int
    message: str


class HealthResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    status: str                                  # 'ok' | 'degraded'
    supabase: str                                # 'connected' | 'error'
    app_env: str
    detail: Optional[str] = None
