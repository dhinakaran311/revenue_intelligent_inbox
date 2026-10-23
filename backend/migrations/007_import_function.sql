-- 007_import_function.sql
-- Helper function (not schema). Runs the revision-aware delivery import as ONE
-- server-side database transaction so the whole delivery commits or rolls back
-- together (no partial state), invoked from the import boundary via the
-- Supabase client's rpc(). The six schema migrations (001-006) own the tables.
--
-- Contract enforced here, mirroring DATA_CONTRACT.md / AGENTS.md:
--   * identity is the exact (source_type, source_id) tuple
--   * new identity        -> INSERT                       (accepted)
--   * new_rev > exist_rev -> full REPLACE of source fields (replaced)
--   * new_rev <= exist_rev -> SKIP, no write              (ignored)
--   * NEVER writes to manual_route_decisions
--   * sets record_processing_state.analysis_state = 'stale' when the usable-text
--     flag changes between revisions (the task's definition of a text change)
--   * logs one import_runs row per delivery with the counts
-- Any error aborts the function's transaction and rolls back the entire delivery.

CREATE OR REPLACE FUNCTION import_delivery(
  p_records  jsonb,
  p_filename text,
  p_checksum text
) RETURNS jsonb
LANGUAGE plpgsql
AS $$
DECLARE
  rec                 jsonb;
  v_source_type       text;
  v_source_id         text;
  v_record_ref        text;
  v_revision          int;
  v_existing_revision int;
  v_existing_usable   boolean;
  v_activity_date     date;
  v_person_name       text;
  v_person_role       text;
  v_has_usable         boolean;
  v_total             int;
  v_accepted          int := 0;
  v_ignored           int := 0;
  v_replaced          int := 0;
BEGIN
  v_total := COALESCE(jsonb_array_length(p_records), 0);

  FOR rec IN SELECT * FROM jsonb_array_elements(p_records)
  LOOP
    v_source_type   := rec->>'source_type';
    v_source_id     := rec->>'source_id';
    v_record_ref    := rec->>'record_ref';
    v_revision      := (rec->>'revision')::int;
    v_activity_date := NULLIF(rec->>'activity_date', '')::date;
    v_person_name   := rec->>'person_name';
    v_person_role   := rec->>'person_role';
    v_has_usable    := (rec->>'has_usable_text')::boolean;

    SELECT revision, has_usable_text
      INTO v_existing_revision, v_existing_usable
      FROM source_records
     WHERE source_type = v_source_type
       AND source_id   = v_source_id;

    IF NOT FOUND THEN
      -- new identity -> INSERT
      INSERT INTO source_records (
        source_type, source_id, record_ref, revision, activity_date,
        person_name, person_role, source_payload, transcript_payload,
        has_usable_text, updated_at
      ) VALUES (
        v_source_type, v_source_id, v_record_ref, v_revision, v_activity_date,
        v_person_name, v_person_role, rec->'source_payload',
        rec->'transcript_payload', v_has_usable, now()
      );

      INSERT INTO record_processing_state (
        source_type, source_id, has_usable_text, intake_state, analysis_state,
        updated_at
      ) VALUES (
        v_source_type, v_source_id, v_has_usable, 'received', 'pending', now()
      )
      ON CONFLICT (source_type, source_id) DO UPDATE
        SET has_usable_text = EXCLUDED.has_usable_text,
            intake_state    = 'received',
            updated_at      = now();

      v_accepted := v_accepted + 1;

    ELSIF v_revision > v_existing_revision THEN
      -- newer revision -> full REPLACE of source fields (incl. nulls)
      UPDATE source_records
         SET record_ref         = v_record_ref,
             revision           = v_revision,
             activity_date      = v_activity_date,
             person_name        = v_person_name,
             person_role        = v_person_role,
             source_payload     = rec->'source_payload',
             transcript_payload = rec->'transcript_payload',
             has_usable_text    = v_has_usable,
             updated_at         = now()
       WHERE source_type = v_source_type
         AND source_id   = v_source_id;

      -- refresh usable flag; mark analysis stale when the usable-text flag changed
      INSERT INTO record_processing_state (
        source_type, source_id, has_usable_text, intake_state, analysis_state,
        updated_at
      ) VALUES (
        v_source_type, v_source_id, v_has_usable, 'received',
        CASE WHEN v_existing_usable IS DISTINCT FROM v_has_usable
             THEN 'stale' ELSE 'pending' END,
        now()
      )
      ON CONFLICT (source_type, source_id) DO UPDATE
        SET has_usable_text = EXCLUDED.has_usable_text,
            intake_state    = 'received',
            analysis_state  = CASE WHEN v_existing_usable IS DISTINCT FROM v_has_usable
                                   THEN 'stale'
                                   ELSE record_processing_state.analysis_state END,
            updated_at      = now();

      v_replaced := v_replaced + 1;

    ELSE
      -- same or older revision -> ignore (no write)
      v_ignored := v_ignored + 1;
    END IF;
  END LOOP;

  INSERT INTO import_runs (
    filename, checksum, total_records, accepted, ignored, replaced, errors
  ) VALUES (
    p_filename, p_checksum, v_total, v_accepted, v_ignored, v_replaced, '[]'::jsonb
  );

  RETURN jsonb_build_object(
    'total',    v_total,
    'accepted', v_accepted,
    'ignored',  v_ignored,
    'replaced', v_replaced,
    'errors',   '[]'::jsonb
  );
END;
$$;
