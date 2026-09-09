CREATE TABLE pipeline_run (
 run_id uuid PRIMARY KEY, mode text NOT NULL, code_version text NOT NULL, config_digest text NOT NULL,
 state text NOT NULL CHECK(state IN ('running','held','failed','complete')),
 started_at timestamptz NOT NULL DEFAULT now(), finished_at timestamptz, manifest jsonb,
 heartbeat_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE source_content (
 content_id uuid PRIMARY KEY, source text NOT NULL, content_digest text NOT NULL,
 schema_version text NOT NULL, parser_version text NOT NULL, artifact_ref text NOT NULL,
 UNIQUE(source,content_digest,schema_version,parser_version)
);
CREATE TABLE source_snapshot (
 snapshot_id uuid PRIMARY KEY, source text NOT NULL, content_id uuid NOT NULL REFERENCES source_content,
 expected_cursor_version bigint NOT NULL, manifest jsonb NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(), state text NOT NULL CHECK(state IN ('validated','committed','quarantined')),
 UNIQUE(source,expected_cursor_version,content_id)
);
CREATE TABLE source_cursor (
 source text PRIMARY KEY, snapshot_id uuid REFERENCES source_snapshot, version bigint NOT NULL DEFAULT 0,
 last_success_at timestamptz
);
CREATE TABLE source_promotion (
 run_id uuid NOT NULL REFERENCES pipeline_run, source text NOT NULL, from_snapshot_id uuid REFERENCES source_snapshot,
 to_snapshot_id uuid NOT NULL REFERENCES source_snapshot, committed_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(run_id,source), UNIQUE(source,to_snapshot_id)
);
CREATE TABLE abr_event (
 event_id uuid PRIMARY KEY, snapshot_id uuid NOT NULL REFERENCES source_snapshot,
 abn text NOT NULL CHECK(abn ~ '^[0-9]{11}$'), event_type text NOT NULL,
 payload jsonb NOT NULL, detected_at timestamptz NOT NULL DEFAULT now(), UNIQUE(snapshot_id,abn,event_type)
);
CREATE TABLE artifact_manifest (
 artifact_id uuid PRIMARY KEY, run_id uuid NOT NULL REFERENCES pipeline_run,
 snapshot_id uuid REFERENCES source_snapshot, source text NOT NULL, object_key text NOT NULL UNIQUE,
 content_digest text NOT NULL, byte_count bigint NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
 verified_at timestamptz, state text NOT NULL CHECK(state IN ('writing','verified','referenced','orphan','deleting','deleted')),
 deletion_reason text
);
CREATE TABLE alarm_outbox (
 alarm_id uuid PRIMARY KEY, run_id uuid NOT NULL REFERENCES pipeline_run, code text NOT NULL, subject_key text NOT NULL,
 payload jsonb NOT NULL, state text NOT NULL DEFAULT 'pending', attempts integer NOT NULL DEFAULT 0,
 UNIQUE(run_id,code,subject_key)
);
