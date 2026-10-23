"""chunker.py — Text chunking for calls and meetings.

Chunk IDs are stable and follow the pattern:
    {source_type}_{source_id}_{revision}_chunk{n}

This guarantees that re-chunking the same revision produces identical IDs,
making Pinecone upserts idempotent.
"""
from __future__ import annotations

import hashlib
from typing import Any


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def chunk_call(
    source_type: str,
    source_id: str,
    revision: int,
    transcript: str,
) -> list[dict[str, Any]]:
    """Return a single-element list with the full call transcript as one chunk.

    One chunk per call is intentional: calls are typically short enough that
    splitting them loses the conversational arc needed for routing decisions.
    """
    chunk_id = f"{source_type}_{source_id}_{revision}_chunk0"
    return [
        {
            "chunk_id": chunk_id,
            "source_type": source_type,
            "source_id": source_id,
            "source_revision": revision,
            "chunk_index": 0,
            "text": transcript,
            "text_hash": _sha256(transcript),
        }
    ]


def chunk_meeting(
    source_type: str,
    source_id: str,
    revision: int,
    turns: list[dict[str, Any]],
    window: int = 5,
) -> list[dict[str, Any]]:
    """Sliding-window chunking over meeting turns.

    Each chunk covers ``window`` consecutive turns.  The window slides by 1
    turn so adjacent chunks share context.  Turn numbers are 1-based to match
    evidence citations used in route items.

    Args:
        source_type: e.g. "meeting"
        source_id: UUID string from Supabase source_records.
        revision: source_revision integer.
        turns: list of dicts with at least 'speaker' and 'text' keys.
        window: number of turns per chunk (default 5).

    Returns:
        List of chunk dicts, each containing:
            chunk_id, source_type, source_id, source_revision, chunk_index,
            text, text_hash, turn_start (1-based), turn_end (1-based).
    """
    if not turns:
        return []

    chunks: list[dict[str, Any]] = []
    for n, start_idx in enumerate(range(0, len(turns), max(1, window - 1))):
        window_turns = turns[start_idx : start_idx + window]
        if not window_turns:
            break

        text = "\n".join(
            f"{t.get('speaker', 'Unknown')}: {t.get('text', '')}"
            for t in window_turns
        )
        turn_start = start_idx + 1          # 1-based
        turn_end = start_idx + len(window_turns)  # 1-based inclusive

        chunks.append(
            {
                "chunk_id": f"{source_type}_{source_id}_{revision}_chunk{n}",
                "source_type": source_type,
                "source_id": source_id,
                "source_revision": revision,
                "chunk_index": n,
                "text": text,
                "text_hash": _sha256(text),
                "turn_start": turn_start,
                "turn_end": turn_end,
            }
        )

        # If the window already reached the end of turns, stop.
        if start_idx + window >= len(turns):
            break

    return chunks


def chunk_record(record: dict[str, Any]) -> list[dict[str, Any]]:
    """Route to chunk_call or chunk_meeting based on source_type.

    Returns an empty list if the record has no usable text
    (``has_usable_text`` is falsy or payload is missing).

    Expected record keys (from Supabase source_records):
        source_type, source_id (or id), source_revision,
        has_usable_text, source_payload, transcript_payload.
    """
    if not record.get("has_usable_text"):
        return []

    source_type: str = record["source_type"]
    source_id: str = record.get("source_id") or record.get("id", "")
    revision: int = record.get("revision") or record.get("source_revision", 1)

    if source_type == "call":
        # Transcript lives inside transcript_payload or source_payload.
        transcript_payload = record.get("transcript_payload") or {}
        transcript: str = transcript_payload.get("transcript", "")
        if not transcript:
            # Fallback: check source_payload
            source_payload = record.get("source_payload") or {}
            transcript = source_payload.get("transcript", "")
        if not transcript:
            return []
        return chunk_call(source_type, source_id, revision, transcript)

    elif source_type == "meeting":
        transcript_payload = record.get("transcript_payload") or {}
        turns: list[dict] = transcript_payload.get("turns", [])
        if not turns:
            return []
        return chunk_meeting(source_type, source_id, revision, turns)

    else:
        # Unknown source type — no chunking rule defined.
        return []
