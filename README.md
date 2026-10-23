# Revenue Intelligence Inbox

A workspace for a sales manager reviewing one day (21 August 2026, Asia/Kolkata) of calls, meetings and transcripts: 44 records, 18 of them with usable text.

| | |
|---|---|
| **Live app** | <https://revenue-intelligent-inbox-phi.vercel.app> |
| **API docs** | <https://revenue-intelligent-inbox-518o.onrender.com/docs> (free tier: the first request after idle takes 30–60 s) |
| **Stack** | Next.js 14 · FastAPI · Supabase Postgres · Groq (optional) · Pinecone (optional) |
| **Analysis** | Prepared and human-reviewed, with every quote machine-checked; runtime AI is optional and labelled (see §6) |

## Review it in 5 minutes

1. **Dashboard:** headline numbers, each with its definition underneath. Try the person filter (for example, Meera).
2. **Needs attention → M04:** one record with three routes, each with its own output. Click **E5** to jump to the cited passage (turn 11).
3. **Brief:** the 21 August manager brief. Every item links to its source passage.
4. **Data & replay:** run steps 0–8 (table in §2) and watch the counters: 44 records, 17 → 18 texts, M07 at revision 2, and M07's manual route preserved.
5. **Export:** Generate, then **Download current bundle (.zip)**.

The first screen answers four questions:

1. **What happened?** Activity by hour and by person, with call reps and meeting organisers kept separate.
2. **What needs me?** A ranked attention list.
3. **Why should I believe it?** Every recommendation links to the exact transcript passage behind it.
4. **What did the system decide, and what did I decide?** Suggested routes and manual routes are stored and shown separately.

**Contents:** 1 Run locally · 2 Replay checks · 3 Outputs · 4 Metrics · 5 Routing · 6 AI usage · 7 Findings · 8 Rejected decision · 9 Limitations · 10 Deploy

---

## 1. Run it locally

Prerequisites: Python 3.12, Node 18+, and a Supabase project with `backend/migrations/001…008` applied (SQL editor or `scripts/apply_migrations.py`).

```bash
# 1. Private data (not in git): copy the two supplied deliveries into ./data/
#    data/01_initial.json   data/02_update.json

# 2. API
cd backend
python -m venv .venv && .venv\Scripts\activate        # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt                        # or requirements-deploy.txt (no torch)
copy .env.example .env                                 # fill SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY (Groq/Pinecone optional)
uvicorn app.main:app --port 8000

# 3. Web app
cd ../frontend
npm install
copy .env.example .env.local                           # NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
npm run dev                                            # http://localhost:3000
```

**Open in the final post-update state:** go to **Data & replay → One-click demo load**. This runs reset → `01_initial` → `02_update` → apply reviewed analyses. You can also call `POST /admin/demo-load`.

**Clean start:** **Data & replay → 0 · Clean start**, or `POST /admin/reset`. Both are disabled when `APP_ENV=production`.

## 2. Reproduce the replay checks

**In the app** (Data & replay page; the counters at the top show records, usable texts, M07 revision and M07 manual route):

| Step | Button | Expect |
|---|---|---|
| 0 | Clean start | 0 records |
| 1 | Import 01_initial.json | 44 records, 17 usable texts |
| 2 | Import 01_initial again, **reversed order** | still 44 / 17; 44 ignored |
| 3 | Open M07 → *Correct the route…* → Save | "MANUAL ROUTE IN EFFECT" |
| 4 | Import 02_update.json | 44 records, 18 usable; M07 is rev 2; M07 shows **Awaiting analysis for revision 2** and the manual route is still in effect |
| 5 | Import 01_initial again | M07 stays rev 2 (rev 1 ignored) |
| 6 | M07 → *Apply reviewed analysis for this revision* (or button 6) | rev-2 analysis is current; manual route still in effect |
| 7 | Restart the API / refresh the browser | everything persists (Postgres) |
| 8 | Export → Generate | manifest shows M07 rev 2, `manual_override: true` |

**From the command line** (API running on :8000):

```bash
python scripts/replay_acceptance_test.py   # the full 8-step sequence, 30+ assertions → "ALL CHECKS PASSED"
python scripts/validate_export.py          # checks every path in the current bundle
python scripts/verify_evidence.py          # offline: every quote in every analysis + the brief is verbatim in the source
```

The last recorded run is in `replay_log.txt`. All three scripts pass.

## 3. Where outputs are written

`backend/exports/` (`EXPORT_ROOT`). Each export writes a new versioned bundle; `CURRENT` names the current one, and older bundles are marked superseded in `export_runs`. The bundle can also be downloaded from **Export → Download current bundle (.zip)**.

