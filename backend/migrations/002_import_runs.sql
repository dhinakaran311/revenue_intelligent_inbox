-- 002_import_runs.sql
-- One row per delivery attempt. Captures the revision-aware import outcome
-- (accepted / ignored / replaced / errors) for audit and replay verification.

CREATE TABLE import_runs (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  filename        TEXT,
  checksum        TEXT,
  received_at     TIMESTAMPTZ DEFAULT now(),
  total_records   INTEGER,
  accepted        INTEGER,
  ignored         INTEGER,
  replaced        INTEGER,
  errors          JSONB
);
