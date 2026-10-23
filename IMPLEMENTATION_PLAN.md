# Volopay Revenue Intelligence Inbox — implementation plan

## Purpose and fixed scope

Build one clickable **Revenue Intelligence Inbox** for the supplied Volopay assessment package. It must help a manager inspect selected call and meeting activity, find conversation-backed work needing attention, understand evidence and uncertainty, correct a route, import a late transcript safely, and export the current state.

This plan is deliberately limited to the Revenue Intelligence Inbox. The separate College Event Management/Growth Associate assignment is out of scope.

The supplied package is the source of truth. Do not publish its datasets or attempt to identify real people.

## Verified assignment facts

| Fact | Requirement |
| --- | --- |
| Source records | 44 distinct records: 30 calls and 14 meetings. |
| Text coverage | 17 usable supplied texts in `01_initial.json`; 18 after `02_update.json`. Ten are calls and eight are meetings after the update. |
| Activity date | All selected activity is 21 August 2026 in Asia/Kolkata. Use call `started_at` and meeting `starts_at` for activity dates. |
| Record identity | Exact, case-sensitive pair: `(source_type, source_id)`. Never use `record_ref`, title, person, phone token, or array order as identity. |
| Revisions | Initial delivery is revision 1; M07 is revision 2. Ignore an equal or older revision. A newer revision replaces the entire source payload and transcript payload, including nulls. |
| Replay invariant | Unique record count remains 44 through every replay step. |
| Manual decision | A manual route must survive the M07 update and an app refresh/restart. |
| Evidence references | Meetings: source ID or readable record reference plus one-based supplied turn number. Calls: record reference/source ID plus a short exact adapted quote; do not invent call turn times. |

## Architecture and responsibility boundaries

Use the following implementation, keeping each service narrowly scoped:

| Component | Service | Responsibility |
| --- | --- | --- |
| Frontend | Next.js on Vercel | Manager dashboard, inbox, detail view, import/replay controls, correction controls, export download, definitions and states. |
| API | FastAPI on Render | Validation, revision-aware imports, aggregation, route state, export assembly, and access to external analysis services. |
| System of record | Supabase PostgreSQL | Raw current source records, import history, derived analysis, manual decisions, review state, export metadata, and persisted app state. |
| Retrieval | Pinecone | Searchable chunks from usable supplied conversation text only; preserve source/revision/chunk metadata. |
| Language analysis | Groq | Structured, evidence-bound analysis only. Use it to prepare or refresh suggestions, never as the authority on record identity, counts, revisions, or manual decisions. |

Simple RAG means: select a record, retrieve its own chunk(s) plus only narrowly relevant context when useful, ask Groq for structured analysis, validate the result, and persist it with the source revision it reflects. It is not an autonomous agent and is not needed to render the app.

### Reliability baseline

The application must have a reviewable path even when Pinecone or Groq is unavailable. Seed/import pre-generated, source-cited analyses for the supplied 18 texts; show those as **prepared analysis** with the source revision. For new or changed text, either run the optional analysis job or visibly mark the record **analysis pending review**. Never present stale analysis as current.

## Proposed repository layout

Create this structure before feature work. Keep source data private and outside public static assets.

```text
volopay-revenue-intelligence-inbox/
  frontend/                 # Next.js application
  backend/                  # FastAPI application
  data/                     # supplied private assessment inputs; excluded from public deployment
  analysis/                 # reviewed prepared analyses and route policy, with source references
  exports/                  # generated current export bundle; ignored except approved sample/manifest if needed
  docs/                     # architecture, metric definitions, replay and submission notes
  scripts/                  # explicit local setup, seed, replay and export entry points
  README.md
  AGENTS.md
```

Do not put raw source records, service-role keys, Groq keys, or Pinecone keys in the frontend or a Git repository.

## Environment configuration

Create separate example files; commit only examples with blank or clearly non-secret placeholders. Keep actual `.env` files local and in the deployment dashboards.

