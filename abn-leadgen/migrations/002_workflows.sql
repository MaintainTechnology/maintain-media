CREATE TABLE relevance_assessment (
 assessment_id uuid PRIMARY KEY, contact_id uuid NOT NULL REFERENCES contact_record,
 channel text NOT NULL CHECK(channel='email'), campaign_id text NOT NULL, template_id text NOT NULL,
 content_sha256 text NOT NULL CHECK(content_sha256 ~ '^[a-f0-9]{64}$'), policy_version text NOT NULL REFERENCES policy,
 state text NOT NULL CHECK(state IN ('pass','fail','unknown')), role_evidence_id uuid NOT NULL,
 reason text NOT NULL CHECK(length(reason) BETWEEN 1 AND 2000), actor_id text NOT NULL,
 assessed_at timestamptz NOT NULL DEFAULT now(), expires_at timestamptz NOT NULL,
 assessment_seq bigint GENERATED ALWAYS AS IDENTITY UNIQUE,
 CHECK(expires_at > assessed_at AND expires_at <= assessed_at + interval '24 hours'),
 FOREIGN KEY(role_evidence_id,contact_id,channel) REFERENCES collection_provenance(provenance_id,contact_id,channel)
);
CREATE TRIGGER immutable_relevance BEFORE UPDATE OR DELETE ON relevance_assessment FOR EACH ROW EXECUTE FUNCTION immutable_evidence();
CREATE TABLE wash_batch (batch_id uuid PRIMARY KEY, digest text NOT NULL, expected_tokens jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE dnc_wash (
 wash_id uuid PRIMARY KEY, batch_id uuid NOT NULL REFERENCES wash_batch,
 endpoint_token text NOT NULL, key_version integer NOT NULL, checked_at timestamptz NOT NULL,
 received_at timestamptz NOT NULL DEFAULT now(), import_sequence bigint GENERATED ALWAYS AS IDENTITY UNIQUE,
 result text NOT NULL CHECK(result IN ('clear','listed','error')), provider text NOT NULL,
 receipt_sha256 text NOT NULL, actor_id text NOT NULL,
 UNIQUE(batch_id,endpoint_token,receipt_sha256)
);
CREATE TABLE action_intent (
 intent_id uuid PRIMARY KEY, lead_id uuid NOT NULL REFERENCES lead_entity,
 contact_id uuid NOT NULL REFERENCES contact_record, actor_id text NOT NULL,
 channel text NOT NULL CHECK(channel IN ('email','phone')), campaign_id text NOT NULL, template_id text NOT NULL,
 content_sha256 text NOT NULL, relevance_id uuid REFERENCES relevance_assessment,
 script_policy_version text, expected_revision bigint NOT NULL, versions jsonb NOT NULL,
 state text NOT NULL CHECK(state IN ('pending','denied','consumed','expired','cancelled')),
 created_at timestamptz NOT NULL DEFAULT now(), expires_at timestamptz NOT NULL,
 request jsonb NOT NULL, decision jsonb, dispatch_id uuid UNIQUE, result jsonb,
 CHECK(expires_at<=created_at+interval '60 seconds')
);
CREATE TABLE budget_month (
 month text PRIMARY KEY, cap bigint NOT NULL CHECK(cap>=0), reserved bigint NOT NULL DEFAULT 0 CHECK(reserved>=0),
 settled bigint NOT NULL DEFAULT 0 CHECK(settled>=0), frozen boolean NOT NULL DEFAULT false,
 CHECK(reserved+settled<=cap)
);
CREATE TABLE budget_reservation (
 reservation_id uuid PRIMARY KEY, operation_id uuid NOT NULL UNIQUE, body_digest text NOT NULL,
 month text NOT NULL REFERENCES budget_month, amount bigint NOT NULL CHECK(amount>=0),
 actual bigint CHECK(actual>=0), state text NOT NULL CHECK(state IN ('reserved','settled','released','uncertain')),
 tariff jsonb NOT NULL, receipt_ref text, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE candidate_queue (
 candidate_id uuid PRIMARY KEY, lead_id uuid NOT NULL REFERENCES lead_entity,
 event_key text NOT NULL, first_qualified_at timestamptz NOT NULL, last_qualifying_at timestamptz NOT NULL,
 state text NOT NULL CHECK(state IN ('pending_enrichment','needs_review','ready','exported','deferred','disqualified','suppressed')),
 tier text NOT NULL CHECK(tier IN ('A','B','C')), score integer NOT NULL CHECK(score BETWEEN 0 AND 100),
 next_attempt_at timestamptz, last_attempt_at timestamptz, attempt_count integer NOT NULL DEFAULT 0,
 lease_owner uuid, lease_until timestamptz, stage_data jsonb NOT NULL DEFAULT '{}',
 deferred_at timestamptz, exported_at timestamptz, UNIQUE(lead_id,event_key)
);
CREATE TABLE worklist (worklist_id uuid PRIMARY KEY, week date NOT NULL UNIQUE, generated_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE worklist_row (
 row_id uuid PRIMARY KEY, worklist_id uuid NOT NULL REFERENCES worklist, lead_id uuid NOT NULL REFERENCES lead_entity,
 candidate_id uuid REFERENCES candidate_queue, version bigint NOT NULL DEFAULT 1,
 outcome text NOT NULL DEFAULT 'not_started', decision jsonb NOT NULL, selected_tier text NOT NULL,
 selected_signal text NOT NULL, approval_state text NOT NULL DEFAULT 'pending',
 UNIQUE(worklist_id,lead_id)
);
CREATE TABLE outcome_event (
 event_id uuid PRIMARY KEY, row_id uuid NOT NULL REFERENCES worklist_row, expected_version bigint NOT NULL,
 actor_id text NOT NULL, status text NOT NULL CHECK(status IN ('not_started','no_usable_contact','attempted_no_answer','contacted_not_interested','contacted_nurture','meeting_booked','meeting_held','disqualified','do_not_contact_requested')),
 attempts integer NOT NULL CHECK(attempts>=0), invitation_state text NOT NULL CHECK(invitation_state IN ('invited','uninvited','unknown')),
 invitation_evidence_ref text, notes text NOT NULL CHECK(length(notes)<=2000), occurred_at timestamptz NOT NULL,
 CHECK(invitation_state<>'invited' OR length(invitation_evidence_ref)>0)
);
CREATE TABLE operator_activity (
 activity_id uuid PRIMARY KEY, actor_id text NOT NULL, worklist_id uuid REFERENCES worklist,
 lead_id uuid REFERENCES lead_entity, category text NOT NULL CHECK(category IN ('calling','research','wash','review','admin')),
 started_at timestamptz NOT NULL, ended_at timestamptz NOT NULL, correction_of uuid REFERENCES operator_activity,
 CHECK(ended_at>=started_at)
);
CREATE TABLE crm_identity (
 location_id text NOT NULL, group_id uuid NOT NULL REFERENCES business_group, remote_id text NOT NULL,
 verified_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY(location_id,group_id), UNIQUE(location_id,remote_id)
);
CREATE TABLE crm_outbox (
 outbox_id uuid PRIMARY KEY, row_id uuid NOT NULL REFERENCES worklist_row, location_id text NOT NULL,
 lead_id uuid NOT NULL REFERENCES lead_entity, approved_version bigint NOT NULL,
 actor_id text NOT NULL, payload_digest text NOT NULL, versions jsonb NOT NULL,
 state text NOT NULL CHECK(state IN ('pending','inflight','retry','succeeded','blocked','uncertain','dead_letter')),
 attempts integer NOT NULL DEFAULT 0, remote_id text, next_attempt_at timestamptz,
 lease_owner uuid, lease_until timestamptz, UNIQUE(location_id,row_id,approved_version)
);
CREATE TABLE propagation_outbox (
 outbox_id uuid PRIMARY KEY, group_id uuid REFERENCES business_group,
 reason text NOT NULL, state text NOT NULL DEFAULT 'pending', created_at timestamptz NOT NULL DEFAULT now(),
 completed_at timestamptz, attempts integer NOT NULL DEFAULT 0
);
CREATE TABLE idempotency_receipt (
 actor_id text NOT NULL, key uuid NOT NULL, body_digest text NOT NULL, status integer NOT NULL,
 receipt jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY(actor_id,key)
);
CREATE TABLE unsubscribe_token (
 token_digest text PRIMARY KEY, group_id uuid NOT NULL REFERENCES business_group,
 created_at timestamptz NOT NULL DEFAULT now()
);