```
export_YYYYMMDD_HHMMSS/
├── README.md
├── manifest.json                  one entry per record (44)
├── manifest.csv                   one row per output file
├── manager_brief_2026-08-21.md    shared output citing many records
├── records/<ref>_<type>_<source_id>.md          dossier for every record, including no-text ones
└── routes/<route_folder>/<ref>_<type>_<source_id>.md   one file per ACTIVE route
    deal_next_steps/ customer_follow_ups/ sales_coaching/ internal_vendor_notes/ human_review/ log_only/
```

**Several outputs per conversation.** M04 has three route files. Each repeats the source identity and revision, links back to the record dossier, and names its sibling routes ("Also routed to: …").

**Corrections.** When a manager overrides a route, only the manual route gets a destination file. The suggestions it replaced are listed in the manifest as `superseded_suggested_routes`.

**Manifest fields per entry:** `source_type`, `source_id`, `applied_revision`, `review_state`, `analysis_freshness`, `analysis_source`, `suggested_routes`, `manual_route`, `manual_override`, `effective_routes`, `superseded_suggested_routes`, `outputs[] {kind, route_id, path}`, and `output_paths`. All paths are relative POSIX paths inside the bundle.

## 4. Metric definitions

These are shown in the app under **Dashboard → Metric definitions**, and as a tip under every headline number.

- **Selected records.** Distinct `(source_type, source_id)` after applying revisions. Re-imports never add rows. This is a selected sample, not a whole-team day.
- **Period.** 21 Aug 2026, Asia/Kolkata. Calls use `started_at` and meetings use `starts_at`. Everything falls on one date, so the dashboard shows activity **by hour** and has **person and source-type filters**.
- **Usable supplied text.** A non-blank call `payload.transcript`, or at least one non-blank meeting turn. Coverage = usable ÷ selected records in the same filter (18/44 in the final state: 10/30 calls, 8/14 meetings).
- **Call reps vs meeting organisers.** Calls group by `rep_name`; meetings group by `organizer_email`. They are never merged, and an organiser is not assumed to be a salesperson or an attendee.
- **Connected calls (source-reported).** `is_connected = true` ÷ calls with non-null `is_connected`, with unknowns shown separately. It is never combined with transcript judgements.
- **Route assignments vs routed records.** A record can have several routes: 35 assignments on 18 records with suggestions only. A manual route replaces the suggestions, so a manual route on M07 (which has two suggestions) shows 34.
- **Review state.** One of: `no_text`, `awaiting_analysis` (new or changed text without an analysis of the current revision), `needs_human_review`, `manual_override` or `suggested`. All 44 records have one.

## 5. Routing taxonomy

| Route | When |
|---|---|
| Deal / partner next step | Prospect or partner evaluation with a concrete next step the text supports |
| Customer follow-up | An existing customer's problem or request, or a commitment SpendNest made to them |
| Sales coaching | A specific behaviour in the conversation worth correcting or reinforcing |
| Internal / product / vendor | Supplier evaluation, product defect or gap, internal process knowledge |
| Human review | Ambiguity, a source label that conflicts with the text, or an unsupported conclusion |
| Log only | It happened, but the text supports no follow-up |

Each route on a record carries its **own** output (a coaching note is not a follow-up task), its priority, its evidence reference, and an owner **only when the text states one**.

## 6. AI usage: what is prepared and what is computed

- **Prepared (shipped) analyses.** The 18 analyses in `analysis/prepared/*.json` and the brief in `analysis/manager_brief.json` were written by reading every full conversation in its final state, with AI assistance (Claude) for drafting. They are labelled **PREPARED** in the UI and in exports.
  - **Every quote is machine-checked.** `scripts/verify_evidence.py` confirms each call quote is an exact substring of the transcript, and each meeting quote sits inside the turn it cites. The check also runs whenever a prepared analysis is applied.
  - **Analyses are tied to a source revision.** The M07 analysis is for revision 2, so it cannot attach to the revision-1 record.
- **What the app computes at runtime.** Identity and revision handling, every count and metric, review state and freshness, the route in effect, label-conflict flags, the brief's live activity numbers, and the export.
- **New or changed text.** The record shows **Awaiting analysis for revision N**, and any older analysis is kept as history only. The manager can then either:
  - apply the reviewed analysis for that exact revision (the human-assisted path), or
  - click **Generate runtime analysis (Groq)**. This sends the record's full text (meeting turns numbered) and requires verbatim quotes. **Any quote that can't be found rejects the output**, nothing is stored, and the record stays awaiting analysis. Runtime results are labelled RUNTIME.
- **Pinecone** is an optional index under revision-scoped vector IDs. Nothing in the UI depends on it, and it is skipped if unavailable.
- **No secrets** are in the repo or the browser. `.env` files are git-ignored, and only `NEXT_PUBLIC_API_BASE_URL` reaches the client.

## 7. Three findings

