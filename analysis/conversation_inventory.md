# Conversation Inventory — Phase 1 (data inspection only)

This is a **data inventory** for the Volopay Revenue Intelligence Inbox. It lists all 44 supplied source records and the 18 usable supplied texts. It contains **no business conclusions, routing, taxonomy, or commercial inference** — those belong to later phases. Every field below is read directly from `data/01_initial.json` and `data/02_update.json` and verified by `scripts/inspect_data.py` (all Phase 1 acceptance checks pass).

## Rules applied (from the governing documents)

- **Identity** (`DATA_CONTRACT.md`): the only record identity is the exact, case-sensitive tuple `(source_type, source_id)`. `record_ref`, title, person, email, phone token, company and array position are **not** identity keys and are not used for deduplication.
- **Revisions** (`DATA_CONTRACT.md`): the initial delivery is revision 1; the update is revision 2. A newer revision replaces the entire source/transcript payload of the matching identity; same or older revisions are ignored. The update supplies M07's usable text, which was withheld from the initial delivery.
- **Usable text** (`DATA_DICTIONARY.md`): a call is usable when `payload.transcript` is non-blank; a meeting is usable when at least one `transcript_payload.turns[].text` is non-blank.
- **Activity date** (`DATA_DICTIONARY.md`): calls use `payload.started_at`, meetings use `payload.starts_at`, viewed in Asia/Kolkata. All selected activity is 2026-08-21 Asia/Kolkata. (Dates were shifted consistently by whole weeks; this is a selected sample, not a team day or performance ranking.)
- **Person field**: calls use `payload.rep_name` (the caller display label — not a verified staff role). Meetings have **no `organizer_name` field** in the payload; the only organiser identifier supplied is `payload.organizer_email`, so that is reported as the meeting person. Per `DATA_DICTIONARY.md`, `organizer_email` is an adapted calendar organiser identifier, **not** proof of attendance or of a selling role, and no organiser-to-transcript-speaker mapping is supplied.
- **Evidence citation** (`DATA_CONTRACT.md`): meeting passages cite the `source_id` and the 1-based turn number in the supplied `turns` array (a readable `record_ref` plus that turn number is also acceptable); call evidence cites the `source_id`/`record_ref` plus a short exact quote from the adapted text. No speaker timecodes or talk ratios are invented.
- `CONVERSATIONS.md` is used as the readable final-state reading library. The exact quotes and turn numbers below are taken from the supplied JSON (`01_initial.json`, and `02_update.json` for M07), which is the authoritative supplied text; `CONVERSATIONS.md` mirrors that text for reading.

## Final state

After applying `02_update.json` (revision 2 for M07) on top of `01_initial.json` (revision 1):

- Unique records: **44** (30 calls, 14 meetings)
- Usable supplied texts: **18** (10 calls, 8 meetings) — 17 initially; the 18th (M07) arrives in the update
- Duplicate identities: **0**
- Activity date: **2026-08-21** Asia/Kolkata for all 44 records

## Inventory — all 44 records

`record_ref` is display only. `source_id` is the exact identity string (paired with `source_type`). "Person" is `rep_name` for calls and `organizer_email` for meetings (see note above).

