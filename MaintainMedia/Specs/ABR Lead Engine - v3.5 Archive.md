---
title: "ABR Lead Engine - v3.5 Archive"
project: Maintain Media
version: "3.5"
synced: 2026-09-09
source: "specs/abr-lead-engine.v3.5.backup.md"
source_sha256: 57c8ec010e7759b667ce6ea92b500a7ac69eeb49c49a81bf5d27efe1a6692038
tags: [abr-lead-engine, maintain-media]
---
> Synced from the repository; local document links adapted for Obsidian.
> [[ABR Lead Engine - Build Hub|Open the build hub]]

# ABR Lead Engine (Part 1) — Spec

**Status:** build-ready · **Owner:** Jon Pepper · **Builds:** developer · **Operates:** lead-gen VA
**Version:** 3.5 · **Written:** 7 September 2026 · **Revised:** 8 September 2026

---

## Changes in 3.5 — buildability review

Every claim in §Constraints and §Data model was tested rather than reviewed. The schema was
executed against a real PostgreSQL 16.4 engine; the diff was benchmarked on synthetic 20.5M-row
snapshots; the ingest path was run end to end; vendor and statutory facts were re-fetched from
primary sources. **Twenty-two of twenty-five candidate findings were refuted or downgraded on a
second adversarial pass and are deliberately NOT reflected here.** What changed:

| # | Severity | Change |
|---|---|---|
| 1 | **Blocker** | `contact_record.first_provenance_id` carried a forward `REFERENCES` to `collection_provenance`, which is defined later. Four tables failed with `42P01`. The FK now attaches by `ALTER TABLE` after both exist |
| 2 | High | R25's 90-day basis expiry was stated but unenforceable — `record_level_pass` is generated over limbs a–d only. The export gate now tests `expires_at` explicitly, with a DoD fixture |
| 3 | High | R33 omitted **Google** as an overseas recipient, while R34 puts the entire worklist in a Google Sheet and R33 requires every recipient be enumerated. Added |
| 4 | Medium | R21 stage 2 now requires a wildcard-aware `robots.txt` parser; the stdlib one ignores `*` and `$`. The DoD test only exercised a literal prefix, so it passed regardless — strengthened |
| 5 | Medium | R5 now requires XML entity-reference resolution and names `iterparse`. The inherited regex reader yields `SMITH &amp; SONS`, corrupting `main_name` and `row_hash` |
| 6 | Medium | R6 now requires bounded-batch Parquet writes — the naive single-table write is the one way this stage breaches the 2 GB cap |
| 7 | Medium | R7 now requires an explicit DuckDB `memory_limit`; the default (~80% of RAM) would OOM the co-tenant Postgres. Measured: the full diff runs in **9.1 s at a 512 MB limit** against a 60 s target |
| 8 | Medium | §Constraints host pricing named a single vendor's floor as a market band. OVHcloud SYD verified at ~A$14/month; every other AU provider is 2.8–4.8×; Hetzner has no AU region |
| 9 | Medium | R25 and Open Question 2 described an "ACMA-recognised access seeker" and "per-tranche pricing". **Neither exists.** Corrected to the published statutory volume-tier subscription; the phone channel is no longer a blocker |
| 10 | Low | R24a said `do_not_market` is "keyed on ABN"; the DDL keys it on `lead_id`, and ABN is null for 45.5% of QBCC leads. Corrected |

**Not changed, having failed verification:** the `EXCLUDE (abn WITH =)` constraint is correct as
written — it defaults to btree, not GiST, and needs no `btree_gist` extension (confirmed by
executing it); the ABS postcode correspondence exists exactly as cited
(`CG_SAL_2021_POA_2021.xlsx`, CC BY 4.0); Sheets dropdown validation does reject invalid typed
input; "lockfile" already admits a crash-safe `flock`; and GoHighLevel's no-bulk-upsert, tag
overwrite and rate-limit claims are all verbatim correct. **Unverified:** the `duckdb-diff`
dimension's dedicated agent was stopped before reporting; its central claims were independently
covered by two other agents' benchmarks, but no separate review of it exists.

---

## Objective

Build a weekly, automated pipeline that ingests the free ABR ABN Bulk Extract, detects
week-over-week changes across the whole Australian business register, classifies them by
entity type / inferred industry / created date, and enriches a qualified slice with
contactable details (website, email, phone, socials) that a lead-gen VA can work inside a
two-hour weekly session.

The output is a defensible, auditable lead list for Maintain Media's marketing and
lead-generation offer — not a data product. Part 2 (client workflow, website build,
marketing/lead-service proposal) consumes this feed and is out of scope.

**One commercial warning, stated up front and then designed around.** "Registered an ABN last
week" is a weak buying signal: registration is free and takes ten minutes, ~67% of
non-cancelled ABNs are not actively trading (ABS, see Appendix), a large share are rideshare/gig registrations,
and a day-one registrant has no revenue. The same pipeline that answers the literal brief also
produces two materially better signals for almost no extra cost — a **GST registration flip on
an established business** (just crossed the $75k turnover threshold) and the **QBCC licensed
contractor register** (QLD building contractors with regulator-verified revenue bands and
street addresses). Both are built here. The brief is delivered in full as tiers B and C; the
better signals are tier A. §14 sets a pre-committed measurement that decides which survives.

---

## Context / background

### What already exists in this repo

`deliverables/abr/extract_new_abns.py` is a working single-pass extractor: streams ABR XML in
8 MB chunks, regex-parses records, filters `status=ACT AND ABNStatusFromDate >= --since`,
infers a trade category from business and trading names via an ordered keyword ruleset
(`TRADE_RULES`, **30** rules), and writes three CSVs. Standard library only. Its README
documents the data ceiling honestly: of 45,556 new ABNs in **one of twenty** split files,
43,455 (95.4%) were unclassifiable, because ~33,000 are sole traders whose only recorded name
is a person's legal name.

This spec keeps `TRADE_RULES` and the streaming-parse approach and replaces the rest
(single-snapshot, no diff, no state, no enrichment, no compliance record).

### Verified facts about the ABR source

Checked directly against data.gov.au on 6–7 September 2026 by API call and HTTP range read —
not taken from documentation, which is stale.

| Fact | Value | Confidence |
|---|---|---|
| Dataset | ABN Bulk Extract. CKAN slug `abn-bulk-extract`, id `5bd7fcab-e315-42cb-8daf-50b7efc2027e`. Both resolve on `package_show` | VERIFIED (called) |
| Cadence | **Weekly. Published Tuesday night UTC, landing Wednesday ~08:33 Australian eastern time.** This is a *local-time* schedule, so the UTC instant shifts with daylight saving: ~22:33 UTC Tuesday during AEST, ~21:33 UTC Tuesday during AEDT (AEDT resumes 4 October 2026, inside the first 8-week window — **never hard-code the UTC time**). Unbroken back to at least Jun 2026; Part 1 and Part 2 both carried `last_modified 2026-09-03`; inner member `20260903_Public01.xml` | VERIFIED — CKAN `package_activity_list` + range read of the ZIP local header |
| Off-cycle republishes | Routine — 5 in the 24 weeks to 3 Sep 2026. Trigger on `last_modified`, never on a weekday | VERIFIED |
| Delivery | 2 ZIPs (~497 MB each, 994.5 MB total) → 20 XML members, ~12.61 GB uncompressed | VERIFIED |
| Records | ~20,495,750 ABNs; each member declares its own `<RecordCount>` in `TransferInfo` | VERIFIED |
| Range requests | `HTTP 206` + `Content-Range` on both ZIPs — resumable download is viable | VERIFIED (tested) |
| Licence | **CC BY 3.0 AU** — commercial use and adaptation expressly permitted, attribution required | VERIFIED (CKAN `license_id: cc-by`). *The absence of a direct-marketing restriction was checked in the licence itself; the ABR's separate bulk-extract terms of use were **not** independently re-verified — confirm at legal review.* |
| Fields present | ABN + status + `ABNStatusFromDate`; `EntityTypeInd`/`Text`; main **or** legal name (mutually exclusive `xsd:choice`); 0..N other names typed `TRD`/`BN`/`OTN`; ASIC number; GST status + date; DGR; **state + postcode only** | VERIFIED |
| Fields absent | **No ANZSIC/industry code. No email. No phone. No street address. No website.** | VERIFIED by exhaustive element enumeration |
| Cancelled records | Retained permanently as `status="CAN"`; records never disappear, so `ACT→CAN` diffing is reliable | VERIFIED |
| `ASICNumberType` | Always the literal string `"undetermined"` — the extract never says whether it is an ACN, ARBN, ARSN or ARFN | VERIFIED |
| Name types present | In an 865,608-record sample of the 2026-09-03 file: `MN` 410,238 · **`TRD` 191,300** · **`BN` 109,569** · `OTN` 18,974 · `DGR` 333 | VERIFIED by inflating the member and counting |

**The gotcha that dictates the architecture.** `ABNStatusFromDate` is heavily backdated —
30.2% of cancellations are backdated more than 30 days, 17.3% more than a year, maximum ~22.8
years. A "cancelled this week" query on that field misses most of the week's real
cancellations. **Closures must be detected by diffing consecutive snapshots.** For the same
reason, snapshots must be retained from run one: the extract carries no history, so the
snapshot archive *is* the history.

Backdating affects registrations far less, and asymmetrically in our favour: a backdated
registration date only makes a business look *older*, which is the safe direction for the
tier A age test in §14. Registration dates are therefore usable for the created-date
dimension and the age band; cancellation dates are not usable for anything.

**Second gotcha: file membership shifts every week.** Members are contiguous ascending-ABN
chunks of a fixed size (currently 1,025,200) recomputed as the register grows. One inserted
ABN shifts records across member boundaries. Diff the whole set keyed on ABN; never member-N
against member-N. Current capacity (20 × 1,025,200 = 20,504,000) is only ~8,250 above the
actual record count, so a re-partition — possibly changing the member count — is imminent.
**Nothing may hard-code the number 20.**

### Verified facts about the QBCC source

Downloaded and parsed in full on 7 September 2026.

| Fact | Value | Confidence |
|---|---|---|
| Resource | QBCC Licensed Contractors Register, `data.qld.gov.au` dataset `980b6499-c0b4-491b-ba9c-1c7506368a50` | VERIFIED |
| Licence | CC BY 4.0 | VERIFIED |
| Size / format | 76,300,852 bytes CSV, **UTF-16LE with BOM `\xff\xfe`** — a UTF-8 read produces garbage | VERIFIED |
| **Freshness** | HTTP `last-modified: Mon, 18 May 2026` — **~16 weeks stale.** The portal describes it as weekly; the CKAN record carries no `update_frequency` and the file has not moved since May | VERIFIED |
| Columns (exactly 11) | Licence Number, Licensee Name, ACN, ABN, Licensee Business Address, Licence Type DESC/CODE, Financial Category DESC/CODE, Licence Grade, Licence Class Type | VERIFIED |
| Licence issue date | **Absent.** New licences are detectable only by diffing snapshots | VERIFIED |
| Street address | **Present and full** (e.g. "53 BUCKINGHAM COURT MOUNT HALLEN QLD 4312") — richer than the ABR, which has state + postcode only | VERIFIED |
| Shape | 196,116 rows / **108,536 distinct licences**; up to 32 rows per licence (one per Licence Class Type) — must collapse to one record per licence number | VERIFIED |
| ABN coverage | ABN on 54.5% of rows, **55,016 distinct ABNs** — the ABR join reaches about half the register | VERIFIED |
| Financial categories | 14 observed codes, not the 9 usually cited: SC2 38,082 · SCT1 28,789 · N/A 27,374 · Cat 2 5,562 · Cat 1 5,518 · Cat 3 1,565 · EMRSC1 345 · Cat 4 274 · Cat 5 238 · EMRSC2 233 · Cat 6 205 · Cat 7 184 · EMR1-2 131 · EMR3-7 36 | VERIFIED |
| **The ICP slice** | **Category 1–2 = approved maximum revenue $800k–$12m = 11,080 licences**, of which 9,083 carry an ABN and 9,969 are companies | VERIFIED |
| Geography | Not QLD-only — QBCC licenses interstate contractors (a sampled Cat 2 licensee is in VIC 3201). Filter on the address, not on the source | VERIFIED |

