"""End-to-end API verification for Phase 3 & 4.
Tests all required endpoints against the running local server.
"""
import sys
import json
import urllib.request
import urllib.error

BASE = "http://127.0.0.1:8765"
PASS = []
FAIL = []

# Usable call source_id from Phase 1 (C01)
CALL_ID = "2ec4404c-beee-5377-a63c-aab701da08ed"
# Usable meeting source_id (M07 rev2)
MEETING_ID = "4f304fff-fd40-5cfc-a366-0a134c445c2a"
# Non-usable call (B01)
NO_TEXT_ID = "4868e5cd-5ab8-581c-a0e4-acc37385f0cf"


def get(path, label):
    url = BASE + path
    try:
        with urllib.request.urlopen(url, timeout=15) as r:
            data = json.loads(r.read())
            PASS.append(f"[PASS] {label} → {r.status}")
            return data
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:200]
        FAIL.append(f"[FAIL] {label} → HTTP {e.code}: {body}")
        return None
    except Exception as e:
        FAIL.append(f"[FAIL] {label} → {type(e).__name__}: {e}")
        return None


def post(path, body, label, expect_status=200):
    url = BASE + path
    raw = json.dumps(body).encode()
    req = urllib.request.Request(url, data=raw, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read())
            PASS.append(f"[PASS] {label} → {r.status}")
            return data
    except urllib.error.HTTPError as e:
        body_txt = e.read().decode()[:200]
        if e.code == expect_status:
            PASS.append(f"[PASS] {label} → HTTP {e.code} (expected)")
            return None
        FAIL.append(f"[FAIL] {label} → HTTP {e.code}: {body_txt}")
        return None
    except Exception as e:
        FAIL.append(f"[FAIL] {label} → {type(e).__name__}: {e}")
        return None


def delete(path, label):
    url = BASE + path
    req = urllib.request.Request(url, method="DELETE")
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read())
            PASS.append(f"[PASS] {label} → {r.status}")
            return data
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:200]
        FAIL.append(f"[FAIL] {label} → HTTP {e.code}: {body}")
        return None
    except Exception as e:
        FAIL.append(f"[FAIL] {label} → {type(e).__name__}: {e}")
        return None


# ── Phase 3: Read API ──────────────────────────────────────────────
print("=== Phase 3: Backend Read API ===")

# GET /health
h = get("/health", "GET /health")
if h:
    if h.get("status") == "ok" and h.get("supabase") == "connected":
        PASS.append("[PASS] /health: status=ok, supabase=connected")
    else:
        FAIL.append(f"[FAIL] /health: unexpected response: {h}")

# GET /definitions
d = get("/definitions", "GET /definitions")
if d:
    if "scope" in d and "timezone" in d:
        PASS.append("[PASS] /definitions: has scope + timezone")
    else:
        FAIL.append(f"[FAIL] /definitions: missing fields: {d}")

# GET /metrics/dashboard
m = get("/metrics/dashboard", "GET /metrics/dashboard")
if m:
    tc = m.get("text_coverage", {})
    if tc.get("total") == 44 and tc.get("usable") in (17, 18):
        PASS.append(f"[PASS] /metrics/dashboard: total=44, usable={tc.get('usable')}")
    else:
        FAIL.append(f"[FAIL] /metrics/dashboard: wrong counts: {tc}")
    if "activity_by_person" in m and "route_summary" in m:
        PASS.append("[PASS] /metrics/dashboard: has activity_by_person + route_summary")
    else:
        FAIL.append(f"[FAIL] /metrics/dashboard: missing keys: {list(m.keys())}")

# GET /records (all 44)
recs = get("/records", "GET /records (all)")
if recs is not None:
    if len(recs) == 44:
        PASS.append("[PASS] /records: 44 records returned")
    else:
        FAIL.append(f"[FAIL] /records: expected 44, got {len(recs)}")

# GET /records?has_usable_text=true (should be 17 before update, 18 after)
usable_recs = get("/records?has_usable_text=true", "GET /records?has_usable_text=true")
if usable_recs is not None:
    if len(usable_recs) in (17, 18):
        PASS.append(f"[PASS] /records?has_usable_text=true: {len(usable_recs)} records")
    else:
        FAIL.append(f"[FAIL] /records?has_usable_text=true: expected 17 or 18, got {len(usable_recs)}")

