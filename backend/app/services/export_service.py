"""Export service — bundle generation for the Revenue Intelligence Inbox.

Each export writes a new versioned bundle and marks it current:

  <export_root>/
  ├── CURRENT                                  name of the current bundle
  ├── export_YYYYMMDD_HHMMSS.zip               the bundle as one download
  └── export_YYYYMMDD_HHMMSS/
      ├── README.md                            how to read the bundle
      ├── manifest.json                        one entry per source record
      ├── manifest.csv                         one row per output file
      ├── manager_brief_2026-08-21.md          shared daily brief (cites many records)
      ├── records/<ref>_<type>_<id>.md         dossier for EVERY record (incl. no-text)
      └── routes/<route_folder>/<ref>_<type>_<id>.md
                                               one file per ACTIVE route of a record

Why this shape: a conversation with several routes produces several route
files, but each one repeats the source identity and revision, links back to
the record dossier, and names its sibling routes, so no output loses its
context. Only effective routes are written: when a manager overrides the
route, the superseded suggested routes are listed in the manifest but get no
active destination file.

DATA RULES:
  2. Manual route decisions are read-only here; never mutated.
  8. analysis_source label ('prepared'|'runtime') included in every manifest entry.
  3. Timestamps are Asia/Kolkata (UTC+05:30).
  - Paths in the manifest are POSIX paths relative to the bundle root.
  - A stale analysis is never exported as current: records awaiting analysis
    get no suggested-route outputs.
"""
from __future__ import annotations

import csv
import io
import json
import logging
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

from app.analysis_contract import ROUTE_DEFINITIONS
from app.config import KOLKATA, get_supabase_client
from app.services.record_service import (
    NO_TEXT_MESSAGE,
    _build_analysis_summary,
    load_state,
)

logger = logging.getLogger(__name__)

BRIEF_FILE = "manager_brief_2026-08-21.md"


def _stem(row: dict) -> str:
    safe_id = row["source_id"].replace("/", "_").replace("\\", "_")
    return f"{row['record_ref'] or 'NA'}_{row['source_type']}_{safe_id}"


def _identity_block(row: dict) -> list[str]:
    return [
        f"- Source: `{row['source_type']}` / `{row['source_id']}` (record_ref {row['record_ref'] or '—'})",
        f"- Applied source revision: {row['revision']}",
        f"- Activity (Asia/Kolkata): {row.get('activity_at') or row.get('activity_date') or '—'}",
        f"- Person ({'call rep' if row['source_type'] == 'call' else 'meeting organiser'}): {row.get('person_name') or '—'}",
    ]


def _evidence_lines(row: dict, analysis: dict) -> list[str]:
    lines = []
    for e in analysis.get("evidence") or []:
        where = f"{row['record_ref']} turn {e['turn']}" if e.get("turn") else f"{row['record_ref']} (call quote)"
        lines.append(f"- **{e['id']}** {where}: \"{e['quote']}\" — {e.get('supports', '')}")
    return lines or ["- (none)"]


