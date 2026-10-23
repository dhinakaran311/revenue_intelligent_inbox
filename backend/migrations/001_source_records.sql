-- 001_source_records.sql
-- System of record for source deliveries. Identity is the exact, case-sensitive
-- pair (source_type, source_id), enforced by a UNIQUE constraint at the schema
-- level. revision is the last applied delivery revision for this identity.

CREATE TABLE source_records (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  source_type     TEXT NOT NULL,
  source_id       TEXT NOT NULL,
  record_ref      TEXT,
  revision        INTEGER NOT NULL,
  activity_date   DATE,
  person_name     TEXT,
  person_role     TEXT,
  source_payload  JSONB NOT NULL,
  transcript_payload JSONB,
  has_usable_text BOOLEAN NOT NULL DEFAULT FALSE,
  created_at      TIMESTAMPTZ DEFAULT now(),
  updated_at      TIMESTAMPTZ DEFAULT now(),
  CONSTRAINT uq_source_identity UNIQUE (source_type, source_id)
);