**The consequence for design.** Because the file is 16 weeks stale, QBCC is **not a weekly
change signal** and must not be specified as one. It is two other things, both valuable:
a **static ICP list** of 11,080 building contractors in the $800k–$12m revenue band with
street addresses, available immediately at zero cost; and a **low-frequency change feed**
whose diff runs whenever the file actually moves.

**Third gotcha: `TRD` trading names are frozen, not current — and this changes how industry is
inferred.** The ABR stopped collecting and updating trading names in May 2012, and from
1 November 2025 only legal names and ASIC-registered business names are shown on ABN Lookup.
Trading names have **not** disappeared from the bulk extract — they are still there in volume —
but they are up to 14 years stale. Measured across the **282,672 records with `status=ACT`**
found in a 648,853-record sample of the 2026-09-03 file (the remaining ~56% are cancelled and
are excluded from this table):

| ABN active from | records | carries `TRD` | carries `BN` | carries `OTN` |
|---|---:|---:|---:|---:|
| 2026 (new) | 29,411 | 5.4% | 15.0% | 0.3% |
| 2023–2025 | 79,371 | 4.6% | 16.4% | 0.3% |
| 2013–2022 | 95,539 | 5.3% | 22.9% | 0.3% |
| 2012 and earlier | 78,351 | **43.3%** | 16.6% | 4.2% |

The cliff at 2012 is exactly the collection cut-off. The consequences for R14:
**`BN` (ASIC-registered business name) is the only live, current, high-confidence name signal.**
`TRD` is legacy data — abundant on pre-2013 ABNs, near-absent on the recent ABNs this pipeline
targets, and never fresh — so it may support `medium` confidence but never `high`. `OTN` is
frequently a personal alias rather than a business name and must be excluded from industry
inference entirely. The existing `extract_new_abns.py` lumps all three together, which is a
defect this spec corrects.

### The binding constraint is marketing law, not licensing

The ABR licence permits commercial use. The Spam Act 2003, Privacy Act 1988, Do Not Call
Register Act 2006 and Australian Consumer Law govern what happens after a contact detail is
attached. Four findings drive §F.

1. **Do not buy a list, or pay a third party to append contacts.** Privacy Act 1988 s 6D(4)
   removes the small-business exemption from an entity that, among other things:
   > "…discloses personal information about another individual to anyone else for a benefit,
   > service or advantage; [or] provides a benefit, service or advantage to collect personal
   > information about another individual from anyone else…"

   Buying or appending a list is the second of those; reselling the list is the first. *(The
   paragraph letters are deliberately not cited here. Whether the subsection's opening words are
   counted as paragraph (a) shifts every letter by one, and reviewers of this spec disagreed
   about it three times. The operative text is unambiguous and is what binds — quote it, don't
   pinpoint it. Confirm the current lettering against the Federal Register of Legislation at the
   time of any legal advice.)* Note also **s 6D(7) and 6D(8)**, which disapply these paragraphs
   where the collection or disclosure is made with the individual's consent or is required or
   authorised by law — neither of which is available for cold-sourced marketing data.
   Buying a mailing list is OAIC's own worked example of trading in personal information, and it
   is the fact pattern behind ACMA's enforceable undertaking against Victorian Institute of
   Technology (September 2022 — investigation report and enforceable undertaking published on
   acma.gov.au; 6,045 messages sent to third-party-supplied addresses. **Verify the citation
   before relying on it in advice.**)
2. **Do not treat "the email was on their website" as a policy.** Spam Act Schedule 2 clause 4 —
   the consent that arises from **conspicuous publication** (distinct from the inferred-consent
   limb elsewhere in Schedule 2) — is a per-address test with cumulative conditions, and s 16(5) puts the
   evidential burden on the sender. It is recorded per record with the source page snapshotted
   at collection, and it fails closed. See R24.
3. **Consent is only the first of three message-level duties.** s 16 (consent) is separate from
   **s 17** (accurate sender identification) and **s 18** (functional unsubscribe), which apply
   to every commercial electronic message with no conspicuous-publication carve-out. **s 22**
   separately prohibits using a harvested-address list, and s 22(2) only saves you where the
   messages do not contravene s 16 — so one failed clause 4(2) assertion stacks contraventions.
4. **Selling a retainer off an uninvited call is an unsolicited consumer agreement.** ACL s 69
   and following apply where a business acquires services under $100,000 — which is every deal
   in this funnel. That brings a 10-business-day cooling-off period and a prohibition on taking
   payment or supplying during it. The pipeline must record whether contact was invited.

**Google Places / Maps Platform is excluded by design, on licensing not price.** The *Google
Maps Platform Terms of Service* (§3.2.3 "No Scraping" / "No Caching") prohibit exporting,
extracting or storing Maps content outside the services, including copying and saving business
names, addresses or user reviews; the separate *Maps Service Specific Terms* grant a caching
right only for latitude/longitude values (30 days) and, under the General Terms, place IDs. A
persistent CRM of Places-sourced names, phones and websites is therefore a breach, and §3.2.3
separately prohibits use "in a listings or directory service or to create or augment an
advertising product". Verify against
`cloud.google.com/maps-platform/terms` and `/maps-service-terms` before any future
reconsideration — clause numbering changes between revisions.

---

## Data model

Authoritative. Column names used here are the ones the code must use.

**Storage split.** DuckDB + Parquet holds snapshots and diffs (columnar, no server, ideal for a
20M-row weekly diff). **PostgreSQL 16 on the same host** holds everything with a compliance or
mutation requirement — contact records, provenance, consent basis, suppression and outcomes —
because those need constraints, encryption and an audit trail that Parquet cannot give.

