"""Phase 1 data inspection for the Volopay Revenue Intelligence Inbox.

Reads data/01_initial.json and data/02_update.json, inventories the supplied
source records, and verifies the Phase 1 invariants from DATA_CONTRACT.md and
AGENTS.md. This script only READS and COUNTS; it draws no business conclusions.

Identity rule (DATA_CONTRACT.md): the only record identity is the exact,
case-sensitive tuple (source_type, source_id). record_ref, title, person,
email, phone token, company and array position are NOT identity keys.

Usable-text rules (DATA_DICTIONARY.md):
  - Call   : payload.transcript is non-blank                  -> usable
  - Meeting: at least one transcript_payload.turns[].text non-blank -> usable

Activity dates (DATA_DICTIONARY.md): calls use payload.started_at, meetings use
payload.starts_at, viewed in Asia/Kolkata. India Standard Time is a fixed
UTC+05:30 offset (no DST since 1945), so a fixed +05:30 timezone is correct for
2026 and avoids the missing tzdata / Windows-zoneinfo dependency on this host.

Person field (per task spec, rep_name for calls / organiser for meetings):
  - Call   : payload.rep_name          (caller display label)
  - Meeting: the organiser. The meeting payload exposes `organizer_email` but
    NO `organizer_name` field, so this script reports `organizer_email` (the
    organiser identifier) and flags that `organizer_name` is absent.
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Fixed Asia/Kolkata offset (UTC+05:30, no DST). See module docstring.
KOLKATA = timezone(timedelta(hours=5, minutes=30))

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"


def parse_ts(value: str) -> datetime:
    """Parse an ISO-8601 timestamp (with Z or explicit offset) to an aware dt."""
    s = value.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    return datetime.fromisoformat(s)


def activity_date(record: dict) -> str:
    """Activity date in Asia/Kolkata (YYYY-MM-DD) from the correct source field."""
    if record["source_type"] == "call":
        ts = record["payload"]["started_at"]
    else:
        ts = record["payload"]["starts_at"]
    return parse_ts(ts).astimezone(KOLKATA).date().isoformat()


def person_field(record: dict):
    """Person label: rep_name for calls, organizer_email for meetings."""
    if record["source_type"] == "call":
        return record["payload"].get("rep_name")
    return record["payload"].get("organizer_email")


def is_usable(record: dict) -> bool:
    """Usable-text check per DATA_DICTIONARY.md."""
    if record["source_type"] == "call":
        t = record["payload"].get("transcript")
        return bool(t and t.strip())
    tp = record.get("transcript_payload")
    return bool(tp and any(turn.get("text", "").strip() for turn in tp.get("turns", [])))


def identity(record: dict) -> tuple[str, str]:
    """Exact case-sensitive identity tuple."""
    return (record["source_type"], record["source_id"])


def pick_call_quote(transcript: str) -> str:
    """Pick a short EXACT verbatim quote from a call transcript.

    Prefers the first sentence that contains the SpendNest self-identification
    (a neutral, factual identifier); otherwise the opening sentence. The
    returned string is a verbatim substring of the supplied transcript.
    """
    t = transcript.strip()
    idx = t.find("SpendNest")
    if idx == -1:
        end = t.find(". ")
        return t if end == -1 else t[: end + 1]
    start = t.rfind(". ", 0, idx)
    start = 0 if start == -1 else start + 2
    end = t.find(". ", idx)
    return t[start:] if end == -1 else t[start : end + 1]


def load_json(name: str) -> dict:
    with (DATA_DIR / name).open(encoding="utf-8") as fh:
        return json.load(fh)


def main() -> None:
    initial = load_json("01_initial.json")
    records = initial["records"]

    # --- Duplicate (source_type, source_id) detection -----------------------
    seen: dict[tuple[str, str], int] = {}
    duplicates: list[tuple[str, str]] = []
    for r in records:
        key = identity(r)
        seen[key] = seen.get(key, 0) + 1
        if seen[key] == 2:
            duplicates.append(key)

    type_counts = Counter(r["source_type"] for r in records)
    n_calls = type_counts.get("call", 0)
    n_meetings = type_counts.get("meeting", 0)
    n_total = len(records)
    n_usable = sum(1 for r in records if is_usable(r))
    n_dupes = len(duplicates)

    # --- Activity dates (all should be 2026-08-21 Asia/Kolkata) --------------
    dates = sorted({activity_date(r) for r in records})

    # --- Person-field sanity: does any meeting have organizer_name? ----------
    meetings = [r for r in records if r["source_type"] == "meeting"]
    has_org_name = any("organizer_name" in r["payload"] for r in meetings)

    # --- Structured inventory table -----------------------------------------
    print("=== Initial inventory (data/01_initial.json) ===")
    print(
        f"{'ref':<7}{'type':<8}{'source_id':<37}{'person':<27}{'date':<11}{'usable':<7}"
    )
    print("-" * 97)
    for r in sorted(records, key=lambda r: (r["source_type"], r["record_ref"])):
        person = person_field(r)
        person_disp = "(null)" if person is None else str(person)
        if len(person_disp) > 25:
            person_disp = person_disp[:24] + "\u2026"
        print(
            f"{r['record_ref']:<7}{r['source_type']:<8}{r['source_id']:<37}"
            f"{person_disp:<27}{activity_date(r):<11}{'yes' if is_usable(r) else 'no':<7}"
        )
    print()

    # --- Summary counts -----------------------------------------------------
    print("=== Summary (initial delivery, revision 1) ===")
    print(f"{'Total records:':<14}{n_total:>7}")
    print(f"{'  Calls:':<14}{n_calls:>7}")
    print(f"{'  Meetings:':<14}{n_meetings:>7}")
    print(f"{'Usable texts:':<14}{n_usable:>7}")
    print(f"{'Duplicate IDs:':<14}{n_dupes:>7}")
    if len(dates) == 1:
        print(f"Activity date:     {dates[0]} (Asia/Kolkata) \u2014 all records")
    else:
        print(f"Activity dates:     {dates} (Asia/Kolkata) \u2014 NOT all the same")
    print()
    print(
        f"Person field: calls use rep_name; meetings use organizer_email "
        f"(organizer_name present in any meeting payload: {has_org_name})"
    )
    print()

    # --- Update delivery check ----------------------------------------------
    update = load_json("02_update.json")
    u_records = update["records"]
    update_n = len(u_records)
    u_rev = update.get("revision")

    # Final state: apply revision-aware replace per DATA_CONTRACT.md.
    final: dict[tuple[str, str], dict] = {}
    for r in records:
        final[identity(r)] = {"record": r, "revision": initial["revision"]}
    update_applied = False
    u_identity = None
    u_ref = None
    prior_rev = None
    u_usable = False
    if update_n == 1:
        ur = u_records[0]
        u_identity = identity(ur)
        u_ref = ur["record_ref"]
        prior_entry = final.get(u_identity)
        prior_rev = prior_entry["revision"] if prior_entry else None
        if prior_rev is not None and u_rev > prior_rev:
            final[u_identity] = {"record": ur, "revision": u_rev}
            update_applied = True
        u_usable = is_usable(ur)

    final_unique = len(final)
    final_usable = sum(1 for v in final.values() if is_usable(v["record"]))

    print("02_update.json:")
    print(f"  Records:         {update_n}")
    if u_identity is not None:
        print(f"  Identity:        ({u_identity[0]}, {u_ref})")
    print(f"  Revision:        {u_rev}  (was: {prior_rev})")
    if u_usable:
        print(f"  Usable text:     YES (revision {u_rev} has turns)")
    else:
        print(f"  Usable text:     NO")
    print(f"  Final unique records: {final_unique}")
    print(f"  Final usable texts:   {final_usable}")
    print(f"  Update applied (rev {u_rev} > prior {prior_rev}): {update_applied}")
    print()

    # --- Usable-record citations (seeds analysis/conversation_inventory.md) --
    print("=== Usable-record citations (final state, for conversation_inventory.md) ===")
    usable_final = [
        v["record"] for v in final.values() if is_usable(v["record"])
    ]
    usable_final.sort(key=lambda r: (r["source_type"], r["record_ref"]))
    for r in usable_final:
        sid = r["source_id"]
        if r["source_type"] == "call":
            quote = pick_call_quote(r["payload"]["transcript"])
            print(f"{r['record_ref']} | call | {sid} | rep={person_field(r)}")
            print(f"    quote: {quote!r}")
        else:
            tp = r["transcript_payload"]
            turn0 = tp["turns"][0]
            print(f"{r['record_ref']} | meeting | {sid} | org={person_field(r)}")
            print(f"    turn 1 | {turn0.get('speaker')}: {turn0.get('text')!r}")
    print()

    # --- No-text records ----------------------------------------------------
    no_text = [v["record"] for v in final.values() if not is_usable(v["record"])]
    no_text.sort(key=lambda r: (r["source_type"], r["record_ref"]))
    print(f"=== No-text records: {len(no_text)} ===")
    print(", ".join(r["record_ref"] for r in no_text))
    print()

    # --- Acceptance-criteria pass/fail --------------------------------------
    print("=== Acceptance criteria ===")
    checks = [
        ("44 unique (source_type, source_id) pairs", n_total == 44 and n_dupes == 0),
        ("30 calls", n_calls == 30),
        ("14 meetings", n_meetings == 14),
        ("17 usable texts initially", n_usable == 17),
        ("18 usable texts after update", final_usable == 18),
        ("Zero duplicate identities", n_dupes == 0),
        ("All activity on 2026-08-21 Asia/Kolkata", dates == ["2026-08-21"]),
        ("Update is 1 record, (meeting, M07), rev 2",
         update_n == 1 and u_identity == ("meeting", "4f304fff-fd40-5cfc-a366-0a134c445c2a")
         and u_ref == "M07" and u_rev == 2),
        ("Final state 44 unique records", final_unique == 44),
    ]
    all_ok = True
    for label, ok in checks:
        print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
        all_ok = all_ok and ok
    print()
    print("RESULT:", "ALL CHECKS PASS" if all_ok else "SOME CHECKS FAILED")


if __name__ == "__main__":
    main()
