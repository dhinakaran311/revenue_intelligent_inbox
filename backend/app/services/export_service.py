"""Export service — bundle generation for the Revenue Intelligence Inbox.

Generates a timestamped export bundle under the given export_root:
  <export_root>/
  └── export_YYYYMMDD_HHMMSSz/
      ├── records/
      │   └── <source_type>_<source_id>.txt   (one per record with analysis)
      └── manifest.json

DATA RULES:
  2. Manual route decisions are read-only here; never mutated.
  8. analysis_source label ('prepared'|'runtime') included in every manifest entry.
  3. Timestamps displayed in Asia/Kolkata (UTC+05:30).
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import KOLKATA, get_supabase_client

logger = logging.getLogger(__name__)


def _to_kolkata_str(ts: str | None) -> str | None:
    if not ts:
        return None
    try:
        s = ts.strip()
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(KOLKATA).isoformat()
    except (ValueError, TypeError):
        return ts


def _render_text_summary(rec: dict, analysis: dict | None) -> str:
    """Render a human-readable text file for a single record's analysis."""
    lines = [
        f"Revenue Intelligence Inbox — Record Analysis",
        f"=" * 60,
        f"Source Type  : {rec.get('source_type', '')}",
        f"Source ID    : {rec.get('source_id', '')}",
        f"Record Ref   : {rec.get('record_ref') or '—'}",
        f"Revision     : {rec.get('revision', '')}",
        f"Activity Date: {rec.get('activity_date') or '—'}",
        f"Person       : {rec.get('person_name') or '—'} ({rec.get('person_role') or '—'})",
        f"Has Text     : {rec.get('has_usable_text', False)}",
        "",
    ]

    if not analysis:
        lines.append("No usable supplied text — analysis unavailable.")
        return "\n".join(lines)

    lines += [
        f"Analysis Source   : {analysis.get('analysis_source', '—')}",
        f"Source Revision   : {analysis.get('source_revision', '—')}",
        f"Freshness         : {analysis.get('freshness_label', '—')}",
        f"Confidence        : {analysis.get('confidence') or '—'}",
        f"Uncertainty       : {analysis.get('uncertainty') or '—'}",
        "",
        "--- Concise Output ---",
        analysis.get("concise_output") or "—",
        "",
        "--- What Was Established ---",
        analysis.get("what_established") or "—",
        "",
        "--- What Was NOT Established ---",
        analysis.get("what_not_established") or "—",
        "",
        "--- Next Action ---",
        analysis.get("next_action") or "—",
        f"Owner: {analysis.get('owner') or '—'}",
        "",
        "--- Suggested Routes ---",
    ]
    routes = analysis.get("suggested_routes") or []
    if routes:
        for r in routes:
            if isinstance(r, dict):
                lines.append(
                    f"  • {r.get('route_id', '')} — {r.get('label', '')} "
                    f"(manual={r.get('is_manual', False)})"
                )
    else:
        lines.append("  (none)")

    return "\n".join(lines)


