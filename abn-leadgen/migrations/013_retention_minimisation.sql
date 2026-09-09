-- Ordinary page bodies may be irreversibly erased after their finite period while
-- immutable digest/identity provenance remains attached to the contact.
ALTER TABLE collection_provenance ADD COLUMN capture_erased_at timestamptz;
ALTER TABLE collection_provenance ALTER COLUMN encrypted_excerpt DROP NOT NULL;
ALTER TABLE collection_provenance DROP CONSTRAINT retained_capture_required;
ALTER TABLE collection_provenance ADD CONSTRAINT finite_capture_state CHECK(
 capture_sha256 IS NOT NULL AND capture_sha256 ~ '^[a-f0-9]{64}$' AND
 ((capture_erased_at IS NULL AND encrypted_capture IS NOT NULL AND encrypted_excerpt IS NOT NULL)
 OR (capture_erased_at IS NOT NULL AND encrypted_capture IS NULL AND encrypted_excerpt IS NULL
     AND capture_erased_at>=collected_at+interval '90 days'))
);
CREATE FUNCTION finite_provenance_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF TG_OP='DELETE' AND current_setting('abr.retention_delete',true)='on' THEN RETURN OLD; END IF;
 IF TG_OP='UPDATE' AND current_setting('abr.retention_delete',true)='on'
    AND OLD.capture_erased_at IS NULL AND NEW.capture_erased_at IS NOT NULL
    AND NEW.encrypted_capture IS NULL AND NEW.encrypted_excerpt IS NULL
    AND NEW.capture_erased_at>=OLD.collected_at+interval '90 days'
    AND (to_jsonb(NEW)-ARRAY['encrypted_capture','encrypted_excerpt','capture_erased_at'])
       =(to_jsonb(OLD)-ARRAY['encrypted_capture','encrypted_excerpt','capture_erased_at'])
 THEN RETURN NEW; END IF;
 RAISE EXCEPTION 'Provenance is immutable except one-way scheduled capture erasure';
END $$;
DROP TRIGGER immutable_provenance ON collection_provenance;
CREATE TRIGGER immutable_provenance BEFORE UPDATE OR DELETE ON collection_provenance
 FOR EACH ROW EXECUTE FUNCTION finite_provenance_mutation();

CREATE TABLE retained_event_metric (
 source text NOT NULL CHECK(source IN ('abr','qbcc')),
 observed_day date NOT NULL,
 event_type text NOT NULL CHECK(event_type IN ('abn_new','abn_cancelled','abn_reactivated','gst_registered',
   'gst_cancelled','name_changed','abn_disappeared','icp_backlog','new','category_changed','unknown')),
 event_count bigint NOT NULL CHECK(event_count>0),
 retained_until timestamptz NOT NULL,
 PRIMARY KEY(source,observed_day,event_type),
 CHECK(retained_until>observed_day::timestamp AT TIME ZONE 'UTC'
   AND retained_until<=(observed_day::timestamp+interval '24 months') AT TIME ZONE 'UTC')
);
