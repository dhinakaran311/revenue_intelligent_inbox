"""analysis_contract.py — Versioned Pydantic v2 schema for all analysis outputs.

SCHEMA_VERSION = "1.0"

Rules enforced here:
- At least one route is required per analysis.
- evidence_ref helpers validate that source_id is present and (for meetings) the
  word 'turn' appears so citations stay machine-parseable.
- analysis_source must be either 'prepared' (pre-vetted JSON) or 'runtime'
  (Groq-generated on request).
- owner is None unless the source explicitly names an owner; never inferred.
"""
from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, field_validator

SCHEMA_VERSION = "1.0"


class RouteId(str, Enum):
    deal_next_step = "deal_next_step"
    customer_follow_up = "customer_follow_up"
    sales_coaching = "sales_coaching"
    internal_vendor_action = "internal_vendor_action"
    human_review = "human_review"


class Confidence(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"


class RouteItem(BaseModel):
    route_id: RouteId
    label: str
    rationale: str
    # Calls  → "source_id — \"exact quote\""
    # Meetings → "source_id turn N"
    evidence_ref: str
    is_manual: bool = False


class AnalysisOutput(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    source_type: str
    source_id: str
    source_revision: int
    analysis_source: Literal["prepared", "runtime"]
    suggested_routes: list[RouteItem]
    concise_output: str       # What happened and why it matters
    what_established: str
    what_not_established: str
    next_action: str
    owner: str | None = None  # Only if source explicitly names an owner
    confidence: Confidence
    uncertainty: str

    @field_validator("suggested_routes")
    @classmethod
    def at_least_one_route(cls, v: list[RouteItem]) -> list[RouteItem]:
        if len(v) == 0:
            raise ValueError("At least one route is required")
        return v


# ---------------------------------------------------------------------------
# Evidence-ref validators (used by groq_service to verify LLM output)
# ---------------------------------------------------------------------------

def validate_evidence_ref_call(source_id: str, ref: str) -> bool:
    """Call evidence ref must contain the source_id."""
    return source_id in ref


def validate_evidence_ref_meeting(source_id: str, ref: str) -> bool:
    """Meeting evidence ref must contain the source_id and the word 'turn'."""
    return source_id in ref and "turn" in ref.lower()
