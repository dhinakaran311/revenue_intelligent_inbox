-- 005_manual_route_decisions.sql
-- A manual route is a human decision. It is never written by import, analysis,
-- update, refresh or restart. The import function does not reference this
-- table at all; reset_app_data() is the only automated writer (for replay).

CREATE TABLE manual_route_decisions (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  source_type TEXT NOT NULL,
  source_id   TEXT NOT NULL,
  route_id    TEXT NOT NULL,
  rationale   TEXT,
  author      TEXT,
  is_active   BOOLEAN NOT NULL DEFAULT TRUE,
  created_at  TIMESTAMPTZ DEFAULT now(),
  reset_at    TIMESTAMPTZ
);
