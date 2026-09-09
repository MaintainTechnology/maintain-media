CREATE TABLE enrichment_attempt (
 attempt_id uuid PRIMARY KEY,
 lead_id uuid NOT NULL REFERENCES lead_entity,
 candidate_id uuid NOT NULL REFERENCES candidate_queue,
 state text NOT NULL CHECK(state IN ('running','blocked','complete','exhausted')),
 reason text,
 lease_owner uuid,
 lease_until timestamptz,
 started_at timestamptz NOT NULL,
 finished_at timestamptz,
 next_eligible_at timestamptz,
 CHECK((state IN ('complete','exhausted'))=(finished_at IS NOT NULL)),
 CHECK(next_eligible_at IS NULL OR next_eligible_at=finished_at+interval '90 days')
);
CREATE UNIQUE INDEX enrichment_one_open ON enrichment_attempt(lead_id) WHERE state IN ('running','blocked');
CREATE TABLE enrichment_operation (
 operation_id uuid PRIMARY KEY,
 attempt_id uuid NOT NULL REFERENCES enrichment_attempt,
 stage text NOT NULL CHECK(stage IN ('lookup','crawl','verify')),
 provider_version text NOT NULL,
 state text NOT NULL CHECK(state IN ('reserved','dispatched','uncertain','complete')),
 reservation_id uuid NOT NULL REFERENCES budget_reservation,
 receipt_ref text,
 encrypted_result text,
 completed_at timestamptz,
 UNIQUE(attempt_id,stage)
);