def _render_record(row: dict, analysis: dict | None, stale: dict | None,
                   manual: dict | None, route_paths: dict[str, str]) -> str:
    title = row.get("title") or row.get("headline") or ""
    out = [f"# {row['record_ref']} — {row['source_type']}" + (f": {title}" if title else ""), ""]
    out += _identity_block(row)
    out += [
        f"- Text: {row['text_status']}",
        f"- Stored source label: {row.get('source_label') or '—'}",
        f"- Review state: **{row['review_state']}** · analysis freshness: **{row['analysis_state']}**",
        "",
    ]

    out += ["## Routing", ""]
    if manual:
        out.append(f"- **Manual route (manager decision):** {ROUTE_DEFINITIONS[manual['route_id']]['label']} "
                   f"— set {manual.get('created_at') or ''}; rationale: {manual.get('rationale') or '—'}")
    sug = row["suggested_route_ids"]
    if sug:
        tag = " (superseded by the manual route)" if manual else ""
        out.append(f"- Suggested routes{tag}: " + ", ".join(ROUTE_DEFINITIONS[r]["label"] for r in sug))
    if route_paths:
        out.append("- Active destination files:")
        out += [f"  - {ROUTE_DEFINITIONS[r]['label']}: `../{p}`" for r, p in route_paths.items()]
    if not (manual or sug):
        out.append("- No route (see review state).")
    out.append("")

    if not row["has_usable_text"]:
        out += ["## Analysis", "", f"{NO_TEXT_MESSAGE}.", "",
                "Intake only. No substantive conclusion is drawn; a missing transcript does not show "
                "that the conversation did not happen.", ""]
        return "\n".join(out)

    if not analysis:
        out += ["## Analysis", "",
                f"**Awaiting analysis for revision {row['revision']}.** The source text changed or has not been "
                "analysed yet. No analysis is presented as current."]
        if stale:
            out += ["", f"A previous analysis exists for revision {stale['source_revision']}; it is history only "
                        "and is not exported as current."]
        return "\n".join(out + [""])

    out += [
        "## Analysis", "",
        f"_Source: {analysis['analysis_source']} analysis of revision {analysis['source_revision']}; "
        f"confidence {analysis.get('confidence') or '—'}._", "",
        f"**{analysis.get('headline') or ''}**", "",
        analysis.get("concise_output") or "", "",
        "**What the evidence establishes:** " + (analysis.get("what_established") or "—"), "",
        "**What it does not establish:** " + (analysis.get("what_not_established") or "—"), "",
        "**Next action:** " + (analysis.get("next_action") or "—"), "",
        "**Owner:** " + (analysis.get("owner") or "not stated in the source"), "",
        "**Uncertainty:** " + (analysis.get("uncertainty") or "—"), "",
    ]
    if analysis.get("label_check"):
        out += ["**Source label check:** " + analysis["label_check"], ""]
    out += ["## Evidence", ""] + _evidence_lines(row, analysis) + [""]
    return "\n".join(out)


def _render_route(row: dict, route_id: str, analysis: dict | None, manual: dict | None,
                  siblings: list[str], record_path: str) -> str:
    d = ROUTE_DEFINITIONS[route_id]
    out = [f"# {d['label']} — {row['record_ref']}", ""]
    out += _identity_block(row)
    is_manual = bool(manual and manual["route_id"] == route_id)
    out += [
        f"- Route origin: {'manual (manager decision)' if is_manual else 'suggested'}",
        f"- Record dossier: `../../{record_path}`",
        "- Also routed to: " + (", ".join(ROUTE_DEFINITIONS[s]['label'] for s in siblings) or "nothing else"),
        "",
    ]
    if is_manual and manual.get("rationale"):
        out += [f"**Manager rationale:** {manual['rationale']}", ""]

    route = next((r for r in (analysis or {}).get("suggested_routes", []) if r["route_id"] == route_id), None)
    if route:
        out += [
            f"**Priority:** {route.get('priority') or '—'}", "",
            "## Output", "", route.get("output") or route.get("rationale") or "", "",
            f"**Why this route:** {route.get('rationale')}", "",
            f"**Evidence:** {route.get('evidence_ref')}", "",
            f"**Owner:** {route.get('owner') or 'not stated in the source'}", "",
        ]
    elif analysis:
        out += ["## Output", "",
                "The manager chose this destination; the analysis has no destination-specific output for it. "
                "Summary for context:", "", analysis.get("concise_output") or "", "",
                f"**Next action (from analysis):** {analysis.get('next_action') or '—'}", ""]
    else:
        out += ["## Output", "",
                f"Awaiting analysis for revision {row['revision']}. Read the source text in the record dossier.", ""]
    return "\n".join(out)


