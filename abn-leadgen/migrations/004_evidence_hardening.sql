ALTER TABLE contact_basis ADD CONSTRAINT pass_basis_explicit CHECK(
 state <> 'pass' OR
 (basis_type='inferred' AND limbs IS NOT NULL AND limbs='{"role":"pass","publication":"pass","agreement":"pass","no_prohibition":"pass"}'::jsonb)
 OR (basis_type='express' AND express_scope IS NOT NULL AND length(express_scope)>0)
);
ALTER TABLE collection_provenance ADD COLUMN encrypted_capture text;
ALTER TABLE collection_provenance ADD COLUMN capture_sha256 text;
-- Initial migration has no imported records; legacy data requires explicit quarantine if present.
ALTER TABLE collection_provenance ADD CONSTRAINT retained_capture_required CHECK(
 encrypted_capture IS NOT NULL AND capture_sha256 IS NOT NULL AND capture_sha256 ~ '^[a-f0-9]{64}$'
);
CREATE FUNCTION never_mutate_restrictions() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'Restriction history cannot be rewritten or deleted'; END $$;
DROP TRIGGER immutable_suppression ON suppression_event;
CREATE TRIGGER immutable_suppression BEFORE UPDATE OR DELETE ON suppression_event FOR EACH ROW EXECUTE FUNCTION never_mutate_restrictions();
CREATE TRIGGER immutable_wash BEFORE UPDATE OR DELETE ON dnc_wash FOR EACH ROW EXECUTE FUNCTION immutable_evidence();
CREATE TRIGGER immutable_outcome BEFORE UPDATE OR DELETE ON outcome_event FOR EACH ROW EXECUTE FUNCTION immutable_evidence();
