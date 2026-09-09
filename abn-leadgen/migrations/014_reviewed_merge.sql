CREATE TABLE group_merge (
 merge_id uuid PRIMARY KEY, source_group_id uuid NOT NULL UNIQUE REFERENCES business_group,
 target_group_id uuid NOT NULL REFERENCES business_group, actor_id text NOT NULL,
 evidence_encrypted text NOT NULL, reviewed_at timestamptz NOT NULL DEFAULT now(),
 CHECK(source_group_id <> target_group_id)
);
CREATE TRIGGER immutable_group_merge BEFORE UPDATE OR DELETE ON group_merge FOR EACH ROW EXECUTE FUNCTION immutable_evidence();
