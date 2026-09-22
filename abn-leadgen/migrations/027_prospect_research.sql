-- Manual research is separate from immutable source rows and contact authority.
-- The retained suppression alias also anchors lookup-key dependencies after erasure.
CREATE TABLE prospect_research (
 prospect_id uuid PRIMARY KEY,
 group_id uuid NOT NULL REFERENCES business_group,
 alias_type text NOT NULL DEFAULT 'abn' CHECK(alias_type='abn'),
 alias_token text NOT NULL,
 key_version integer NOT NULL,
 source text NOT NULL CHECK(source IN ('abr','qbcc')),
 snapshot_id uuid NOT NULL REFERENCES source_snapshot,
 payload_encrypted text NOT NULL,
 website_presence text NOT NULL CHECK(website_presence IN ('unknown','present','absent')),
 email_presence text NOT NULL CHECK(email_presence IN ('unknown','present','absent')),
 social_presence text NOT NULL CHECK(social_presence IN ('unknown','present','absent')),
 contact_stage text NOT NULL CHECK(contact_stage IN ('not_contacted','contacted','interested','follow_up','not_interested')),
 registration_date date,
 follow_up_on date,
 revision bigint NOT NULL DEFAULT 1 CHECK(revision>0),
 created_at timestamptz NOT NULL,
 saved_at timestamptz NOT NULL,
 expires_at timestamptz NOT NULL,
 actor_id text NOT NULL,
 UNIQUE(alias_token,key_version),
 FOREIGN KEY(alias_type,key_version,alias_token) REFERENCES suppression_alias(alias_type,key_version,alias_token),
 CHECK(expires_at>saved_at AND expires_at<=saved_at+interval '180 days')
);
CREATE INDEX prospect_research_recent ON prospect_research(saved_at DESC,prospect_id);
CREATE INDEX prospect_research_expiry ON prospect_research(expires_at);
CREATE INDEX prospect_research_group ON prospect_research(group_id);