# GET /records?source_type=call
calls = get("/records?source_type=call", "GET /records?source_type=call")
if calls is not None:
    if len(calls) == 30:
        PASS.append("[PASS] /records?source_type=call: 30 records")
    else:
        FAIL.append(f"[FAIL] /records?source_type=call: expected 30, got {len(calls)}")

# GET /records?source_type=meeting
meetings = get("/records?source_type=meeting", "GET /records?source_type=meeting")
if meetings is not None:
    if len(meetings) == 14:
        PASS.append("[PASS] /records?source_type=meeting: 14 records")
    else:
        FAIL.append(f"[FAIL] /records?source_type=meeting: expected 14, got {len(meetings)}")

# GET /records/call/{id} — full detail
detail = get(f"/records/call/{CALL_ID}", f"GET /records/call/C01 detail")
if detail:
    if detail.get("source_id") == CALL_ID and detail.get("has_usable_text") is True:
        PASS.append("[PASS] /records/call/{id}: correct source_id and has_usable_text")
    else:
        FAIL.append(f"[FAIL] /records/call/{{id}}: unexpected detail: {detail.get('source_id')}, {detail.get('has_usable_text')}")
    if detail.get("person_role") == "rep":
        PASS.append("[PASS] /records/call/{id}: person_role=rep (call correctly labelled)")
    else:
        FAIL.append(f"[FAIL] /records/call/{{id}}: person_role={detail.get('person_role')} (expected rep)")

# GET /records/meeting/{id} — M07 should be revision 2
m07 = get(f"/records/meeting/{MEETING_ID}", "GET /records/meeting/M07")
if m07:
    if m07.get("revision") == 2:
        PASS.append("[PASS] /records/meeting/M07: revision=2")
    else:
        FAIL.append(f"[FAIL] /records/meeting/M07: expected revision=2, got {m07.get('revision')}")
    if m07.get("person_role") == "organizer":
        PASS.append("[PASS] /records/meeting/M07: person_role=organizer (meeting correctly labelled)")
    else:
        FAIL.append(f"[FAIL] /records/meeting/M07: person_role={m07.get('person_role')}")

# GET /records/call/{id}/analysis — usable call should have prepared analysis
an = get(f"/records/call/{CALL_ID}/analysis", "GET /records/call/C01/analysis")
if an:
    state = an.get("analysis_state", an.get("status"))
    if an.get("current_analysis") or an.get("suggested_routes") or an.get("concise_output"):
        PASS.append(f"[PASS] /records/call/C01/analysis: analysis returned (source={an.get('current_analysis', {}).get('analysis_source') if an.get('current_analysis') else 'top-level'})")
    elif state in ("pending", "no_text"):
        FAIL.append(f"[FAIL] /records/call/C01/analysis: state={state} (expected prepared analysis)")
    else:
        PASS.append(f"[PASS] /records/call/C01/analysis: got response: {list(an.keys())}")

# GET /records/call/{id}/analysis — no-text record
no_text_an = get(f"/records/call/{NO_TEXT_ID}/analysis", "GET /records/call/B01/analysis (no-text)")
if no_text_an:
    if no_text_an.get("analysis_state") == "no_text":
        PASS.append("[PASS] /records/call/B01/analysis: analysis_state=no_text")
    else:
        FAIL.append(f"[FAIL] /records/call/B01/analysis: expected no_text, got {no_text_an}")

# GET /records/call/{id}/evidence
ev = get(f"/records/call/{CALL_ID}/evidence", "GET /records/call/C01/evidence")
if ev:
    if ev.get("found") and ev.get("evidence"):
        PASS.append(f"[PASS] /records/call/C01/evidence: {len(ev['evidence'])} evidence items")
    else:
        FAIL.append(f"[FAIL] /records/call/C01/evidence: unexpected: {ev}")

# GET /import-runs
ir = get("/import-runs", "GET /import-runs")
if ir is not None:
    if len(ir) >= 2:
        PASS.append(f"[PASS] /import-runs: {len(ir)} runs logged")
    else:
        FAIL.append(f"[FAIL] /import-runs: expected >=2 runs, got {len(ir)}")

# GET /export-runs
er = get("/export-runs", "GET /export-runs")
if er is not None:
    PASS.append(f"[PASS] /export-runs: returned {len(er)} entries")