```sql
-- ── Snapshot (Parquet, one file per extract: snapshots/abr_<YYYYMMDD>.parquet) ──
-- abn VARCHAR(11) NOT NULL          abn_status VARCHAR(3)        -- ACT | CAN
-- abn_status_from_date DATE         entity_type_ind VARCHAR(4)
-- entity_type_text VARCHAR(100)     main_name VARCHAR(200)   -- see name_source
-- legal_given_names VARCHAR(120)    legal_family_name VARCHAR(80)
-- name_source VARCHAR(6) NOT NULL   -- 'main' | 'legal'; MainEntity and LegalEntity are an
--                                   -- xsd:choice, so exactly one branch is populated. For
--                                   -- legal-name records main_name = GivenName(s) + FamilyName
--                                   -- joined by single spaces, uppercased, whitespace collapsed.
-- other_names STRUCT(type VARCHAR, text VARCHAR)[]               -- TRD | BN | OTN, 0..N
-- asic_number VARCHAR(9)            gst_status VARCHAR(3)        -- ACT | CAN | NON
-- gst_status_from_date DATE         state VARCHAR(3)             -- nullable
-- postcode VARCHAR(4)               -- nullable
-- record_last_updated_date DATE     row_hash VARCHAR(32)         -- md5 of business fields
-- source_member VARCHAR(40)         -- provenance only; never used as a join or diff key

-- Events are split by source. A single `events` table keyed on ABN cannot work: 45.5% of QBCC
-- rows carry no ABN, and ABN is not unique per licence (55,016 distinct ABNs across 108,536
-- distinct licences), so QBCC rows would both violate NOT NULL and collide on the key.
CREATE TABLE abr_events (                 -- append-only
  abn            CHAR(11)     NOT NULL,
  event_type     TEXT         NOT NULL,   -- see R8
  snapshot_from  DATE,                    -- null on the baseline run
  snapshot_to    DATE         NOT NULL,
  detected_at    TIMESTAMPTZ  NOT NULL,
  field_before   JSONB,                   -- only the fields that changed
  field_after    JSONB,
  rules_version  TEXT         NOT NULL,
  lead_tier      CHAR(1),                 -- A | B | C | null (not a lead event)
  lead_score     INT,                     -- provisional only; immutable. See R17.
  PRIMARY KEY (abn, event_type, snapshot_to)   -- one ABN MAY emit several event types per run
);

CREATE TABLE qbcc_events (                -- append-only; keyed on licence, not ABN
  licence_number TEXT         NOT NULL,
  event_type     TEXT         NOT NULL,   -- qbcc_licence_new | qbcc_category_changed
                                          -- | qbcc_icp_backlog (the one-off Phase 0 emission)
  snapshot_from  DATE, snapshot_to DATE NOT NULL,
  detected_at    TIMESTAMPTZ  NOT NULL,
  field_before   JSONB, field_after JSONB,
  rules_version  TEXT         NOT NULL,
  lead_tier      CHAR(1), lead_score INT,
  PRIMARY KEY (licence_number, event_type, snapshot_to)
);

CREATE TABLE businesses (                 -- current-state table, UPSERTED each run, never truncated
  abn CHAR(11) PRIMARY KEY, entity_type_text TEXT, entity_class TEXT, -- see R14
  main_name TEXT, other_names JSONB, state TEXT, postcode TEXT,
  abn_status TEXT, abn_status_from_date DATE, abn_age_months INT,
  gst_status TEXT, gst_status_from_date DATE, asic_number TEXT,
  industry TEXT, industry_confidence TEXT,  -- high | medium | none
  industry_matched_on TEXT,                 -- the literal name string that matched
  created_month CHAR(7),                    -- YYYY-MM
  date_in_future BOOLEAN NOT NULL DEFAULT FALSE
);

-- Not every lead has an ABN: 45.5% of QBCC licence rows carry none, and the Phase 0 ICP list is
-- the first thing built. All lead-bearing tables therefore key on lead_entity, not on abn.
CREATE TABLE lead_entity (
  -- NOTE: abn is deliberately NOT a foreign key to businesses. Phase 0 (the QBCC ICP list) runs
  -- in week 1, before any ABR snapshot exists, so businesses is empty; an FK here would make the
  -- first deliverable unbuildable. Referential integrity to businesses is asserted by a nightly
  -- reconciliation check, not by a constraint.
  lead_id UUID PRIMARY KEY,
  abn CHAR(11),                                   -- nullable; not an FK, see note above
  qbcc_licence_number TEXT,                       -- nullable; not an FK (qbcc_licence is
                                                  -- snapshot-keyed, so it has no single row here)
  display_name TEXT NOT NULL, state TEXT, postcode TEXT,
  CONSTRAINT has_a_source CHECK (abn IS NOT NULL OR qbcc_licence_number IS NOT NULL),
  -- One lead per QBCC licence. NOT unique on abn: ~2 licences share an ABN on average
  -- (55,016 ABNs across 108,536 licences), so a UNIQUE(abn) would reject the second licence.
  UNIQUE (qbcc_licence_number),
  -- An ABR-sourced lead (no licence) is unique on ABN; a licence-sourced lead is not.
  CONSTRAINT one_abr_lead_per_abn EXCLUDE (abn WITH =) WHERE (qbcc_licence_number IS NULL)
);

CREATE TABLE contact_record (
  contact_id UUID PRIMARY KEY,
  lead_id UUID NOT NULL REFERENCES lead_entity(lead_id),
  channel TEXT NOT NULL                      -- v1 ships email | mobile | landline only.
    CHECK (channel IN ('email','mobile','landline')),   -- postal and social_dm are out of scope:
    -- neither has a gate defined in section F, so allowing them would bypass the compliance gate
  endpoint_value BYTEA NOT NULL,             -- pgcrypto pgp_sym_encrypt
  endpoint_hash CHAR(64) NOT NULL,           -- sha256 of the NORMALISED value; survives deletion
    -- NOT globally unique: two businesses legitimately share a bookkeeper's email or an office
    -- landline, which is common in this cohort. Unique per lead+channel instead (see below).
    -- Suppression still keys on the bare hash, so suppressing a shared endpoint suppresses it
    -- for every lead that carries it — which is the correct and safest behaviour.
    -- Normalisation is defined once and used by suppression, DNC wash and dedupe alike:
    --   email : lower-case; strip surrounding whitespace; no other transformation
    --           (do NOT strip dots or +tags — that is Gmail-specific and wrong elsewhere)
    --   phone : strip all non-digits; drop a leading 0; prefix +61; reject if not 11 chars
  is_personal_information BOOLEAN NOT NULL,  -- see R23
  role_address BOOLEAN NOT NULL,             -- info@ admin@ sales@ enquiries@ office@ accounts@
  contact_person_name TEXT, role_or_title TEXT,
  verification_status TEXT,                  -- deliverable | catch_all | unknown | undeliverable | n/a
  first_provenance_id UUID NOT NULL,         -- makes an endpoint-without-provenance unrepresentable
    -- The FK is attached by the ALTER TABLE below, NOT here. collection_provenance does not exist
    -- yet at this point in the script, and a forward REFERENCES fails with 42P01 undefined_table,
    -- taking contact_record, collection_provenance, spam_act_basis and send_eligibility down with
    -- it. VERIFIED by executing this DDL against PostgreSQL 16.4.
  first_seen TIMESTAMPTZ NOT NULL, last_seen TIMESTAMPTZ NOT NULL,
  UNIQUE (lead_id, channel, endpoint_hash)
);

CREATE TABLE collection_provenance (       -- append-only, never updated
  provenance_id UUID PRIMARY KEY,
  contact_id UUID NOT NULL REFERENCES contact_record(contact_id),
  source_type TEXT NOT NULL,               -- abr_bulk_extract | qbcc_register | serp_result
                                           -- | business_own_website | inbound_form | referral
  source_url TEXT NOT NULL,
  source_page_snapshot_ref TEXT,           -- object-store key of the rendered HTML at collection
  page_text_excerpt TEXT,                  -- ±500 chars around the endpoint, for limb evidence
  terms_page_checked BOOLEAN NOT NULL DEFAULT FALSE,   -- required for limb_d; see R24
  CONSTRAINT web_sources_need_evidence CHECK (
    source_type NOT IN ('serp_result','business_own_website')
    OR (source_page_snapshot_ref IS NOT NULL AND page_text_excerpt IS NOT NULL)),
  collected_at_utc TIMESTAMPTZ NOT NULL,
  collected_by TEXT NOT NULL,              -- pipeline version or operator id
  collection_method TEXT NOT NULL,         -- automated_crawl | api | manual
  robots_txt_compliant BOOLEAN NOT NULL,
  site_terms_snapshot_ref TEXT
);

-- The circular reference is closed here, deferred, so the pair can be inserted in one transaction.
-- Insert order inside that transaction is contact_record FIRST, then collection_provenance; the
-- deferred check passes at COMMIT. This does NOT work under autocommit — a single-statement insert
-- of contact_record still fails at statement end. VERIFIED against PostgreSQL 16.4.
ALTER TABLE contact_record
  ADD CONSTRAINT contact_record_first_provenance_fk
  FOREIGN KEY (first_provenance_id) REFERENCES collection_provenance(provenance_id)
  DEFERRABLE INITIALLY DEFERRED;

CREATE TABLE spam_act_basis (          -- RECORD-level limbs only; one row per contact+channel
  contact_id UUID NOT NULL REFERENCES contact_record(contact_id),
  channel TEXT NOT NULL,
  basis TEXT NOT NULL,                     -- express_consent | conspicuous_publication_sch2_cl4 | none
  limb_a_identifiable_role       BOOLEAN NOT NULL,
  limb_b_conspicuously_published BOOLEAN NOT NULL,
  limb_c_published_with_agreement BOOLEAN NOT NULL,
  limb_d_no_no_unsolicited_statement BOOLEAN NOT NULL,
  -- limb_e (message relevant to role) is NOT here: it is a property of the message, not the
  -- record, so it lives in send_eligibility below. Folding it in here would let a record that
  -- passed for one campaign auto-pass for the next.
  record_level_pass BOOLEAN GENERATED ALWAYS AS (
    limb_a_identifiable_role AND limb_b_conspicuously_published
    AND limb_c_published_with_agreement AND limb_d_no_no_unsolicited_statement) STORED,
  evidence_provenance_id UUID NOT NULL REFERENCES collection_provenance(provenance_id),
  assessed_at TIMESTAMPTZ NOT NULL, assessed_by TEXT NOT NULL,
  expires_at TIMESTAMPTZ NOT NULL,         -- assessed_at + 90 days; see R25
  override_by TEXT, override_reason TEXT, override_at TIMESTAMPTZ,
  CONSTRAINT override_complete CHECK (
    (override_by IS NULL AND override_reason IS NULL AND override_at IS NULL) OR
    (override_by IS NOT NULL AND override_reason IS NOT NULL AND override_at IS NOT NULL)),
  PRIMARY KEY (contact_id, channel)
);

CREATE TABLE send_eligibility (        -- PER-SEND limb (e); asserted per campaign, never inherited
  send_id UUID PRIMARY KEY, contact_id UUID NOT NULL, channel TEXT NOT NULL,
  campaign_id TEXT NOT NULL, template_id TEXT NOT NULL,
  limb_e_relevant_to_role BOOLEAN NOT NULL,
  asserted_by TEXT NOT NULL, asserted_at TIMESTAMPTZ NOT NULL,
  FOREIGN KEY (contact_id, channel) REFERENCES spam_act_basis(contact_id, channel)
);

CREATE TABLE do_not_market (           -- APP 7 opt-out, at entity level; see R24a
  lead_id UUID PRIMARY KEY REFERENCES lead_entity(lead_id), reason TEXT NOT NULL,
  requested_at TIMESTAMPTZ NOT NULL, source TEXT NOT NULL
);

CREATE TABLE enrichment (              -- the output of section E; referenced by R22, R23, R34
  lead_id UUID PRIMARY KEY REFERENCES lead_entity(lead_id),
  website_url TEXT, website_found_by_query SMALLINT,   -- 1 | 2 | 3, which template matched
  contact_form_url TEXT, social_urls JSONB,
  positioning_notes VARCHAR(400),
  google_business_profile_present BOOLEAN,             -- from the SERP result only; no Places data
  enrichment_status TEXT NOT NULL                      -- pending | complete | exhausted | skipped
    CHECK (enrichment_status IN ('pending','complete','exhausted','skipped')),
  stages_run TEXT[], serp_queries_used SMALLINT NOT NULL DEFAULT 0,
  page_fetches_used SMALLINT NOT NULL DEFAULT 0, verifications_used SMALLINT NOT NULL DEFAULT 0,
  first_enriched_at TIMESTAMPTZ, last_enriched_at TIMESTAMPTZ
);

CREATE TABLE qbcc_licence (            -- one row per LICENCE NUMBER **per snapshot**: the diff
                                       -- needs two snapshots to coexist, so snapshot_date is
                                       -- part of the key, not a plain column
  licence_number TEXT NOT NULL, licensee_name TEXT NOT NULL,
  acn TEXT, abn CHAR(11),                              -- nullable: 45.5% of rows carry no ABN
  street_address TEXT, state TEXT, postcode TEXT,      -- parsed from the single address string
  licence_type TEXT,                                   -- Individual | Company
  financial_category_code TEXT, financial_category_desc TEXT,
  licence_grade TEXT, class_types TEXT[],              -- every Licence Class Type for this licence
  snapshot_date DATE NOT NULL, row_hash CHAR(32) NOT NULL,
  PRIMARY KEY (licence_number, snapshot_date)
);

CREATE TABLE worklist_candidate (      -- resolves the two-pass lead_score problem; see R17
  worklist_week DATE NOT NULL, lead_id UUID NOT NULL REFERENCES lead_entity(lead_id),
  signal TEXT NOT NULL,      -- the event_type that qualified it, from abr_events or qbcc_events
                             -- (the Phase 0 ICP list uses 'qbcc_icp_backlog')
  lead_tier CHAR(1) NOT NULL,
  lead_score_provisional INT NOT NULL,                 -- at qualify time, contactability = 0
  lead_score_final INT,                                -- recomputed after enrichment
  rank INT, carried_over_from DATE, exported BOOLEAN NOT NULL DEFAULT FALSE,
  PRIMARY KEY (worklist_week, lead_id)
);

CREATE TABLE dnc_wash (                    -- see R25
  wash_id UUID PRIMARY KEY, endpoint_hash CHAR(64) NOT NULL,
  washed_at TIMESTAMPTZ NOT NULL, result TEXT NOT NULL,  -- clear | listed | error
  provider TEXT NOT NULL, provider_receipt_ref TEXT NOT NULL
);

CREATE TABLE suppression (                 -- ENDPOINT level; global across all Maintain entities; never deleted
  endpoint_hash CHAR(64) PRIMARY KEY,
  reason TEXT NOT NULL,                    -- unsubscribe | complaint | abn_cancelled
                                           -- | no_unsolicited_notice | manual
  suppressed_at TIMESTAMPTZ NOT NULL, source TEXT NOT NULL
);

CREATE TABLE outcomes (                    -- written back by the VA; see R30
  lead_id UUID NOT NULL REFERENCES lead_entity(lead_id), worklist_week DATE NOT NULL,
  lead_tier CHAR(1) NOT NULL, signal TEXT NOT NULL,
  status TEXT NOT NULL,                    -- see R30 for the closed vocabulary
  invited_contact BOOLEAN NOT NULL DEFAULT FALSE,     -- ACL s 69; see R28
  attempts INT NOT NULL DEFAULT 0, first_touch DATE, last_touch DATE,
  meeting_booked BOOLEAN NOT NULL DEFAULT FALSE, meeting_held BOOLEAN NOT NULL DEFAULT FALSE,
  notes TEXT,
  PRIMARY KEY (lead_id, worklist_week)
);
```

---

## Build sequence and what it costs

**Phase 0 — week 1, before a line of ABR pipeline code.** Parse the 76 MB QBCC CSV, emit the
11,080 Category 1–2 licensees, enrich the top 200 by the R21 rules, and hand the VA four weeks of
worklists. This is the only VERIFIED volume figure in the document, it comes with street
addresses, it needs no diff engine, no snapshot archive and no weekly trigger, and it can be
delivered in **1–2 developer-days**. It also produces real outcome data before the expensive part
is built.

**Phase 1 is conditional on Phase 0.** If four weeks of QBCC worklists produce no booked meeting,
the problem is the offer or the script, not the data — and building a 20-million-record weekly
pipeline will not fix it. Stop and fix the offer first.

**ESTIMATED build effort** (developer-days, one experienced developer):

| Module | Days |
|---|---|
| Phase 0 — QBCC parse, ICP list, first worklists | 1–2 |
| Ingest (poll, download, stream-parse, snapshot) | 2–3 |
| Diff and events | 1–2 |
| Classify and qualify (incl. rules YAML) | 1–2 |
| Enrich (SERP, crawl, verify) | 3–4 |
| Compliance schema and export gate | 3–4 |
| Export, worklist, GoHighLevel sync | 2–3 |
| Ops, alarms, runbook, tests | 2–3 |
| **Total** | **15–23 developer-days** |

**What it is worth if it works.** At an ESTIMATED 200–600 enriched leads per week and the
phone-channel benchmarks, the honest funnel is stated so it can be falsified. Note the binding
constraint first: the worklist is capped at **60 leads/week = ~260/month**, and one VA at 2 hours
a week cannot make 1,600 dials — so the volume ceiling is the worklist, not the dialler.
At ~260 leads/month, ~2 dial attempts each → ~30% connect → ~5–10% of connects set an appointment
→ ~60–70% held → ~15–25% close ≈ **0.5–1.5 sales/month.** Raising that means either lifting the
worklist cap and the VA's hours, or improving conversion — not dialling harder. Against the $50k/month cash-flow target that needs ~20 clients at $2.5k/month, **this channel at
this staffing level is off by an order of magnitude.** It is a test bench, not the engine. Either
staff it properly or treat it as a source of qualified conversations feeding a higher-value
offer. **This is the number to argue with before building, not after.**

