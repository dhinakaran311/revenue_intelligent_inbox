"""Validate the current export bundle (backend/exports/CURRENT).

Checks:
  1. 44 manifest entries, one per unique (source_type, source_id)
  2. Every entry lists at least its record dossier
  3. Every listed output path (and shared output) exists and is relative POSIX
  4. M07 is at applied revision 2
  5. 18 entries have usable text; 26 do not; no-text entries have no route outputs
  6. Each route output path sits in its route's folder; superseded routes have no file
  7. manifest.csv has one row per listed output
"""
import csv
import io
import json
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

EXPORTS = Path(__file__).resolve().parent.parent / "backend" / "exports"


def main() -> int:
    marker = EXPORTS / "CURRENT"
    if not marker.exists():
        print("FAIL: no CURRENT export marker")
        return 1
    bundle = EXPORTS / marker.read_text(encoding="utf-8").strip()
    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    entries = manifest["entries"]
    ok = True

    def check(name, cond, detail=""):
        nonlocal ok
        ok &= bool(cond)
        print(f"{'PASS' if cond else 'FAIL'}: {name}" + (f" — {detail}" if detail else ""))

    ids = {(e["source_type"], e["source_id"]) for e in entries}
    check("44 entries, unique identities", len(entries) == 44 and len(ids) == 44, f"{len(entries)} entries")
    check("every entry has a record dossier",
          all(any(o["kind"] == "record_dossier" for o in e["outputs"]) for e in entries))

    paths = [p for e in entries for p in e["output_paths"]] + [s["path"] for s in manifest["shared_outputs"]]
    bad = [p for p in paths if p.startswith("/") or "\\" in p or ":" in p or ".." in p]
    missing = [p for p in paths if not (bundle / p).is_file()]
    check("all paths relative POSIX", not bad, str(bad[:3]))
    check("all listed files exist", not missing, f"{len(paths)} paths; missing {missing[:3]}")

    m07 = [e for e in entries if e["source_id"] == "4f304fff-fd40-5cfc-a366-0a134c445c2a"]
    check("M07 applied revision 2", m07 and m07[0]["applied_revision"] == 2,
          f"rev={m07[0]['applied_revision'] if m07 else None}, manual={m07[0]['manual_route'] if m07 else None}, "
          f"freshness={m07[0]['analysis_freshness'] if m07 else None}")

    text = [e for e in entries if e["has_usable_text"]]
    check("18 with usable text / 26 without", len(text) == 18 and len(entries) - len(text) == 26, f"{len(text)}")
    check("no-text entries have no route outputs",
          all(len(e["output_paths"]) == 1 for e in entries if not e["has_usable_text"] and not e["manual_override"]))

    folders = {k: v["folder"] for k, v in manifest["routes"].items()}
    misplaced = [o["path"] for e in entries for o in e["outputs"]
                 if o["kind"] == "route_output" and not o["path"].startswith(folders[o["route_id"]] + "/")]
    check("route outputs in their route folders", not misplaced, str(misplaced[:3]))
    leaked = [e["record_ref"] for e in entries
              if any(o["route_id"] in e["superseded_suggested_routes"] for o in e["outputs"])]
    check("superseded routes have no active file", not leaked, str(leaked))

    rows = list(csv.DictReader((bundle / "manifest.csv").open(encoding="utf-8")))
    check("manifest.csv one row per output", len(rows) == len(paths) - len(manifest["shared_outputs"]), f"{len(rows)} rows")

    print(f"\nBundle: {bundle}")
    print("ALL CHECKS PASSED" if ok else "SOME CHECKS FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
