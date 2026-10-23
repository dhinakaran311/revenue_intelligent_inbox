"""analysis_service.py — Orchestrator for prepared and runtime analysis.

Two ways an analysis enters the system, both tied to a source revision:

* Prepared (human-reviewed): analysis/prepared/<record_ref>.json, written by
  reading each full conversation and checked by scripts/verify_evidence.py.
  ``apply_prepared`` stores one only when its source_revision equals the
  record's CURRENT revision. A prepared analysis for revision 2 is never
  attached to a revision-1 record, and vice versa.

* Runtime (Groq, on request) — run_analysis_for_record:
    1. Fetch record; no usable text → status='no_text' (nothing generated)
    2. Index the record's chunks in Pinecone under revision-scoped IDs
       (best effort; analysis does not depend on retrieval being up)
    3. Send the record's own FULL text to Groq, with meeting turns numbered.
       Earlier versions sent only top-k retrieved chunks, and the drafts
       reasoned from opening lines alone, so single-record analysis now
       uses the whole conversation.
    4. Validate the schema, then verify every quote against the source text;
       any unverifiable quote rejects the whole output (status='rejected')
    5. Persist as a new history row (never overwrite) with analysis_source='runtime'

manual_route_decisions is NEVER touched by this module.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from app.analysis_contract import AnalysisOutput, verify_evidence
from app.config import get_supabase_client

logger = logging.getLogger(__name__)

PREPARED_DIR = Path(__file__).resolve().parents[3] / "analysis" / "prepared"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _fetch_record(source_type: str, source_id: str) -> dict[str, Any] | None:
    """Fetch a single source record from Supabase by source_type + source_id."""
    rows = (
        get_supabase_client().table("source_records").select("*")
        .eq("source_type", source_type).eq("source_id", source_id)
        .limit(1).execute().data or []
    )
    return rows[0] if rows else None


def _persist_analysis(analysis: dict[str, Any], analysis_source: str) -> str:
    """Insert a new row into the analyses table; returns the row id.

    Every insert is a new history row — existing rows are never updated.
    Schema-1.1 fields without their own column (evidence list, headline,
    priority, label check) are kept together in the evidence_refs jsonb.
    """
    routes = [r if isinstance(r, dict) else r.model_dump(mode="json")
              for r in analysis.get("suggested_routes", [])]
    extras = {
        "schema_version": analysis.get("schema_version", "1.1"),
        "record_ref": analysis.get("record_ref"),
        "headline": analysis.get("headline"),
        "priority": analysis.get("priority"),
        "evidence": analysis.get("evidence") or [],
        "label_check": analysis.get("label_check"),
        "label_agrees": analysis.get("label_agrees"),
    }
    payload = {
        "source_type": analysis["source_type"],
        "source_id": analysis["source_id"],
        "source_revision": analysis["source_revision"],
        "analysis_source": analysis_source,
        "suggested_routes": routes,
        "concise_output": analysis.get("concise_output"),
        "evidence_refs": extras,
        "what_established": analysis.get("what_established"),
        "what_not_established": analysis.get("what_not_established"),
        "next_action": analysis.get("next_action"),
        "owner": analysis.get("owner"),
        "confidence": analysis.get("confidence"),
        "uncertainty": analysis.get("uncertainty"),
    }
    rows = get_supabase_client().table("analyses").insert(payload).execute().data or []
    return rows[0]["id"] if rows else ""


def _update_processing_state(
    source_type: str,
    source_id: str,
    analysis_state: str,
    analysis_revision: int | None = None,
) -> None:
    """Update record_processing_state for the given record."""
    payload: dict[str, Any] = {"analysis_state": analysis_state}
    if analysis_revision is not None:
        payload["analysis_revision"] = analysis_revision
    get_supabase_client().table("record_processing_state").update(payload).eq(
        "source_type", source_type
    ).eq("source_id", source_id).execute()


def _full_text_context(record: dict[str, Any]) -> str:
    """The record's own complete text; meeting turns carry their 1-based number."""
    if record["source_type"] == "call":
        return (record.get("source_payload") or {}).get("transcript") or ""
    turns = (record.get("transcript_payload") or {}).get("turns") or []
    return "\n".join(
        f"Turn {i} | {t.get('speaker', 'Unknown')}: {t.get('text', '')}"
        for i, t in enumerate(turns, start=1)
        if (t.get("text") or "").strip()
    )


def _index_for_retrieval(record: dict[str, Any]) -> None:
    """Best-effort Pinecone upsert under revision-scoped chunk IDs."""
    try:
        from app.services.chunker import chunk_record
        from app.services.embedder import embed_chunks
        from app.services.pinecone_service import upsert_chunks

        chunks = chunk_record(record)
        if chunks:
            upsert_chunks(embed_chunks(chunks))
    except Exception as exc:  # retrieval is optional; never block analysis
        logger.warning("Retrieval indexing skipped for %s: %s",
                       record.get("record_ref"), type(exc).__name__)


