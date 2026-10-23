"""Validate the most recent export bundle.

Checks:
  1. 44 manifest entries
  2. All output_path fields are non-null
  3. All files exist at their relative paths
  4. M07 has revision=2
  5. 18 entries have analysis (analysis_state not no_text and analysis_source not null)
  6. 26 entries with no_text analysis_state
  7. All paths are relative (not absolute)
"""
import json
import os
import sys
from pathlib import Path

# Resolve the exports directory relative to this script's location
SCRIPT_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = SCRIPT_DIR.parent
EXPORTS_DIR = PROJECT_ROOT / "backend" / "exports"


def find_latest_bundle() -> Path | None:
    if not EXPORTS_DIR.exists():
        return None
    bundles = sorted(
        [d for d in EXPORTS_DIR.iterdir() if d.is_dir() and d.name.startswith("export_")],
        key=lambda d: d.name,
        reverse=True,
    )
    return bundles[0] if bundles else None


def main() -> int:
    bundle_dir = find_latest_bundle()
    if not bundle_dir:
        print("FAIL: No export bundle found in backend/exports/")
        return 1

    manifest_path = bundle_dir / "manifest.json"
    if not manifest_path.exists():
        print(f"FAIL: manifest.json not found in {bundle_dir}")
        return 1

    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)

    entries = manifest.get("entries", [])
    all_pass = True

    def check(name: str, ok: bool, detail: str = "") -> None:
        nonlocal all_pass
        status = "PASS" if ok else "FAIL"
        if not ok:
            all_pass = False
        msg = f"{status}: {name}"
        if detail:
            msg += f" — {detail}"
        print(msg)

    # Check 1: 44 entries
    check("44 manifest entries", len(entries) == 44, f"got {len(entries)}")

    # Check 2: all output_path non-null
    null_paths = [e["source_id"] for e in entries if not e.get("output_path")]
    check(
        "All output_path non-null",
        len(null_paths) == 0,
        f"{len(null_paths)} null: {null_paths[:5]}" if null_paths else "",
    )

    # Check 3: all files exist
    missing = []
    for e in entries:
        if e.get("output_path"):
            full = bundle_dir / e["output_path"]
            if not full.exists():
                missing.append(e["output_path"])
    check(
        "All output files exist",
        len(missing) == 0,
        f"{len(missing)} missing: {missing[:5]}" if missing else "",
    )

    # Check 4: M07 has revision=2
    m07 = next(
        (e for e in entries if e.get("source_type") == "meeting" and e.get("source_id") == "M07"),
        None,
    )
    if m07:
        check("M07 revision=2", m07.get("revision") == 2, f"got {m07.get('revision')}")
    else:
        check("M07 revision=2", False, "M07 not found in manifest")

    # Check 5: 18 entries with analysis
    with_analysis = [
        e for e in entries
        if e.get("analysis_state") != "no_text" and e.get("analysis_source") is not None
    ]
    check(
        "18 entries with analysis",
        len(with_analysis) == 18,
        f"got {len(with_analysis)}",
    )

    # Check 6: 26 entries with no_text
    no_text = [e for e in entries if e.get("processing_state", {}).get("analysis_state") == "no_text"]
    check(
        "26 entries with no_text analysis_state",
        len(no_text) == 26,
        f"got {len(no_text)}",
    )

    # Check 7: all paths are relative
    absolute_paths = [
        e["output_path"]
        for e in entries
        if e.get("output_path") and os.path.isabs(e["output_path"])
    ]
    check(
        "All paths relative",
        len(absolute_paths) == 0,
        f"{len(absolute_paths)} absolute: {absolute_paths[:3]}" if absolute_paths else "",
    )

    print()
    print("\n".join([
        f"Bundle    : {bundle_dir}",
        f"Entries   : {len(entries)}",
        f"Generated : {manifest.get('generated_at', 'unknown')}",
    ]))
    print()
    print("ALL CHECKS PASSED" if all_pass else "SOME CHECKS FAILED")
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
