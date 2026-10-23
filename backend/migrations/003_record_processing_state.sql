-- 003_record_processing_state.sql
-- Per-identity processing state, kept separate from source fields per the data
-- contract. The FK to source_records enforces that processing state cannot
-- exist without its source record. analysis_state is set to 'stale' by the
-- import function when the usable-text flag changes between revisions.

CREATE TABLE record_processing_state (
  source_type       TEXT NOT NULL,
  source_id         TEXT NOT NULL,
  has_usable_text   BOOLEAN NOT NULL DEFAULT FALSE,
  intake_state      TEXT NOT NULL DEFAULT 'pending',
  analysis_state    TEXT NOT NULL DEFAULT 'pending',
  analysis_revision INTEGER,
  updated_at        TIMESTAMPTZ DEFAULT now(),
  CONSTRAINT pk_processing_state PRIMARY KEY (source_type, source_id),
  CONSTRAINT fk_source FOREIGN KEY (source_type, source_id)
    REFERENCES source_records(source_type, source_id)
);