### `backend/.env.example`

| Variable | Required | Use |
| --- | --- | --- |
| `APP_ENV` | Yes | `development`, `test`, or `production`. |
| `APP_BASE_URL` | Yes | Public API base URL for generated links/CORS checks. |
| `FRONTEND_ORIGIN` | Yes | Exact Vercel/local frontend origin allowed by CORS. |
| `SUPABASE_URL` | Yes | Supabase project URL. |
| `SUPABASE_SERVICE_ROLE_KEY` | Server only | Backend database access; never expose it to the browser. |
| `SUPABASE_ANON_KEY` | Optional | Only if the backend genuinely needs it; do not use it as a substitute for server secrets. |
| `PINECONE_API_KEY` | Optional at first | Retrieval service credential. |
| `PINECONE_INDEX_NAME` | Optional at first | The dedicated index name for this app/environment. |
| `PINECONE_NAMESPACE` | Yes when retrieval enabled | Environment-scoped namespace, e.g. development or production. |
| `GROQ_API_KEY` | Optional at first | Server-only model credential. |
| `GROQ_MODEL` | Yes when analysis enabled | The selected structured-output-capable model identifier. |
| `EMBEDDING_PROVIDER` | Yes when retrieval enabled | Chosen embedding provider identifier; decide once and document it. |
| `EMBEDDING_MODEL` | Yes when retrieval enabled | Exact embedding model/version used for the index. |
| `EXPORT_ROOT` | Yes locally | Relative path used for generated export bundles. |
| `LOG_LEVEL` | Yes | Logging level without secret payloads. |

### `frontend/.env.example`

| Variable | Required | Use |
| --- | --- | --- |
| `NEXT_PUBLIC_API_BASE_URL` | Yes | Public FastAPI URL; this may be browser-visible. |
| `NEXT_PUBLIC_APP_NAME` | Yes | Display label. |
| `NEXT_PUBLIC_DEFAULT_TIME_ZONE` | Yes | `Asia/Kolkata`. |

Never prefix a secret with `NEXT_PUBLIC_`. Configure the same values in Vercel/Render/Supabase/Pinecone dashboards only after local verification.

## Data design

Use migrations and enforce the identity/revision rules in the database as well as the API. Names are illustrative; field meanings are mandatory.

| Entity | Required responsibility |
| --- | --- |
| `source_records` | One current row per `(source_type, source_id)` with record reference for display, last applied revision, current full source envelope/payload, current transcript payload, extracted local activity date, transcript availability, and timestamps. Unique constraint on the identity pair. |
| `import_runs` | Delivery batch ID, delivery revision, received time, source filename/checksum, totals, accepted/ignored/replaced counts, and errors. This is audit data, not a source-record identity. |
| `record_processing_state` | Intake/review state for all 44 records, usable-text flag, current analysis freshness, and reason for unavailable/pending/stale states. |
| `analyses` | Suggested route(s), concise type-specific output, evidence references, what the evidence establishes/does not establish, next action, stated owner only when supported, confidence/uncertainty, analysis source, and source revision analysed. Preserve history rather than overwriting it. |
| `manual_route_decisions` | Explicit manager route overrides, author label if supplied, timestamp, optional rationale, active/superseded status, and reset action. This table is independent from analysis. |
| `export_runs` | Export version/current flag, created time, bundle path, manifest path, and source-state snapshot reference. |

Store raw source material separately from any derived fields. The update replaces raw source fields for M07, but it must not replace a manual route. Use a database transaction for each accepted delivery so a failed import leaves no half-applied state.

## Routing and analysis policy

Do not lock the taxonomy before reviewing every final-state conversation. Begin with a small, explainable policy such as:

- Deal next step — an evidence-backed evaluation or commercial next action.
- Customer follow-up — an explicit request, problem, or response commitment involving an existing customer.
- Sales coaching — a specific, observable coaching opportunity.
- Internal/vendor action — a supported operational, integration, billing, or supplier matter.
- Human review — ambiguity, competing routes, unavailable text, or unsupported ownership.

