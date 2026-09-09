CREATE TABLE qbcc_event (
 event_id uuid PRIMARY KEY, snapshot_id uuid NOT NULL REFERENCES source_snapshot,
 licence_number text NOT NULL, event_type text NOT NULL, payload jsonb NOT NULL,
 detected_at timestamptz NOT NULL DEFAULT now(), UNIQUE(snapshot_id,licence_number,event_type)
);
CREATE TABLE source_observation (
 observation_id uuid PRIMARY KEY, run_id uuid NOT NULL REFERENCES pipeline_run,
 source text NOT NULL, manifest jsonb NOT NULL, observed_at timestamptz NOT NULL
);
CREATE TABLE fixture_crm_record (
 remote_id text PRIMARY KEY, group_id uuid NOT NULL UNIQUE, encrypted_payload text NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE retention_hold (
 hold_id uuid PRIMARY KEY, object_type text NOT NULL, object_id text NOT NULL,
 owner text NOT NULL, reason text NOT NULL, review_at timestamptz NOT NULL
);
