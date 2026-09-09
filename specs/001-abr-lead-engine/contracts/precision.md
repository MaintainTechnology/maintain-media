# Build Contract Precision — ABR Lead Engine v4.0

This supplement makes existing R2/R3/R7/R9/R16–R26/R29/R36 contracts implementable.
It does not enable a live adapter or introduce a new product feature. It is normative alongside
[interfaces.md](interfaces.md) and [data-model.md](../data-model.md).

## Publication inventory and source mapping — R2/R3/R6/R8, T035–T039

Normalised source manifest fields are defined by this application, not represented as literal
publisher XML fields:

The official XSD checked on 2026-09-08 defines `/Transfer/TransferInfo/FileSequenceNumber`
(integer), `/Transfer/TransferInfo/RecordCount` (integer), and
`/Transfer/TransferInfo/ExtractTime` (dateTime), plus required `/Transfer/@error` (string).
[Official XSD](https://data.gov.au/data/dataset/5bd7fcab-e315-42cb-8daf-50b7efc2027e/resource/f3f8f8a1-590c-4d87-8285-806b093c2c69/download/bulkextract.xsd).
It supplies no generation UUID, total-member count or cross-part checksum. The
[publisher README](https://data.gov.au/data/dataset/5bd7fcab-e315-42cb-8daf-50b7efc2027e/resource/3b975e4f-af2f-4de7-a20e-6dcb3f67805c/download/abnlookupbulkextractreadme.pdf)
does not establish ExtractTime as a unique cross-part publication token. Preserve its raw
lexical value/timezone; do not invent an offset when absent. Sequence coverage and accepted
header relationships must be in the approved mapping, which must not hard-code the historical
20-member example. Require success/error values backed by the source fixture; unknown values hold.
Same-day partial corrections that cannot be grouped from evidence remain held. This is an explicit
live-source acceptance dependency, not a claim that metadata proximity proves completeness.

```json
{
  "manifest_version": 1,
  "source": "abr",
  "dataset_id": "publisher identifier",
  "mapping_version": "approved source-schema mapping digest",
  "discovered_at": "UTC timestamp",
  "resource_inventory_digest": "sha256",
  "resources": [{
    "resource_id": "publisher resource identifier",
    "resource_url": "https://...",
    "part_label": "label resolved by the approved mapping",
    "last_modified": "UTC timestamp or null",
    "etag": "validator or null",
    "declared_size": 123,
    "download_sha256": "sha256",
    "members": [{
      "name": "publisher member name",
      "content_sha256": "sha256",
      "crc32": "hex",
      "schema_version": "mapped value",
      "declared_record_count": 123,
      "generation_evidence": {"field_paths": [], "values": [], "effective_date": "date or null"},
      "first_abn": "11 digits",
      "last_abn": "11 digits"
    }]
  }],
  "coherence": "pending",
  "coherence_reason_codes": [],
  "snapshot_id": "uuid",
  "expected_previous_snapshot_id": "uuid or null"
}
```

The production source adapter MUST use a versioned, approved `source_mapping.json` containing
exact namespace-aware publisher XPath/attribute mappings, expected schema signature, resource
selection predicate, required part labels and accepted generation-equality rules. The mapping
and official sample/XSD fixture are G2 evidence, not guessed from prose or an assumed field
named GenerationId. A missing generation field is stored null and cannot satisfy an equality
test by comparing null to null. No trusted mapping means `SOURCE_MAPPING_UNAPPROVED` and hold.
Fixture mappings are fully explicit and may run independently of a live mapping.

Inventory equality compares resource IDs/part labels before and after transfer; verify every
selected part exactly once, member uniqueness, mapped generation consistency across all members,
record totals, no duplicate ABNs, and schema signatures. Content hash alone proves integrity,
not that two independent halves belong together. Where the publisher exposes no sufficient
generation evidence, fail with `GENERATION_UNPROVABLE`; an operator can investigate/obtain an
approved adapter mapping from publisher evidence but cannot waive validation to force promotion.
An ordinary operator acknowledgement is never a substitute for missing source facts.

Content identity hashes exactly this projection: `{"identity_version":1,"parts":[{"part_label":<stable mapped label>,"members":[{"member_label":<stable mapped member label>,"uncompressed_sha256":<SHA256 of complete uncompressed member bytes>}]}]}`.
Sort parts by part_label and members by member_label using UTF-8 byte order; reject duplicate labels.
Serialize UTF-8 JSON with those exact field names/order, no insignificant whitespace, and standard
JSON escaping. SHA-256 that serialized projection. Exclude resource URL/ID, retrieval time,
validators, download_sha256, ZIP CRC/compression/metadata, byte lengths and run/snapshot UUIDs.
The complete manifest retains those excluded values as integrity/retrieval evidence. Recompressing
identical member bytes under unchanged mapped labels is therefore the same identity.
Retrieval time, URL validators and physical ZIP compression are evidence, not business-event fields.
Record fields get their own versioned semantic hash. Changed layout/member partitioning may create
a new snapshot identity but zero business events; identical normalised records produce no leads.
Byte-identical inventory is a no-op only against the CURRENT accepted cursor content under the
same parser/schema contract, never against all historical content. Separate deduplicated source_content
from publication-occurrence source_snapshot UUID. A-to-B-to-A with fresh verified publisher evidence
creates a new occurrence UUID and B-to-A events, optionally reusing retained verified artifact bytes.
Persistent occurrence/run IDs and expected cursor version bind retries; an old cached artifact is
not a new source observation. Changed member content with the same effective date creates a
new snapshot UUID and normal whole-set comparison. A first snapshot/rebaseline creates zero ABR events.

Required named fixtures: `abr_baseline`, `abr_changed`, `abr_same_date_correction`,
`abr_identical_republish`, `abr_repartition_semantic_noop`, `abr_mixed_generation`,
`abr_missing_generation`, `abr_inventory_changes_during_download`, `abr_a_b_a_then_retry`.
The recurrence fixture accepts A1 baseline, B2 change and evidenced A3 recurrence (A3 UUID differs
from A1, content_id may match); B-to-A events appear once, retry of A3 adds none, and a subsequent
poll identical to current A3 is a no-op. Cached A1 replay without fresh source evidence holds.
Each has explicit expected
source pointer, content IDs, event counts and whether promotion is permitted. No fixed20-member
assumption or production data count is baked into fixtures.

## Staging ownership and cleanup — R7, T036–T039/T053

`artifact_manifest` fields: artifact_id UUID PK, run_id FK, source, snapshot_id FK nullable,
object_key UNIQUE, content_digest, byte_count, created_at, verified_at nullable,
state(writing/verified/referenced/orphan/deleting/deleted), deletion_reason nullable.
Object keys begin `staging/<source>/<run_id>/` or immutable accepted snapshot prefix.
The writer creates the manifest row before uploading. Storage tagging repeats run/source/artifact ID;
it is cross-checked but never trusted in place of the database manifest.

A cleanup worker selects only artifacts older than seven days with no committed snapshot/evidence
reference, no active run lease and matching recorded prefix/digest/ownership. It obtains the run
lock and rechecks references in a transaction, marks deleting, deletes exactly that key, and records
the deletion result. Not-found is idempotent success. Referenced objects are governed by retention,
not staging cleanup. Unknown/orphan keys are quarantined/reported; never recursively delete a prefix
based on an untrusted input path. A racing promotion cannot use a deleting artifact.

## DNS and connect contract — R17, T018/T020

The resolver returns all A/AAAA addresses. Reject the target if any candidate is non-public,
ambiguous, IPv4-mapped-private, loopback, link-local, multicast, unspecified or reserved by the
approved IP policy. Select one allowed address and connect directly to that address without a
second implicit DNS resolution. Keep the original validated hostname for HTTP Host and TLS SNI;
verify TLS certificate against that hostname and verify the connected peer matches the selected
allowed address. Do not disable certificate validation to implement pinning.

Every redirect repeats URL/hostname/IP resolution/pinning/peer checks and consumes redirect/request
budgets. Disable proxy environment inheritance. No generic HTTP client retry may bypass this transport.
Outbound firewall rules additionally deny internal/metadata networks. Test DNS response changes
between resolution and connect, changed peer, IPv6/private-mapped variants, redirect-to-metadata,
mixed public/private answers and certificate mismatch. No blocked destination reaches the socket.

## Rule recovery decision — R9, T004/T040/T041

Record `decision_id`, `status(recovered/replacement_approved/pending)`, source_uri/path,
source_sha256, retrieved_at, rule_file_digest, rule_count, ordered_rule_ids, mapping_version,
reviewer, owner_approved_at, reason, differences_from_legacy_claim and fixture_suite_digest.
Recovered status must account for all30 claimed legacy rules. A replacement is explicitly labelled
a replacement and needs an owner-approved version change; it cannot pretend to be the original.
Synthetic minimum suite covers BN before main before TRD, OTN exclusion, within-type sorting,
overlapping rules/first match, case/space/punctuation handling, multi-name matches and no-match.
Missing production decision yields `CLASSIFIER_DISABLED`; no live ABR lead classification begins.
QBCC-only pilot does not require fabricated ABR rules. T001 creates all proposed `abr_engine/` paths;
none is asserted to exist or be tested in this documentation package.

## Relevance evidence and coherent current reads — R21/R24, T023/T028/T031

Email-only `relevance_assessment`: assessment_id UUID, contact_id/channel(email), campaign_id, template_id,
content_digest SHA-256, policy_version, actor_id, state(pass/fail/unknown), reason text (1–2000 chars),
role_evidence_id, assessed_at, expires_at, assessment_seq monotonic. Expiry is the earliest of
24 hours after assessment, basis expiry, identity expiry, policy expiry or explicit withdrawal.
Any content/campaign/endpoint change requires a new record; match by exact digests/IDs, never by
friendly template name. Only trained reviewer scope can record pass. Unknown/fail denies consumption.

Email `action_intent` references the exact stored reviewer relevance assessment; caller-supplied
boolean/actor assertions cannot create a pass. `POST /relevance-assessments` is the reviewer-only
creation route in interfaces.md; action creation supplies relevance_assessment_id. Phone intents
instead reference current approved calling/script policy and latest wash; no email basis or relevance
assessment is required for phone. Every intent carries expected applicable contact, identity,
basis(email only), policy and suppression revisions. At consumption acquire group UUID then endpoint locks,
read the latest committed current pointers and latest applicable wash, use database transaction time,
and require every version/predicate still current. The update to consumed and final decision snapshot
is one transaction. Relevance pending/expired/changed denies. Intent creation alone never grants contact.
Identity, permission, relevance, wash import, merge and suppression changes obtain the same applicable locks
and invalidate pending intents before commit. An already-dispatched request remains explicitly in-flight.

Named cases: deliverable-but-no-basis denied; wash-clear-but-timezone-unknown denied;
old-pass-new-unknown denied; old-pass-new-withdrawn denied; template-content-changed denied;
forged-caller-relevance denied; valid-phone-without-email-basis allowed;
fully-current-synthetic-candidate allowed; suppression-first denied; consume-first in-flight logged.

## Minimal retained suppression fields — R25/R26/R29, T009/T016/T029/T033/T034

After profile deletion retain only: restriction event ID; reason/status; committed/request time;
minimal source/actor reference; keyed endpoint lookup token and key_version; canonical group UUID;
keyed normalised ABN/licence alias tokens and type/key_version; alias-to-group links; resolution
event links; migration version. Do not retain business names, street addresses, plaintext endpoints,
page content or positioning notes in the suppression ledger. Evidence with an independently recorded
retention purpose lives in the separate restricted evidence store.

All relational restriction, deletion and CRM identity references use `business_group.group_id UUID`.
`lead_source_link` stores active encrypted source identifiers plus HMAC token and is erased with its
marketing profile; `suppression_alias` retains only type/key_version/HMAC token to group UUID links.
The string `canonical_business_key` (`abn:<digits>`/`qbcc:<licence>`) may exist transiently during
normalisation but is never persisted as a key or retained after erasure. Profile deletion must prove
no plaintext ABN/licence alias survives in the restriction tables, logs or external deletion receipts.

Future incoming identifiers are normalised and HMAC-tokenised with active/previous migration keys
before profile creation/enrichment/export. A token match reconstructs the group restriction without
recreating the deleted marketing profile. Only compliance service may query exact matches; only
compliance role may inspect audit reasons. Operators see blocked state, not a browsable stop-list.
Cancellation resolution appends a signed reason-specific event and only resolves that reason;
unsubscribe/complaint and unrelated manual blocks remain effective. Restore must replay these
minimal aliases as well as endpoint tokens before any action is enabled.

Token-only restrictions cannot be migrated by computing HMAC(new_key, old_token): matching requires
the original normalised identifier, which was deliberately erased. Keep each prior key encrypted
in the dedicated key store with suppression-lookup-only access while any retained restriction
depends on it. New writes use the active key; matching incoming identifiers checks all dependent
versions. Only retire/destroy a prior key when zero restrictions depend on it, or all have verified
equivalent matchable replacements under a reviewed migration. Reacquired original identifiers may
produce a replacement token in the ordinary controlled matching path; do not recollect profiles
solely to manufacture key retirement. Compromise freezes affected actions and escalates, never
deletes blocks. Required fixture: erase profile/active plaintext aliases, rotate key, ingest same
identifier, prove old-key lookup still blocks; reject premature key destruction and rehash-of-HMAC.

## Usage cap versus cash authority — R19/R38, T003/T011/T012/T050

The automatic monthly enrichment usage cap is A$150. The automatic procurement cash cap is A$0:
this system has no capability to buy subscriptions, top up balances or commit prepaid credit.
An owner makes any purchase outside the pipeline after reviewing a dated cost record. The record
states gross currency/tax/FX amount, period, vendor, minimum commitment, approved_by/at and receipt.
Configured balances do not imply authority to replenish them. Usage reservations still apply to
prepaid calls, preventing free-looking consumption from evading the usage ceiling.

## Capacity worksheet and admission — R36, T055

Before a production run compute free-space requirement in bytes:
remaining_downloads + staged_parquet_upper_bound + prior_snapshot_bytes + new_snapshot_upper_bound
+ configured_spill_limit + projected_DB_growth + projected_WAL_growth + temporary_backup_bytes
+ 25 GiB safety headroom. Do not double-count a file already subtracted by filesystem free-space;
the worksheet records existing/remaining allocations separately. Unknown upper bounds block the
large production run until a bounded sizing sample establishes them. Pilot synthetic runs use their
own known bounds. Start with a configured spill ceiling, reject a run whose plan exceeds it and
alarm on exhaustion; never grow spill indefinitely to make a benchmark pass.

Measure a representative bounded sample to derive uncompressed-record/Parquet bytes per row and
promoted-row DB/index/WAL bytes; use at least2x measured upper estimate for new artifacts until a
full run establishes a tighter bound. Save sample size, distribution, schema/rule/runtime versions,
observed peak RSS and safety factor in `capacity.json`. Full20.5M synthetic validation includes
wide names, all events and output materialisation. Eight-GiB host capacity remains unproven until
T055 passes; obtain a larger disk/host or revise the scope if the admission formula fails.
