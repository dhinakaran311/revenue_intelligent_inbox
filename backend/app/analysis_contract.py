"""analysis_contract.py — Versioned Pydantic v2 schema for all analysis outputs.

SCHEMA_VERSION = "1.1"  (1.0 documents still validate; new fields are optional)

Rules enforced here:
- At least one route is required per analysis.
- Each route may carry its own destination-specific output (a coaching note is
  not a follow-up task), so one conversation can produce several outputs.
- `evidence` items quote the supplied text. `verify_evidence()` checks every
  quote against the current source text: a call quote must be an exact
  substring of payload.transcript; a meeting quote must be an exact substring
  of the cited 1-based turn. Unverifiable evidence is rejected, not displayed.
- analysis_source must be either 'prepared' (human-reviewed JSON) or 'runtime'
  (Groq-generated on request).
- owner is None unless the source explicitly states who will act; never inferred.
"""
from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, field_validator

SCHEMA_VERSION = "1.1"


class RouteId(str, Enum):
    deal_next_step = "deal_next_step"
    customer_follow_up = "customer_follow_up"
    sales_coaching = "sales_coaching"
    internal_vendor_action = "internal_vendor_action"
    human_review = "human_review"
    log_only = "log_only"


ROUTE_DEFINITIONS: dict[str, dict[str, str]] = {
    "deal_next_step": {
        "label": "Deal / partner next step",
        "folder": "deal_next_steps",
        "definition": "A prospect or partner evaluation with a concrete next step the text supports.",
    },
    "customer_follow_up": {
        "label": "Customer follow-up",
        "folder": "customer_follow_ups",
        "definition": "An existing customer raised a problem or request, or SpendNest made a commitment to them.",
    },
    "sales_coaching": {
        "label": "Sales coaching",
        "folder": "sales_coaching",
        "definition": "A specific, observable behaviour in the conversation worth correcting or reinforcing.",
    },
    "internal_vendor_action": {
        "label": "Internal / product / vendor note",
        "folder": "internal_vendor_notes",
        "definition": "Supplier evaluation, product defect or gap, or internal process knowledge — not customer-facing.",
    },
    "human_review": {
        "label": "Human review",
        "folder": "human_review",
        "definition": "Ambiguity, a source label that conflicts with the text, or a conclusion the evidence cannot support.",
    },
    "log_only": {
        "label": "Log only",
        "folder": "log_only",
        "definition": "A conversation happened but the text supports no follow-up; recorded so it is not lost.",
    },
}


class Confidence(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"


Priority = Literal["high", "medium", "low"]


class EvidenceItem(BaseModel):
    id: str                     # local label, e.g. "E1"
    turn: int | None = None     # 1-based meeting turn; None for calls
    quote: str                  # exact excerpt of the supplied text
    supports: str               # what this passage is used to show


class RouteItem(BaseModel):
    route_id: RouteId
    label: str
    rationale: str
    # Calls  → 'C03 — "exact quote"'; Meetings → 'M07 turn 19'
    evidence_ref: str
    is_manual: bool = False
    priority: Priority = "medium"
    output: str | None = None   # the destination-specific deliverable
    owner: str | None = None    # only when the text states who will act


class AnalysisOutput(BaseModel):
    schema_version: Literal["1.0", "1.1"] = "1.1"
    source_type: str
    source_id: str
    record_ref: str | None = None
    source_revision: int
    analysis_source: Literal["prepared", "runtime"]
    headline: str | None = None
    priority: Priority = "medium"
    suggested_routes: list[RouteItem]
    evidence: list[EvidenceItem] = []
    concise_output: str       # What happened and why it matters
    what_established: str
    what_not_established: str
    next_action: str
    owner: str | None = None  # Only if source explicitly names an owner
    confidence: Confidence
    uncertainty: str
    label_check: str | None = None  # stored source label vs. what the text shows
    label_agrees: bool | None = None  # False when a stored label conflicts with the text

    @field_validator("suggested_routes")
    @classmethod
    def at_least_one_route(cls, v: list[RouteItem]) -> list[RouteItem]:
        if len(v) == 0:
            raise ValueError("At least one route is required")
        return v


# ---------------------------------------------------------------------------
# Evidence verification
# ---------------------------------------------------------------------------

def _norm(s: str) -> str:
    return " ".join(s.split())


def verify_evidence(
    source_type: str,
    evidence: list[dict],
    source_payload: dict | None,
    transcript_payload: dict | None,
) -> list[str]:
    """Return a list of problems; empty means every quote was found verbatim.

    Whitespace is normalised; nothing else is. A meeting quote must sit inside
    the turn it cites, so a correct quote with a wrong turn number fails.
    """
    problems: list[str] = []
    if source_type == "call":
        text = _norm((source_payload or {}).get("transcript") or "")
        for ev in evidence:
            if not text:
                problems.append(f"{ev.get('id')}: record has no call transcript")
            elif _norm(ev.get("quote", "")) not in text:
                problems.append(f"{ev.get('id')}: quote not found in transcript")
        return problems

    turns = (transcript_payload or {}).get("turns") or []
    for ev in evidence:
        n = ev.get("turn")
        if not isinstance(n, int) or n < 1 or n > len(turns):
            problems.append(f"{ev.get('id')}: turn {n} does not exist ({len(turns)} turns)")
            continue
        if _norm(ev.get("quote", "")) not in _norm(turns[n - 1].get("text") or ""):
            problems.append(f"{ev.get('id')}: quote not found in turn {n}")
    return problems


def validate_evidence_ref_call(source_id: str, ref: str, record_ref: str | None = None) -> bool:
    """Call evidence ref must name the record (source_id or record_ref)."""
    return source_id in ref or bool(record_ref and record_ref in ref)


def validate_evidence_ref_meeting(source_id: str, ref: str, record_ref: str | None = None) -> bool:
    """Meeting evidence ref must name the record and a turn."""
    named = source_id in ref or bool(record_ref and record_ref in ref)
    return named and "turn" in ref.lower()
