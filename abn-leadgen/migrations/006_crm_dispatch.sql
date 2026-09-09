ALTER TABLE crm_outbox ADD COLUMN desired_payload_encrypted text;
ALTER TABLE crm_outbox ADD COLUMN operation_kind text CHECK(operation_kind IN ('lookup','create','update'));
ALTER TABLE crm_outbox ADD COLUMN dispatched_at timestamptz;
