CREATE TABLE retained_cohort_fact (
 row_id uuid PRIMARY KEY, worklist_id uuid NOT NULL REFERENCES worklist,
 group_id uuid NOT NULL REFERENCES business_group,
 selected_tier text NOT NULL CHECK(selected_tier IN ('A','B','C')),
 selected_signal text NOT NULL, generated_at timestamptz NOT NULL,
 retained_until timestamptz NOT NULL
);
CREATE TABLE retained_outcome_fact (
 event_id uuid PRIMARY KEY, row_id uuid NOT NULL REFERENCES retained_cohort_fact,
 status text NOT NULL CHECK(status IN ('contacted','meeting_booked','meeting_held','other')),
 attempts integer NOT NULL CHECK(attempts>=0), attempt_increment integer NOT NULL CHECK(attempt_increment>=0),
 occurred_at timestamptz NOT NULL, recorded_seq bigint NOT NULL,
 retained_until timestamptz NOT NULL
);
CREATE TABLE retained_activity_fact (
 activity_id uuid PRIMARY KEY, worklist_id uuid REFERENCES worklist,
 group_id uuid REFERENCES business_group, actor_key uuid NOT NULL,
 category text NOT NULL CHECK(category IN ('calling','research','wash','review','admin')),
 started_at timestamptz NOT NULL, ended_at timestamptz NOT NULL,
 correction_of uuid, recorded_seq bigint NOT NULL, retained_until timestamptz NOT NULL,
 CHECK(started_at<=ended_at)
);
ALTER TABLE operator_activity ADD COLUMN metrics_archived_at timestamptz;
CREATE TRIGGER immutable_retained_cohort BEFORE UPDATE OR DELETE ON retained_cohort_fact FOR EACH ROW EXECUTE FUNCTION immutable_evidence();
CREATE TRIGGER immutable_retained_outcome BEFORE UPDATE OR DELETE ON retained_outcome_fact FOR EACH ROW EXECUTE FUNCTION immutable_evidence();
CREATE TRIGGER immutable_retained_activity BEFORE UPDATE OR DELETE ON retained_activity_fact FOR EACH ROW EXECUTE FUNCTION immutable_evidence();
