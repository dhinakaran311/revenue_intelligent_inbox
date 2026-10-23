"""analysis_service.py — Orchestrator for the full analysis pipeline.

Sequence for run_analysis_for_record:
    1. Fetch record from Supabase
    2. Guard: no usable text → return status='no_text'
    3. Chunk text
    4. Embed chunks
    5. Upsert to Pinecone (idempotent — stable chunk IDs)
    6. Query Pinecone to retrieve relevant chunk text
    7. Build text_context from retrieved chunks
    8. Call Groq → AnalysisOutput dict
    9. If Groq fails → mark analysis_state='pending', return status='groq_failed'
   10. Validate with Pydantic
   11. Persist to analyses table (new row, never overwrite)
   12. Update record_processing_state: analysis_state='current'
   13. Return {status: 'ok', analysis: result}

manual_route_decisions is NEVER touched by this module.
"""
from __future__ import annotations

import logging
from typing import Any

from app.config import get_supabase_client
from app.analysis_contract import AnalysisOutput
from app.services.chunker import chunk_record
from app.services.embedder import embed_chunks, embed_texts
from app.services.pinecone_service import upsert_chunks, query_similar
from app.services.groq_service import analyze_record

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _fetch_record(source_type: str, source_id: str) -> dict[str, Any] | None:
    """Fetch a single source record from Supabase by source_type + source_id."""
    supabase = get_supabase_client()
    resp = (
        supabase.table("source_records")
        .select("*")
        .eq("source_type", source_type)
        .eq("source_id", source_id)
        .limit(1)
        .execute()
    )
    rows = resp.data or []
    return rows[0] if rows else None


def _persist_analysis(analysis_dict: dict[str, Any], analysis_source: str) -> str:
    """Insert a new row into the analyses table.

    Returns the inserted row's id.
    Every insert is a new history row — existing rows are never updated.
    """
    supabase = get_supabase_client()
    routes = analysis_dict.get("suggested_routes", [])
    suggested_routes_data = [
        r if isinstance(r, dict) else r.model_dump()
        for r in routes
    ]
    evidence_refs_data = [
        r.get("evidence_ref") if isinstance(r, dict) else getattr(r, "evidence_ref", None)
        for r in suggested_routes_data
    ]

    payload = {
        "source_type": analysis_dict["source_type"],
        "source_id": analysis_dict["source_id"],
        "source_revision": analysis_dict["source_revision"],
        "analysis_source": analysis_source,
        "suggested_routes": suggested_routes_data,
        "concise_output": analysis_dict.get("concise_output"),
        "evidence_refs": evidence_refs_data,
        "what_established": analysis_dict.get("what_established"),
        "what_not_established": analysis_dict.get("what_not_established"),
        "next_action": analysis_dict.get("next_action"),
        "owner": analysis_dict.get("owner"),
        "confidence": analysis_dict.get("confidence"),
        "uncertainty": analysis_dict.get("uncertainty"),
    }
    resp = supabase.table("analyses").insert(payload).execute()
    rows = resp.data or []
    return rows[0]["id"] if rows else ""


def _update_processing_state(
    source_type: str,
    source_id: str,
    analysis_state: str,
    analysis_revision: int | None = None,
) -> None:
    """Upsert record_processing_state for the given record."""
    supabase = get_supabase_client()
    payload: dict[str, Any] = {
        "source_type": source_type,
        "source_id": source_id,
        "analysis_state": analysis_state,
    }
    if analysis_revision is not None:
        payload["analysis_revision"] = analysis_revision

    # Upsert on (source_type, source_id) — assumes a unique constraint exists.
    supabase.table("record_processing_state").upsert(
        payload,
        on_conflict="source_type,source_id",
    ).execute()


