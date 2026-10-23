"""AGENTS.md Replay Acceptance Test -- 8-step sequence.

Steps:
1.  reset_db -> clean state
2.  import 01_initial.json -> 44 records, 17 usable (M07 rev-1, no transcript)
3.  import 01_initial.json again (reordered) -> no new records, no duplicates
4.  Set M07 manual route via POST /records/meeting/<id>/route
5.  import 02_update.json -> M07 stays 1 record, becomes rev 2, 18 usable
6.  M07 manual route survives (GET /records/meeting/<id>/route)
7.  import 01_initial.json again -> M07 stays revision 2 (older rev ignored)
8.  Verify all 44 records, M07 rev 2, manual route persists; test export
"""
from __future__ import annotations

import io
import json
import sys
import hashlib
from pathlib import Path
import urllib.request
import urllib.error

# Force UTF-8 output so emoji survive on Windows CP1252 terminals
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.config import app_env, get_supabase_client
from app import importer

# ── Constants ────────────────────────────────────────────────────────────────
M07_ID = "4f304fff-fd40-5cfc-a366-0a134c445c2a"
BASE_URL = "http://localhost:8000"
DATA_DIR = ROOT / "data"
PASS_STR = "[PASS]"
FAIL_STR = "[FAIL]"


# ── HTTP helpers ──────────────────────────────────────────────────────────────
def api_get(path: str):
    """GET a path. Returns parsed JSON (list or dict)."""
    req = urllib.request.Request(f"{BASE_URL}{path}")
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode())


def count_records() -> int:
    """Count total records from the /records list endpoint."""
    data = api_get("/records")
    if isinstance(data, list):
        return len(data)
    return data.get("total", -1)




def api_post(path: str, body: dict) -> dict:
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        f"{BASE_URL}{path}", data=data,
        headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return {"_http_error": e.code, "_detail": e.read().decode()[:200]}


# ── Import helper ─────────────────────────────────────────────────────────────
def do_import(filename: str, reorder: bool = False) -> dict:
    path = DATA_DIR / filename
    raw = path.read_bytes()
    data = json.loads(raw.decode("utf-8"))
    revision = data.get("revision")
    checksum = hashlib.sha256(raw).hexdigest()
    records = data.get("records", [])
    if reorder:
        records = list(reversed(records))
    return importer.import_delivery(
        records, revision, filename=path.name + (" (reordered)" if reorder else ""), checksum=checksum
    )


# ── Reset helper ──────────────────────────────────────────────────────────────
def do_reset() -> None:
    """Delete all app-owned data. Uses appropriate filter for each table's PK."""
    client = get_supabase_client()
    # Tables with UUID 'id' PK
    for t in ("analyses", "import_runs", "export_runs"):
        client.table(t).delete().neq(
            "id", "00000000-0000-0000-0000-000000000000"
        ).execute()
    # Tables with composite PK (source_type, source_id) — use gt on source_type
    for t in ("manual_route_decisions", "record_processing_state", "source_records"):
        client.table(t).delete().neq("source_type", "__never__").execute()


# ── Assertion tracker ─────────────────────────────────────────────────────────
failures: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    tag = PASS_STR if condition else FAIL_STR
    suffix = f"  ({detail})" if detail else ""
    print(f"  {tag}  {label}{suffix}")
    if not condition:
        failures.append(label)


