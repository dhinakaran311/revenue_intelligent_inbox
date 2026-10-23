-- 008_reset_function.sql
-- Helper function (not schema). Atomically deletes all app-owned data for
-- replay testing, in FK-safe order (record_processing_state -> source_records
-- is the only foreign key). scripts/reset_db.py refuses to call this when
-- APP_ENV=production. Never deploys or alters schema.

CREATE OR REPLACE FUNCTION reset_app_data() RETURNS void
LANGUAGE plpgsql
AS $$
BEGIN
  DELETE FROM manual_route_decisions;
  DELETE FROM analyses;
  DELETE FROM record_processing_state;
  DELETE FROM source_records;
  DELETE FROM import_runs;
  DELETE FROM export_runs;
END;
$$;
