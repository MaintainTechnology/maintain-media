-- Constant-space, transactional replication intent. No identity/contact data or I/O.
CREATE TABLE backup_ledger_state (
 singleton boolean PRIMARY KEY DEFAULT true CHECK(singleton),
 generation bigint NOT NULL DEFAULT 1 CHECK(generation>=1),
 acknowledged_generation bigint NOT NULL DEFAULT 0 CHECK(acknowledged_generation>=0 AND acknowledged_generation<=generation),
 pending_since timestamptz DEFAULT clock_timestamp(),
 last_attempt_at timestamptz,
 last_acknowledged_at timestamptz,
 last_receipt jsonb,
 last_error text,
 consecutive_failures integer NOT NULL DEFAULT 0 CHECK(consecutive_failures>=0)
);
INSERT INTO backup_ledger_state(singleton) VALUES(true);

CREATE FUNCTION mark_backup_ledger_dirty() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 -- Deferred until commit, after source-row locks/work; coalesce bulk changes.
 IF current_setting('abr.backup_ledger_marked',true) IS DISTINCT FROM 'on' THEN
  UPDATE backup_ledger_state SET generation=generation+1,
   pending_since=COALESCE(pending_since,clock_timestamp()) WHERE singleton;
  IF NOT FOUND THEN RAISE EXCEPTION 'Backup ledger state missing'; END IF;
  PERFORM set_config('abr.backup_ledger_marked','on',true);
 END IF;
 RETURN NULL;
END $$;
CREATE CONSTRAINT TRIGGER backup_groups_dirty AFTER INSERT OR UPDATE OR DELETE ON business_group
 DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION mark_backup_ledger_dirty();
CREATE CONSTRAINT TRIGGER backup_aliases_dirty AFTER INSERT OR UPDATE OR DELETE ON suppression_alias
 DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION mark_backup_ledger_dirty();
CREATE CONSTRAINT TRIGGER backup_restrictions_dirty AFTER INSERT OR UPDATE OR DELETE ON suppression_event
 DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION mark_backup_ledger_dirty();
CREATE CONSTRAINT TRIGGER backup_deletions_dirty AFTER INSERT OR UPDATE OR DELETE ON deletion_job
 DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION mark_backup_ledger_dirty();
