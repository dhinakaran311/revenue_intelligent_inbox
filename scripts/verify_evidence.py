#!/usr/bin/env python3
"""verify_evidence.py — check every prepared analysis against the source text.

Builds the final source state from data/01_initial.json + data/02_update.json
(revision rule: higher revision replaces the whole record), then for each
analysis/prepared/*.json:

  * validates it against the AnalysisOutput contract;
  * checks it targets an existing identity at that identity's final revision;
  * checks the record has usable supplied text (no analysis for silent records);
  * verifies every evidence quote verbatim (calls: substring of the transcript;
    meetings: substring of the cited 1-based turn);
  * verifies every route's evidence_ref: quoted call text must exist, a cited
    meeting turn must exist.

Also checks that every usable-text record has exactly one prepared analysis.
Runs offline (no database). Exit code 0 only when everything passes.

Usage:  python scripts/verify_evidence.py
"""
from __future__ import annotations

import io
import json
import re
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.analysis_contract import AnalysisOutput, verify_evidence  # noqa: E402
from app.importer import is_usable  # noqa: E402


def final_state() -> dict[tuple[str, str], dict]:
    state: dict[tuple[str, str], dict] = {}
    for name in ("01_initial.json", "02_update.json"):
        delivery = json.loads((ROOT / "data" / name).read_text(encoding="utf-8"))
        rev = delivery["revision"]
        for rec in delivery["records"]:
            key = (rec["source_type"], rec["source_id"])
            if key not in state or rev > state[key]["revision"]:
                state[key] = {**rec, "revision": rev}
    return state


def check_brief(state: dict) -> list[str]:
    """Every brief reference must resolve to an identity; every quote/cite must verify."""
    brief = json.loads((ROOT / "analysis" / "manager_brief.json").read_text(encoding="utf-8"))
    ids = brief.get("records", {})
    out: list[str] = []
    n = 0

    def walk(x):
        nonlocal n
        if isinstance(x, list):
            for v in x:
                walk(v)
            return
        if not isinstance(x, dict):
            return
        ref = x.get("record_ref")
        if ref:
            ident = ids.get(ref)
            rec = state.get((ident["source_type"], ident["source_id"])) if ident else None
            if rec is None:
                out.append(f"brief: {ref} does not resolve to a source identity")
            else:
                for text in (x.get("quote"), x.get("cite")):
                    if not text:
                        continue
                    m = re.fullmatch(r"turn (\d+)", text)
                    turns = (rec.get("transcript_payload") or {}).get("turns") or []
                    if m:
                        ok = 1 <= int(m.group(1)) <= len(turns)
                        probs = [] if ok else [f"turn {m.group(1)} missing"]
                    elif rec["source_type"] == "call":
                        probs = verify_evidence("call", [{"id": "brief", "quote": text}], rec["payload"], None)
                    else:
                        tm = re.fullmatch(r"turn (\d+)", x.get("cite") or "")
                        turn = int(tm.group(1)) if tm else None
                        cands = [turn] if turn else range(1, len(turns) + 1)
                        probs = ["quote not found in any turn"]
                        for t in cands:
                            if not verify_evidence("meeting", [{"id": "b", "turn": t, "quote": text}], None,
                                                   rec.get("transcript_payload")):
                                probs = []
                                break
                    n += 1
                    out.extend(f"brief {ref}: {p} — {text[:60]}" for p in probs)
        for v in x.values():
            walk(v)

    walk({k: v for k, v in brief.items() if k != "records"})
    print(f"  checked manager_brief.json: {n} citations")
    return out


def main() -> int:
    state = final_state()
    failures: list[str] = []
    seen: set[tuple[str, str]] = set()

    files = sorted((ROOT / "analysis" / "prepared").glob("*.json"))
    for f in files:
        data = json.loads(f.read_text(encoding="utf-8"))
        tag = f.name
        try:
            a = AnalysisOutput.model_validate(data).model_dump(mode="json")
        except Exception as exc:  # noqa: BLE001
            failures.append(f"{tag}: schema — {exc}")
            continue

        key = (a["source_type"], a["source_id"])
        rec = state.get(key)
        if rec is None:
            failures.append(f"{tag}: identity {key} not in source data")
            continue
        if key in seen:
            failures.append(f"{tag}: duplicate analysis for {key}")
        seen.add(key)
        if a["source_revision"] != rec["revision"]:
            failures.append(f"{tag}: analyses revision {a['source_revision']} but final revision is {rec['revision']}")
        if not is_usable(rec):
            failures.append(f"{tag}: record has no usable text — substantive analysis not allowed")
            continue
        if not a["evidence"]:
            failures.append(f"{tag}: no evidence items")

        problems = verify_evidence(a["source_type"], a["evidence"], rec["payload"], rec.get("transcript_payload"))
        failures += [f"{tag}: {p}" for p in problems]

        # Route-level references
        for r in a["suggested_routes"]:
            ref = r["evidence_ref"]
            if a["source_type"] == "call":
                m = re.search(r'"(.+)"', ref)
                if not m:
                    failures.append(f"{tag}: route {r['route_id']} ref has no quote: {ref}")
                    continue
                probe = [{"id": f"route:{r['route_id']}", "quote": m.group(1)}]
                failures += [f"{tag}: {p}" for p in verify_evidence("call", probe, rec["payload"], None)]
            else:
                m = re.search(r"turn (\d+)", ref)
                turns = (rec.get("transcript_payload") or {}).get("turns") or []
                if not m or not (1 <= int(m.group(1)) <= len(turns)):
                    failures.append(f"{tag}: route {r['route_id']} cites a missing turn: {ref}")

        print(f"  checked {tag:10s} {a['source_type']:7s} rev {a['source_revision']}  "
              f"{len(a['evidence'])} quotes, {len(a['suggested_routes'])} routes")

    usable = {k for k, r in state.items() if is_usable(r)}
    for key in sorted(usable - seen):
        failures.append(f"missing prepared analysis for usable record {state[key]['record_ref']} {key}")

    failures += check_brief(state)

    print()
    print(f"Final state: {len(state)} records, {len(usable)} with usable text; {len(files)} prepared analyses")
    if failures:
        print(f"FAILED ({len(failures)}):")
        for x in failures:
            print("  -", x)
        return 1
    print("ALL EVIDENCE VERIFIED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
