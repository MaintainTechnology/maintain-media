ALTER TABLE contact_basis ADD COLUMN express_evidence_encrypted text;
ALTER TABLE contact_basis ADD CONSTRAINT express_evidence_required CHECK(
 state<>'pass' OR basis_type<>'express' OR express_evidence_encrypted IS NOT NULL
);
CREATE TABLE restricted_evidence_archive (
 archive_id uuid PRIMARY KEY, group_id uuid NOT NULL REFERENCES business_group,
 purpose text NOT NULL, encrypted_payload text NOT NULL, retained_until timestamptz NOT NULL,
 archived_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE restore_receipt (
 restore_id uuid PRIMARY KEY, ledger_digest text NOT NULL, restored_at timestamptz NOT NULL,
 state text NOT NULL CHECK(state IN ('quarantined','reconciled')), details jsonb NOT NULL
);