1. **Credit, not prepaid, is the recurring product gap, and it is a retention risk with an existing customer.** An Asterloom buyer stopped the demo: *"Wait, these are prepaid? I had thought about a corporate credit card."* (**M03 turn 6**). Cedarwave, an existing customer whose card programme is closing: *"moving from prepaid to credit is the main issue for us. At some stage we will have to consider another option for that."* (**M04 turn 11**).
   - *Where it shows:* M04 is the brief's #2 priority with a `customer_follow_up` + `internal_vendor_action` route, and the brief's "Product and vendor signals" section names the theme. The M03 coaching note says to set the prepaid expectation early.
2. **Stored outcome labels contradict the text, so routing never trusts them.** C10 is labelled `follow_up`, but the prospect said *"No. I said I will contact you if there is anything to discuss."* C02 is flagged `is_conversation=true`, but the caller only reached a receptionist (*"It looks as though she isn't in the office today."*). C05's `follow_up` is a deck for a hypothetical switch.
   - *Where it shows:* the "label conflict" flags in the Inbox, the "Source label check" box on each record, the Dashboard's "Stored label conflicts" list, and the brief's Data quality section. C10 is routed to Sales coaching ("respect a declined follow-up").
3. **Per-person attribution can't always be trusted.** C06 is attributed to rep `Meera`, but the caller says *"Good evening. Ravi here."*
   - *Where it shows:* C06 is routed to **Human review** (attribution) rather than feeding Meera's coaching. The dashboard's Call reps table notes the conflict and still counts the call under the source `rep_name`, without reassigning it silently.

Also worth a look: **M07** (late transcript) contains a time-bound promise, *"I expect an update or resolution in an hour or two"* (turn 19), which makes it the brief's #1 priority.

## 8. A decision I rejected

**Rejected:** shipping LLM/RAG output (Groq over top-k Pinecone chunks) as the analyses. The project's first drafts did exactly this, and they were wrong in ways a manager would act on:
- C08 was called an "ambiguous inbound call"; it is an outbound cold call that produced a referral.
- M10 was "cannot be routed"; it is internal billing training.
- M04, an existing customer at risk, was filed as a generic "migration" task.

The model had reasoned from the opening chunk only.

**Chosen instead:**
- Human-reviewed prepared analyses, with every quote mechanically verified against the source text.
- The runtime LLM is kept only as an explicitly labelled option. It receives the full record and is rejected outright on any unverifiable quote.

**Trade-off accepted:** a new transcript does not get an instant automatic analysis. It shows **Awaiting analysis** until a human applies a reviewed one or generates a verified runtime one.

*In the product:* the M07 page after the update, the PREPARED/RUNTIME labels, `verify_evidence.py`, and the rejection path in `analysis_service.run_analysis_for_record`.

## 9. Known limitations and what I would do next

- **Meeting owners are speaker labels.** No organiser-to-speaker mapping is supplied, so meeting owners appear as "Team member A (stated)".
- **M13 and M04 are not merged.** M13 may be the same Cedarwave migration meeting as M04, but only the title suggests it, so it is flagged rather than merged.
- **Reset is not atomic in this environment.** When direct Postgres access is unavailable, reset uses PostgREST deletes. Imports themselves are atomic (a single `import_delivery` SQL function).
- **Marking stale on text changes.** The import SQL marks analysis stale only when the usable-text flag changes. The API derives freshness by comparing revisions, so a changed but still-usable text also shows as awaiting analysis.
- **Not built:** authentication, account matching, search, CRM writes, or automated tests beyond the replay, export and evidence scripts.
- **Next:**
  - a "reviewed by" sign-off on suggested routes
  - due dates for the stated commitments (M07's 1–2 hours, M09's "today or Monday")
  - a person page combining coaching notes per rep

**Approximate time spent:** _fill in before submitting_.

## 10. Deploy (private demo)

Currently deployed at the links at the top: the API on Render, the web app on Vercel, both using the same Supabase database.

**API on Render**
1. New → Web Service → this repo.
2. Root directory `backend`.
3. Build command `pip install -r requirements-deploy.txt`.
4. Start command `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
5. Environment variables:
   - `APP_ENV=development` (keeps the replay buttons enabled for reviewers)
   - `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY`
   - `FRONTEND_ORIGIN=https://<your-app>.vercel.app,http://localhost:3000`
   - `EXPORT_ROOT=exports`
   - optional: `GROQ_API_KEY`, `GROQ_MODEL`

**Web app on Vercel**
1. New Project → this repo.
2. Root directory `frontend`.
3. Environment variable `NEXT_PUBLIC_API_BASE_URL=https://<your-api>.onrender.com`.

**Data on a hosted deployment.** The raw data is not in git. The hosted app reads the same Supabase database, so it opens in whatever state was last loaded.

To make the replay buttons and demo-load work on Render, add the two deliveries as **Secret Files** named `initial.json` and `update.json` (Render names must start with a letter) (Render → Environment → Secret Files) and set `DATA_DIR=/etc/secrets`. Without them, demo-load refuses and resets nothing, and you can still replay with **Data & replay → upload a delivery file**.

`render.yaml` describes the API service.