## Requirements

### A. Ingest

1. A scheduler polls
   `https://data.gov.au/data/api/3/action/package_show?id=abn-bulk-extract` every 6 hours and
   compares each ZIP resource's `last_modified` against the last processed value stored
   locally. A run triggers only when **both** Part 1 and Part 2 carry a `last_modified` newer
   than the last processed run **and** the two values are within 48 hours of each other.
   Mismatched halves are never processed together. **Deadlock escape:** if the two halves remain
   mismatched for more than 7 days, raise a `halves_mismatched` alarm and hold. Processing an
   inconsistent pair requires an explicit, logged manual override naming the operator and the
   reason; it is never automatic, because a mixed-date diff manufactures phantom entries and
   exits across the entire register.
2. Download both ZIPs with HTTP range-resume on failure, verify the byte length against the
   CKAN-declared `size`, and retry up to 5 times with exponential backoff before failing.
3. Parse **every XML member found in the two ZIPs, whatever the count**, streaming from within
   the archive (`zipfile.ZipFile.open`) without materialising 12.6 GB. Peak process memory must
   stay under 2 GB. No code may hard-code the member count.
4. Per member, assert `parsed_record_count == that member's declared TransferInfo/RecordCount`,
   and assert the sum of declared counts equals the total parsed. Any mismatch fails the run
   with a non-zero exit and an alarm; a partially-parsed snapshot is never written. A member
   count differing from the previous run raises an alarm but does **not** fail the run — this is
   the expected signature of the imminent re-partition.
5. Extract the snapshot columns listed in §Data model. The parser must tolerate self-closing
   elements (`<GST ... />`) and must not depend on attribute order. **It must also resolve XML
   entity and character references** (`&amp;` → `&`, `&#39;` → `'`). This is why the inherited
   regex-on-chunks reader from `extract_new_abns.py` is replaced by
   `xml.etree.ElementTree.iterparse` with element clearing: measured on ABR-shaped fixtures, the
   regex reader yields `SMITH &amp; SONS` where `iterparse` yields `SMITH & SONS`. That corruption
   is silent, it lands in `main_name`, and because `row_hash` is computed over the business fields
   it would manufacture a `name_changed` event for every affected record the moment the reader is
   ever fixed. `iterparse` measured only ~19% slower on the same fixture, and parsing is not the
   bottleneck. A reader that streams fixed-size chunks must additionally carry a tail buffer
   across chunk boundaries, or it silently drops roughly one record per boundary.
6. Write `snapshots/abr_<YYYYMMDD>.parquet` (zstd), where `<YYYYMMDD>` is the inner member
   filename date, and replicate to object storage. Snapshots are immutable and retained
   indefinitely. **The write must be streamed in bounded batches** (measured: 50,000-row batches
   hold peak RSS to ~351 MB for a full 20.5M-row write). Building a single in-memory table over
   all ~20.5M rows before writing is the one way this stage breaches the 2 GB cap in R3, and it is
   the default shape of most Parquet examples — so it is called out here rather than left to
   discovery.

### B. Diff and event detection

7. Diff the new snapshot against the immediately prior snapshot with a single DuckDB
   `FULL OUTER JOIN ... USING (abn)` over the two Parquet files, inserting into `abr_events`.
   **A single ABN may produce several rows in one run** — one per event type — keyed
   `(abn, event_type, snapshot_to)`.
   **DuckDB's `memory_limit` and `temp_directory` must both be set explicitly before the join.**
   DuckDB defaults `memory_limit` to ~80% of system RAM; on the shared 8 GB host of §Constraints
   that lets the diff claim memory PostgreSQL needs and get Postgres OOM-killed mid-run. This
   costs nothing: the full 20.5M × 20.5M `FULL OUTER JOIN` was measured at **9.1 seconds with
   `memory_limit` set to 512 MB and zero spill**, against a 60-second acceptance target — so the
   cap is free headroom, not a tradeoff.
8. Emit these event types, each recording the before/after values in `field_before`/`field_after`:
   - `abn_new` — absent last week, present and `ACT` this week
   - `abn_cancelled` — `ACT` last week, `CAN` this week
   - `abn_reactivated` — `CAN` last week, `ACT` this week
   - `gst_registered` — GST not `ACT` last week, `ACT` this week. **Fires only where the ABN was
     present in the prior snapshot.** An ABN that first appears already GST-registered is
     `abn_new`, not `gst_registered` — without this rule every new GST-registered ABN would also
     emit a GST event and flood tier A's input.
   - `gst_cancelled` — GST `ACT` last week, not `ACT` this week
   - `name_changed` — a change in the **normalised name set**: uppercase, collapse internal
     whitespace, strip punctuation, exclude `OTN`, compare as a set. Without normalisation, a
     re-casing in the source emits a change event for a large fraction of the register.
   - `abn_disappeared` — present last week, absent this week. Expected ~zero; a non-zero count
     is a data-quality alarm, not a business event, and never a lead.
9. `abn_new` and `abn_reactivated` are mutually exclusive. An ABN present-and-`CAN` last week
   and `ACT` this week is a reactivation regardless of its `ABNStatusFromDate`.
10. Closures are detected **only** by the `ACT→CAN` snapshot transition. `ABNStatusFromDate`
    must never be used as a recency filter for cancellations, and the implementation must carry
    a comment saying so with the 30.2%-backdating figure.
11. On the first ever run there is no prior snapshot: write the snapshot, emit zero events, set
    `baseline_established: true` in the manifest, log it, and exit 0. R37's volume alarms do not
    apply to a baseline run.

### C. Classify

12. Every ABN in the current snapshot is materialised into `businesses` with three dimensions:
    - **Entity type** — `entity_type_text` verbatim from the ABR, plus a derived `entity_class`
      ∈ {`sole_trader`, `company`, `trust`, `partnership`, `super_fund`, `government`, `other`}
      mapped from `entity_type_ind` by an explicit lookup table committed to the repo.
    - **Industry** — a fully specified algorithm, because the DoD requires byte-identical output
      across runs. Evaluate names in this type order: **all `BN` names → `main_name` → all `TRD`
      names.** `OTN` is never read. Within each name, apply `TRADE_RULES` in file order and take
      the first rule that matches. The first name in the type order producing any match sets
      `industry`, `industry_confidence` and `industry_matched_on`; evaluation then stops. No match
      anywhere ⇒ `Unclassified`, which is the fallback, not a rule.
    - **Created date** — `abn_status_from_date` for `ACT` records, exposed as a date and a
      `YYYY-MM` bucket.
13. **v1 ships the existing 30 `TRADE_RULES` rules unchanged.** (The repo's summary CSV has 31
    rows because the 31st is `Unclassified`, which is the no-match fallback, not a rule. A test
    asserts `len(TRADE_RULES) == 30`.) Extending the ruleset to
    non-trade categories (hospitality, retail, allied health, professional services, beauty,
    fitness, education) is explicitly deferred to v1.1, because each category needs its own
    keyword list and its own false-positive spot-check, and shipping empty categories would
    silently reclassify records. v1.1 adds one category at a time, each with ≥15 seed keywords
    and a passing spot-check per R33.
14. `industry_confidence` is `high` only where the match came from a name typed **`BN`** (an
    ASIC-registered business name — the only live, current name signal); `medium` where it came
    from `main_name` or from a `TRD` trading name (legacy, frozen since May 2012, and therefore
    possibly describing a business that no longer trades under it); `none` for `Unclassified`.
    **`OTN` names are excluded from industry inference** — they are usually personal aliases and
    matching keywords against them produces false positives.
    `industry_matched_on` stores the literal string that matched, so a false positive can be
    traced to its rule without re-running the classifier.
15. The unclassified rate for `abn_new` is recorded every run. **The expected band is
    established from the first three runs and written to the manifest; thereafter the alarm is a
    week-over-week movement of more than 3 percentage points**, not an absolute band. (An
    absolute band would have to be re-baselined every time `TRADE_RULES` changes, which
    guarantees a false alarm on every ruleset edit.)

### D. Qualify

15a. **`lead_entity` creation.** Nothing else in this spec would create these rows, so it is stated
    explicitly. A `lead_entity` row is created, idempotently, at the moment a lead-bearing event is
    first tiered A or B: from an `abr_events` row, keyed on ABN with `qbcc_licence_number` null;
    from a `qbcc_events` row, keyed on licence number with `abn` populated where the register
    carries one. `display_name`, `state` and `postcode` are copied from whichever source created
    the row — for QBCC that means parsing the single address string (R18a). Re-running a week is a
    no-op: the row is matched on `(abn)` for ABR leads and `(qbcc_licence_number)` for QBCC leads.

16. A version-controlled YAML rules file assigns every lead-bearing event a `lead_tier` and a
    `lead_score`. Only tiers A and B are enriched. The shipped v1 rules:

    | Tier | Rule |
    |---|---|
    | **A** | `gst_registered` where `abn_age_months` is 12–60 (**`abn_age_months` is computed from `abn_status_from_date` to the snapshot date; the band is inclusive of 12 and exclusive of 60**). An established business that has just crossed the $75k GST turnover threshold — it has customers, cash flow, a website to critique, and usually a conspicuously published business email, which is what makes lawful contact available at all. |
    | **A** | QBCC Category 1–2 licensee (approved revenue $800k–$12m), on first appearance in the worklist or on a category change (R18). |
    | **B** | `abn_new` where `entity_class` ∈ {`company`, `trust`} **and** `gst_status = ACT` **and** `industry_confidence` ∈ {`high`, `medium`}. This is the literal brief, filtered to the slice that can be contacted and can pay. |
    | **C** | All other `abn_new`. Counted, sorted and reported; never enriched. |
    | — | `abn_cancelled` → suppression (R26). `abn_disappeared`, `name_changed`, `gst_cancelled` → reported, never leads. |

17. `lead_score` is defined in the same YAML and is the worklist sort key. **It is computed
    twice**, because the contactability term does not exist until after enrichment:
    a **provisional** score (`tier_base + industry_confidence + geography + entity_class`,
    contactability = 0) is written at qualify time into `worklist_candidate.lead_score_provisional`
    and orders the enrichment queue; a **final** score is recomputed after enrichment into
    `lead_score_final` and orders the worklist. `events.lead_score` stores the provisional value
    and is immutable. Shipped v1 formula, capped at 100:

    ```
    lead_score = tier_base            (A 60, B 30)
               + industry_confidence  (high +15, medium +5)
               + geography            (in target state set +10)
               + contactability       (verified-deliverable email +20, phone +15,
                                       website only +5 — take the highest single value)
               + entity_class         (company +5)
    ```
    Ties break on `abn_age_months` descending (older business first), then ABN ascending.
    **For QBCC-sourced leads these inputs do not exist** — there is no `businesses` row in week 1,
    so `industry_confidence`, `entity_class` and `abn_age_months` are all null and 11,080 leads
    would collapse onto two or three identical scores with a null tie-break. The QBCC branch
    therefore uses its own terms, from columns the register actually carries:
    `tier_base(A) 60 + financial_category(Cat 2 +20, Cat 1 +15, Cat 3–7 +10, SC2 +5, else 0)
    + licence_type(Company +5) + geography(in target set +10) + contactability(as above)`,
    ties breaking on licence number ascending. Deterministic, and derived only from data in hand.
18. A parallel QBCC ingest applies the same snapshot → diff pattern. Given the source is ~16
    weeks stale (§Context), it is **not** specified as weekly: the poller checks the resource's
    HTTP `Last-Modified` weekly and ingests only when it moves. It must decode **UTF-16LE**,
    collapse the up-to-32 rows per licence to one record keyed on Licence Number, and join to
    the ABR spine on ABN (normalising the spaced `"19 168 101 522"` format — strip spaces, keep
    11 digits). **An ABN may carry several licences** (55,016 ABNs across 108,536 licences): each
    licence becomes its own `lead_entity` row, and the worklist de-duplicates on ABN at export so
    the VA is never handed the same business twice in one week. It emits
    `qbcc_licence_new` and `qbcc_category_changed`. On the first ingest it also emits a
    one-off **ICP backlog** of the 11,080 Category 1–2 licensees, which is the single highest-value
    output available on day one and does not depend on any diff ever running.