A record may have multiple suggested routes. Each route must state whether it is suggested or manual, why it applies, its evidence reference, and the concrete destination/output it creates. If route-assignment counts exceed unique records, label that clearly.

For every text-backed analysis, produce a differentiated concise output—not a generic summary—with:

1. what happened and why it matters;
2. one or more findable evidence references;
3. what the evidence establishes and does not establish;
4. a next action; and
5. an owner only if the conversation/source explicitly establishes ownership.

For every record without usable supplied text, show an honest intake/review state such as `No usable supplied text — substantive analysis unavailable`. Do not create a fabricated summary or commercial inference.

### Prepared-analysis workflow

1. Apply both deliveries in an isolated review environment to reach final state.
2. Review all 18 usable final texts against the supplied conversation library.
3. Use RAG/Groq only as drafting assistance; verify every suggested route and evidence reference against the supplied text.
4. Save vetted prepared analyses with `analysis_source=prepared` and the exact source revision.
5. Seed those analyses in the app. On a later source revision, mark the prior analysis stale/pending until refreshed; retain it as history, not current truth.

## Exact implementation sequence

Complete a phase and its acceptance criteria before beginning the next. Do not start dashboard polishing or external deployment before the replay core works.

### Phase 0 — establish the project and decisions

1. Create the repository structure, root README skeleton, root `AGENTS.md`, ignore rules, and example environment files.
2. Copy the provided assessment data into a private local `data/` location; ensure it is ignored and never exposed through Next.js public assets.
3. Record architectural decisions: API owns imports/exports, Supabase owns durable state, prepared analysis is allowed, and optional RAG is server-only.
4. Write a concise metric-definition document before building cards.

**Accept:** no secret or raw source dataset is tracked; all assumptions distinguish source fact from product policy.

### Phase 1 — inspect and model the supplied data

1. Read `ASSIGNMENT.md`, `DATA_DICTIONARY.md`, `DATA_CONTRACT.md`, `CONVERSATIONS.md`, and `SUBMISSION_CHECKLIST.md`.
2. Build a record inventory directly from `01_initial.json`: 44 unique identities, source type, display reference, activity date, person field appropriate to type, and usable-text status.
3. Inspect `02_update.json`; confirm it contains only M07 at revision 2 and that it is an existing meeting identity.
4. Create a final-state conversation inventory of the 18 usable texts and their valid evidence-reference format.

**Accept:** the inventory reports 30 calls, 14 meetings, 17 initial usable texts, M07 update, and 18 final usable texts; no business conclusion has been invented.

### Phase 2 — create durable storage and import core

1. Implement Supabase migrations, constraints, indexes, and row-level access appropriate to a backend-owned application.
2. Implement delivery validation: expected envelope fields, permitted source types, `payload.id === source_id`, revision is an integer, and meeting/call transcript locations match the contract.
3. Implement one revision-aware upsert transaction per delivery: insert unseen identity, replace entire current source fields only for a higher revision, and log same/older records as ignored.
4. Derive usable supplied text exactly: nonblank call transcript, or at least one nonblank meeting turn.
5. Set/update processing state. A changed source text must make analysis stale or pending; leave manual decisions untouched.
6. Provide a non-production clean-reset workflow that deletes only app-owned local/test data and enables replay from a blank state.

**Accept:** import initial twice without count change; use a reordered initial delivery to prove order independence; database state contains exactly 44 identities.

### Phase 3 — backend read API and audit definitions

1. Expose read endpoints for dashboard metrics, filtered record list, record detail, evidence, import history, analysis freshness, manual decision state, and export metadata.
2. Expose write endpoints for import, manual route set/reset, optional analysis refresh, clean demo reset, and export generation.
3. Make metric definitions accessible in API and UI. Label counts as selected records; use Asia/Kolkata dates.
4. Keep people grouping type-aware: call rep fields are not interchangeable with meeting organiser fields. Do not imply organiser attendance or sales role.
5. Return actionable validation errors without raw secrets or source-data dumps.