| record_ref | source_type | source_id | person | activity date | usable supplied text |
|---|---|---|---|---|---|
| B01 | call | 4868e5cd-5ab8-581c-a0e4-acc37385f0cf | Arun | 2026-08-21 | No |
| B02 | call | 5747e4cd-e24f-5bed-bf74-9e3f326b2d77 | Leela | 2026-08-21 | No |
| B03 | call | 024caffc-d16e-5843-b325-682dbc8d448e | Arun | 2026-08-21 | No |
| B04 | call | 530207ea-d67b-521a-8085-bdb9ae665417 | Arun | 2026-08-21 | No |
| B05 | call | 903641e9-d761-591a-a149-334ddfcd236e | Leela | 2026-08-21 | No |
| B06 | call | 53f61c95-27b9-50c2-8755-08f957594950 | Leela | 2026-08-21 | No |
| B07 | call | f9be8537-1ad9-58fc-be24-78f73d09db9c | Arun | 2026-08-21 | No |
| B08 | call | 77350513-913c-5fed-b4e6-71009de9df03 | Leela | 2026-08-21 | No |
| B09 | call | 747390bc-f359-5609-bf79-0a44ef8919bd | Arun | 2026-08-21 | No |
| B10 | call | 3ea930a1-0496-51e3-9dca-adc3be29331a | Arun | 2026-08-21 | No |
| B11 | call | bfefcb48-1a98-5610-a0ee-0f03434188a9 | Leela | 2026-08-21 | No |
| B12 | call | 9a64eb58-d462-5a6e-aa9e-c0f88852ebe0 | Arun | 2026-08-21 | No |
| B13 | call | 6521ed7d-53fc-5b3b-be77-7d4610c90ed7 | Arun | 2026-08-21 | No |
| B14 | call | 81da63f4-eac6-5efd-95e1-69ad6e6def25 | Leela | 2026-08-21 | No |
| B15 | call | 2ada5ab0-8a84-54b7-a071-cd5bd6ad5abd | Arun | 2026-08-21 | No |
| B16 | call | 1f5181ed-4175-5d73-a16b-01d404b1820d | Leela | 2026-08-21 | No |
| B17 | call | 1645d595-1896-5201-9395-cb8a9f1c5f3a | Arun | 2026-08-21 | No |
| B18 | call | 26c3ccc3-63a6-55f6-a5a3-e279b36b7e88 | Arun | 2026-08-21 | No |
| B19 | call | 6ee11c0e-c74a-5805-b552-657443378b72 | Arun | 2026-08-21 | No |
| B20 | call | 94b4f015-b243-5b89-b435-9957125ecdd4 | Leela | 2026-08-21 | No |
| C01 | call | 2ec4404c-beee-5377-a63c-aab701da08ed | Arun | 2026-08-21 | Yes |
| C02 | call | 4b870624-8aad-5315-a60e-0db95981cf99 | Arun | 2026-08-21 | Yes |
| C03 | call | 20d509ba-d589-5334-9aef-ea4ce6105b1a | Kiran | 2026-08-21 | Yes |
| C04 | call | bcdcbf56-d338-5c78-9a97-42c2fc1c9931 | Arun | 2026-08-21 | Yes |
| C05 | call | 75a6b94f-7717-5cfb-9e41-0acc94415e17 | Meera | 2026-08-21 | Yes |
| C06 | call | 12216d5c-e254-52c6-b344-47de4c6e1ae5 | Meera | 2026-08-21 | Yes |
| C07 | call | 428817fa-7e9e-5418-a7d4-bb396d28dfbf | Dev | 2026-08-21 | Yes |
| C08 | call | 129497b2-8e1d-5e01-919c-e8a852b5ff68 | Meera | 2026-08-21 | Yes |
| C09 | call | 4a1de681-f884-55e8-b1ad-de22d17cd959 | Meera | 2026-08-21 | Yes |
| C10 | call | b747f592-810e-583c-9b81-8db5ab035806 | Meera | 2026-08-21 | Yes |
| M01 | meeting | cb5cecac-e68d-52b7-b10b-b0c748efc467 | team06@example.com | 2026-08-21 | Yes |
| M02 | meeting | 1a21c409-c050-5787-90af-2667e057e1b6 | team07@example.com | 2026-08-21 | Yes |
| M03 | meeting | 398672e7-62dd-5afd-846d-0237d49792fb | team08@example.com | 2026-08-21 | Yes |
| M04 | meeting | b0f79b3d-37ba-52f9-b2bc-58b159dd6d91 | team09@example.com | 2026-08-21 | Yes |
| M05 | meeting | e0ecb112-ed94-5e8e-ae71-19def5536337 | team08@example.com | 2026-08-21 | No |
| M06 | meeting | 657b9e9d-9472-5b01-a127-a648ad7e8cf7 | team10@example.com | 2026-08-21 | Yes |
| M07 | meeting | 4f304fff-fd40-5cfc-a366-0a134c445c2a | team09@example.com | 2026-08-21 | Yes (revision 2) |
| M08 | meeting | 883182d8-eb86-56f9-a928-152365998d15 | team08@example.com | 2026-08-21 | No |
| M09 | meeting | 4b5b9192-f3fc-505a-8e77-4d2ffaa54594 | team11@example.com | 2026-08-21 | Yes |
| M10 | meeting | 337f297d-9385-5b82-9e54-5019c1ed912c | team12@example.com | 2026-08-21 | Yes |
| M11 | meeting | fc651475-187c-5882-a644-b501408e8647 | team13@example.com | 2026-08-21 | No |
| M12 | meeting | c759b921-e9d3-540c-a06b-474c5710342d | arun@example.com | 2026-08-21 | No |
| M13 | meeting | 794a9d1c-889d-5957-873f-8a1271b03455 | team09@example.com | 2026-08-21 | No |
| M14 | meeting | 93f4867d-65cd-5236-bc55-7bd57df8ac24 | team14@example.com | 2026-08-21 | No |

