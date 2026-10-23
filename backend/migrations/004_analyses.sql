-- 004_analyses.sql
-- Candidate-derived analysis, kept separate from source fields. source_revision
-- ties every analysis to the revision of the source it reflects, so stale
-- analysis can be detected after a source revision replaces it.

CREATE TABLE analyses (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  source_type     TEXT NOT NULL,
  source_id       TEXT NOT NULL,
  source_revision INTEGER NOT NULL,
  analysis_source TEXT NOT NULL,
  suggested_routes JSONB,
  concise_output  TEXT,
  evidence_refs   JSONB,
  what_established TEXT,
  what_not_established TEXT,
  next_action     TEXT,
  owner           TEXT,
  confidence      TEXT,
  uncertainty     TEXT,
  created_at      TIMESTAMPTZ DEFAULT now()
);
