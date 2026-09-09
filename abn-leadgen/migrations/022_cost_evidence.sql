CREATE TABLE cost_statement (
 statement_id uuid PRIMARY KEY,
 period_start timestamptz NOT NULL, period_end timestamptz NOT NULL,
 cohort_id uuid REFERENCES worklist, tier text CHECK(tier IN ('A','B','C')),
 evidence_digest text NOT NULL CHECK(evidence_digest ~ '^[a-f0-9]{64}$'),
 encrypted_evidence text, numeric_facts jsonb NOT NULL, evidence_erased_at timestamptz,
 imported_by text NOT NULL, imported_at timestamptz NOT NULL DEFAULT now(),
 CHECK(period_start<period_end), CHECK((cohort_id IS NULL)=(tier IS NULL)),
 CHECK((encrypted_evidence IS NOT NULL AND evidence_erased_at IS NULL) OR (encrypted_evidence IS NULL AND evidence_erased_at IS NOT NULL AND evidence_erased_at>=imported_at+interval '90 days')),
 UNIQUE NULLS NOT DISTINCT(period_start,period_end,cohort_id,tier)
);
CREATE FUNCTION finite_cost_evidence() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF current_setting('abr.retention_delete',true)='on' THEN
   IF TG_OP='DELETE' THEN RETURN OLD; END IF;
   IF OLD.encrypted_evidence IS NOT NULL AND NEW.encrypted_evidence IS NULL
      AND OLD.evidence_erased_at IS NULL AND NEW.evidence_erased_at>=OLD.imported_at+interval '90 days'
      AND (to_jsonb(NEW)-'encrypted_evidence'-'evidence_erased_at')=(to_jsonb(OLD)-'encrypted_evidence'-'evidence_erased_at') THEN RETURN NEW; END IF;
 END IF;
 RAISE EXCEPTION 'Immutable cost facts with finite receipt evidence';
END $$;
CREATE TRIGGER immutable_cost_statement BEFORE UPDATE OR DELETE ON cost_statement FOR EACH ROW EXECUTE FUNCTION finite_cost_evidence();
