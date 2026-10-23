-- 006_export_runs.sql
-- Export bundle registry. is_current marks the active logical output; a repeat
-- export must not create multiple active copies of the same logical output
-- without explanation (superseded rows set is_current=false).

CREATE TABLE export_runs (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  is_current      BOOLEAN NOT NULL DEFAULT TRUE,
  bundle_path     TEXT,
  manifest_path   TEXT,
  created_at      TIMESTAMPTZ DEFAULT now()
);