# ---------------------------------------------------------------------------
# Prepared analyses
# ---------------------------------------------------------------------------

def load_prepared_files() -> dict[tuple[str, str], dict[str, Any]]:
    """All prepared analyses keyed by identity (validated against the contract)."""
    out: dict[tuple[str, str], dict[str, Any]] = {}
    for f in sorted(PREPARED_DIR.glob("*.json")):
        data = AnalysisOutput.model_validate(
            json.loads(f.read_text(encoding="utf-8"))
        ).model_dump(mode="json")
        out[(data["source_type"], data["source_id"])] = data
    return out


def apply_prepared(source_type: str, source_id: str, force: bool = False) -> dict[str, Any]:
    """Store the prepared analysis for one record, if it matches the record.

    Returns {'status': ...}:
      not_found          — no such record
      no_text            — record has no usable text (never analysed)
      no_prepared        — no prepared file for this identity
      revision_mismatch  — the prepared file reflects a different revision
      unchanged          — identical prepared analysis already current
      verification_failed— a quote no longer matches the stored text
      applied            — inserted as the current analysis
    """
    record = _fetch_record(source_type, source_id)
    if not record:
        return {"status": "not_found"}
    if not record.get("has_usable_text"):
        return {"status": "no_text"}

    prepared = load_prepared_files().get((source_type, source_id))
    if not prepared:
        return {"status": "no_prepared"}
    if prepared["source_revision"] != record["revision"]:
        return {
            "status": "revision_mismatch",
            "prepared_revision": prepared["source_revision"],
            "record_revision": record["revision"],
        }

    problems = verify_evidence(
        source_type, prepared["evidence"],
        record.get("source_payload"), record.get("transcript_payload"),
    )
    if problems:
        return {"status": "verification_failed", "problems": problems}

    if not force:
        existing = (
            get_supabase_client().table("analyses").select("concise_output, analysis_source")
            .eq("source_type", source_type).eq("source_id", source_id)
            .eq("source_revision", record["revision"])
            .order("created_at", desc=True).limit(1).execute().data or []
        )
        if (existing and existing[0]["analysis_source"] == "prepared"
                and existing[0]["concise_output"] == prepared["concise_output"]):
            return {"status": "unchanged"}

    row_id = _persist_analysis(prepared, "prepared")
    _update_processing_state(source_type, source_id, "current", record["revision"])
    return {"status": "applied", "id": row_id, "source_revision": record["revision"]}


def apply_all_prepared() -> dict[str, Any]:
    """Apply every prepared analysis that matches its record's current revision."""
    results: dict[str, list[str]] = {}
    for (source_type, source_id), data in load_prepared_files().items():
        res = apply_prepared(source_type, source_id)
        results.setdefault(res["status"], []).append(data.get("record_ref") or source_id)
    return results


# Back-compat name used by scripts/seed_analyses.py in earlier revisions.
def persist_prepared_analysis(analysis_dict: dict[str, Any]) -> dict[str, Any]:
    return apply_prepared(analysis_dict["source_type"], analysis_dict["source_id"])


# ---------------------------------------------------------------------------
# Runtime analysis
# ---------------------------------------------------------------------------

def run_analysis_for_record(
    source_type: str,
    source_id: str,
    analysis_source: str = "runtime",
) -> dict[str, Any]:
    """Generate, verify and persist a runtime analysis for one record.

    Returns {'status': 'not_found' | 'no_text' | 'groq_failed' | 'rejected' | 'ok', ...}
    """
    from app.services.groq_service import analyze_record

    record = _fetch_record(source_type, source_id)
    if not record:
        return {"status": "not_found"}

    record_ref = record.get("record_ref") or source_id
    revision: int = record["revision"]

    if not record.get("has_usable_text"):
        return {"status": "no_text"}

    _index_for_retrieval(record)

    result = analyze_record(
        source_type=source_type,
        source_id=source_id,
        source_revision=revision,
        text_context=_full_text_context(record),
        record_ref=record_ref,
    )
    if result is None:
        logger.error("Groq analysis failed for %s — left awaiting analysis", record_ref)
        return {"status": "groq_failed"}

    result["record_ref"] = record_ref
    problems = verify_evidence(
        source_type, result.get("evidence") or [],
        record.get("source_payload"), record.get("transcript_payload"),
    )
    if not result.get("evidence"):
        problems.append("no evidence quotes returned")
    if problems:
        logger.warning("Runtime analysis for %s rejected: %d unverifiable quote(s)",
                       record_ref, len(problems))
        return {"status": "rejected", "problems": problems}

    _persist_analysis(result, analysis_source)
    _update_processing_state(source_type, source_id, "current", revision)
    logger.info("Runtime analysis stored for %s (revision=%d)", record_ref, revision)
    return {"status": "ok", "analysis": result}
