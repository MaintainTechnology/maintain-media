-- Preserve business-wide cooldown identity after marketing profile erasure.
ALTER TABLE enrichment_attempt ADD COLUMN group_id uuid REFERENCES business_group;
UPDATE enrichment_attempt a SET group_id=l.group_id FROM lead_entity l WHERE a.lead_id=l.lead_id;
-- Already erased legacy attempts without recoverable group identity must be reconciled
-- explicitly; do not guess a business or silently waive its paid-attempt cooldown.
ALTER TABLE enrichment_attempt ALTER COLUMN group_id SET NOT NULL;
CREATE FUNCTION validate_enrichment_group_identity() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF TG_OP='UPDATE' AND NEW.group_id IS DISTINCT FROM OLD.group_id THEN
   RAISE EXCEPTION 'Enrichment group identity is immutable';
 END IF;
 IF NEW.lead_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM lead_entity l WHERE l.lead_id=NEW.lead_id AND l.group_id=NEW.group_id) THEN
   RAISE EXCEPTION 'Enrichment group must match its original lead';
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER enrichment_group_identity BEFORE INSERT OR UPDATE ON enrichment_attempt
FOR EACH ROW EXECUTE FUNCTION validate_enrichment_group_identity();
