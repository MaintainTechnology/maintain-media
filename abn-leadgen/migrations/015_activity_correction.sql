CREATE UNIQUE INDEX one_activity_correction ON operator_activity(correction_of) WHERE correction_of IS NOT NULL;
ALTER TABLE operator_activity ADD CONSTRAINT bounded_activity CHECK(ended_at <= started_at + interval '24 hours');
