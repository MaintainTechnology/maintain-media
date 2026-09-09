CREATE TABLE business_group (
 group_id uuid PRIMARY KEY, restriction_revision bigint NOT NULL DEFAULT 0,
 merged_into_group_id uuid REFERENCES business_group, CHECK(group_id <> merged_into_group_id)
);
CREATE TABLE lead_entity (
 lead_id uuid PRIMARY KEY, group_id uuid NOT NULL UNIQUE REFERENCES business_group,
 display_name text NOT NULL, source text NOT NULL CHECK(source IN ('abr','qbcc')),
 state text, postcode text CHECK(postcode ~ '^[0-9]{4}$'),
 tier text CHECK(tier IN ('A','B','C')), signal text NOT NULL, score integer CHECK(score BETWEEN 0 AND 100),
 fields jsonb NOT NULL DEFAULT '{}', lifecycle text NOT NULL DEFAULT 'active'
 CHECK(lifecycle IN ('active','disqualified','cancelled','suppressed')),
 revision bigint NOT NULL DEFAULT 1, first_qualified_at timestamptz NOT NULL DEFAULT now(),
 last_qualifying_at timestamptz NOT NULL DEFAULT now(), UNIQUE(lead_id,group_id)
);
CREATE TABLE lead_source_link (
 link_id uuid PRIMARY KEY, group_id uuid NOT NULL REFERENCES business_group,
 source_type text NOT NULL CHECK(source_type IN ('abn','qbcc')), encrypted_identifier text NOT NULL,
 alias_token text NOT NULL, key_version integer NOT NULL, linked_at timestamptz NOT NULL DEFAULT now(),
 evidence_ref text NOT NULL, UNIQUE(source_type,alias_token,key_version)
);
CREATE TABLE suppression_alias (
 alias_type text NOT NULL CHECK(alias_type IN ('abn','qbcc')), key_version integer NOT NULL,
 alias_token text NOT NULL, group_id uuid NOT NULL REFERENCES business_group,
 linked_at timestamptz NOT NULL DEFAULT now(), migration_version integer NOT NULL DEFAULT 1,
 PRIMARY KEY(alias_type,key_version,alias_token)
);
CREATE TABLE domain_identity (
 identity_id uuid PRIMARY KEY, lead_id uuid NOT NULL REFERENCES lead_entity,
 registrable_domain text NOT NULL CHECK(registrable_domain = lower(registrable_domain)),
 assessment_seq bigint GENERATED ALWAYS AS IDENTITY UNIQUE,
 assessment text NOT NULL CHECK(assessment IN ('approved','rejected','ambiguous')),
 method text NOT NULL, evidence jsonb NOT NULL, reason text NOT NULL,
 actor_id text NOT NULL, assessed_at timestamptz NOT NULL DEFAULT now(), expires_at timestamptz NOT NULL,
 CHECK(expires_at > assessed_at AND expires_at <= assessed_at + interval '90 days'),
 UNIQUE(identity_id,lead_id,registrable_domain)
);
CREATE TABLE licence_review (
 review_id uuid PRIMARY KEY, lead_id uuid NOT NULL REFERENCES lead_entity,
 encrypted_licence text NOT NULL, status text NOT NULL CHECK(status IN ('active','suspended','cancelled','unknown')),
 identity_match boolean NOT NULL, evidence_ref text NOT NULL, actor_id text NOT NULL,
 reviewed_at timestamptz NOT NULL, import_seq bigint GENERATED ALWAYS AS IDENTITY UNIQUE
);
CREATE TABLE contact_record (
 contact_id uuid PRIMARY KEY, lead_id uuid NOT NULL REFERENCES lead_entity,
 channel text NOT NULL CHECK(channel IN ('email','mobile','landline')),
 encrypted_value text NOT NULL, endpoint_token text NOT NULL, token_key_version integer NOT NULL,
 first_provenance_id uuid NOT NULL, verification_status text NOT NULL DEFAULT 'unverified'
 CHECK(verification_status IN ('deliverable','catch_all','unknown','undeliverable','unverified')),
 verified_at timestamptz, revision bigint NOT NULL DEFAULT 1,
 created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(contact_id,channel), UNIQUE(contact_id,lead_id,channel), UNIQUE(lead_id,channel,endpoint_token)
);
CREATE TABLE collection_provenance (
 provenance_id uuid PRIMARY KEY, contact_id uuid NOT NULL, lead_id uuid NOT NULL, channel text NOT NULL,
 registrable_domain text NOT NULL, domain_identity_id uuid NOT NULL,
 source_url text NOT NULL, source_type text NOT NULL CHECK(source_type IN ('website','express')),
 content_sha256 text NOT NULL CHECK(content_sha256 ~ '^[a-f0-9]{64}$'),
 encrypted_excerpt text NOT NULL, object_ref text NOT NULL, collector_version text NOT NULL,
 method text NOT NULL, robots_result text NOT NULL, terms_scope text NOT NULL,
 collected_at timestamptz NOT NULL DEFAULT now(), actor_id text NOT NULL,
 UNIQUE(provenance_id,contact_id,channel),
 FOREIGN KEY(contact_id,lead_id,channel) REFERENCES contact_record(contact_id,lead_id,channel) DEFERRABLE INITIALLY DEFERRED,
 FOREIGN KEY(domain_identity_id,lead_id,registrable_domain) REFERENCES domain_identity(identity_id,lead_id,registrable_domain) DEFERRABLE INITIALLY DEFERRED,
 CHECK(source_url ~ '^https?://' AND
   lower(split_part(split_part(regexp_replace(source_url,'^https?://',''),'/',1),':',1)) ~ ('(^|\.)' || replace(registrable_domain,'.','\.') || '$'))
);
ALTER TABLE contact_record ADD CONSTRAINT first_provenance_exact
 FOREIGN KEY(first_provenance_id,contact_id,channel)
 REFERENCES collection_provenance(provenance_id,contact_id,channel) DEFERRABLE INITIALLY DEFERRED;