def _render_brief(brief: dict) -> str:
    def refs(items):
        return "; ".join(
            f"{r['record_ref']}" + (f" ({r['cite']})" if r.get("cite") else "")
            for r in items
        )

    a = brief.get("activity", {})
    t, cov = a.get("totals", {}), a.get("text_coverage", {})
    out = [f"# Manager brief — {brief['date']} ({brief['timezone']})", "",
           f"_{brief['basis']}_", "",
           f"Selected records: {t.get('records')} ({t.get('calls')} calls, {t.get('meetings')} meetings). "
           f"Usable supplied text: {cov.get('usable')} of {cov.get('total')}.", "",
           brief["summary"], "", "## Priorities", ""]
    for p in brief["priorities"]:
        out += [f"{p['rank']}. **{p['title']}** — {p['why']} _Action:_ {p['action']} "
                f"_Owner:_ {p['owner']}. _Evidence:_ {refs(p['refs'])}"]
    out += ["", "## Follow-ups with stated next steps", ""]
    out += [f"- **{f['record_ref']}** ({f['owner']}): {f['action']}" for f in brief["follow_ups"]]
    out += ["", "## Coaching", ""]
    out += [f"- **{c['theme']}** — {c['detail']} ({refs(c['refs'])})" for c in brief["coaching"]]
    out += ["", "## Product / vendor signals", ""]
    out += [f"- **{s['signal']}** — {s['detail']} ({refs(s['refs'])})" for s in brief["product_signals"]]
    out += ["", "## Data quality", ""]
    out += [f"- **{q['issue']}** — {q['detail']}" for q in brief["data_quality"]]
    out += ["", "## What this brief does not establish", ""]
    out += [f"- {x}" for x in brief["not_established"]]
    return "\n".join(out) + "\n"


_README = """# Revenue Intelligence Inbox — export bundle

Generated {generated} (Asia/Kolkata). Bundle `{name}`; the current bundle is named in `../CURRENT`.

* `manifest.json` — one entry per source record (identity, applied revision, review state,
  analysis freshness, suggested / manual / effective routes, every output path).
* `manifest.csv` — the same outputs flattened to one row per file, for spreadsheets.
* `records/` — one dossier per record ({records} records), including records with no usable text.
* `routes/<route>/` — one file per active route. A record with two routes has two files;
  each repeats the source identity and links back to its dossier.
* `{brief}` — the 21 August 2026 manager brief (a shared output citing many records).

Route folders: {folders}

All paths are relative to this folder. Suggested routes replaced by a manager's manual
route are listed in the manifest as `superseded_suggested_routes` and have no active file.
"""


