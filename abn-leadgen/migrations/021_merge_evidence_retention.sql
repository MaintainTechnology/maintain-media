-- Identifying corroboration is finite; the minimal reviewed merge graph persists.
ALTER TABLE group_merge ALTER COLUMN evidence_encrypted DROP NOT NULL;
ALTER TABLE group_merge ADD COLUMN evidence_erased_at timestamptz;
ALTER TABLE group_merge ADD CONSTRAINT merge_evidence_retention_shape CHECK (
 (evidence_encrypted IS NOT NULL AND evidence_erased_at IS NULL)
 OR (evidence_encrypted IS NULL AND evidence_erased_at IS NOT NULL AND evidence_erased_at>=reviewed_at+interval '90 days')
);
DROP TRIGGER immutable_group_merge ON group_merge;
CREATE FUNCTION finite_merge_evidence() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF TG_OP='UPDATE' AND current_setting('abr.retention_delete',true)='on'
    AND OLD.evidence_encrypted IS NOT NULL AND OLD.evidence_erased_at IS NULL
    AND NEW.evidence_encrypted IS NULL AND NEW.evidence_erased_at IS NOT NULL
    AND NEW.evidence_erased_at>=OLD.reviewed_at+interval '90 days'
    AND (to_jsonb(NEW)-'evidence_encrypted'-'evidence_erased_at')=(to_jsonb(OLD)-'evidence_encrypted'-'evidence_erased_at') THEN
   RETURN NEW;
 END IF;
 RAISE EXCEPTION 'Immutable reviewed merge with one-way finite evidence erasure';
END $$;
CREATE TRIGGER immutable_group_merge BEFORE UPDATE OR DELETE ON group_merge
FOR EACH ROW EXECUTE FUNCTION finite_merge_evidence();