18a. **QBCC address parsing.** The register carries one unstructured address string
    ("53 BUCKINGHAM COURT MOUNT HALLEN QLD 4312"). R19's geography filter depends on it for the
    entire Phase 0 cohort, so the rule is fixed here: take the **last 4-digit token** as postcode
    and the **state token immediately preceding it** from the set {NSW, VIC, QLD, WA, SA, TAS, ACT,
    NT}; everything before that is the street/suburb string, retained verbatim and not further
    parsed. A row that yields no state-plus-postcode tail is stored with null state and postcode,
    excluded from the geography filter, counted, and reported — never silently dropped. A test
    asserts the parse against a committed fixture of 50 real address strings including the
    malformed ones.

19. `state` filter, shipped default: **QLD and northern NSW (postcodes 2450–2490) for the first
    8 weeks.** This is where Maintain Media sells, and it cuts enrichment spend by roughly 80%
    versus Australia-wide. It is one line in the rules YAML and reversible without a code change.
20. A **monthly enrichment spend cap is enforced in code** (shipped default A$150/month).
    Reaching the cap halts enrichment, completes the run, raises an alarm, and queues the
    remaining records for the next run. There is no path to an unbounded API bill.

### E. Enrich

21. Enrichment runs only on tier A and B, and only on leads whose `enrichment.last_enriched_at`
    is null or older than 90 days — **not** on `contact_record.last_seen`, which does not exist
    for a lead where enrichment found nothing, and those are the majority of tier B. Keying on
    the contact row would re-bill every expensive failure every week, forever.
    Stages, in order:
    1. **Web presence resolution** — a paid SERP API (Serper.dev or equivalent). Query 1:
       `"<main_name>" <suburb> <state>`, where suburb is resolved from postcode via the **ABS
       Australian Statistical Geography Standard postcode-to-locality correspondence** (free,
       CC BY 4.0), loaded as a static lookup table committed to the repo. Where a postcode maps
       to several localities, use the highest-population one and record which was used. Query 2, only if 1 returns no accepted
       result: `"<registered business name>" <industry keyword> <state>`, taking the first `BN`
       entry from `other_names` (never a `TRD` name — R14 demotes those as legacy). Skipped where
       the lead has no `BN` name. Query 3, only if 1 and 2 fail:
       `"<main_name>" <postcode>`. Accept the first organic result whose registrable domain is
       not in a committed blocklist (directories, marketplaces and social platforms —
       yellowpages, truelocal, hotfrog, localsearch, oneflare, hipages, airtasker, facebook,
       linkedin, instagram, abn.business.gov.au, and similar). Record the accepted domain and
       the query that found it. **Google Places / Maps Platform must not be called.**
    2. **Own-website crawl** — fetch the homepage and up to 4 same-domain pages whose href or
       link text matches `contact|about|our-team|get-a-quote`, with `requests` +
       `BeautifulSoup`; a headless-browser fallback only where the page renders no text.
       Honour `robots.txt`; 1 request per second per domain; a User-Agent naming Maintain Media
       with a contact URL. **Use `protego` (or another wildcard-aware parser) — not the standard
       library's `urllib.robotparser`, which silently ignores `*` and `$` wildcards** and will
       therefore fetch pages the site actually disallowed. Since limb (c) and limb (d) both rest
       on a lawful crawl, a parser that quietly over-fetches is a compliance defect, not a
       politeness one.
    3. **Email verification** — a verification service (MillionVerifier or equivalent). Only
       `deliverable` results become sendable endpoints; `catch_all` and `unknown` are stored
       with their status for audit and are never sent to.
22. **Stop condition.** Stages run in order and are not alternatives — stage 3 verifies stage 2's
    output. Stop after stage 1 if no own-domain website is found (nothing to crawl). Stop after
    stage 2 if it yielded a phone and no email. Always run stage 3 when stage 2 yielded an email.
    Otherwise stop when all applicable stages have run.
    Hard per-record ceilings: 3 SERP queries, 6 page fetches, 1 verification call. A record
    that exhausts its ceiling has `enrichment_status = 'exhausted'` and is not retried for 90 days.
23. Enrichment writes `website_url`, `contact_form_url`, emails (0..N), phones (0..N), social
    profile URLs, and `positioning_notes`. **`positioning_notes` is deterministic extraction, not
    generated prose:** the page `<title>`, the meta description, the first `<h1>`, and and the three most
    frequent terms from the homepage body that appear in a **committed service-term vocabulary**
    (the same keyword corpus that backs `TRADE_RULES`, lower-cased, stop-words removed) — not
    "nouns", which would require an unspecified tokeniser and make the output non-reproducible.
    Stored verbatim, 400 characters maximum. (A generated summary would be an unattributed claim about a real business sitting
    in a compliance-audited record; extraction is auditable, generation is not.)
    Every collected endpoint writes a `collection_provenance` row in the same transaction —
    no endpoint may exist without one.

### F. Compliance — non-negotiable

24. `spam_act_basis` records Schedule 2 clause 4 as five named booleans, each with a stated test:
    - `limb_a_identifiable_role` — the address enables messages to a particular individual or a
      person holding a particular office/role. A named address at the business's own domain
      passes. A generic role address passes only where
      `entity_class = sole_trader` (or, for a lead with no ABN and therefore no `businesses` row —
      the Phase 0 QBCC cohort — where `qbcc_licence.licence_type = 'Individual'`, which is the
      equivalent signal in that source), **or** where the captured page shows that role address
      alongside a named individual in a stated role at that business. (The earlier draft tested
      for a single-director company; the ABR extract carries no director data, so that test was
      unevaluable from data in hand.) It fails otherwise.
    - `limb_b_conspicuously_published` — the address is rendered as visible text on a page
      reachable without login, form submission or scripting. Evidence:
      `source_page_snapshot_ref` + `page_text_excerpt`.
    - `limb_c_published_with_agreement` — the page is on the business's **own** registrable
      domain. Third-party directories, aggregators, review sites and job boards fail this limb
      automatically and permanently.
    - `limb_d_no_no_unsolicited_statement` — the captured page **and** the site's terms page
      contain no "no unsolicited", "no canvassing", "no marketing", "do not contact" or equivalent
      statement, matched case-insensitively against a committed phrase list. Passes where the crawl checked a
      terms page and found no such statement, **or** where the crawl completed and established
      that the site has no terms page (the common case for a small trade site — recorded as
      `terms_page_checked = true` with a null terms URL). It fails only where the crawl did not
      complete or a matching phrase was found. Requiring a terms page to *exist* would make the
      email channel unexportable for most of the target cohort.
    - `limb_e_message_relevant_to_role` — the template being sent is registered against the
      recipient's industry and role. This is asserted **per send, not per record**: a record
      that passed for one campaign does not automatically pass for the next.
24a. **APP 7 — direct marketing.** This pipeline uses personal information (every sole trader,
    every named individual) for direct marketing, collected from a third party (the ABR), which
    engages **APP 7.3**. Three obligations follow and each is a system control, not a policy:
    (i) a recorded APP 7.3 assessment per cohort, held in the rules YAML with its reasoning and a
    review date, of whether obtaining consent is impracticable; (ii) **a prominent, simple opt-out
    in every direct-marketing communication on every channel** — not just email, so the VA's call
    script carries a verbal equivalent; and (iii) **APP 7.6(e): on request, Maintain Media must
    tell the individual its source for their information.** The `collection_provenance` row is
    what makes (iii) answerable; without it the obligation cannot be met. Opt-outs are recorded in
    `do_not_market` keyed on `lead_id` (**not** on ABN — an earlier draft said ABN, which
    contradicts both the DDL and the rule at §Data model that all lead-bearing tables key on
    `lead_entity`, and would be unrepresentable for the 45.5% of QBCC leads that carry no ABN)
    and are checked by the export gate alongside `spam_act_basis`,
    `dnc_wash` and `suppression`.

25. **Fail closed, and the gate lives in the export step, not in the VA's judgement.**
    - No email endpoint is exported as sendable unless `record_level_pass = true` (limbs a–d)
      **and `spam_act_basis.expires_at > now()`** and no `do_not_market` row exists for the
      `lead_id`. **The expiry must be tested explicitly by the export query.** `record_level_pass`
      is a generated column over limbs a–d only, so it keeps reading `true` forever after the basis
      expires; without a separate `expires_at` predicate the 90-day rule below is stated but never
      enforced. A DoD item asserts an expired-basis fixture is refused. **Limb e is asserted at send time by the
      Part 2 sending system, which writes the `send_eligibility` row; Part 1 must not require one
      to exist, or the email channel would export nothing at all.** What Part 1 exports is an
      endpoint marked `email_sendable_pending_relevance` — cleared on limbs a–d, awaiting the
      per-template limb e assertion. The sending system refuses to send without that row; the
      export step refuses to hand over an endpoint failing a–d. Two gates, each satisfiable.
    - No phone endpoint is exported as callable unless a `dnc_wash` row exists for its
      `endpoint_hash` with `result = 'clear'` and `washed_at` within 30 days. Washing is done
      through a Do Not Call Register subscription held directly with the Register operator, or
      through a commercial washing service that holds one. **There is no ACMA "accreditation" or
      "licensing" scheme for washing providers, and there is no negotiated tranche pricing** — the
      earlier draft asserted both and neither exists. Access is a published statutory
      cost-recovery fee table with tiers set by the volume of numbers washed per year; at this
      pipeline's volume (60 leads/week ⇒ well under 20,000 numbers/year) the applicable tier is a
      low-hundreds-of-dollars annual subscription, not a per-tranche charge. **Confirm at signup
      whether automated access (SFTP/SOAP) — as opposed to manual web upload — forces a higher
      tier, because that is the one variable that could move this from trivial to material.**
      The account must be established **before** the first call, the chosen tier's annual fee
      recorded in the cost model, and the provider receipt reference stored. Since the 2010 amendments the Do Not Call
      Register accepts business numbers as well as private ones, so there is no category of
      number that is safe to dial unwashed — and this cohort runs on personal mobiles in any
      case. **Every number is washed; no B2B exemption is assumed.**
    - **The record-level basis expires 90 days after `assessed_at`**, matching the enrichment
      refresh window. An expired basis blocks export until limbs b–d are re-verified against a
      fresh page capture. This matters because a business can add a "no unsolicited marketing"
      notice at any time, and an assessment made once and never revisited would silently go stale.
      **A carried-over lead is re-gated on every export, never on the week it was first scored.**
    - Overrides require `override_by`, `override_reason` and `override_at` together, enforced by
      the `override_complete` CHECK constraint.
26. Suppression is global across all Maintain entities, immediate, permanent, and keyed on
    `endpoint_hash` so it survives record deletion. An unsubscribe recorded against Maintain
    Media suppresses MaintainAI and QuoteMax. An `abn_cancelled` event suppresses the business.
    Suppressed endpoints are never re-solicited and never re-enriched.