## Usable records — evidence citations (18)

For each usable record, one evidence citation is given in the `DATA_CONTRACT.md` format. These are **descriptive references demonstrating the citation format** — they are not findings, recommendations, or analysis. Call quotes are short exact substrings of the supplied adapted transcript; meeting citations use the 1-based turn number in the supplied `turns` array.

### Calls (10 usable)

**C01** — source_type: call · source_id: `2ec4404c-beee-5377-a63c-aab701da08ed` · person (rep): Arun · usable text: YES
> Citation: `2ec4404c-beee-5377-a63c-aab701da08ed` — "Hi Pranav, Arun calling from SpendNest."

**C02** — source_type: call · source_id: `4b870624-8aad-5315-a60e-0db95981cf99` · person (rep): Arun · usable text: YES
> Citation: `4b870624-8aad-5315-a60e-0db95981cf99` — "Good morning, you've reached Fernhaven Group."

**C03** — source_type: call · source_id: `20d509ba-d589-5334-9aef-ea4ce6105b1a` · person (rep): Kiran · usable text: YES
> Citation: `20d509ba-d589-5334-9aef-ea4ce6105b1a` — "Hello? Hi Milan, Kiran here from SpendNest."

**C04** — source_type: call · source_id: `bcdcbf56-d338-5c78-9a97-42c2fc1c9931` · person (rep): Arun · usable text: YES
> Citation: `bcdcbf56-d338-5c78-9a97-42c2fc1c9931` — "Arun from SpendNest, following up on our earlier conversation about expense software for Lanternpath Media."

**C05** — source_type: call · source_id: `75a6b94f-7717-5cfb-9e41-0acc94415e17` · person (rep): Meera · usable text: YES
> Citation: `75a6b94f-7717-5cfb-9e41-0acc94415e17` — "I'm with SpendNest."

**C06** — source_type: call · source_id: `12216d5c-e254-52c6-b344-47de4c6e1ae5` · person (rep): Meera · usable text: YES
> Citation: `12216d5c-e254-52c6-b344-47de4c6e1ae5` — "SpendNest brings invoices, vendor payments and documents into one dashboard."

**C07** — source_type: call · source_id: `428817fa-7e9e-5418-a7d4-bb396d28dfbf` · person (rep): Dev · usable text: YES
> Citation: `428817fa-7e9e-5418-a7d4-bb396d28dfbf` — "Dev calling from SpendNest."

**C08** — source_type: call · source_id: `129497b2-8e1d-5e01-919c-e8a852b5ff68` · person (rep): Meera · usable text: YES
> Citation: `129497b2-8e1d-5e01-919c-e8a852b5ff68` — "What is it regarding? I'm from SpendNest."

**C09** — source_type: call · source_id: `4a1de681-f884-55e8-b1ad-de22d17cd959` · person (rep): Meera · usable text: YES
> Citation: `4a1de681-f884-55e8-b1ad-de22d17cd959` — "I'm with SpendNest, an expense platform."