# ── Main test sequence ────────────────────────────────────────────────────────
def main() -> int:
    env = app_env()
    if env == "production":
        print("REFUSED: replay test will not run in production.")
        return 1

    print("=" * 65)
    print("AGENTS.md REPLAY ACCEPTANCE TEST")
    print("=" * 65)

    # ── Step 1: Reset ─────────────────────────────────────────────────────────
    print("\n[Step 1] Reset all app data")
    try:
        do_reset()
        print("  [OK]  DB cleared")
    except Exception as exc:
        print(f"  [FAIL]  reset error: {exc}")
        failures.append("Step 1: reset")
        return 1  # Can't continue without a clean slate

    # ── Step 2: Import initial data ───────────────────────────────────────────
    print("\n[Step 2] Import 01_initial.json")
    r2 = do_import("01_initial.json")
    print(f"  accepted={r2.get('accepted')} ignored={r2.get('ignored')} "
          f"replaced={r2.get('replaced')} errors={len(r2.get('errors', []))}")
    check("44 records accepted on first import", r2.get("accepted") == 44, f"got {r2.get('accepted')}")
    check("No errors on first import", len(r2.get("errors", [])) == 0)

    recs_api = count_records()
    check("API reports 44 total records", recs_api == 44, f"got {recs_api}")

    m7_detail = api_get(f"/records/meeting/{M07_ID}")
    check("M07 exists after initial import", m7_detail.get("source_id") == M07_ID)
    check("M07 is revision 1 after initial import", m7_detail.get("revision") == 1,
          f"got {m7_detail.get('revision')}")

    metrics = api_get("/metrics/dashboard")
    usable = metrics.get("text_coverage", {}).get("usable", -1)
    check("17 usable texts after initial import", usable == 17, f"got {usable}")

    # ── Step 3: Re-import initial (idempotency) ───────────────────────────────
    print("\n[Step 3] Re-import 01_initial.json in REVERSED order (idempotency check)")
    r3 = do_import("01_initial.json", reorder=True)
    print(f"  accepted={r3.get('accepted')} ignored={r3.get('ignored')} "
          f"replaced={r3.get('replaced')} errors={len(r3.get('errors', []))}")
    check("Re-import: 0 accepted (all same revision -> ignored)", r3.get("accepted") == 0,
          f"got {r3.get('accepted')}")
    check("Re-import: 44 ignored", r3.get("ignored") == 44, f"got {r3.get('ignored')}")
    cnt2 = count_records()
    check("API still shows 44 records after re-import", cnt2 == 44, f"got {cnt2}")

    # ── Step 4: Set M07 manual route ──────────────────────────────────────────
    print(f"\n[Step 4] Set M07 manual route -> internal_vendor_action")
    r4 = api_post(f"/records/meeting/{M07_ID}/route", {
        "route_id": "internal_vendor_action",
        "label": "Replay test manual route",
        "rationale": "Set by replay acceptance test to verify persistence",
    })
    check("Manual route set (no HTTP error)", "_http_error" not in r4, f"{r4}")
    # Response wraps as {"source_type": ..., "manual_route": {"route_id": ...}}
    r4_route_id = (r4.get("manual_route") or {}).get("route_id") or r4.get("route_id")
    check("Manual route_id correct", r4_route_id == "internal_vendor_action",
          f"got {r4_route_id}")

    m7_with_route = api_get(f"/records/meeting/{M07_ID}")
    mr = m7_with_route.get("manual_route")
    check("M07 manual_route returned in detail", mr is not None, f"manual_route={mr}")
    if mr:
        check("M07 manual route_id persisted in DB", mr.get("route_id") == "internal_vendor_action",
              f"got {mr.get('route_id')}")

    # ── Step 5: Import update (02_update.json) ────────────────────────────────
    print(f"\n[Step 5] Import 02_update.json (M07 -> revision 2 + transcript)")
    r5 = do_import("02_update.json")
    print(f"  accepted={r5.get('accepted')} ignored={r5.get('ignored')} "
          f"replaced={r5.get('replaced')} errors={len(r5.get('errors', []))}")
    check("Update import: errors=0", len(r5.get("errors", [])) == 0,
          f"{r5.get('errors', [])[:3]}")

    cnt3 = count_records()
    check("Still 44 records after update (M07 updated, not duplicated)",
          cnt3 == 44, f"got {cnt3}")

    m7_after_update = api_get(f"/records/meeting/{M07_ID}")
    check("M07 now at revision 2", m7_after_update.get("revision") == 2,
          f"got {m7_after_update.get('revision')}")

    metrics2 = api_get("/metrics/dashboard")
    usable2 = metrics2.get("text_coverage", {}).get("usable", -1)
    check("18 usable texts after update import", usable2 == 18, f"got {usable2}")

    # ── Step 6: Manual route survives update ──────────────────────────────────
    print(f"\n[Step 6] M07 manual route survives import update")
    m7_route_check = api_get(f"/records/meeting/{M07_ID}")
    mr2 = m7_route_check.get("manual_route")
    check("M07 manual_route still present after update import", mr2 is not None,
          f"manual_route={mr2}")
    if mr2:
        check("M07 manual route_id unchanged after update", mr2.get("route_id") == "internal_vendor_action",
              f"got {mr2.get('route_id')}")

    check("M07 analysis is NOT shown as current after new text (awaiting analysis)",
          m7_route_check.get("analysis_state") in ("pending", "stale")
          and m7_route_check.get("current_analysis") is None,
          f"analysis_state={m7_route_check.get('analysis_state')}")
    ap = api_post(f"/records/meeting/{M07_ID}/analysis/prepared", {})
    check("Reviewed revision-2 analysis applied for M07", ap.get("status") == "applied", f"{ap}")
    m7_an = api_get(f"/records/meeting/{M07_ID}")
    check("M07 analysis now current at revision 2",
          m7_an.get("analysis_state") == "current"
          and (m7_an.get("current_analysis") or {}).get("source_revision") == 2)
    check("Manual route still in effect after analysis refresh",
          m7_an.get("effective_route_ids") == ["internal_vendor_action"], f"{m7_an.get('effective_route_ids')}")

    # ── Step 7: Re-import initial (older revision ignored for M07) ────────────
    print(f"\n[Step 7] Re-import 01_initial.json -> M07 must stay at revision 2")
    r7 = do_import("01_initial.json")
    print(f"  accepted={r7.get('accepted')} ignored={r7.get('ignored')} "
          f"replaced={r7.get('replaced')} errors={len(r7.get('errors', []))}")
    check("Re-import of older file: 0 errors", len(r7.get("errors", [])) == 0)

    m7_after_revert = api_get(f"/records/meeting/{M07_ID}")
    check("M07 still revision 2 (older revision ignored)", m7_after_revert.get("revision") == 2,
          f"got {m7_after_revert.get('revision')}")
    cnt4 = count_records()
    check("Still 44 records after re-import of old data", cnt4 == 44, f"got {cnt4}")

    # ── Step 8: Verify persistence (simulates restart) ────────────────────────
    print(f"\n[Step 8] Persistence check (manual route, revision, record count)")
    m7_final = api_get(f"/records/meeting/{M07_ID}")
    mr3 = m7_final.get("manual_route")
    check("M07 manual route persists", mr3 is not None, f"manual_route={mr3}")
    if mr3:
        check("M07 route_id persists", mr3.get("route_id") == "internal_vendor_action",
              f"got {mr3.get('route_id')}")
    check("M07 revision=2 persists", m7_final.get("revision") == 2,
          f"got {m7_final.get('revision')}")

    cnt_final = count_records()
    check("44 total records persist", cnt_final == 44, f"got {cnt_final}")

    # Test export endpoint
    print("\n[Step 8b] Export generation")
    exp = api_post("/export", {"format": "json", "include_analysis": True})
    check("Export created (no HTTP error)", "_http_error" not in exp,
          f"status={exp.get('_http_error')} detail={exp.get('_detail', '')[:100]}")
    if "_http_error" not in exp:
        has_run_id = "run_id" in exp or "id" in exp
        check("Export response has run_id or id", has_run_id, f"keys={list(exp.keys())}")

    # ── Summary ───────────────────────────────────────────────────────────────
    print("\n" + "=" * 65)
    if failures:
        print(f"RESULT: {len(failures)} FAILURE(S):")
        for f in failures:
            print(f"   - {f}")
        print("=" * 65)
        return 1
    else:
        print("RESULT: ALL CHECKS PASSED")
        print("AGENTS.md replay acceptance test complete.")
        print("=" * 65)
        return 0


if __name__ == "__main__":
    sys.exit(main())
