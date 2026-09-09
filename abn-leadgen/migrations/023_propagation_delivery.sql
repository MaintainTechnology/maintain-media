ALTER TABLE propagation_outbox ADD COLUMN lease_owner uuid;
ALTER TABLE propagation_outbox ADD COLUMN lease_until timestamptz;
ALTER TABLE propagation_outbox ADD COLUMN next_attempt_at timestamptz;
ALTER TABLE propagation_outbox ADD COLUMN last_error_code text;
ALTER TABLE propagation_outbox ADD COLUMN receipt jsonb;