**C10** — source_type: call · source_id: `b747f592-810e-583c-9b81-8db5ab035806` · person (rep): Meera · usable text: YES
> Citation: `b747f592-810e-583c-9b81-8db5ab035806` — "SpendNest brings together scheduled payments and approval workflows so managers can see more of what is happening across operations and finance."

### Meetings (8 usable, including M07 from revision 2)

**M01** — source_type: meeting · source_id: `cb5cecac-e68d-52b7-b10b-b0c748efc467` · person (organizer_email): team06@example.com · usable text: YES
> Citation: `cb5cecac-e68d-52b7-b10b-b0c748efc467` turn 1 (Partner A): "My understanding was that you help people open bank accounts remotely. That is what I wanted to explore for the clients coming through Harborpath Advisory."

**M02** — source_type: meeting · source_id: `1a21c409-c050-5787-90af-2667e057e1b6` · person (organizer_email): team07@example.com · usable text: YES
> Citation: `1a21c409-c050-5787-90af-2667e057e1b6` turn 1 (Team member A): "I work on strategy and partnerships at SpendNest. We serve businesses with cards and accounts payable, and we are developing accounts receivable. We want to understand whether LedgerBridge can give us compliant invoicing coverage across our operating markets. My colleague leads the product side."

**M03** — source_type: meeting · source_id: `398672e7-62dd-5afd-846d-0237d49792fb` · person (organizer_email): team08@example.com · usable text: YES
> Citation: `398672e7-62dd-5afd-846d-0237d49792fb` turn 1 (Customer A): "We spoke a while ago. My finance colleague is joining today because we need to understand how this would actually work, and then revisit the price."

**M04** — source_type: meeting · source_id: `b0f79b3d-37ba-52f9-b2bc-58b159dd6d91` · person (organizer_email): team09@example.com · usable text: YES
> Citation: `b0f79b3d-37ba-52f9-b2bc-58b159dd6d91` turn 1 (Team member A): "I wanted to discuss the migration while there is still time to plan it. We should cover the present situation, the next steps and any feedback from your side."

**M06** — source_type: meeting · source_id: `657b9e9d-9472-5b01-a127-a648ad7e8cf7` · person (organizer_email): team10@example.com · usable text: YES
> Citation: `657b9e9d-9472-5b01-a127-a648ad7e8cf7` turn 1 (Team member A): "Good to speak after connecting professionally. I work on finance at SpendNest, and part of my interest is how finance teams spend their time. We have expense workflows and are also working on receivables automation. I would like to understand your role before jumping into the product."

**M07** — source_type: meeting · source_id: `4f304fff-fd40-5cfc-a366-0a134c445c2a` · person (organizer_email): team09@example.com · usable text: YES (text supplied in revision 2 update; withheld from revision 1)
> Citation: `4f304fff-fd40-5cfc-a366-0a134c445c2a` turn 1 (Team member A): "I wanted to go through the issues you sent yesterday. If you share your screen, we can look at what is happening and I can take the details back to the team."

**M09** — source_type: meeting · source_id: `4b5b9192-f3fc-505a-8e77-4d2ffaa54594` · person (organizer_email): team11@example.com · usable text: YES
> Citation: `4b5b9192-f3fc-505a-8e77-4d2ffaa54594` turn 1 (Customer A): "I finally have time to return to the account setup. The invitation for Brookmint Holdings did not work when I tried it. It may have expired, or perhaps we can try again together."

**M10** — source_type: meeting · source_id: `337f297d-9385-5b82-9e54-5019c1ed912c` · person (organizer_email): team12@example.com · usable text: YES
> Citation: `337f297d-9385-5b82-9e54-5019c1ed912c` turn 1 (Team member A): "I am finishing another call. Give me a couple of minutes and I will be back for the session."

## No-text records (26)

The following 26 records have no usable supplied text. Per `AGENTS.md` and `DATA_DICTIONARY.md`, no substantive analysis is created for them; their state is `No usable supplied text — analysis unavailable`. Background calls have a null `payload.transcript` (not supplied in this package, not proof of no recording); no-text meetings have an empty `turns` array with an `unavailable_reason`.

