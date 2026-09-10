-- Source-bound reviewer decisions. No licence/name/address is copied into this ledger.
ALTER TABLE licence_review DROP CONSTRAINT licence_review_status_check;
ALTER TABLE licence_review ADD CONSTRAINT licence_review_status_check CHECK(status IN ('active','suspended','cancelled','inactive','unknown'));
CREATE TABLE qbcc_source_review (
 review_id uuid PRIMARY KEY, snapshot_id uuid NOT NULL REFERENCES source_snapshot,
 row_digest text NOT NULL CHECK(row_digest ~ '^[0-9a-f]{64}$'),
 alias_token text NOT NULL, key_version integer NOT NULL,
 status text NOT NULL CHECK(status IN ('active','suspended','cancelled','inactive','unknown')),
 identity_match boolean NOT NULL, evidence_encrypted text NOT NULL,
 actor_id text NOT NULL, reviewed_at timestamptz NOT NULL,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 review_seq bigint GENERATED ALWAYS AS IDENTITY UNIQUE,
 lead_id uuid REFERENCES lead_entity, request_digest text NOT NULL,
 receipt jsonb NOT NULL
);
CREATE INDEX qbcc_source_review_current ON qbcc_source_review(alias_token,key_version,reviewed_at DESC,review_seq DESC);
CREATE TRIGGER qbcc_source_review_immutable BEFORE UPDATE OR DELETE ON qbcc_source_review FOR EACH ROW EXECUTE FUNCTION immutable_evidence();
