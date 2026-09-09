CREATE TABLE ops_observation (
 observation_id uuid PRIMARY KEY, run_id uuid NOT NULL REFERENCES pipeline_run,
 source text NOT NULL CHECK(source IN ('abr','qbcc')), observed_at timestamptz NOT NULL,
 digest text NOT NULL CHECK(digest ~ '^[a-f0-9]{64}$'), payload jsonb NOT NULL,
 UNIQUE(run_id,source,digest)
);
ALTER TABLE alarm_outbox ADD COLUMN lease_owner uuid;
ALTER TABLE alarm_outbox ADD COLUMN lease_until timestamptz;
ALTER TABLE alarm_outbox ADD COLUMN next_attempt_at timestamptz;
ALTER TABLE alarm_outbox ADD COLUMN delivered_at timestamptz;
ALTER TABLE alarm_outbox ADD COLUMN last_error_code text;
CREATE TABLE ops_mock_delivery (
 alarm_id uuid PRIMARY KEY REFERENCES alarm_outbox,
 delivered_at timestamptz NOT NULL, payload jsonb NOT NULL
);