27. **Message-level duties.** Part 1 does not send anything (see Non-goals). What it *does* own is
    the **export contract**: every exported lead carries the fields the sending system is required
    to render, and the export fails if any is missing. Part 1 therefore defines and tests these
    fields; Part 2 renders them. They are independent of consent and have no
    conspicuous-publication carve-out:
    - **s 17** — sender identification block: Maintain Media's legal name, ABN, postal address,
      and a phone or email that remains valid for at least 30 days after sending.
    - **s 18** — a functional unsubscribe, honoured within 5 working days, that does not require
      a login or a fee, and that writes to `suppression` automatically.
    - **APP 5 collection notice** on first contact on any channel: who Maintain Media is, that
      the details were collected from the public ABR extract and the business's own website,
      why, that a privacy policy is available at a stated URL, how to complain, and that data is
      accessible to contractors overseas (naming the countries).
    - **s 22 — is the crawler address-harvesting software?** This must be answered explicitly at
      legal review, not assumed away: s 5 defines address-harvesting software as software
      "specifically designed or marketed for" searching the internet for electronic addresses and
      harvesting them, which is a fair description of stage 2. The defence is s 22(2) — the
      prohibition does not apply where the use is **not** in connection with sending messages in
      contravention of s 16. That defence holds only for as long as the clause 4 gate holds, so a
      single failed limb converts one s 16 contravention into a stacked s 16 + s 22 exposure. The
      clause 4 gate plus the provenance record is the demonstration; The clause 4(2) gate plus the
      provenance record is that demonstration; without it, a failed limb stacks an s 22
      contravention on top of the s 16 one.
28. **Calling is governed by the Telecommunications (Telemarketing and Research Calls) Industry
    Standard 2017, which binds B2B calls even where the Do Not Call Register Act does not.**
    Calling windows, enforced in the worklist and in any dialler, in the **recipient's** time
    zone: weekdays 9am–8pm, Saturdays 9am–5pm, **never Sundays**, never national public
    holidays. Where a sale could be closed on the call, the ACL unsolicited-consumer-agreement
    window applies instead: **weekdays 9am–6pm**. Default to 6pm. Calls must present calling
    line identification, identify the caller and purpose, and terminate on request.