**Accept:** each UI-needed state is available without querying Pinecone or Groq at page load.

### Phase 4 — source-grounded analysis and simple RAG

1. Define a versioned structured analysis contract before calling Groq, including allowed route IDs, evidence references, limitations, source revision, and parser validation.
2. Chunk only usable supplied text. Keep chunk boundaries and metadata sufficient to recover source record, source revision, record reference, call quote location or meeting turn number, and text hash.
3. Upsert Pinecone vectors idempotently using a stable record/revision/chunk key. Remove or supersede obsolete vectors on a newer text revision so retrieval cannot return old M07 text as current.
4. Retrieve narrowly. In a single-record analysis, prioritise chunks from that record; do not blend unrelated conversations into claimed evidence.
5. Send Groq only the necessary adapted text/context. Require structured output, validate it, verify citations against source text, and reject/mark pending malformed or unsupported output.
6. Persist a fresh analysis tied to the current source revision. Never overwrite manual decisions.
7. Prepare and review analyses for all 18 final texts. Clearly label prepared versus runtime-generated content in the product and README.

**Accept:** every visible recommendation has a valid source reference; no textless record has substantive analysis; changed M07 analysis is stale/pending or refreshed at revision 2.

### Phase 5 — implement the manager experience

1. Build the dashboard first: selected-record activity by day and person, transcript coverage, routing/review counts, visible definitions, and at least a working person or source-type filter. Because activity is one local day, do not rely on date filtering alone.
2. Build an inbox/list view that includes all 44 records, source type, activity date, person/organiser label, text availability, route/review state, analysis freshness, and filters.
3. Build the record-detail view: intact source metadata, readable conversation evidence, suggested analysis, manual route, uncertainty, prior/current analysis state, and an explicit route correction/reset control.
4. Build the 21 August 2026 Asia/Kolkata manager brief. It may be fixed/pre-generated. Include activity, important conversations, practical coaching/follow-up priorities, coverage limitation, and concise evidence links.
5. Make the manager flow discoverable: dashboard → filtered inbox → record → evidence → correction → export.

**Accept:** a reviewer can move from every headline metric and recommendation to its supporting records/text; manual and suggested routes are visually distinct.

### Phase 6 — exports and output organisation

1. Generate an actual current-state export bundle, not merely a proposed folder tree.
2. Produce one or more readable route/brief outputs plus a machine-readable JSON or CSV manifest.
3. Give every active manifest entry: `source_type`, `source_id`, applied source revision, route(s), output path(s), processing/review state, manual-override flag, and analysis freshness.
4. Use paths relative to the export bundle. Verify every active listed file exists. If a record has multiple outputs, retain source identity in each and show all outputs in the manifest.
5. On repeat export, either update one clearly identified current bundle or retain explicit versions with a clear current marker. Never leave unexplained duplicate active exports or obsolete active destinations.

**Accept:** a download/open action works; the manifest can be read independently and every path resolves within the bundle.

### Phase 7 — automated checks and mandatory replay

Implement focused tests for identity, revision ordering, whole-record replacement, text availability, analysis freshness, manual-route preservation, calculations, export manifest validity, and API validation. Then execute and document this exact end-to-end sequence:

1. Start clean; import `01_initial.json`.
   - Expect 44 unique records and 17 usable supplied texts.
2. Import the same initial delivery again, preferably with records reordered.
   - Expect 44 unique records; no inflated metrics.
3. Set a manual route for M07.
   - Expect a visible manual decision, separate from any suggestion.
4. Import `02_update.json`.
   - Expect M07 to remain one meeting record, show revision 2 text, and total usable supplied texts to become 18.
