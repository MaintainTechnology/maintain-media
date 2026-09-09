-- Minimal paid-operation authority survives deletion without marketing profile links.
ALTER TABLE enrichment_attempt ALTER COLUMN lead_id DROP NOT NULL;
ALTER TABLE enrichment_attempt ALTER COLUMN candidate_id DROP NOT NULL;
ALTER TABLE enrichment_attempt ADD COLUMN erased_at timestamptz;
ALTER TABLE enrichment_attempt ADD CONSTRAINT enrichment_erasure_shape CHECK (
 (erased_at IS NULL AND lead_id IS NOT NULL AND candidate_id IS NOT NULL)
 OR (erased_at IS NOT NULL AND lead_id IS NULL AND candidate_id IS NULL)
);