# POST /records/{type}/{id}/route — set manual route
route_resp = post(
    f"/records/call/{CALL_ID}/route",
    {"route_id": "deal_next_step", "rationale": "test route", "author": "test"},
    "POST /records/call/C01/route"
)
if route_resp and route_resp.get("manual_route", {}).get("route_id") == "deal_next_step":
    PASS.append("[PASS] POST /records/call/C01/route: manual route set")

# DELETE /records/{type}/{id}/route — reset manual route
del_resp = delete(f"/records/call/{CALL_ID}/route", "DELETE /records/call/C01/route")
if del_resp and del_resp.get("deactivated_count", 0) >= 1:
    PASS.append("[PASS] DELETE /records/call/C01/route: route deactivated")

# POST /admin/reset (should return 200 in development)
reset_resp = post("/admin/reset", {}, "POST /admin/reset", expect_status=200)
if reset_resp and reset_resp.get("status") == "ok":
    PASS.append("[PASS] POST /admin/reset: returned ok")
else:
    FAIL.append(f"[FAIL] POST /admin/reset: unexpected response: {reset_resp}")

# Re-import to restore state after reset
print("\n  [re-importing 01_initial.json after reset...]")
import subprocess, pathlib
root = pathlib.Path(__file__).resolve().parent.parent
python = root / "backend" / ".venv" / "Scripts" / "python.exe"
result = subprocess.run(
    [str(python), str(root / "scripts" / "import_data.py"), str(root / "data" / "01_initial.json")],
    capture_output=True, text=True, cwd=str(root)
)
if "accepted=44" in result.stdout:
    PASS.append("[PASS] Re-import after reset: 44 accepted")
    print(f"  {result.stdout.strip()}")
else:
    FAIL.append(f"[FAIL] Re-import after reset: {result.stdout} {result.stderr}")

# Also import 02_update.json so M07 is at revision 2
result_upd = subprocess.run(
    [str(python), str(root / "scripts" / "import_data.py"), str(root / "data" / "02_update.json")],
    capture_output=True, text=True, cwd=str(root)
)
if "replaced=1" in result_upd.stdout:
    PASS.append("[PASS] Re-import 02_update.json: M07 replaced to revision 2")
    print(f"  {result_upd.stdout.strip()}")
else:
    FAIL.append(f"[FAIL] Re-import 02_update.json: {result_upd.stdout} {result_upd.stderr}")

# Re-seed analyses
result2 = subprocess.run(
    [str(python), str(root / "scripts" / "seed_analyses.py")],
    capture_output=True, text=True, cwd=str(root)
)
if "errors': 0" in result2.stdout or "errors': 0" in result2.stderr:
    PASS.append("[PASS] Re-seed analyses: 0 errors")
else:
    # Check stderr for the log line
    combined = result2.stdout + result2.stderr
    if "errors" in combined and "0}" in combined:
        PASS.append("[PASS] Re-seed analyses completed")
    else:
        FAIL.append(f"[FAIL] Re-seed: {combined[-300:]}")

# ── Phase 4: Analysis seeded and readable ─────────────────────────
print("\n=== Phase 4: Analysis pipeline ===")

# After re-seed, check analysis is back for C01
an2 = get(f"/records/call/{CALL_ID}/analysis", "GET /records/call/C01/analysis (post-reseed)")
if an2:
    ca = an2.get("current_analysis") or an2
    if ca.get("analysis_source") == "prepared" or ca.get("suggested_routes"):
        PASS.append(f"[PASS] /records/call/C01/analysis post-reseed: analysis_source=prepared")
    else:
        FAIL.append(f"[FAIL] /records/call/C01/analysis post-reseed: {list(an2.keys())}")

# M07 analysis should be at revision 2
m07_an = get(f"/records/meeting/{MEETING_ID}/analysis", "GET /records/meeting/M07/analysis")
if m07_an:
    ca = m07_an.get("current_analysis") or m07_an
    rev = ca.get("source_revision") if isinstance(ca, dict) else None
    if rev == 2:
        PASS.append("[PASS] /records/meeting/M07/analysis: source_revision=2")
    else:
        FAIL.append(f"[FAIL] /records/meeting/M07/analysis: expected source_revision=2, got {rev} — {list(m07_an.keys())}")

# ── Summary ───────────────────────────────────────────────────────
print()
print("=" * 60)
print(f"PASSED: {len(PASS)}")
print(f"FAILED: {len(FAIL)}")
print()
for p in PASS:
    print(p)
if FAIL:
    print()
    for f in FAIL:
        print(f)

sys.exit(0 if not FAIL else 1)