def generate_export(export_root: str) -> dict:
    """Generate a complete export bundle and register it in export_runs.

    Steps:
      1. Mark all existing export_runs as is_current=false.
      2. Query all records with state, manual routes, latest analysis.
      3. Create a timestamped bundle directory.
      4. Write per-record .txt files for records with analysis.
      5. Write manifest.json.
      6. Verify all listed output_path files exist.
      7. Insert export_runs row with is_current=true.
      8. Return metadata dict.
    """
    client = get_supabase_client()

    # 1. Mark all existing runs as not current
    client.table("export_runs").update({"is_current": False}).eq(
        "is_current", True
    ).execute()

    # 2. Query all records
    sr_resp = client.table("source_records").select(
        "source_type, source_id, record_ref, revision, has_usable_text, "
        "person_name, person_role, activity_date"
    ).execute()
    all_records: list[dict] = sr_resp.data or []

    # Processing states
    ps_resp = client.table("record_processing_state").select(
        "source_type, source_id, intake_state, analysis_state, analysis_revision"
    ).execute()
    ps_map = {
        (r["source_type"], r["source_id"]): r for r in (ps_resp.data or [])
    }

    # Active manual routes
    mr_resp = client.table("manual_route_decisions").select(
        "source_type, source_id, route_id, is_active"
    ).eq("is_active", True).execute()
    mr_map = {
        (r["source_type"], r["source_id"]): r for r in (mr_resp.data or [])
    }

    # Latest analyses per identity (for current revision)
    an_resp = client.table("analyses").select(
        "source_type, source_id, source_revision, analysis_source, "
        "concise_output, suggested_routes, what_established, what_not_established, "
        "next_action, owner, confidence, uncertainty, evidence_refs, created_at"
    ).order("created_at", desc=True).execute()
    an_map: dict[tuple, dict] = {}
    for a in (an_resp.data or []):
        key = (a["source_type"], a["source_id"])
        if key not in an_map:
            an_map[key] = a

    # 3. Create bundle directory
    now_kolkata = datetime.now(tz=KOLKATA)
    timestamp_str = now_kolkata.strftime("%Y%m%d_%H%M%S")
    bundle_dir = Path(export_root) / f"export_{timestamp_str}"
    records_dir = bundle_dir / "records"
    records_dir.mkdir(parents=True, exist_ok=True)

    manifest_entries: list[dict] = []
    written_paths: list[Path] = []

    # 4. Write per-record text summaries
    for rec in all_records:
        key = (rec["source_type"], rec["source_id"])
        ps = ps_map.get(key, {})
        mr = mr_map.get(key)
        an = an_map.get(key)

        has_usable = rec.get("has_usable_text", False)
        raw_analysis_state = ps.get("analysis_state", "pending")
        analysis_state = "no_text" if not has_usable else raw_analysis_state

        # Determine route_ids
        route_ids: list[str] = []
        if mr:
            route_ids.append(mr["route_id"])
        elif an and an.get("suggested_routes"):
            routes = an["suggested_routes"]
            if isinstance(routes, list):
                route_ids = [r["route_id"] for r in routes if isinstance(r, dict) and "route_id" in r]

        # Determine analysis freshness
        analysis_dict = None
        if an:
            analysis_source = an.get("analysis_source", "prepared")
            is_current = an.get("source_revision") == rec.get("revision")
            analysis_freshness = "current" if is_current else "stale"
            analysis_dict = {
                "analysis_source": analysis_source,
                "source_revision": an.get("source_revision"),
                "freshness_label": analysis_freshness,
                "confidence": an.get("confidence"),
                "uncertainty": an.get("uncertainty"),
                "concise_output": an.get("concise_output"),
                "what_established": an.get("what_established"),
                "what_not_established": an.get("what_not_established"),
                "next_action": an.get("next_action"),
                "owner": an.get("owner"),
                "suggested_routes": an.get("suggested_routes") or [],
            }
        else:
            analysis_source = None
            analysis_freshness = None

        # Always write a .txt file for every record
        safe_source_id = rec["source_id"].replace("/", "_").replace("\\", "_")
        filename = f"{rec['source_type']}_{safe_source_id}.txt"
        out_path = records_dir / filename
        out_path.write_text(
            _render_text_summary(rec, analysis_dict), encoding="utf-8"
        )
        written_paths.append(out_path)
        output_path = str(Path("records") / filename)  # always relative

        manifest_entries.append({
            "source_type": rec["source_type"],
            "source_id": rec["source_id"],
            "record_ref": rec.get("record_ref"),
            "revision": rec.get("revision"),
            "route_ids": route_ids,
            "output_path": output_path,
            "processing_state": {
                "intake_state": ps.get("intake_state", "pending"),
                "analysis_state": analysis_state,
            },
            "has_manual_route": mr is not None,
            "analysis_freshness": analysis_freshness,
            "analysis_source": analysis_source,
        })

    # 5. Write manifest.json
    manifest: dict[str, Any] = {
        "generated_at": now_kolkata.isoformat(),
        "timezone": "Asia/Kolkata (UTC+05:30)",
        "record_count": len(all_records),
        "entries": manifest_entries,
    }
    manifest_path = bundle_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # 6. Verify all listed output_paths exist
    missing: list[str] = []
    for entry in manifest_entries:
        if entry["output_path"]:
            full = bundle_dir / entry["output_path"]
            if not full.exists():
                missing.append(entry["output_path"])
    if missing:
        logger.error("Export verification failed — missing files: %s", missing)
        raise RuntimeError(
            f"Export verification failed: {len(missing)} file(s) missing: {missing[:5]}"
        )

    # 7. Insert export_runs row
    bundle_path_str = str(bundle_dir)
    manifest_path_str = str(manifest_path)

    insert_resp = client.table("export_runs").insert({
        "is_current": True,
        "bundle_path": bundle_path_str,
        "manifest_path": manifest_path_str,
    }).execute()
    inserted_run = (insert_resp.data or [{}])[0]

    # 8. Return metadata
    return {
        "run_id": inserted_run.get("id"),
        "bundle_path": bundle_path_str,
        "manifest_path": manifest_path_str,
        "record_count": len(all_records),
        "manifest_entry_count": len(manifest_entries),
        "generated_at": now_kolkata.isoformat(),
    }
