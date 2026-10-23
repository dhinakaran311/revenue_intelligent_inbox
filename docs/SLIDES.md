# Five slides — Revenue Intelligence Inbox

---

## 1 · The manager problem and what I found

**Problem chosen:** at the start of the day, a manager needs to know what happened, what needs them, and whether to trust it. A pile of 44 records doesn't tell them.

**Main findings (21 Aug 2026, 44 selected records, 18 with usable text):**
- **The urgent work is with existing customers, not new deals.**
  - M07: reimbursements stuck, with an update promised within 1–2 hours.
  - M04: card programme closing; the customer needs credit (retention risk).
  - M09: login blocked for the larger company.
- **Credit vs prepaid is a recurring gap** (M03 turn 6, M04 turn 11).
- **Stored labels and identity can't be trusted blindly.**
  - C10 is labelled "follow_up" but the prospect declined a follow-up.
  - C06 is attributed to Meera, but the caller says "Ravi".
- **26/44 records have no usable text** (20 background calls, 6 meetings). They get an intake state, never an invented analysis.

---

## 2 · Interface choices and what I left out

- **Dashboard first screen.** Activity by hour (everything is one date), call reps and meeting organisers in separate tables, a "Needs attention" list, routes, review states, and why text is missing. Every number has a definition under it and clicks through to the filtered inbox.
- **Filters:** person and source type.
- **Record page.** The analysis states what the evidence establishes and what it does *not*, the next action, and an owner only when stated. Every route has its own output. The full source text has cited turns and quotes highlighted, and each citation jumps to its passage.
- **Brief.** A prepared, date-fixed brief: priorities, follow-ups, coaching, product signals and data quality. Each item links to the passage, and live state shows if a cited record has since been re-routed.
- **Deliberately left out:**
  - pipeline value and win probability (not in the data)
  - rep leaderboards (a selected sample, with attribution conflicts)
  - date filters (one date)
  - sentiment scores
  - talk ratios (not recomputable from adapted text)

---

## 3 · Routing, folders and one difficult case

- **Six routes:** deal/partner next step · customer follow-up · sales coaching · internal/product/vendor · human review · log only.
- **Multiple routes per record:** 35 assignments on 18 records.
- **Manual routes** are stored separately, survive every re-import and restart, and keep a history.
- **Export layout:** `records/` holds one dossier for every record; `routes/<route>/` holds one file per *active* route. Each route file repeats identity and revision, links to the dossier, and names its sibling routes. The manifest (JSON + CSV) lists every path; replaced suggestions appear as `superseded_suggested_routes`.
- **Difficult case — M04, Cedarwave.**
  - It looks like a routine "migration" call, but it is an existing customer being told their cards will stop, who says credit is "the main issue… we will have to consider another option".
  - Routed to **Customer follow-up** (eligibility and accounting answers, a migration plan) + **Internal/product** (credit gap, bank-card feed questions) + **Human review**. M13, "Cedarwave – Migration discussion", has the same organiser and no notetaker; it may be the same meeting, but only the title suggests it, so it is flagged rather than merged.

---

## 4 · How I checked a number and a conclusion

- **Number: usable-text coverage 17 → 18 of 44.**
  - Computed from the stored state, not the import counters.
  - `replay_acceptance_test.py` asserts 44/17 after the initial import, 44/17 after a **reversed** re-import, 44/18 after the update, and M07 stays rev 2 after re-importing revision 1.
  - Also checked after a real API restart.
- **Conclusion: "M07 needs urgent customer follow-up".**
  - The cited quote, *"I expect an update or resolution in an hour or two, and I will inform you when they confirm."*, is verified to sit inside **M07 turn 19** by `verify_evidence.py`.
  - That script checks all 18 analyses and all 38 brief citations; a wrong turn number fails it.
  - Before the update, M07 shows "Awaiting analysis for revision 2", never an old analysis.

---

## 5 · Trade-offs, AI usage, limits, next

- **AI.** Analyses were drafted with AI assistance from the full text, human-reviewed, and machine-verified. They are labelled PREPARED.
  - A runtime Groq path exists (labelled RUNTIME); it gets the full record and is rejected if any quote doesn't verify.
  - Metrics, state, routing, replay and export are computed by the app.
- **Rejected:** shipping LLM-over-retrieved-chunks output. The early drafts misread C08, M10 and M04. The trade-off is that new text waits in "Awaiting analysis" until reviewed.
- **Limits:**
  - meeting owners are speaker labels only
  - M13/M04 left unmerged
  - reset is non-atomic via REST
  - no auth or search
- **Next:** reviewer sign-off on suggestions, due dates for stated commitments, and per-rep coaching pages.

---

# Recording script (≈3 min, your own voice)

1. **Dashboard, 0:00–0:45.** Explain "usable text 18/44 = usable ÷ selected records; missing text ≠ no conversation". Filter to Meera, then click into the attention list → M04.
2. **Difficult routing, 0:45–1:30.** On M04, show the three routes and their separate outputs; click E5 to jump to turn 11 ("credit is the main issue"). Mention the M13 association that is flagged but not merged.
3. **Replay, 1:30–2:45.** On Data & replay:
   - Clean start → Import initial (44/17) → Import initial reversed (still 44/17).
   - Open M07, set a manual route with a reason.
   - Import update: 44/18, M07 rev 2, **Awaiting analysis**, manual route still in effect.
   - Import initial again (M07 stays rev 2).
   - Restart the API or refresh: still there.
   - Apply the reviewed analysis.
4. **Export, 2:45–3:00.** Generate, then show that M07's manifest row has rev 2, manual_override yes, and its route file.