| record_ref | source_type | source_id | person | usable supplied text |
|---|---|---|---|---|
| B01 | call | 4868e5cd-5ab8-581c-a0e4-acc37385f0cf | Arun | No usable supplied text |
| B02 | call | 5747e4cd-e24f-5bed-bf74-9e3f326b2d77 | Leela | No usable supplied text |
| B03 | call | 024caffc-d16e-5843-b325-682dbc8d448e | Arun | No usable supplied text |
| B04 | call | 530207ea-d67b-521a-8085-bdb9ae665417 | Arun | No usable supplied text |
| B05 | call | 903641e9-d761-591a-a149-334ddfcd236e | Leela | No usable supplied text |
| B06 | call | 53f61c95-27b9-50c2-8755-08f957594950 | Leela | No usable supplied text |
| B07 | call | f9be8537-1ad9-58fc-be24-78f73d09db9c | Arun | No usable supplied text |
| B08 | call | 77350513-913c-5fed-b4e6-71009de9df03 | Leela | No usable supplied text |
| B09 | call | 747390bc-f359-5609-bf79-0a44ef8919bd | Arun | No usable supplied text |
| B10 | call | 3ea930a1-0496-51e3-9dca-adc3be29331a | Arun | No usable supplied text |
| B11 | call | bfefcb48-1a98-5610-a0ee-0f03434188a9 | Leela | No usable supplied text |
| B12 | call | 9a64eb58-d462-5a6e-aa9e-c0f88852ebe0 | Arun | No usable supplied text |
| B13 | call | 6521ed7d-53fc-5b3b-be77-7d4610c90ed7 | Arun | No usable supplied text |
| B14 | call | 81da63f4-eac6-5efd-95e1-69ad6e6def25 | Leela | No usable supplied text |
| B15 | call | 2ada5ab0-8a84-54b7-a071-cd5bd6ad5abd | Arun | No usable supplied text |
| B16 | call | 1f5181ed-4175-5d73-a16b-01d404b1820d | Leela | No usable supplied text |
| B17 | call | 1645d595-1896-5201-9395-cb8a9f1c5f3a | Arun | No usable supplied text |
| B18 | call | 26c3ccc3-63a6-55f6-a5a3-e279b36b7e88 | Arun | No usable supplied text |
| B19 | call | 6ee11c0e-c74a-5805-b552-657443378b72 | Arun | No usable supplied text |
| B20 | call | 94b4f015-b243-5b89-b435-9957125ecdd4 | Leela | No usable supplied text |
| M05 | meeting | e0ecb112-ed94-5e8e-ae71-19def5536337 | team08@example.com | No usable supplied text |
| M08 | meeting | 883182d8-eb86-56f9-a928-152365998d15 | team08@example.com | No usable supplied text |
| M11 | meeting | fc651475-187c-5882-a644-b501408e8647 | team13@example.com | No usable supplied text |
| M12 | meeting | c759b921-e9d3-540c-a06b-474c5710342d | arun@example.com | No usable supplied text |
| M13 | meeting | 794a9d1c-889d-5957-873f-8a1271b03455 | team09@example.com | No usable supplied text |
| M14 | meeting | 93f4867d-65cd-5236-bc55-7bd57df8ac24 | team14@example.com | No usable supplied text |

## Acceptance criteria (Phase 1)

| Criterion | Status |
|---|---|
| Exactly 44 unique `(source_type, source_id)` pairs | PASS |
| 30 calls, 14 meetings | PASS |
| 17 usable texts initially, 18 after update | PASS |
| Zero duplicate identities | PASS |
| All activity on 2026-08-21 Asia/Kolkata | PASS |
| Update = 1 record, identity `(meeting, M07)`, revision 2 (was 1), usable text YES | PASS |
| All 18 usable records listed with evidence citations | PASS |
| All 26 no-text records listed with "No usable supplied text" | PASS |
| No business conclusions invented | PASS (inventory only; analysis deferred to later phases) |

Verified by running `scripts/inspect_data.py` with `backend/.venv` Python (`RESULT: ALL CHECKS PASS`).