5. Confirm M07's manual route remains active.
   - Its analysis must be refreshed or visibly stale/pending at revision 2.
6. Import `01_initial.json` once more.
   - Expect the revision-1 M07 record to be ignored; M07 remains revision 2.
7. Refresh/restart the application.
   - Expect all 44 records, revision-2 M07 content, and its manual route to persist.
8. Generate and inspect an export.
   - Verify M07's current revision, manual override flag, active output paths, and analysis freshness in the manifest.

Capture screenshots or a short test log for this sequence; use them in the README, slides, and recording preparation.

### Phase 8 — deploy only after local replay passes

1. Create separate development and production configuration values; use a production Supabase project/schema and a production Pinecone namespace/index if feasible.
2. Deploy FastAPI to Render. Configure backend-only secrets, CORS for the exact Vercel origin, health endpoint, and persistent Supabase connection configuration.
3. Deploy Next.js to Vercel. Configure only browser-safe `NEXT_PUBLIC_*` values.
4. Seed the permitted prepared analyses and final post-update demo state. Provide one explicit clean-start/reset action or instruction for reviewers.
5. Test the live manager workflow, replay, export download, cold-start/loading/error states, and direct-navigation routes. Account for potential Render free-tier cold starts with honest UI feedback.

**Accept:** the private deployed app is usable without giving reviewers credentials or secrets. If a live service is unavailable, provide exact local startup/replay steps as the supported fallback.

### Phase 9 — assemble submission material

1. Complete README: setup, startup, private-data placement, environment variables, replay steps, reset, exports, metric definitions, analysis mode (prepared/runtime), approximate hours, limitations, and unfinished work.
2. Include the editable source without keys, dependency folders, or raw private data unless the recruiter explicitly requests the package privately.
3. Generate the actual export bundle and manifest.
4. Make five slides covering: manager problem/main findings; interface choices/omissions; routing/folder design and difficult case; a checked number and source-backed conclusion; AI, trade-offs, limits, and next steps.
5. State three important findings, each with a valid source passage and the screen/rule/output it influenced.
6. State one rejected decision, its reason, accepted trade-off, and resulting product choice.
7. Record one continuous three-minute screen capture with the applicant's own narration. Show a manager workflow, difficult route, repeated import with no count increase, M07 update, and preserved manual correction.
8. Submit a private URL or ZIP and recording/private link as requested by the recruiter.

## Testing and calculation guardrails

- Count distinct identities after revisions; a repeated import is never activity.
- Show selected-record scope, period, denominator, unknowns, and text-coverage limitations beside headline metrics.
- Do not treat source API-search totals as package totals.
- Do not equate `has_transcript=true` with usable text if turns are empty; do not equate a null call transcript with proof no conversation occurred.
- Use source-reported connection metrics only with the documented non-null denominator and unknown count; do not merge them with transcript-based assessment.
- Do not sum source-reported meeting duration as verified attendance time.
- Do not infer speaker talk ratios, identity mappings, company/account joins, deals, pipeline value, purchase commitments, staff roles, or ownership without evidence.
- Preserve null values when an update replaces a record; do not do a partial merge.
- Use exact string/case identity handling and a database unique constraint.
- Never log full private conversation text, raw credentials, or service tokens in client-visible logs.

## Definition of done

The project is ready only when all of the following are true:

- All four required capabilities work: manager workspace, routed/evidence-backed analysis, actual export bundle, and replay-safe imports/corrections.
- The final app contains the correct 44-record, 18-text post-update state and offers a documented clean replay path.
- M07 remains one identity at revision 2 after the full replay and retains its manual route after restart.
- Every substantive recommendation is traceable to a valid supplied passage and declares uncertainty/limits.
- All 44 records have visible intake/review state, including honest no-text states.
- The export manifest and all active output paths validate.
- The README, five slides, three findings, rejected decision, and narrated three-minute recording are complete.
- No source data or secrets are publicly exposed.