CREATE TABLE contact_basis (
 basis_id uuid PRIMARY KEY, contact_id uuid NOT NULL, channel text NOT NULL CHECK(channel='email'),
 assessment_seq bigint GENERATED ALWAYS AS IDENTITY UNIQUE,
 state text NOT NULL CHECK(state IN ('pass','fail','unknown','withdrawn')),
 basis_type text NOT NULL CHECK(basis_type IN ('inferred','express','none')),
 provenance_id uuid NOT NULL, limbs jsonb, express_scope text, reason text NOT NULL,
 actor_id text NOT NULL, policy_version text NOT NULL,
 assessed_at timestamptz NOT NULL DEFAULT now(), expires_at timestamptz NOT NULL,
 CHECK(expires_at > assessed_at AND expires_at <= assessed_at + interval '90 days'),
 CHECK(state <> 'pass' OR (basis_type='inferred' AND limbs = '{"role":"pass","publication":"pass","agreement":"pass","no_prohibition":"pass"}'::jsonb)
 OR (basis_type='express' AND length(express_scope)>0)),
 FOREIGN KEY(provenance_id,contact_id,channel) REFERENCES collection_provenance(provenance_id,contact_id,channel)
);
CREATE TABLE release_gate (
 gate_name text NOT NULL, environment text NOT NULL, scope text NOT NULL, revision bigint NOT NULL,
 evidence_ref text NOT NULL, evidence_sha256 text NOT NULL, actor_id text NOT NULL,
 approved_at timestamptz NOT NULL, expires_at timestamptz NOT NULL,
 PRIMARY KEY(gate_name,environment,scope,revision), CHECK(expires_at>approved_at)
);
CREATE TABLE policy (
 version text PRIMARY KEY, state text NOT NULL CHECK(state IN ('approved','withdrawn')),
 scope text NOT NULL, evidence_ref text NOT NULL, actor_id text NOT NULL,
 approved_at timestamptz NOT NULL DEFAULT now(), expires_at timestamptz NOT NULL,
 settings jsonb NOT NULL, CHECK(expires_at>approved_at)
);
CREATE TABLE suppression_event (
 event_id uuid PRIMARY KEY, request_id uuid NOT NULL,
 scope text NOT NULL CHECK(scope IN ('business','endpoint')),
 group_id uuid REFERENCES business_group, endpoint_token text, key_version integer,
 reason text NOT NULL CHECK(reason IN ('unsubscribe','complaint','no_unsolicited_notice','cancellation','manual')),
 action text NOT NULL DEFAULT 'add' CHECK(action IN ('add','resolve')),
 resolves_event_id uuid REFERENCES suppression_event,
 requested_at timestamptz NOT NULL, committed_at timestamptz NOT NULL DEFAULT now(),
 actor_id text NOT NULL, source text NOT NULL,
 CHECK((scope='business' AND group_id IS NOT NULL AND endpoint_token IS NULL) OR
 (scope='endpoint' AND endpoint_token IS NOT NULL AND key_version IS NOT NULL AND group_id IS NULL)),
 CHECK(action='add' OR (reason='cancellation' AND resolves_event_id IS NOT NULL)),
 UNIQUE NULLS NOT DISTINCT(request_id,scope,group_id,endpoint_token)
);
CREATE INDEX suppression_group ON suppression_event(group_id);
CREATE INDEX suppression_token ON suppression_event(endpoint_token,key_version);
CREATE TABLE audit_event (
 event_id uuid PRIMARY KEY, actor_id text NOT NULL, action text NOT NULL,
 object_type text NOT NULL, object_id text NOT NULL, metadata jsonb NOT NULL DEFAULT '{}',
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE deletion_job (
 job_id uuid PRIMARY KEY, group_id uuid NOT NULL REFERENCES business_group,
 requested_at timestamptz NOT NULL DEFAULT now(), primary_done_at timestamptz,
 backup_expiry_at timestamptz, state text NOT NULL DEFAULT 'pending'
 CHECK(state IN ('pending','primary_complete','complete','held')), external_receipts jsonb NOT NULL DEFAULT '{}'
);
CREATE TABLE system_state (name text PRIMARY KEY, value jsonb NOT NULL);
INSERT INTO system_state VALUES ('restore_quarantine','false'),('key_compromised','false');
CREATE FUNCTION immutable_evidence() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF TG_OP='DELETE' AND current_setting('abr.retention_delete',true)='on' THEN RETURN OLD; END IF;
 RAISE EXCEPTION 'Append-only evidence';
END $$;
CREATE TRIGGER immutable_identity BEFORE UPDATE OR DELETE ON domain_identity FOR EACH ROW EXECUTE FUNCTION immutable_evidence();
CREATE TRIGGER immutable_provenance BEFORE UPDATE OR DELETE ON collection_provenance FOR EACH ROW EXECUTE FUNCTION immutable_evidence();
CREATE TRIGGER immutable_basis BEFORE UPDATE OR DELETE ON contact_basis FOR EACH ROW EXECUTE FUNCTION immutable_evidence();
CREATE TRIGGER immutable_suppression BEFORE UPDATE OR DELETE ON suppression_event FOR EACH ROW EXECUTE FUNCTION immutable_evidence();
CREATE TRIGGER immutable_audit BEFORE UPDATE OR DELETE ON audit_event FOR EACH ROW EXECUTE FUNCTION immutable_evidence();