29. **ACL unsolicited consumer agreements.** Any agreement reached from an uninvited call or
    visit, for services under $100,000, is an unsolicited consumer agreement. The cooling-off
    period is the best-known duty but not the only one, and naming it alone understates the
    exposure: the **caller-disclosure obligations** (identify yourself, say the purpose is to
    seek an agreement, state that you must leave on request, and give the supplier's details)
    are required elements of the VA's opening script, committed to the repo and asserted by a
    script test; the **agreement-form obligations** (written agreement, prominent cooling-off
    notice, signed and given to the consumer) are required blocks in the proposal template when
    `invited_contact = false`. A **10-business-day cooling-off period** applies, during which no
    payment may be taken and no service supplied — **and where the required disclosures
    were not given, the termination period extends to 3 months, or to 6 months for the more
    serious contraventions.** Treat the script and the form as the
    control, not the calendar.
    `outcomes.invited_contact` records whether the contact was invited, and the proposal
    template branches on it. This is in Part 1 because the flag must be set at first touch —
    it cannot be reconstructed later.
30. **Outcome write-back.** The weekly worklist carries a validated status column with a closed
    vocabulary — `not_started`, `no_usable_contact`, `attempted_no_answer`,
    `contacted_not_interested`, `contacted_nurture`, `meeting_booked`, `meeting_held`,
    `disqualified`, and **`do_not_contact_requested`** — plus `attempts`, `invited_contact` and
    free-text notes. `do_not_contact_requested` is deliberately distinct from
    `contacted_not_interested`: the read-back converts it, in one transaction, into a
    `do_not_market` row for the `lead_id` **and** `suppression` rows for every `endpoint_hash` on
    that lead. Without this, a verbal opt-out taken on a call never reaches the suppression list and the
    business gets contacted again — the single most likely source of a complaint. These are read back
    into `outcomes` at the start of the following run. **Without this the week-8 kill decision in
    the Definition of done cannot be executed**, so it is a requirement, not a nicety.
31. Retention: consent, collection and send evidence for **7 years** — the Spam Act gives ACMA a
    6-year window to bring civil penalty proceedings (s 26(2)), plus a 12-month margin.
    Suppression hashes indefinitely. Enriched profiles for suppressed or disqualified records
    are destroyed or de-identified on a documented schedule, reconciling APP 11.2 minimisation
    against that evidence requirement.
31a. **APP 3 necessity, and the elephant in the snapshot archive.** This pipeline retains the
    entire Australian business register indefinitely — ~20.5 million records per weekly snapshot,
    including millions of sole traders' legal names, which are personal information. APP 3.1/3.2
    permit collecting personal information only where **reasonably necessary** for the entity's
    functions, and APP 11.2 requires destruction or de-identification once it is no longer needed.
    Retaining every record forever, when the business only ever markets to a filtered slice of
    QLD and northern NSW, is difficult to defend on necessity grounds. The design position, which
    must be written down and reviewed with the lawyer at Open Question 3:
    - **The snapshot archive is the change-detection mechanism, not a marketing database.** It is
      necessary in full, because a diff cannot be computed against a filtered subset — filtering
      before the diff would make every out-of-scope record look "new" the moment it entered scope.
    - Snapshots are therefore retained, but **access-controlled separately from the lead tables**,
      never queried for marketing, and never exported.
    - **Only records passing the R19 geography filter and the R16 tiers are ever promoted into
      `lead_entity` / `contact_record`**, which is where the marketing use actually happens.
    - A **snapshot retention limit** is set (recommended: keep all weekly snapshots for 24 months,
      then thin to monthly) rather than "indefinitely", so the position is a decision on the
      record and not an omission.
    - If the lawyer's view is that full-register retention is not defensible, the fallback is to
      retain only a **hashed ABN + row_hash index** of out-of-scope records, which supports the
      diff without retaining names. This is a real design option, so it is stated here rather
      than discovered later.

32. `is_personal_information` is set true where the record identifies an individual — every
    `sole_trader`, every partnership of individuals, and any named-person contact at a company —
    not by entity type alone.
33. **Data residency and overseas recipients.** Snapshots and the Postgres instance are hosted in
    an Australian region. That is not the whole APP 8 picture, and the earlier draft named only
    the VA. **Every overseas recipient must be enumerated, with its country and the APP 8.1
    reasonable steps taken:**

    | Recipient | What it receives | Country |
    |---|---|---|
    | Lead-gen VA | Full worklist and CRM access, including contact details | to be named |
    | **Google (Sheets / Drive)** | **The entire weekly worklist — contact details, positioning notes, and every record R32 flags as personal information. R34 puts the worklist in a Google Sheet, so Google is a recipient by construction; an earlier draft omitted it from this table while requiring that "every overseas recipient must be enumerated"** | **US** |
    | **GoHighLevel** | Tier A contact records pushed by R34 | **US** |
    | SERP provider | Business name, suburb, state as query terms | US, typically |
    | Email verification provider | Email addresses | US, typically |
    | Object store | Page captures, which may contain personal information | **AU — required, not optional** (see Constraints) |

    For each: contractual APP-equivalent obligations, audit rights, and a Spam Act and DNCR Act
    compliance warranty **flowing to Maintain Media** (the VIT vendor contract disclaimed all
    warranties, which is exactly what made it worthless). Where Maintain Media is an APP entity
    and no APP 8.2 exception applies, **s 16C makes it liable for an overseas recipient's acts as
    though it had done them itself.** All countries are named in the privacy policy and the APP 5
    notice.

### G. Output, delivery and operations

34. Each run produces, in order:
    - **A summary report** (markdown + a one-screen HTML view styled with the Maintain Media
      design system): counts by event type, entity type, industry, state and creation month;
      new-this-week and closed-this-week highlighted; week-over-week deltas; unclassified rate;
      measured enrichment hit rates by tier; spend against cap; and every alarm.
    - **A VA worklist** — Google Sheet, **capped at the top 60 leads by `lead_score_final`** (the
      volume one VA can work in two hours at roughly two minutes per lead). Leads above the cap
      carry to the following week and are re-ranked, not discarded; the report states how many
      carried over. **The queue must drain.** The Phase 0 backlog alone is 11,080 leads against a
      60/week cap — 185 weeks — and pure re-ranking would cycle the same losers forever. Two
      rules prevent that: a lead not exported within **8 weeks** of first qualifying is marked
      `deferred` and leaves the active queue (it returns only on a new event for that lead); and
      each week's worklist reserves **at least 10 of its 60 slots** for the oldest un-worked
      qualifying leads, so age eventually beats score. Columns: business, signal in plain English ("registered for GST last week
      after 3 years trading"), contact details, per-channel gate status, positioning notes,
      calling window for their time zone, and the write-back columns from R30. **Gate status is
      rendered in plain English, not engineering terms** — "Email: OK to send", "Do not email",
      "Call after DNC wash" — and each row carries a per-signal opener keyed to its `event_type`
      ("registered for GST last week after 3 years trading" reads differently from "holds a QBCC
      Category 2 licence"), plus the next action for that gate state. A list without a play is a
      list the VA cannot work.
    - **A CRM push** — tier A leads passing the gate are upserted to GoHighLevel via API v2
      (`https://services.leadconnectorhq.com`, header `Version: 2021-07-28`), **one contact per
      call — there is no bulk contact create/upsert endpoint** — respecting 100 requests per 10
      seconds and 200,000 per day. Tags are applied via the add/remove-tag endpoints, **never by
      writing the `tags` field, which overwrites all existing tags.** Tier B goes to the worklist
      only, pending human review.
35. GoHighLevel mapping, committed as a table in the repo and asserted by a test: ABN, signal,
    lead score, lead tier, industry, entity class, state, website, positioning notes and
    consent-basis summary each map to a named custom field with a declared type. Tags applied:
    `abr-tier-<a|b>`, `signal-<event_type>`, `industry-<slug>`, `state-<code>`. The target
    location id is configuration, not a literal.
36. Every run writes `run_manifest.json`: run id, trigger `last_modified` values, snapshot dates,
    member count, records parsed vs declared, event counts by type, tier counts, enrichment
    attempted/succeeded by tier, spend, CRM upserts attempted/succeeded, rules version,
    wall-clock duration, and every alarm.
37. **Alarms** are appended to the manifest **and** delivered by email to a configured operations
    address and to a healthcheck endpoint that alerts on a missed run. Alarm conditions: no
    publication in 10 days; count mismatch; member count changed; zero events on a
    non-baseline run; any event type outside ±50% of the trailing 4-week median (evaluated only
    once four non-baseline runs exist); enrichment hit rate below its band two weeks running;
    spend cap reached; API quota exhausted; `abn_disappeared` non-zero;
    `halves_mismatched` past 7 days (R1); unclassified rate moving more than 3 points (R15);
    field-fill canary outside 2 points (Edge cases); QBCC address parse failures above 1%.
    **This list is the complete alarm inventory** — the DoD tests it in full, so anything added
    later must be added here too.
38. **Operations:** one repository with `ingest/`, `diff/`, `classify/`, `enrich/`, `compliance/`,
    `export/`, `ops/` and `tests/`. All credentials come from environment variables loaded from
    a file outside the repo, never committed; the README lists every required variable. A
    lockfile prevents concurrent runs. A documented runbook covers: the extract is late, the
    parse fails, the spend cap is hit, the CRM push half-completes, and how to re-run a single
    stage against an existing snapshot.

---

## Non-goals

- **Part 2 in its entirety** — client onboarding workflow, website builds, and the marketing /
  lead-service proposal. This spec ends at "a qualified, compliant, contactable lead in the VA's
  worklist and, for tier A, in GoHighLevel."
- **Sending anything.** No email, SMS or dialling is built here. This pipeline produces the gate
  status and the calling window; the sending system honours them.
- **A saleable data product.** Enrichment is a commodity — an Apify actor sells Australian
  business records with name, phone, email, address, website and categories at US$2.99 per 1,000
  [ESTIMATE of the market floor, vendor-published, provenance unverified] — so there is no margin in reselling, and reselling would
  engage the Privacy Act s 6D(4) disclosure-for-benefit paragraph quoted in §Context. This feed fills Maintain Media's own pipeline.
- **Buying, licensing, or paying a third party to append contact data.** Excluded on legal
  grounds — the s 6D(4) collection-for-benefit paragraph quoted in §Context — not cost grounds.
- **Google Places / Maps Platform enrichment.** Excluded on licensing grounds.
- **Scraping SEEK or other job boards.** SEEK's terms expressly prohibit automated harvesting.
  Job ads remain the strongest intent signal available, but they stay a VA-operated manual play.
- **Extending `TRADE_RULES` beyond the existing 30 rules** — deferred to v1.1 (R13).
- **Historical backfill.** The extract carries no history and no public archive exists. History
  begins at the first run.
- **A daily or event-driven feed via the ABN Lookup web services.** The bulk extract is not the
  only ABR interface: the **ABN Lookup web services are free** (register for a GUID at
  `abr.business.gov.au/Tools/WebServices`) and expose `SearchByRegistrationEvent` and
  `SearchByUpdateEvent`, which could be polled daily and would give lower latency than a weekly
  file. They are excluded from v1 for three reasons, not because they don't exist: the filter
  methods return bare ABN lists that must then be hydrated one `SearchByABN` call at a time, so
  enumerating a postcode costs thousands of calls; the service publishes no rate limit but the
  Web Services Agreement reserves the right to suspend access, so throughput is revocable rather
  than guaranteed; and the weekly snapshot is required anyway, because it is the only way to
  detect closures (the API has no "what changed" primitive that survives backdating). **Revisit
  in v1.1** as a latency reducer on top of the snapshot spine, not as a replacement for it.

---

## Constraints

- **Source cadence:** ABR weekly, landing Wednesday ~08:33 Australian eastern time (the UTC
  instant shifts with daylight saving — see the fact table); QBCC irregular (16 weeks stale at
  writing). Both are event-driven off `last_modified`, never scheduled to a weekday or a clock time.
- **Data volume:** 994.5 MB compressed, 12.61 GB uncompressed, ~20.5M ABR records per run;
  76.3 MB / 196k rows for QBCC.
- **Stack:** Python 3.11+; DuckDB + Parquet for snapshots and diffs; PostgreSQL 16 for
  compliance and outcome tables, with `endpoint_value` encrypted using `pgcrypto` and the key
  supplied by environment variable; `cron` + `systemd` for orchestration. No Airflow, Prefect or
  n8n — a one-developer team must be able to SSH in and run the exact command cron runs.
- **Host:** a small VPS (4 vCPU / 8 GB / ~75–80 GB NVMe) in an **Australian region**. The price
  band is **vendor-specific, not a market rate, and the vendor must be named**: verified Sept 2026
  from providers' own AU pricing, OVHcloud VPS-2 in the **SYD** datacentre (4 vCore / 8 GB /
  75 GB NVMe) renews at **~A$14/month ex GST**, while every other provider with a real Australian
  region is 2.8–4.8× that — Binary Lane ~A$39, Vultr Sydney ~A$56, DigitalOcean SYD1 and
  Akamai/Linode Sydney ~A$67. **Hetzner has no Australian region at all**, so its headline pricing
  is not available to this project. Budget **A$14/month on OVHcloud SYD, or ~A$40–67/month on any
  other AU provider** — an earlier draft quoted the single cheapest vendor as if it were the
  market band.
  Add object storage in an Australian region for snapshots and page captures. **The local disk
  holds only the working set** — the two ZIPs (~1 GB), the current and prior snapshots, and
  Postgres — with a pre-run free-space check that aborts below 25 GB; 75 GB satisfies this. The
  24-month snapshot archive (R31a) lives in object storage, ESTIMATED at 300–500 MB per weekly
  snapshot ⇒ ~40–60 GB over 24 months. **Verified AU-region storage pricing for that volume:
  OVH Object Storage `ap-southeast-syd` ~A$0.61/month with no egress fees, AWS S3
  `ap-southeast-2` ~A$2.09/month — so the ~A$1–3/month estimate holds.** Note that the two
  obvious cheap alternatives are disqualified by this spec's own AU-residency rule:
  **Cloudflare R2's Oceania location is a best-effort hint with no AU jurisdictional guarantee,
  and Backblaze B2 has no AU region.** Measure the first snapshot and replace the size estimate.
- **Estimated running cost:** infrastructure **~A$15/month on OVHcloud SYD (A$14 VPS + A$0.61
  storage), or ~A$41–69/month on any other AU provider** — an earlier draft said "~A$20–35/month",
  which reconciled with neither the component lines above nor any single vendor. Enrichment
  ~US$5–8 per 1,000 records [SERP verified at ~US$1 per 1,000 (the earlier US$2–3 estimate was
  conservative), verification verified at ~US$3.70 per 1,000; both vendor list prices, to be
  confirmed at signup]. DNC access is a **published statutory annual subscription fee set by
  volume tier, not per-tranche pricing** (see R25) — expect a low-hundreds-of-dollars annual
  figure at this volume; confirm the tier before the first call.
  With the QLD/northern-NSW filter and an ESTIMATED 200–600 enriched records per week, enrichment
  alone is **~A$6–10/month at 200/wk and ~A$18–29/month at 600/wk**. All-in monthly cost therefore
  depends almost entirely on the hosting choice, not on enrichment volume:
  **~A$21–44/month on OVHcloud SYD, or ~A$47–98/month on any other AU provider**, excluding DNC
  access. (An earlier draft gave a flat A$28–74/month against the superseded A$20–35 infra line.)
  **The R20 cap of A$150/month is a cap on enrichment spend specifically**, so against A$6–29/month
  of actual enrichment it carries roughly 5–25× headroom — a safety ceiling, not a budget. Note
  that hosting is the dominant term at every volume in this range, which is worth knowing before
  optimising enrichment. Volume is measured in week 1 and the estimate replaced.
- **Attribution:** CC BY 3.0 AU (ABR) and CC BY 4.0 (QBCC) require attribution and a licence
  link wherever the data is published or shown to a client.
- **Team:** built once by the developer, operated by the lead-gen VA. Operator burden under
  2 hours per week, all of it working leads rather than running the pipeline.
- **Handover quality:** one repo, one README, one command runs the whole pipeline.

---

## Edge cases to handle

**Source and ingest**
- No new publication → `last_modified` unchanged; log, exit 0, no alarm. Alarm only after 10 days.
- Part 1 and Part 2 published on different dates → do not process; wait; alarm past 48 hours.
  A mixed-date diff manufactures phantom entries and exits.
- Off-cycle republish → treated as a normal trigger keyed on `last_modified`; the diff against
  the last processed snapshot remains correct and the run is a near-no-op.
- Download truncated → range-resume, verify byte length against CKAN `size`, 5 retries, then
  fail. Never parse a short file.
- Parsed count ≠ declared `RecordCount` → fail, write no snapshot, alarm. Exact test, not heuristic.
- Member count changes (the imminent re-partition) → alarm, continue. Diffing is keyed on ABN
  across the whole set, so a re-partition is harmless. Caching ABN→member is prohibited.
- XML serialisation changes (attribute order, whitespace, self-closing `<GST/>`) → the record
  count assertion does **not** catch these: a field-level parse failure still yields the right
  number of records, each silently missing a field. Add **field-fill canaries**: assert that the
  non-null rate of `entity_type_text`, `state`, `gst_status` and `main_name`/`legal_family_name`
  is within 2 percentage points of the prior snapshot, and fail the run otherwise.
- QBCC file read as UTF-8 → garbage. Decode UTF-16LE, and assert the BOM before parsing.
- QBCC file unchanged for months → expected. Log and skip; never alarm on QBCC staleness alone.
- QBCC licence with 32 rows → collapse to one record per Licence Number; retain all class types
  in a list column.
- QBCC record with no ABN (45.5% of rows) → retained for the ICP list, keyed on Licence Number;
  cannot be joined to ABR; enriched on name + street address instead.

**Data quality**
- Backdated `ABNStatusFromDate` → never used for cancellation recency; snapshot diff only.
- Future-dated `ABNStatusFromDate` → retained, `date_in_future = true`, excluded from
  "new this week" counts.
- ABN reactivated after cancellation → `abn_reactivated`, not `abn_new`; removed from
  suppression only after human review.
- Empty `state` or `postcode` (~0.2%) → nullable; reported as `UNKNOWN`; still enrichable.
- An ABN with 300+ `OtherEntity` nodes → all names retained; classification reads all of them;
  the worklist shows the first three plus a count.
- Sole trader with only a legal name → `Unclassified`, tier C, never enriched. ~73% of new
  ABNs. A data ceiling, not a bug.
- `ASICNumberType` is always `"undetermined"` → treat as an opaque 9-digit identifier; never
  assume it is an ACN.
- Run produces zero events on a non-baseline run → alarm, not success. A real weekly diff of
  20.5M records always produces thousands.
- Baseline run produces zero events → expected; R37's volume alarms are suppressed.

**Enrichment**
- Website found, contact form only → record `website_url` and `contact_form_url`; the lead still
  qualifies on phone.
- Email found, verification returns catch-all/unknown → not sendable; stored with status; falls
  back to phone.
- Page carries "no unsolicited marketing" → `limb_d` fails, `record_level_pass` false, email channel
  suppressed permanently and the endpoint added to `suppression`.
- `robots.txt` disallows the contact page → do not fetch; record `robots_txt_compliant`; proceed
  with what was lawfully collected.
- Target returns 403/429 or is bot-protected → back off, retry once, abandon web enrichment for
  that record, log it. **Never use residential proxies or evasion to defeat a block.**
- Only a directory listing is found, no own domain → `limb_c` fails automatically; the email is
  not sendable; the phone may still be used after washing.
- SERP or verification quota exhausted mid-run → stop enriching, complete the run, report the
  un-enriched count, queue for next week. Never silently truncate.
- Spend cap reached mid-run → same handling, plus an alarm.
- Business already enriched within 90 days → skipped, not re-billed.

**Delivery and outcomes**
- More than 60 qualifying leads → top 60 by `lead_score_final`; the remainder carry over and are
  re-ranked next week; the carry-over count is reported.
- Duplicate contact already in GoHighLevel → upsert on the location's duplicate rules; never
  create a second record; log upsert-vs-create per contact.
- GoHighLevel 429 → honour the rate-limit headers, back off, resume; remaining contacts carry to
  the next run rather than being dropped.
- CRM push half-completes → the manifest records attempted vs succeeded; the next run retries
  only the failures, keyed on ABN.
- VA edits a worklist status to a value outside the closed vocabulary → rejected by sheet
  validation; the read-back logs and skips the row rather than writing a junk status.
- Business unsubscribes → suppression by `endpoint_hash`, global, immediate, permanent.
- Business cancels its ABN after being enriched → `abn_cancelled` suppresses it and flags any
  open CRM opportunity for review.
- Two runs overlap → a lockfile prevents concurrency; the second exits immediately with a log.

---

## Definition of done

**Sequencing.** Most diff acceptance cannot run in build week, because a diff needs two snapshots
and there is no backfill. Acceptance is therefore staged: **Phase 0** items and every
fixture-based item pass in week 1; the **first real diff** items pass in week 2; the **commercial
validation** items at weeks 4 and 8. Items below are tagged where the timing is not obvious.

**Ingest and diff**
- [ ] A run triggered by a real `last_modified` change downloads both ZIPs, parses every member,
      and writes a Parquet snapshot, with peak RSS measured under 2 GB by the run manifest.
- [ ] `parsed_count == declared RecordCount` asserted per member; a deliberately truncated
      fixture fails the run and writes no snapshot.
- [ ] A fixture with a different member count completes successfully and raises exactly one
      `member_count_changed` alarm.
- [ ] Two consecutive real snapshots diff in under 60 seconds and produce an `events` table
      containing at least one each of `abn_new`, `abn_cancelled` and `gst_registered`.
- [ ] A synthetic fixture pair proves an ABN going `CAN → ACT` emits `abn_reactivated` and not
      `abn_new`.
- [ ] A synthetic fixture pair proves one ABN can emit two event types in one run, with both
      rows present under the composite primary key.
- [ ] A fixture with mismatched Part 1 / Part 2 dates is refused by the trigger.
- [ ] A first run with no prior snapshot exits 0, emits zero events, sets
      `baseline_established: true`, and raises no volume alarm.

**Classify and qualify**
- [ ] Every `businesses` row carries entity type, `entity_class`, industry,
      `industry_confidence`, `industry_matched_on` and `created_month`.
- [ ] The report shows counts by industry × entity type × state × creation month, with
      new-this-week and closed-this-week separately visible.
- [ ] The unclassified rate is written to the manifest each run, and a fixture whose rate moves
      more than 3 points week-over-week raises exactly one alarm.
- [ ] **Industry precision:** two reviewers independently label a fixed 50-record sample of
      `high`-confidence classifications against the written rule "the matched name states this
      service"; inter-reviewer disagreements are adjudicated by a third; **precision ≥ 90%**
      (≤5 false positives). Every false positive found is fixed in `TRADE_RULES` and the sample
      is re-run. The labelled sample is committed to `tests/fixtures/` so the check is repeatable.
- [ ] Changing a threshold in the rules YAML changes tier assignment on the next run with no
      code change, and the manifest records the rules version.
- [ ] Given a fixed fixture, `lead_score` is byte-identical across two runs (deterministic
      ordering, including tie-breaks).
- [ ] **[Phase 0, week 1]** The QBCC ingest decodes UTF-16LE (asserting the BOM), collapses rows
      to one record per Licence Number, and emits the Category 1–2 ICP backlog. Against the
      18 May 2026 file the expected figures are 196,116 rows → 108,536 licences → 11,080 Cat 1–2;
      **the test asserts the collapse and filter logic against a committed fixture, not these
      absolute counts**, so it does not break when QBCC republishes.

**Enrich**
- [ ] Enrichment runs only on tiers A and B; a test asserts zero outbound HTTP calls attributable
      to a tier C record.
- [ ] The stop condition behaves as R22 specifies — proven by three fixtures: no own-domain site
      found halts after stage 1; a site yielding a phone and no email halts after stage 2; a site
      yielding an email always runs stage 3.
- [ ] Per-record ceilings (3 SERP queries, 6 page fetches, 1 verification) are enforced — proven
      by a fixture that would exceed each.
- [ ] A record enriched within 90 days is skipped on the next run, proven by asserting zero
      outbound calls for it.
- [ ] `robots.txt` is honoured — a fixture site disallowing `/contact` is not fetched, **and a
      second fixture using wildcard rules (`Disallow: /*/contact` and `Disallow: /*.php$`) is also
      not fetched.** The literal-prefix case alone passes even with a parser that ignores
      wildcards, so on its own it does not test what it appears to test.
- [ ] Crawl rate does not exceed 1 request per second per domain, asserted from request
      timestamps in the run log.
- [ ] `grep -ri "places\|maps.googleapis" src/` returns no call sites.
- [ ] The spend cap halts enrichment and alarms — proven by setting the cap to zero.
- [ ] Measured hit rates are reported **separately for tier A and tier B**, over records where
      enrichment was attempted, and stored in the manifest for trending. ESTIMATED bands to
      compare against: tier B (new ABNs) website 15–25%, verified email 12–20%, phone 35–55%;
      tier A (established businesses) materially higher — **no band is asserted for tier A; the
      first four runs set it.**

**Compliance**
- [ ] A query for contact endpoints with no `collection_provenance` row returns zero rows, and a
      NOT NULL foreign key makes the orphan state unrepresentable.
- [ ] Every `spam_act_basis` row has all **four** record-level limb booleans populated (limb e
      lives in `send_eligibility` by design); a row with a null limb is rejected by NOT NULL.
- [ ] **A fully compliant record actually exports.** A fixture lead passing limbs a–d, with a
      verified-deliverable email, no suppression and no `do_not_market` row, appears in the
      worklist marked `email_sendable_pending_relevance`. **Without this test a gate that exports
      nothing at all would pass every other item in this section** — which is the exact failure
      mode a fail-closed design invites.
- [ ] A fully compliant phone endpoint with a wash inside 30 days exports as callable.
- [ ] **An otherwise-compliant email endpoint whose `spam_act_basis.expires_at` has passed is
      refused by the export gate** — proven by a fixture. `record_level_pass` still reads `true`
      in that state, so this test is the only thing standing between R25's 90-day rule and it
      being decorative.
- [ ] The full DDL in §Data model executes top-to-bottom on a clean PostgreSQL 16 instance with
      zero errors, asserted in CI against a real database — not reviewed by eye.
- [ ] The export step emits zero email endpoints where `record_level_pass = false`, and zero phone
      endpoints lacking a `dnc_wash` row with `result='clear'` inside 30 days — each proven by a
      fixture that would otherwise be exported.
- [ ] An email harvested from a third-party directory has `limb_c = false` and is not exported —
      proven by fixture.
- [ ] An override row without `override_reason` is rejected by a database constraint.
- [ ] A suppression added for one `endpoint_hash` blocks that endpoint across every entity and
      channel on the next run, and prevents re-enrichment.
- [ ] Every exported message carries a non-null s 17 sender block and s 18 unsubscribe link, and
      first-contact exports carry the APP 5 notice — asserted by a template test that fails on a
      missing field.
- [ ] The worklist shows a calling window for each lead in the recipient's time zone, and no lead
      is presented as callable on a Sunday — proven by a fixture across all Australian time zones.
- [ ] **Evidence drill:** 10 randomly selected enriched records are each reconstructed in under
      15 minutes — source URL, page snapshot, collection timestamp and method, all five limbs,
      wash receipt, suppression state — recorded as a dated, signed-off checklist committed to
      the repo. Median reconstruction time is recorded.
- [ ] A written residency note records where snapshots and Postgres live, enumerates every
      overseas recipient in the R33 table with its country, and states the s 16C position.
- [ ] A written APP 3 necessity note records the R31a position, the snapshot retention schedule,
      and whether the hashed-index fallback was adopted. Snapshot storage is access-controlled
      separately from the lead tables — proven by showing the lead-pipeline credentials cannot
      read the snapshot bucket.

**Delivery and operations**
- [ ] The worklist is capped at 60 rows; a fixture producing 200 qualifying leads carries 140
      forward and reports the carry-over count.
- [ ] **[week 2+]** The VA completes a full weekly worklist in under 2 hours of *worked* time,
      measured across 2 consecutive weeks. Instrument: an Apps Script `onEdit` handler appends
      `{row, column, timestamp}` to an activity sheet; worked time is the sum of gaps under 15
      minutes between consecutive edits. (First-to-last-edit elapsed time measures the calendar,
      not the work, and would pass or fail for the wrong reasons.)
- [ ] Write-back is read into `outcomes` at the start of the next run; a status outside the
      closed vocabulary is logged and skipped, not written.
- [ ] Tier A leads appear in GoHighLevel with every field in the R35 mapping populated and every
      R35 tag applied, with no duplicate created — verified against a location with duplicate
      detection enabled, and asserted by a test against the mapping table.
- [ ] `run_manifest.json` contains every field listed in R36.
- [ ] Each alarm in R37 is fired once by a fixture and delivered to the configured email address
      and healthcheck endpoint.
- [ ] A single documented command runs the full pipeline end to end on a clean machine.
- [ ] The README lists every required environment variable, and the repo contains no credentials
      (asserted by a secret-scanning check in CI).
- [ ] The runbook covers all five scenarios in R38.
- [ ] The developer, given only the repo, completes a full cycle unaided.
- [ ] READMEs and any client-facing output carry the CC BY 3.0 AU and CC BY 4.0 attributions.

**Commercial validation — the gate that matters**
- [ ] Before build, a one-hour count is run against an existing snapshot: ABNs whose
      `gst_status_from_date` falls in the last 7 days, broken down by ABN age band and state.
      This replaces the unsourced tier A volume estimate with a measured figure and confirms the
      cost model before a line of pipeline code is written.
- [ ] After 4 weeks, actual weekly tier A and tier B volumes are recorded against the estimates.
- [ ] After 8 weeks of VA outreach, `outcomes` yields contact rate, meeting-booked rate,
      meeting-held rate and cost per booked meeting **per tier**.
- [ ] **Pre-committed decision:** if tier B (the literal new-ABN brief) has produced no booked
      meeting by week 8 while tier A has, tier B enrichment is switched off in the rules YAML and
      the spend moves to tier A. Recorded here so it does not need to be argued later.

---

## Open questions

1. **CRM destination.** This spec assumes tier A auto-pushes to GoHighLevel and tier B goes to a
   human-reviewed worklist. If the CRM must stay clean until a human approves every record, R34
   becomes worklist-only — a one-line change.
2. **DNC washing access tier and lead time.** *(Largely settled in v3.5 — this is no longer the
   channel-blocker the earlier draft described.)* R25 requires a wash receipt before any call.
   Verified: access is a **published statutory cost-recovery fee table with tiers set by annual
   wash volume**; there is no ACMA accreditation of washing providers and no negotiated tranche
   pricing. At this pipeline's volume the applicable tier is a low-hundreds-of-dollars annual
   subscription. **Two things remain genuinely open:** whether automated access (SFTP/SOAP), as
   opposed to manual web upload, forces a materially higher tier; and the account lead time. Both
   must be confirmed before the first call and added to the cost model.
3. **Legal sign-off.** §F reflects careful research, not legal advice. The clause 4(2) limb
   tests, the APP 5 notice wording, and the ACL unsolicited-consumer-agreement handling should
   be reviewed by an Australian lawyer before the first send.

---

## Appendix — why the qualification rules are ordered the way they are

The brief asks for newly created businesses. That is built, in full, as tiers B and C. The
ordering puts a different event first, for reasons worth recording:

| | New ABN | GST flip on a 12–60 month old ABN | QBCC Cat 1–2 licensee |
|---|---|---|---|
| Cost of the signal to the business | Free, ~10 minutes | Crossing $75k turnover | Fees, experience proof, net-tangible-asset test |
| Has revenue | No | Yes, >$75k | Yes, $800k–$12m, regulator-verified |
| Published email, so lawful contact exists | Rarely | Usually | Usually |
| Website to critique in the opener | Rarely | Usually | Usually |
| Street address available | No (state + postcode) | No | **Yes** |
| Competing for the moment | Lawpath, EasyCompanies and every accountant — mid-transaction, with consent | Nobody | Nobody |
| Volume | ~26,000/week ESTIMATE | ~5,000–6,000/week ESTIMATE, unverified — measure it | **11,080 total, VERIFIED** |

Roughly 67% of non-cancelled ABNs are not actively trading — ABS *Counts of Australian
Businesses* methodology, June 2025: of ~8.9m non-cancelled ABNs, roughly 6.0m are excluded as not
actively trading, leaving ~2.7–2.9m in scope. [The published figures come from successive
exclusion steps and do not form a clean two-way partition — **do not present them as one
subtraction.** Re-derive from the ABS methodology page before quoting exact numbers to a client.] Three-year survival for
non-employing businesses is 43.3% versus 61% for employing businesses [VERIFIED, ABS CABEE
latest release]. And ABN registration is a free form, not a purchase. A new
ABN is a registration signal wearing the costume of a buying signal.

The QBCC Category 1–2 list is the strongest asset here and the only one whose size is measured
rather than estimated: 11,080 building contractors with an approved revenue band of $800k–$12m
and a street address, free, available on day one, and matching Maintain Media's stated ICP more
closely than anything the ABR can produce. It does not depend on the diff engine ever running.

The strongest signal of all — a job ad for a coordinator, scheduler or admin — is out of scope
because SEEK's terms prohibit automated harvesting. It stays a VA-operated manual play.

Volume figures marked ESTIMATE derive from published ABS, ASIC and Lawpath aggregates. The
tier A figure is the one the cost model depends on and is the first thing measured (see
Definition of done, Commercial validation).

---

*Source data: Australian Business Register ABN Bulk Extract, © Commonwealth of Australia,
licensed CC BY 3.0 AU (https://creativecommons.org/licenses/by/3.0/au/). QBCC Licensed
Contractors Register, © State of Queensland, licensed CC BY 4.0
(https://creativecommons.org/licenses/by/4.0/).*
