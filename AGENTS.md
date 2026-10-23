# AGENTS.md — Volopay Revenue Intelligence Inbox

## Mission and boundaries

Implement only the **Revenue Intelligence Inbox** in the supplied assessment package. Do not implement or reference the separate College Event Management/Growth Associate assignment.

Treat these files as the governing product contract, in this order when they address the same issue:

1. `DATA_CONTRACT.md` — identity, revision, replay, evidence, and export rules.
2. `DATA_DICTIONARY.md` — field meaning, calculation limits, dates, and uncertainty.
3. `ASSIGNMENT.md` — required product capabilities and assessment expectations.
4. `SUBMISSION_CHECKLIST.md` — submission evidence.
5. `CONVERSATIONS.md` — convenient final-state reading library, not an alternate delivery source.

Do not invent requirements, customer/deal links, business outcomes, roles, ownership, or transcript evidence. If a requirement is ambiguous, keep the UI/data state explicit and conservative rather than silently guessing.

## Non-negotiable data rules

- The only record identity is the exact, case-sensitive tuple `(source_type, source_id)`.
- Never use `record_ref`, title, person, email, phone token, company, or array position for identity or deduplication.
- Apply a delivery only when its revision is greater than the last applied revision for that identity. Ignore same or older revisions.
- A newer revision replaces the complete source payload and transcript payload, including null values. Do not partially merge source fields.
- The initial delivery has 44 records, 30 calls, 14 meetings, and 17 usable supplied texts. The update is revision 2 for M07; final state remains 44 records and has 18 usable supplied texts.
- A usable call text is a nonblank `payload.transcript`. A usable meeting text has at least one nonblank `transcript_payload.turns[].text`.
- Keep raw source state, derived analysis, processing state, suggested route, and manual route in separate fields/tables.
- A manual route is a human decision. It must never be overwritten by import, analysis, update, refresh, or restart unless the user explicitly resets it.
- When text changes, mark derived analysis stale/pending or refresh it at the new revision. Never display old analysis as current.
- All selected activity is 21 August 2026 in `Asia/Kolkata`. Use call `started_at` and meeting `starts_at` for activity views.

## Evidence and analytical integrity

- Review all 18 final-state usable conversations before finalizing the routing taxonomy or manager brief.
- Every substantive recommendation needs a findable supporting passage and a statement of what that evidence does **not** establish.
- Cite meeting evidence using source ID or readable record reference plus a one-based supplied turn number.
- Cite call evidence using source ID/record reference plus a short exact adapted quote. Do not invent call turn numbers, timecodes, speakers, or talk ratios.
- Do not create substantive analysis for records without usable supplied text. Use an explicit state such as `No usable supplied text — analysis unavailable`.
- Do not infer purchase commitment, deal value, pipeline total, account ownership, cross-record identity, staff role, attendance, or next-action ownership without source support.
- Treat source metadata as source-reported where applicable. In particular, do not combine source connection status with transcript-based judgments, and do not treat meeting duration as verified attended time.
- If a conclusion is ambiguous, route to human review or give multiple labelled suggested routes; explain why.

## Product requirements that must work

- A manager dashboard with selected-record activity by day and person, usable-text coverage, route/review counts, metric definitions, and a working person or source-type filter.
- A route from metrics to source records, and from recommendations to readable source evidence.
- A concise 21 August 2026 Asia/Kolkata manager brief covering activity, priorities, coaching/follow-up, and coverage limits.
- An inbox/detail experience for all 44 records that exposes source type, text availability, processing/freshness, suggested route(s), manual route, and correction/reset actions.
- Actual generated outputs plus a machine-readable export manifest. Each active manifest row must include source identity, applied revision, route(s), output path(s), processing/review state, manual-override flag, and analysis freshness. Paths must be relative to the export bundle and must exist.
- A documented clean-start/reset path and the full replay path.

## Required replay acceptance test

Before calling the work complete, run and document exactly this sequence:

1. Clean state → import `01_initial.json`: 44 unique records; 17 usable supplied texts.
2. Import the initial delivery again, preferably reordered: still 44 unique records and no inflated counts.
3. Set a manual route on M07.
4. Import `02_update.json`: M07 remains one record, applies revision 2 text, total usable supplied texts becomes 18.
5. Verify M07's manual route survives; analysis is refreshed or visibly stale/pending.
6. Import `01_initial.json` again: revision 1 cannot overwrite M07 revision 2.
7. Refresh/restart: records, M07 revision-2 text, and manual route persist.
8. Generate an export and validate every active manifest path.

Do not start deployment, slide production, or cosmetic polish until this test works locally.

## Architecture rules

- Use Next.js for the browser experience, FastAPI for the API/import/export boundary, Supabase PostgreSQL as the durable system of record, Pinecone only for retrieval, and Groq only for structured language analysis.
- The browser communicates with FastAPI, not directly with Groq, Pinecone, or privileged Supabase credentials.
- API endpoints, database constraints, and tests must each enforce the important data rules; do not rely on UI checks alone.
- External AI/retrieval services are optional for basic review. The supplied data must remain reviewable through prepared, source-cited analysis if those services are unavailable.
- Label prepared analysis and runtime-generated analysis clearly. Tie all analysis to the source revision it reflects.
- Use stable vector IDs containing record identity, source revision, and chunk identity. Do not retrieve old M07 chunks as current after revision 2.
- Keep imports/export operations idempotent and transactional. A failed delivery must not leave partial state.

## Secrets, privacy, and deployment

- Never commit `.env` files, API keys, Supabase service-role credentials, raw assessment data, export bundles containing private data, dependency directories, or build artifacts.
- Never place a secret in `NEXT_PUBLIC_*`, browser code, screenshots, recordings, slides, logs, or error messages.
- Keep the supplied de-identified data private. Do not publish it in a public repository, public Vercel asset, public demo, issue, or prompt.
- Use example environment files with names and explanations only; actual values live locally or in the relevant service dashboard.
- Do not run destructive database operations, reset production data, modify deployment configuration, or expose a public deployment without explicit user authorization.
- Configure CORS to exact frontend origins; do not use a wildcard in production.

## Implementation order

Follow this dependency order. Do not skip ahead.

1. Read the governing package documents and inventory the JSON contract.
2. Create project structure, ignore rules, example environment files, metric definitions, and migrations.
3. Implement and test revision-aware import plus clean reset.
4. Implement durable state, read/write API, and calculations.
5. Build and validate prepared analysis/RAG pipeline with source citations.
6. Build dashboard, inbox, detail, correction, and manager brief UX.
7. Implement actual export bundle and manifest validation.
8. Run the required replay and regression tests.
9. Deploy only after local acceptance is green.
10. Produce README, slides, findings, rejected decision, and narrated recording from the verified app.

If a later phase reveals a data-model flaw, fix the lower layer and rerun its tests; do not patch around it in the UI.

## Quality gates for each change

- Read the relevant source contract before changing import, analysis, metric, export, or replay code.
- Add or update a focused automated test for every changed rule, regression, or endpoint behaviour.
- Run the smallest affected checks first, then the full lint/type/test/build checks declared by the repository before handoff.
- Inspect database migrations and generated export manifest paths manually after related changes.
- Re-run the complete replay after any change to identity, revision, import, processing state, manual routing, analysis freshness, or exports.
- Keep changes small and single-purpose. Do not combine schema changes, broad refactors, UI redesigns, dependency upgrades, and deployment changes in one unverified change.
- Preserve working existing behavior unless a documented requirement explicitly changes it.

## Handoff standard

Do not claim a check, replay step, deployment, or finding was completed unless it was actually completed and recorded.

Before final handoff, provide:

- files changed and their purpose;
- checks actually run and their result;
- replay result, including 44/17/18 invariants and M07 preservation;
- export/manifest verification result;
- prepared-versus-runtime AI explanation;
- known limitations, incomplete work, and any required setup; and
- confirmation that no secrets or private source data were included in the deliverable.
