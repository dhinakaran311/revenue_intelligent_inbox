"""Revision-aware delivery import for the Volopay Revenue Intelligence Inbox.

This module implements the import boundary (Phase 2, steps 2.3-2.4):

* ``validate_delivery`` / ``validate_record`` — client-side contract checks
  that return *structured* errors (field + code), never raw source data dumps.
* ``import_delivery`` — validates the whole delivery first (no partial state
  on validation failure), then upserts every record inside ONE server-side
  database transaction via the Supabase ``import_delivery`` rpc. On any
  database error the transaction rolls back the entire delivery.

Identity, revision and replace rules (DATA_CONTRACT.md / AGENTS.md):
  - identity is the exact, case-sensitive pair ``(source_type, source_id)``;
  - a delivery applies only when its revision is GREATER than the last applied
    revision for that identity; same/older revisions are ignored;
  - a newer revision FULLY replaces the source payload and transcript_payload
    (including null values) — it is not a partial field merge;
  - import NEVER touches ``manual_route_decisions``;
  - when the usable-text flag changes between revisions, the analysis is marked
    ``stale`` (the task's definition of a text change).

Derived fields (mirror scripts/inspect_data.py, Phase 1 findings):
  - has_usable_text: call -> non-blank payload.transcript;
                     meeting -> >=1 non-blank transcript_payload.turns[].text
  - person_name:  call -> rep_name (person_role='rep');
                  meeting -> organizer_email (person_role='organizer')
  - activity_date: call -> started_at; meeting -> starts_at, in Asia/Kolkata
    (fixed UTC+05:30 offset)
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.config import KOLKATA, get_supabase_client

VALID_SOURCE_TYPES = ("call", "meeting")


# --- Field derivation (mirrors scripts/inspect_data.py) -----------------------

def parse_ts(value: str) -> datetime:
    """Parse an ISO-8601 timestamp (with Z or explicit offset) to an aware dt."""
    s = value.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    return datetime.fromisoformat(s)


def is_usable(record: dict) -> bool:
    """Usable-text check per DATA_DICTIONARY.md."""
    if record["source_type"] == "call":
        t = record["payload"].get("transcript")
        return bool(t and t.strip())
    tp = record.get("transcript_payload")
    return bool(tp and any(turn.get("text", "").strip() for turn in tp.get("turns", [])))


def person_field(record: dict):
    """Person label: rep_name for calls, organizer_email for meetings."""
    if record["source_type"] == "call":
        return record["payload"].get("rep_name")
    return record["payload"].get("organizer_email")


def activity_date(record: dict):
    """Activity date in Asia/Kolkata (YYYY-MM-DD) from the correct source field.

    Returns ``None`` if the timestamp is missing/unparseable rather than raising,
    so a single bad date cannot abort the whole delivery.
    """
    try:
        if record["source_type"] == "call":
            ts = record["payload"]["started_at"]
        else:
            ts = record["payload"]["starts_at"]
        return parse_ts(ts).astimezone(KOLKATA).date().isoformat()
    except (KeyError, TypeError, ValueError):
        return None


# --- Validation (step 2.3) ---------------------------------------------------

def validate_record(record: Any, revision: Any) -> dict | None:
    """Validate one record against the delivery contract.

    Returns a structured error dict (identity + per-field error codes) if the
    record is invalid, else ``None``. Never includes raw payload / transcript
    content — only envelope identity and field/code indicators.
    """
    errors: list[dict] = []
    source_type = record.get("source_type") if isinstance(record, dict) else None
    source_id = record.get("source_id") if isinstance(record, dict) else None

    # 1. Required envelope fields present (source_type, source_id, revision)
    if source_type is None:
        errors.append({"field": "source_type", "code": "missing"})
    if source_id is None:
        errors.append({"field": "source_id", "code": "missing"})
    if revision is None:
        errors.append({"field": "revision", "code": "missing"})

    # 2. source_type is 'call' or 'meeting'
    if source_type not in VALID_SOURCE_TYPES:
        errors.append(
            {"field": "source_type", "code": "invalid", "allowed": list(VALID_SOURCE_TYPES)}
        )

    # 4. revision is a positive integer (bool is not an integer here)
    if not (isinstance(revision, int) and not isinstance(revision, bool) and revision > 0):
        errors.append({"field": "revision", "code": "invalid_positive_integer"})

    # 3 & 5. payload.id === source_id (exact string match) + transcript location
    payload = record.get("payload") if isinstance(record, dict) else None
    if not isinstance(payload, dict):
        errors.append({"field": "payload", "code": "missing_or_not_object"})
    else:
        # 3. payload.id === source_id (exact string match)
        if payload.get("id") != source_id:
            errors.append({"field": "payload.id", "code": "mismatch_source_id"})
        if source_type == "call":
            if "transcript" not in payload:
                errors.append({"field": "payload.transcript", "code": "missing"})
        elif source_type == "meeting":
            tp = record.get("transcript_payload")
            if not isinstance(tp, dict) or "turns" not in tp:
                errors.append({"field": "transcript_payload.turns", "code": "missing"})

    if errors:
        return {
            "source_type": source_type,
            "source_id": source_id,
            "record_ref": record.get("record_ref") if isinstance(record, dict) else None,
            "errors": errors,
        }
    return None


def validate_delivery(records: list, revision: Any) -> dict:
    """Validate every record in a delivery.

    Returns ``{"valid": bool, "total": int, "valid_count": int, "errors": [...]}``.
    A delivery is valid only if every record passes; invalid records are listed
    with structured errors (no raw source data).
    """
    errors = [e for e in (validate_record(r, revision) for r in records) if e is not None]
    return {
        "valid": not errors,
        "total": len(records),
        "valid_count": len(records) - len(errors),
        "errors": errors,
    }


# --- Normalization (build the payload sent to the import rpc) ----------------

def normalize_record(record: dict, revision: int) -> dict:
    """Build the normalized record handed to the server-side import function."""
    return {
        "source_type": record["source_type"],
        "source_id": record["source_id"],
        "record_ref": record.get("record_ref"),
        "revision": revision,
        "activity_date": activity_date(record),
        "person_name": person_field(record),
        "person_role": "rep" if record["source_type"] == "call" else "organizer",
        "source_payload": record.get("payload"),
        "transcript_payload": record.get("transcript_payload"),
        "has_usable_text": is_usable(record),
    }


# --- Import (step 2.4) -------------------------------------------------------

def _log_import_run(
    client,
    filename: str | None,
    checksum: str | None,
    total: int,
    accepted: int,
    ignored: int,
    replaced: int,
    errors: list,
) -> None:
    """Best-effort log to import_runs (used on validation / db-error paths)."""
    try:
        client.table("import_runs").insert({
            "filename": filename,
            "checksum": checksum,
            "total_records": total,
            "accepted": accepted,
            "ignored": ignored,
            "replaced": replaced,
            "errors": errors,
        }).execute()
    except Exception:
        # Logging must never mask the import result.
        pass


def import_delivery(
    records: list,
    revision: int,
    filename: str | None = None,
    checksum: str | None = None,
) -> dict:
    """Import a delivery transactionally.

    ``records`` are the raw ``records[]`` from the delivery file; ``revision``
    is the delivery-level revision that applies to every record (DATA_CONTRACT.md
    stores revision at the delivery level, not per record).

    Flow:
      1. Validate ALL records. If any fail, the delivery is rejected whole
         (no DB writes) and the errors are logged — no partial state.
      2. Otherwise upsert every record inside ONE server-side transaction via
         the ``import_delivery`` rpc. Any DB error rolls back the entire
         delivery; the failure is logged and returned with ``accepted=0``.

    Returns ``{"total", "accepted", "ignored", "replaced", "errors"}``.
    """
    client = get_supabase_client()
    total = len(records)

    # 1. Whole-delivery validation first.
    validation = validate_delivery(records, revision)
    if not validation["valid"]:
        _log_import_run(client, filename, checksum, total, 0, 0, 0, validation["errors"])
        return {
            "total": total,
            "accepted": 0,
            "ignored": 0,
            "replaced": 0,
            "errors": validation["errors"],
        }

    # 2. Atomic server-side upsert of the whole delivery.
    payload_records = [normalize_record(r, revision) for r in records]
    try:
        resp = client.rpc("import_delivery", {
            "p_records": payload_records,
            "p_filename": filename,
            "p_checksum": checksum,
        }).execute()
    except Exception as exc:  # transaction failed -> no partial state
        db_error = [{"code": "db_error", "detail": str(exc)[:200]}]
        _log_import_run(client, filename, checksum, total, 0, 0, 0, db_error)
        return {
            "total": total,
            "accepted": 0,
            "ignored": 0,
            "replaced": 0,
            "errors": db_error,
        }

    data = resp.data if hasattr(resp, "data") else resp
    # PostgREST may wrap a scalar/jsonb return in a single-element list.
    if isinstance(data, list) and data:
        data = data[0]
    if isinstance(data, dict):
        return data
    return {
        "total": total,
        "accepted": 0,
        "ignored": 0,
        "replaced": 0,
        "errors": [{"code": "unexpected_response", "detail": str(data)[:200]}],
    }