def _build_text_context(
    chunks: list[dict[str, Any]],
    retrieved: list[dict[str, Any]],
) -> str:
    """Build the text_context string sent to the LLM.

    Retrieved matches from Pinecone contain only metadata, not full text.
    We look up the matching chunk text from the in-memory chunks list.

    Falls back to joining all chunk texts if no Pinecone results (e.g. first run).
    """
    if not chunks:
        return ""

    # Build lookup: chunk_id → text
    chunk_lookup = {c["chunk_id"]: c["text"] for c in chunks}

    if retrieved:
        # Use retrieved order (highest similarity first).
        texts = [
            chunk_lookup[r["chunk_id"]]
            for r in retrieved
            if r["chunk_id"] in chunk_lookup
        ]
    else:
        texts = [c["text"] for c in chunks]

    return "\n\n---\n\n".join(texts)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_analysis_for_record(
    source_type: str,
    source_id: str,
    analysis_source: str = "runtime",
) -> dict[str, Any]:
    """Full pipeline orchestrator for a single record.

    Args:
        source_type: "call" or "meeting".
        source_id: UUID string.
        analysis_source: "runtime" (default) or "prepared".

    Returns:
        dict with 'status' key:
            {'status': 'not_found'}             — record not in Supabase
            {'status': 'no_text'}               — has_usable_text is falsy
            {'status': 'no_chunks'}             — chunker produced nothing
            {'status': 'groq_failed'}           — Groq call or validation failed
            {'status': 'ok', 'analysis': dict}  — success
    """
    # 1. Fetch record
    record = _fetch_record(source_type, source_id)
    if not record:
        logger.warning("Record not found: source_type=%s source_id=%s", source_type, source_id)
        return {"status": "not_found"}

    record_ref = record.get("record_ref", source_id)
    source_revision: int = record.get("revision") or record.get("source_revision", 1)

    # 2. Guard: no usable text
    if not record.get("has_usable_text"):
        logger.info("No usable text for %s — skipping analysis", record_ref)
        _update_processing_state(source_type, source_id, "no_text")
        return {"status": "no_text"}

    # 3. Chunk
    chunks = chunk_record(record)
    if not chunks:
        logger.warning("Chunker returned no chunks for %s", record_ref)
        return {"status": "no_chunks"}

    # 4. Embed
    chunks = embed_chunks(chunks)

    # 5. Upsert to Pinecone (idempotent)
    upsert_chunks(chunks)

    # 6. Query Pinecone — use the first chunk's embedding as the query vector.
    query_vec: list[float] = chunks[0]["embedding"]
    retrieved = query_similar(query_vec, source_type, source_id, top_k=3)

    # 7. Build text_context from retrieved chunks
    text_context = _build_text_context(chunks, retrieved)

    # 8. Call Groq
    result = analyze_record(
        source_type=source_type,
        source_id=source_id,
        source_revision=source_revision,
        text_context=text_context,
        record_ref=record_ref,
    )

    # 9. Handle Groq failure
    if result is None:
        logger.error("Groq analysis failed for %s — marking pending", record_ref)
        _update_processing_state(source_type, source_id, "pending")
        return {"status": "groq_failed"}

    # 10. Final Pydantic validation (belt-and-suspenders)
    try:
        AnalysisOutput.model_validate(result)
    except Exception as exc:
        logger.error("Post-Groq validation failed for %s: %s", record_ref, exc)
        _update_processing_state(source_type, source_id, "pending")
        return {"status": "groq_failed"}

    # 11. Persist to analyses table
    _persist_analysis(result, analysis_source)

    # 12. Update processing state → current
    _update_processing_state(source_type, source_id, "current", source_revision)

    logger.info("Analysis complete for %s (revision=%d)", record_ref, source_revision)

    # 13. Return result
    return {"status": "ok", "analysis": result}


def persist_prepared_analysis(analysis_dict: dict[str, Any]) -> dict[str, Any]:
    """Insert a pre-generated (vetted) analysis with analysis_source='prepared'.

    Validates against AnalysisOutput schema before inserting.
    Also updates record_processing_state to 'current'.

    Args:
        analysis_dict: Dict conforming to AnalysisOutput schema, with
            analysis_source='prepared'.

    Returns:
        {'id': <inserted row id>} or raises on validation failure.
    """
    # Ensure analysis_source is set correctly.
    analysis_dict = dict(analysis_dict)
    analysis_dict["analysis_source"] = "prepared"

    # Validate schema
    validated = AnalysisOutput.model_validate(analysis_dict)
    validated_dict = validated.model_dump()

    row_id = _persist_analysis(validated_dict, "prepared")

    _update_processing_state(
        validated_dict["source_type"],
        validated_dict["source_id"],
        "current",
        validated_dict["source_revision"],
    )

    return {"id": row_id}