def generate_export(export_root: str) -> dict:
    """Generate a complete export bundle, verify it, zip it and mark it current."""
    from app.routers.brief import load_brief
    from app.services.metric_service import get_dashboard_metrics

    client = get_supabase_client()
    rows = load_state(client)

    analyses = client.table("analyses").select("*").order("created_at", desc=True).execute().data or []
    manual_rows = client.table("manual_route_decisions").select("*").eq("is_active", True).execute().data or []
    manual_map = {(m["source_type"], m["source_id"]): m for m in manual_rows}

    now = datetime.now(tz=KOLKATA)
    name = f"export_{now.strftime('%Y%m%d_%H%M%S')}"
    root = Path(export_root)
    bundle = root / name
    bundle.mkdir(parents=True, exist_ok=True)

    def write(rel: str, text: str) -> str:
        p = bundle / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        return rel

    entries: list[dict[str, Any]] = []
    csv_rows: list[dict[str, Any]] = []

    for row in sorted(rows, key=lambda r: (r["source_type"], r["record_ref"] or "")):
        key = (row["source_type"], row["source_id"])
        mine = [a for a in analyses if (a["source_type"], a["source_id"]) == key]
        cur = next((a for a in mine if a["source_revision"] == row["revision"]), None)
        analysis = _build_analysis_summary(cur, row["revision"]) if (cur and row["has_usable_text"]) else None
        stale = (_build_analysis_summary(mine[0], row["revision"])
                 if (mine and not cur and row["has_usable_text"]) else None)
        manual = manual_map.get(key)

        stem = _stem(row)
        record_path = f"records/{stem}.md"
        route_paths = {
            rid: f"routes/{ROUTE_DEFINITIONS[rid]['folder']}/{stem}.md"
            for rid in row["effective_route_ids"]
        }
        write(record_path, _render_record(row, analysis, stale, manual, route_paths))
        for rid, rel in route_paths.items():
            siblings = [s for s in row["effective_route_ids"] if s != rid]
            write(rel, _render_route(row, rid, analysis, manual, siblings, record_path))

        superseded = [r for r in row["suggested_route_ids"] if manual and r != manual["route_id"]]
        entry = {
            "source_type": row["source_type"],
            "source_id": row["source_id"],
            "record_ref": row["record_ref"],
            "applied_revision": row["revision"],
            "has_usable_text": row["has_usable_text"],
            "text_status": row["text_status"],
            "intake_state": row["intake_state"],
            "review_state": row["review_state"],
            "analysis_freshness": row["analysis_state"],
            "analysis_source": analysis["analysis_source"] if analysis else None,
            "analysis_revision": analysis["source_revision"] if analysis else (stale or {}).get("source_revision"),
            "suggested_routes": row["suggested_route_ids"],
            "manual_route": manual["route_id"] if manual else None,
            "manual_override": manual is not None,
            "effective_routes": row["effective_route_ids"],
            "superseded_suggested_routes": superseded,
            "priority": row.get("priority"),
            "headline": row.get("headline"),
            "outputs": [{"kind": "record_dossier", "route_id": None, "path": record_path}]
                       + [{"kind": "route_output", "route_id": r, "path": p} for r, p in route_paths.items()],
        }
        entry["output_paths"] = [o["path"] for o in entry["outputs"]]
        entries.append(entry)
        for o in entry["outputs"]:
            csv_rows.append({
                "source_type": row["source_type"], "source_id": row["source_id"],
                "record_ref": row["record_ref"], "applied_revision": row["revision"],
                "output_kind": o["kind"], "route_id": o["route_id"] or "", "path": o["path"],
                "effective_routes": "|".join(row["effective_route_ids"]),
                "manual_override": manual is not None,
                "review_state": row["review_state"], "analysis_freshness": row["analysis_state"],
                "analysis_source": entry["analysis_source"] or "",
            })

    brief = load_brief()
    brief["activity"] = get_dashboard_metrics()
    write(BRIEF_FILE, _render_brief(brief))

    route_counts = {rid: sum(rid in e["effective_routes"] for e in entries) for rid in ROUTE_DEFINITIONS}
    manifest: dict[str, Any] = {
        "bundle": name,
        "generated_at": now.isoformat(),
        "timezone": "Asia/Kolkata (UTC+05:30)",
        "is_current": True,
        "record_count": len(entries),
        "usable_text_count": sum(e["has_usable_text"] for e in entries),
        "manual_override_count": sum(e["manual_override"] for e in entries),
        "route_record_counts": route_counts,
        "route_assignment_count": sum(len(e["effective_routes"]) for e in entries),
        "routes": {rid: {"label": d["label"], "folder": f"routes/{d['folder']}", "definition": d["definition"]}
                   for rid, d in ROUTE_DEFINITIONS.items()},
        "shared_outputs": [{"kind": "manager_brief", "path": BRIEF_FILE,
                            "date": "2026-08-21", "cites": sorted(brief.get("records", {}))}],
        "entries": entries,
    }
    write("manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")

    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(csv_rows[0].keys()) if csv_rows else ["path"])
    w.writeheader()
    w.writerows(csv_rows)
    write("manifest.csv", buf.getvalue())
    write("README.md", _README.format(
        generated=now.isoformat(), name=name, records=len(entries), brief=BRIEF_FILE,
        folders=", ".join(f"`{d['folder']}` ({d['label']})" for d in ROUTE_DEFINITIONS.values()),
    ))

    # Verify every listed path exists inside the bundle.
    listed = [p for e in entries for p in e["output_paths"]] + [BRIEF_FILE]
    missing = [p for p in listed if not (bundle / p).is_file()]
    if missing:
        raise RuntimeError(f"Export verification failed: {len(missing)} file(s) missing: {missing[:5]}")

    zip_path = root / f"{name}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in sorted(bundle.rglob("*")):
            if f.is_file():
                zf.write(f, f"{name}/{f.relative_to(bundle).as_posix()}")

    (root / "CURRENT").write_text(name + "\n", encoding="utf-8")
    client.table("export_runs").update({"is_current": False}).eq("is_current", True).execute()
    inserted = (client.table("export_runs").insert({
        "is_current": True,
        "bundle_path": str(bundle),
        "manifest_path": str(bundle / "manifest.json"),
    }).execute().data or [{}])[0]

    return {
        "run_id": inserted.get("id"),
        "bundle": name,
        "bundle_path": str(bundle),
        "manifest_path": str(bundle / "manifest.json"),
        "zip_path": str(zip_path),
        "record_count": len(entries),
        "manifest_entry_count": len(entries),
        "output_file_count": len(listed),
        "route_assignment_count": manifest["route_assignment_count"],
        "manual_override_count": manifest["manual_override_count"],
        "generated_at": now.isoformat(),
    }
