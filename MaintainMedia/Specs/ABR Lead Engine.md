---
title: "ABR Lead Engine"
project: Maintain Media
version: "4.0"
synced: 2026-09-09
source: "specs/abr-lead-engine.md"
source_sha256: f1c9a83385766fd017e4d8b4d8a7c219f08ec7aa39c7990b45195a6f2532ba48
tags: [abr-lead-engine, maintain-media]
---
> Synced from the repository; local document links adapted for Obsidian.
> [[ABR Lead Engine - Build Hub|Open the build hub]]

# ABR Lead Engine (Part 1) — Specification

**Version:** 4.0 · **Revised:** 9 September 2026 · **Owner:** Jon Pepper
**Scoped policy amendments:** QBCC-PILOT-2026-09-11, WEBSITE-PHONE-PILOT-2026-09-11, GHL-DND-PILOT-2026-09-11 and ABR-EARLY-VALIDATION-2026-09-11, each version 1.0.0; delegated-owner authority below. Product and rule baseline v4.0 is unchanged.
**Status:** v4.0 product baseline with scoped live-pilot decisions; exact capability activation and acceptance are recorded separately.
**Purpose of this revision:** make the specification clear, consistent and buildable. This document
does not itself certify application behaviour, capacity or legal approval. Executed build evidence
is recorded in [[ABR Lead Engine - Implementation Status|implementation status]].

## Document authority and revision history

This file is the canonical product and control specification. The Spec Kit feature package is
[[ABR Lead Engine - Product Specification|001-abr-lead-engine]]: product stories, plan, data model, interface
contracts, tasks, checks and review evidence. Its FR-001–FR-043 correspond to R1–R43 here.
Technical detail lives in that package; requirements and policy decisions here take precedence.
Resolve any contradiction before implementation. The Obsidian copy is a generated mirror.
The [[ABR Lead Engine - Build Contract Precision|precision contract]] defines exact source header
fields and live-source evidence limitations, cleanup ownership, DNS pinning, relevance schemas,
minimal suppression aliases, cash authority and capacity formulas for the existing requirements.

The exact previous document is preserved in [[ABR Lead Engine - v3.5 Archive|v3.5 backup]].
Its assertions of verified SQL execution, data counts and benchmark timings are historical claims,
not current evidence. This revision removes unsupported certainty and replaces conflicting rules.
Major corrections: signal meaning, DNCR automation cost, coherent snapshot identity, authoritative
suppression, consent assessment, crawl identity/security, finite retention, durable queue/spend/CRM
state, realistic pilot sequencing, and explicit release evidence.

### Delegated-owner QBCC pilot amendment — 11 September 2026

The user explicitly instructed Business source collection to start without waiting
for Jon and delegated that decision to Codex. Under the constitution's explicit-user
authority, [decision QBCC-PILOT-2026-09-11 v1.0.0](abn-leadgen/ops/acceptance/live-sources/qbcc-pilot-delegated-owner-20260911.json)
authorises **manual QBCC intake and authenticated internal review only**, from
2026-09-10T23:18:20Z until 2026-09-24T23:18:20Z. This is the approving user's
delegated decision, not Jon's signature or a qualified adviser report.

This narrow amendment supersedes the adviser prerequisite in R27/G1 for that scope
and interval. `adviser_status=not_obtained`; Privacy Act applicability, notice
assessment and legal compliance are not certified. It permits the actual 11
publisher fields, including licensee names/business addresses that can identify
individuals, plus state/postcode, classifications and necessary source/review
provenance. The full bounded publication may include non-target rows for validation.
Targeting remains unchanged and the worklist stays capped at 60 businesses/week.
Missing licence status and entity class remain UNKNOWN until genuine evidence.

The permitted architecture is the existing private encrypted AWS Sydney service,
Maintain Technology Vercel Sydney server functions, existing Maintain Media Clerk
identity and authenticated admin `jeph@quotemax.com.au`. Clerk middleware is global;
support/other processing countries and the admin's access country are not fully
verified. This limitation is explicitly accepted for these existing accounts in
this pilot, without claiming Australian-only processing. This scoped R30
disposition does not approve Google, GHL or another recipient. Website contact
collection, ABR, outreach, campaign enrolment and external exports remain off.

G3 for this pilot may accept existing verified Sydney encryption/access controls
and bounded storage checks. Full disaster recovery and independent key-custodian
certification remain unverified and are explicitly deferred for the recoverable
public-source pilot; they are not passed for general production or backups.
Current G2 source/mapping and applicable G7 technical evidence remain separate.
No source coherence, UNKNOWN, suppression or finite-retention control is waived.

Adopt the existing 30-day raw-source and 90-day accepted-snapshot maxima, with
seven-day expiry of unreferenced intake staging. Applicable deletion must be
enabled and verified separately. Show exact QBCC attribution, actual source age
and retrieval provenance. Expiry stops new collection and does not prevent due
deletion. No weekly timer, source acquisition, gate row or full production pass
is created by this document. This amendment leaves historical decisions and
scores unchanged; a wider or renewed scope needs a new attributable decision.

### Delegated-owner website phone pilot amendment — 11 September 2026

The user subsequently explicitly directed website contact collection to proceed
without waiting for Jon and delegated that decision to Codex. This is new authority;
the preceding QBCC-only decision did not approve website contacts. The separate
[WEBSITE-PHONE-PILOT-2026-09-11 v1.0.0 decision](abn-leadgen/ops/acceptance/live-sources/website-phone-pilot-delegated-owner-20260911.json)
limits the requested work to **manual collection of public business phone evidence
from a genuinely reviewed business's own website, for private internal review**.
It co-terminates with collection authority at 2026-09-24T23:18:20Z. Notice readback,
current technical evidence and actual gate/policy installation remain separate
conditions; this specification does not claim they have passed.
The owner record includes the actual public-notice HTTP/content readback at
2026-09-11T00:33:01Z; this does not certify installed engine activation.

Only valid Australian `mobile` and `landline` contact channels are permitted.
Automated email extraction and email-address indexing are excluded. No paid search,
verification, directories, Maps/Places, social-site discovery or bulk website crawl
is authorised. Existing genuine qualification, current licence review less than
30 days old, approved own-domain identity valid for at most 90 days, suppression
and R15 cooldowns still apply. Each manually supplied HTTPS root needs an actual
terms review strictly less than 30 days old and an attributable evidence reference.
Robots permission, a checkbox or failure to detect a prohibition cannot replace
that review. Retain all R17 request, size, public-IP, same-domain, robots and no-bypass
bounds. At most ten new normalised phone contacts may be saved per attempt, each
with atomic provenance; they remain unverified and confer no calling permission.

The user delegates this narrow R27/G1 owner decision; `adviser_status=not_obtained`.
No qualified legal assessment, APP applicability, individual-notice sufficiency or
address-harvesting compliance certification is claimed. Publish the scoped
[business research notice](https://www.maintainmedia.com.au/business-research-notice)
and verify its live contents before admission. It must distinguish QBCC records
from own-website phone evidence, state purpose and finite retention, explain the
existing recipient/access limitations, and provide the existing published source,
privacy and objection contact. The actual registered legal entity/ABN remain
unverified and must not be invented. No individual email, call or form submission
is authorised as a way to deliver the notice. Public business information can
identify individuals; full encrypted page evidence may incidentally include email
addresses or other personal information even though email extraction is disabled.

The decision records the checked [ACMA spam guidance](https://www.acma.gov.au/avoid-sending-spam)
and [OAIC APP 5 guidance](https://www.oaic.gov.au/privacy/australian-privacy-principles/australian-privacy-principles-guidelines/chapter-5-app-5-notification-of-the-collection-of-personal-information).
These inform the conservative phone-only and transparent-notice choices; they do
not certify this implementation. A public notice alone is not proof of individual
awareness. The owner's decision does not grant a website operator's permission or
override site terms, and public listing alone does not establish permission.

The existing AWS Sydney, Vercel Sydney server functions, Clerk and private admin
architecture is accepted separately for this additional phone-evidence scope,
including the previously recorded unknown global/support/admin-access countries.
This does not approve a new vendor or certify Australian-only processing. The
limited G3 disposition requires current private-access/encryption evidence and
explicitly accepts possible loss of manual review if host/key recovery fails.
Full disaster recovery, independent custody and production backups remain unverified;
the earlier public-source-only exception is not silently reused for contact data.

Retention must be extended by a new attributable policy version, preserving the
original QBCC policy. Encrypted pending website requests expire within 24 hours;
ordinary page captures/excerpts within 90 days; unworked profiles within 180 days
of their last qualifying event; unnecessary fields within 30 days of suppression
or disqualification. A crawl does not restart the profile clock. For this pilot,
`settings.retention.retain_selected_evidence=false`: do not create seven-year
selected-evidence archives, and do not extend page retention merely because a
worklist row exists. Scoped, attributable holds and minimum suppression aliases
remain protected. Finite deletion authority ends at 2027-09-10T23:18:20Z and is not
renewed by this amendment; collection expiry does not stop due deletion.

Admission requires own `website_collection` G1/G3/G7 plus current parent
`collection` G1/G2/G3/G7, a current approved policy binding the exact owner-record
hash and the two allowed phone channels, and applicable retention G1/G3/G7 covering
this new evidence. Recheck policy and authority at queued execution, around each
DNS/HTTP operation and before contact commit. Google/GHL data flows, ABR expansion,
email/phone actions, campaigns and external exports remain disabled. Targeting,
rule hashes, historical approvals, scores and task checkboxes are unchanged.

### Delegated-owner GHL DND pilot amendment — 11 September 2026

The user expressly directed enabling a narrow GoHighLevel hand-off without
waiting for Jon and delegated the decision to Codex. The separate
[GHL-DND-PILOT-2026-09-11 v1.0.0 owner record](abn-leadgen/ops/acceptance/live-integration-20260910/ghl-dnd-pilot-delegated-owner-20260911.json)
supplies the R27/G1 and R30 owner disposition for the existing Maintain Media
location `xHZFHMOE476t5CxY9vCG`, effective 2026-09-11T01:38:51Z until
2026-09-24T23:18:20Z. No Jon signature, qualified adviser assessment, account-specific
contract signature, individual's consent or legal-compliance certification is
claimed. The earlier QBCC and website-phone owner records remain immutable and
do not supply this onward disclosure authority by implication.

Only manually approved, selected tier-A worklist records may enter the CRM outbox.
Preserve R21–R24 and R33 checks: current identity, suppression, phone verification,
locality/timezone and genuine clear DNCR evidence less than 30 days old. Approval
binds the current row version and desired projection. Neither vendor activation
nor DND supplies missing eligibility or approves an individual business. Existing
targeting and the weekly group limit are unchanged.

The adapter may disclose one eligible phone plus the mapped business/review
summary, opaque engine identifiers and owned tags. The live account config must
enforce `allowed_channels: [phone]`; global outbound DND stays enabled on every
engine create/update. No email values, raw captures, private evidence excerpts,
full register records, physical addresses or unrelated fields are transferred.
No call, message, campaign/workflow enrolment, AI, enrichment, paid action, Google
Sheet or other vendor hand-off is authorised by this amendment.

The [dated vendor review](abn-leadgen/ops/production/ghl-vendor-review-20260911.md)
records United States storage and United States/India service/support. The owner
accepts these countries for this bounded purpose, together with the explicit
uncertainty about optional routing, further support locations and isolated
provider backup expiry. No Australian-only handling, APP 8 exception or sufficient
APP 5 notification is certified. The [public notice readback](website/acceptance/vercel/ghl-handoff-notice-readback-20260911.json)
verified the limited recipient, countries, retention limits and existing request
contact before this decision. Publication does not prove individual notification.

DND is not workflow isolation. The [actual account contract receipt](abn-leadgen/ops/acceptance/live-integration-20260910/ghl-live-account-contract-20260911.json)
records two expressly synthetic contacts created, checked, cleared and deleted;
six workflows remained Draft with zero enrolments. It verifies field/group lookup,
duplicate rejection without overwrite, delayed-index reconciliation without a
second create, unrelated-tag preservation and DND/field clearing. It is not a
real business hand-off or a maximum provider-index-latency measurement.

The installed adapter must check the complete all-Draft workflow inventory hash
before every mutation and recheck local authority afterwards. Changed, published,
paginated or unverified inventory holds further mutations, including removal,
until a reviewed config/installation/G5 renewal. Preserve the global duplicate
setting; never adopt an endpoint-only match. Reconcile uncertain creates before
retry; an empty index result must not turn a known remote identity into a new
create. The engine cannot revoke an already completed disclosure or prevent every
action of an independently authorised GHL administrator; R24's limitation remains.

Admission requires separately current `crm` G1/G3/G5/G7, the exact enabled account
configuration and installation, and current parent collection/policy checks.
G1 binds this owner record; G5 binds the installation bytes, config hash, actor,
location and seven check receipts. G3/G7 bind the independently reviewed runtime
and technical decision. The existing website-phone policy remains the collection
and retention policy: its source-scope text does not itself approve GHL. No policy
replacement or source expansion follows from this separate CRM purpose decision.

Preserve the 180-day unworked-profile clock, 30-day unnecessary-field limit after
suppression/disqualification, 90-day private page evidence and no seven-year
archive; export never restarts those clocks. Remote removal clears engine-owned
marketing values while preserving minimal group/restriction state and unrelated
customer metadata. GHL backup expiry remains unknown; the engine's 35-day rule
is not a provider-backup promise. New hand-off G1/G7 expires on 24 September;
the separate minimum-removal installation/G3/G5 authority continues until
2027-09-10T23:18:20Z, subject to current controls. This limited G3 disposition
accepts evidenced account/security controls and disclosed architecture, with
independent custody/full restore still unverified and no production-backup pass.

At recording, the owner decision and synthetic account checks are complete;
the new runtime's installation, exact release gates and actual outbox operation
are recorded separately. No individual lead approval, task completion or score
increase follows from this amendment alone.

### Delegated-owner early ABR validation amendment — 11 September 2026

The user separately instructed broader ABR discovery to proceed now without waiting
for Jon and delegated the decision to Codex. [ABR-EARLY-VALIDATION-2026-09-11 v1.0.0](abn-leadgen/ops/acceptance/live-sources/abr-early-validation-delegated-owner-20260911.json)
approves **manual public ABN Lookup bulk collection for private source validation,
an initial complete baseline, later coherent comparison and rule-accuracy review**
from 2026-09-11T02:40:20Z until 2026-09-24T23:18:20Z. This is a new delegated-owner
source-purpose and sequencing decision, not an implied extension of earlier QBCC,
website or CRM approval, Jon's signature, or an adviser assessment.

For this scope, it prospectively supersedes R38/FR-038/G6's requirement to finish
four measured QBCC weeks before genuine ABR source work begins. G6 records the
early-sequencing decision; **it must not say that the four-week pilot, commercial
value, source implementation or matching accuracy has passed**. The measured pilot
and cohort evaluation remain open acceptance work. The constitutional principles
remain unchanged: the user controls this sequence while actual integrity, capacity,
privacy-purpose, suppression and technical evidence remain separately required.

Use only the official public bulk dataset, not government-only ABR Explorer data
or a third-party mirror. The publisher describes weekly XML registration fields;
it supplies no phone/email list or proof of actual trade, revenue, continuing business
activity or contact permission. Its dataset-specific licence is CC BY 3.0 Australia;
retain attribution, source/licence links, modification notice and no endorsement.
The licence does not settle other privacy rights. Current schema, payload and
generation evidence must come from genuine source checks; historical catalogue
timestamps and fixture header fields are not sufficient. Public legal/business
names, ABNs and location fields may identify individuals. Whole-register input is
justified only for coherent validation and comparison; do not turn every baseline
record into a lead or publish the input register.

The initial phase is technically **validation only**. An accepted baseline emits
zero ABR events. Later complete publications may produce private, unqualified change
observations; a partial sample cannot establish a source cursor or a new-business
claim. Shadow name-rule predictions may prepare genuine private review samples,
but cannot create eligible leads, enrichment jobs, worklist rows or vendor exports.
Before operational ABR qualification, complete R9's at least 100 real stratified
classified-record reviews, preserve unresolved outcomes, block affected rules above
10% false positives and bind the computed evidence to source/mapping/rule/reviewer
identities. A declared sample count or the classifier's own answer is not that proof.
Record a separate exact-release admission before enabling operational qualification.
Targets, 30-rule order, tier definitions, suppression and weekly caps are unchanged.

Before source-row acquisition, verify the ABR-specific public research notice and
current scoped `abr` G1/G2/G3/G6/G7 evidence. G2 must explicitly distinguish authentic
source/parser validation from unfinished classifier approval. Measure actual full
input storage, spill and process bounds before admission; never substitute the
existing small QBCC run for whole-register capacity evidence. Preserve R2–R8
coherence, complete inventories, source hashes, atomic baseline/diff and recovery.

The new decision accepts the existing private encrypted Sydney engine/storage,
Vercel Sydney functions and Clerk/admin access with global/support/access-country
limits explicitly unresolved. No adviser or legal/APP certification is claimed.
Full DR and independent recovery custody remain deferred for this recoverable
public-source validation scope; no general G3 or production-backup pass follows.
Raw archives expire within 30 days, analytical snapshots and private accuracy
samples within 90, and abandoned staging within seven. Continue separately admitted
finite deletion until 2027-09-10T23:18:20Z; accepted pointers do not waive expiry.
Preserve existing website phone retention, minimal suppression and no seven-year
archive. No ABR-driven contact extraction, paid enrichment, automatic schedule,
Google/GHL hand-off or outreach is authorised here. Existing separately approved
QBCC/phone/CRM work is unchanged. Source-purpose approval is effective now; actual
notice, implementation, admission and first-run receipts are separate evidence.

## The idea

Find Australian businesses that may be a good fit for Maintain Media's services. Give a human
assistant a small, useful list with evidence about each business and clear restrictions on contact.
A government registration or building licence is a clue to investigate, not proof of a sale,
business revenue, current trading, consent or a need for marketing.

There are two data sources:
- **ABR bulk extract:** a regularly published public business-register snapshot. Compare complete,
  coherent publications to detect changes first observed between them.
- **QBCC contractors register:** a separate building-contractor list. Start with financial
  Categories 1 and 2 as a potential customer-fit proxy. It can be useful as a static list even
  when its publisher has not refreshed it. Show its actual source age.

The ABR bulk field list includes identifiers, names, registration statuses and state/postcode;
it does not supply the contact details needed for outreach. The system may find a likely business
website, confirm its identity, and collect limited contact evidence under approved policy.

**Part 1 does not send email or SMS, make calls, take payment, or build client websites.**
It prepares records, enforces eligibility and suppression controls, records outcomes, and offers
a tightly defined contract for a separately approved sending/calling system.

## People, defaults and decisions

| Topic | Decision for the build |
|---|---|
| Owner | Jon Pepper approves business rules, spend changes and release gates |
| Developer | Builds, operates technical recovery and supplies test evidence |
| Reviewer/VA | Reviews identity and permission evidence, approves individual CRM exports, records outcomes |
| First geography | QLD; NSW only where postcode is 2450–2490 inclusive |
| Weekly list | Up to 60 distinct businesses, with up to 10 places reserved for oldest eligible work |
| Human time | Two hours/week is a pilot hypothesis; measure calls, research and administration, not just sheet edits |
| Enrichment cap | A$150/calendar month, inclusive of configured FX buffer, tax and billable retries |
| CRM | Worklist first; human-approved tier A records only; no automatic campaign enrolment |
| DNCR | Manual web wash and receipt import in the pilot; direct SOAP/SFTP disabled |
| Contact modes | Email candidates and manually reviewed phone candidates; no SMS, social DM or contact-form submissions |
| Unknowns | Unknown identity, permission, current wash, source coherence or action-time gate means blocked |
| Scope of this task | The user's later instruction authorises building and running the v4.0 system in `abn-leadgen/`, with autonomous build/review cycles; live release still requires the gates below |

On 9 September 2026 the user approved the recovered 30 trade categories, the listed
geography, QBCC Categories 1–2 and the 60-business weekly limit as the targeting
direction. The [decision record](abn-leadgen/ops/acceptance/live-sources/targeting-approval-2026-09-09.json)
preserves that scope. Other defaults remain planning decisions; collection/privacy,
vendor, accuracy-review and release approvals are separate.
Any change has an owner, reason, date, version and affected tests in the decision register.
The dated delegated-owner amendment above supplies the later user's collection
decision for its exact scope; the 9 September targeting record remains unchanged.

## Evidence and what the signals mean

| Signal | What it says | What it cannot prove |
|---|---|---|
| New ABN observation | ABN was absent in the previous accepted snapshot and is active now | Business was created last week, has customers, has money, or wants contact |
| GST registration transition | Existing ABN was not GST-active before and is active now | Turnover crossed $75,000; registration can be voluntary or based on expected turnover |
| QBCC Category 1 or 2 | Licence financial category describes permitted revenue capacity | Actual revenue, profitability, current demand or a newly issued licence |
| Website/email found | A page displays a possible business endpoint | Identity match, current ownership, consent or deliverability |
| Email deliverable | Verification service considers delivery plausible | Permission to send |
| DNCR clear | Number did not match the register in a particular wash | Permission for every call or exemption from other obligations |

Official checks and their limits are recorded in [[ABR Lead Engine - Source Checks|source checks]].
ABR publication is described as weekly by the publisher. No exact publication clock time, ZIP
count, record count or permanent absence-of-deletions guarantee is assumed. Prior figures such
as 20.5 million records and 11,080 target licences are sizing hypotheses until reproduced against
a dated source manifest. QBCC category count is recomputed; it is never a required constant.

## Requirements

### Source ingestion and state

**R1 — Scope, actors and release gates.** The system MUST default to synthetic/offline mode with
outbound integrations disabled. Authorised roles are owner, developer, reviewer and operator;
reviewers cannot change policies, credentials or suppression history. Production modes require
the named gates below. A technical build can start with fixtures while gates remain closed.

**R2 — Source evidence.** Every discovery/download records source type, dataset/resource identifier,
URL, retrieval UTC time, publisher timestamps, response validators, content SHA-256, licence
reference, parser version and source-generation evidence in an immutable manifest. A timestamp
alone is not a content identity. Metadata absence is represented explicitly, never invented.

**R3 — Coherent ABR generation.** Poll discovery every six hours. Discover ZIP resources by the
publisher's supported dataset schema, not a fixed number of XML members. Before processing,
establish that all required parts belong to one publication using consistent inner transfer
metadata/date and a recorded part inventory. Re-read metadata after downloading; changes restart
validation. A 48-hour timestamp proximity is not proof of coherence. Hold uncertain or mixed
generations; alarm after 48 hours and escalate after seven days. Operators may retry or quarantine,
but cannot waive completeness/coherence for promotion. An identical content manifest is a no-op
only against the current accepted cursor under the same parser/schema contract. Historical content
recurrence A-to-B-to-A requires fresh source-coherence evidence and a new publication-occurrence
UUID; it may reuse retained verified bytes but must compare B-to-A. Replaying old cached bytes
or retrying an existing run is not evidence of a new publication occurrence.
A same-date content change is a distinct publication.

**R4 — Bounded downloads.** Use HTTPS, explicit connect/read timeouts, five attempts total with
exponential backoff and jitter. Resume only with a matching strong validator using If-Range and
validated Content-Range; restart if a server returns 200 or changes content. Validate length when
provided, ZIP CRC, source hashes and member paths. Reject encrypted, nested or unsafe archives,
unexpected member formats, duplicate members and configured decompression/record size ceilings.
A failure leaves the accepted baseline untouched.

**R5 — Streaming parser.** Parse every XML record with a hardened streaming XML parser; reject
DTDs/external entities, decode ordinary XML entities/character references, tolerate namespaces,
attribute order and empty GST nodes, and clear both processed elements and accumulated siblings.
Validate each declared RecordCount, required fields, unique valid 11-digit ABNs and enum values.
Unknown schema/enums are quarantined with samples; no silent replacement with active status.
Fail on count mismatch or >2 percentage-point required-field fill change against the accepted
baseline, pending explicit source-schema investigation. Process RSS target is at most 2 GiB.
Write bounded batches; no whole-register Python object list.

**R6 — Immutable snapshots.** Store raw and normalised snapshot artifacts under source plus
snapshot UUID/content identity, not just YYYYMMDD. Date is descriptive metadata. Use zstd Parquet,
a versioned column schema and canonical field hashing. Stage writes, verify read-back/schema/
counts/checksums, upload under an immutable key, then mark ready. Partial artifacts have no
accepted pointer. Same-day correction must coexist with its predecessor. Apply R29 retention.

**R7 — Atomic promotion and recovery.** A source has one committed accepted-snapshot pointer.
A run stages events/current state against that pointer. One database transaction commits events,
candidate changes and the new pointer using compare-and-swap against the expected prior pointer.
Use unique run/event keys; a replay of a committed generation adds nothing. Crash before commit
means retry staged work; crash after commit means resume delivery from its durable outbox.
Object upload may precede commit; unreferenced staging is garbage-collected after seven days.
Separate source runs cannot corrupt one another. Single-host process lock plus database stage
lock is required; lease/heartbeat expiry, ownership and lock release are defined in the plan.

**R8 — ABR events and time meaning.** Whole-set comparison keyed by ABN emits abn_new,
abn_cancelled, abn_reactivated, gst_registered, gst_cancelled, name_changed and abn_disappeared.
Identity is source snapshot UUID + ABN + event type. An ABN can have several event types.
GST events require a prior ABN row. New and reactivated are mutually exclusive. A missing ABN
is a quality anomaly and is quarantined from marketing; not assumed cancelled. Baseline emits
zero ABR events. Content identical to the current accepted snapshot is a valid no-op; historical
content recurrence is compared as a new evidenced occurrence. Zero events alone is not a
failure. Cancellation recency comes only from ACT-to-CAN observation, never backdated status dates.
Store observed_at, effective_date and source dates separately. Describe events as first observed
between snapshots, not necessarily occurring that week.

### Classification, qualification and work

**R9 — Deterministic classification and reviewed rules.** Preserve the intended 30 legacy trade
rules only after their exact source is recovered and reviewed. On 9 September 2026,
`deliverables/abr/extract_new_abns.py` was present and all 30 ordered literal rules were
recovered without executing that script. The [review packet](abn-leadgen/ops/acceptance/live-sources/rules-approval-packet.md)
records hashes, behavioural differences and the user's targeting-direction approval.
Production precision review remains pending. Synthetic fixtures enable engineering tests;
production classification stays disabled until
a committed rules file, provenance, ordered regexes and expected-output fixtures are approved.
Evaluate BN names first, then main/legal display name, then TRD; exclude OTN. Within each type
use a sorted unique canonical name list; within a name evaluate rules in committed order.
First match wins. Store literal matched name, rule ID, rule version and confidence.
The early ABR validation amendment permits explicitly unapproved shadow predictions
only for private accuracy review; it does not bypass operational precision approval.
BN yields high heuristic confidence; main/TRD medium; no match Unclassified/none.
These labels measure rule evidence, not actual industry certainty. Spot-check at least 100
stratified classified records at launch and after rule changes; false positives above 10% block
the affected rule pending review. Rule changes do not create source-change events.

**R10 — Tiers.** Tier A: GST registration observed for an active ABN with 12 <= completed months
since its active-status effective date < 60; OR a QBCC Category 1/2 licence backlog/new/category
change candidate. The age proxy is not incorporation or trading age. Tier B: new active ABN,
company/trust, GST-active and classified with high/medium heuristic confidence. Other new ABNs
are tier C, counted only. Cancellation, disappearance, name change, GST cancellation and
reactivation alone never qualify as a fresh lead. Suspended/cancelled/inactive evidence blocks
promotion. No business revenue field is inferred from either signal.

**R11 — Geography and dates.** Enrichment requires QLD or NSW postcode 2450–2490. Unknown/conflicting
geography is held for review, not enriched. Store postcodes as four-character strings. Calculate
completed calendar months against publication effective date with end-of-month clamping;
future effective dates are flagged and excluded from recency/age-based tiering. Do not label
ABN status date as business creation date. Expose its literal meaning and confidence.

**R12 — QBCC.** Poll weekly and use metadata plus content hashes to detect change; stale source
is labelled and reported, not called a new-licence feed. Decode BOM-declared UTF-16LE and validate
expected headers; collapse rows by licence number, sort unique licence classes, and quarantine
conflicting ABN/category/address values rather than choose the first. Normalise and validate ABNs;
missing ABNs are allowed. Parse an exact final state plus four-digit postcode tail, preserving
original address. Recompute categories/counts. First accepted snapshot produces a backlog,
subsequent snapshots produce source changes. Before live action, reviewers must record a current
licence/status identity check no older than 30 days; stale bulk data is discovery evidence only.
No invented licence issue date.

**R13 — Identity and deduplication.** Persistent lead_id is the work identity. Keep explicit
ABN/licence aliases and reviewed merges; no forced ABN on QBCC records. When an ABN is known,
all matching aliases share a business group. At most one group per weekly worklist/CRM record.
Without ABN use licence identity and flag likely name/address/domain/phone duplicates for review;
do not auto-merge on name alone. Merging propagates all suppressions before any export.
A source cancellation blocks its business group. Entity-only blocks remain possible with no endpoint.
Endpoint reuse by unrelated businesses still inherits endpoint-level opt-out.

**R14 — Durable queue and ranking.** Store first_qualified_at, last_qualifying_event, state,
deferred_at, exported_at, worklist_week, attempt counters and rule versions.
States: pending_enrichment, needs_review, ready, exported, deferred, disqualified, suppressed.
Active eligible queue expires eight weeks after first qualification; a genuinely new qualifying
source event may reactivate deferred work, never suppression. Each list selects up to 10 oldest
ready/unworked groups, then fills remaining places by final score, deduplicating both selections.
No more than 60 total. Recheck eligibility immediately before export.
ABR score = A60/B30 + confidence(high15/medium5) + geography10 + company5 +
max(deliverable email20, phone15, website5, none0), capped at100.
QBCC score = A60 + category(Cat2=20,Cat1=15) + Company5 + geography10 + same contact term,
capped at100. Provisional contact term is zero. Scores never substitute for permission.
Use one total order across sources: final_score descending, first_qualified_at ascending,
then lead_id ascending. Provisional enrichment uses the same order with provisional_score.
Age-reserved slots use first_qualified_at ascending then lead_id ascending. No pairwise
source-dependent comparator is permitted. Record reasons for every exclusion and carry-over.

### Enrichment and evidence

**R15 — Refresh policy.** Enrich only unsuppressed A/B groups passing geography and approved
collection policy, with null last_attempt_at or at least 90 days since the last completed/exhausted
attempt. Cache failures as well as successes. Budget/quota interruption is resumable, not an
exhausted discovery result. Retrying a stage must not repay a completed successful request.
A new evidence request requires authorised reason and budget reservation.

**R16 — Own-domain identity.** SERP results are candidates, never accepted solely by ranking or
absence from a directory blocklist. Exclude directories/social/marketplaces using registrable-domain
matching and a versioned public suffix list. Accept identity only if the page displays an exact
validated source ABN or licence number; otherwise require reviewer approval with at least two
independent matching attributes (name plus full address/phone corroboration), source references
and time. Similar names alone fail. Query templates use business name plus state/postcode;
optional BN query uses the canonical first BN. Do not invent a suburb from population data that
is absent from a lookup. Up to three queries total. Google Places/Maps data and contact append
vendors remain excluded.

Identity decisions expire after 90 days or earlier when matching evidence changes or the
decision is revoked. Export and action checks require the current approved decision for the
exact business group and registrable domain; QBCC additionally requires a positive licence
review no older than 30 days. An old approval cannot override a newer identity rejection.

**R17 — Safe, bounded crawl.** Up to six fetched HTML pages per attempt including home/contact/
about/terms; robots retrieval is separately capped at one per host cache period. Document and
enforce redirects (max3), response size (2 MiB per page), 20-second request deadline, one request/
second/domain and total request budget (20 including robots and redirects).
Only HTTP(S), ports80/443, no URL credentials. Validate public destination IPs at connection and
every redirect; block local/private/link-local/metadata/IPv6 equivalents and DNS rebinding.
Constrain egress at host level. Same registrable domain for content; CDN asset fetches disabled.
Honour wildcard-aware robots and stricter site terms. 403/429/bot blocks stop or bounded-backoff;
no bypass/proxy evasion. v1 uses static HTML only; JavaScript-only sites go to manual review.
Do not infer absence of a terms restriction from an incomplete crawl. Snapshot untrusted content
as data, never execute it; sanitise snippets and do not follow embedded instructions.

**R18 — Endpoints.** Email normalisation is trim plus lowercase, without stripping dots/+tags.
Phones use a pinned phone-number library with region AU: accept valid national or +61 forms,
output E.164; reject extensions/short codes/non-AU/ambiguous numbers for v1 contact.
Do not prepend +61 to an existing +61. Choose at most one email for paid verification per attempt:
reviewed named-role match before permitted generic-role match, then normalised lexical order.
Other emails remain unverified/blocked. Verification states include deliverable, catch_all, unknown,
undeliverable and unverified. Only current deliverable evidence can pass the email gate.
Store website/contact-form/social URLs for review only; v1 never contacts forms or social profiles.
Positioning notes are deterministic title/meta/heading excerpts, max400 characters, clearly sourced.

**R19 — Spend authority.** Reserve worst-case charge atomically before each billable request.
Use integer micro-AUD, a configured FX rate/date and 10% contingency; include taxes and retries.
The calendar month is Australia/Brisbane. Pending + settled reservations cannot exceed A$150.
Each operation has an idempotency key, tariff version, reservation, settlement and provider receipt.
Timeout with unknown billing retains its reservation until reconciliation. No safe tariff/FX means
no paid call. Cross-month requests charge their reservation month; cancellation/refund is audited.
Provider prepaid minimums and subscriptions are separate cash-flow commitments, shown in the budget.
Zero remaining budget stops paid work, keeps resumable queue state and raises an alarm.

**R20 — Provenance integrity.** Every endpoint and permission assessment links to evidence for
that exact contact/lead/channel. Database composite keys or equivalent constraints enforce this,
including the first provenance pointer; linking another contact's page cannot satisfy the gate.
Website provenance binds identity_id, lead_id and registrable_domain through a composite
relationship and checks the captured URL's domain. Another lead's approved domain decision
cannot authorise this contact.
Persist contact and first evidence in a single transaction with deferred referential validation.
Evidence includes URL, captured content digest/object key, excerpt, UTC time, collector/parser
version, method, robots decision, terms search scope and identity decision. Evidence is append-only
during its retention period; corrections append a superseding decision. Evidence access is audited.

### Permission, suppression and safe hand-off

**R21 — Permission assessment.** Three-valued assessment (pass/fail/unknown) must separate:
identifiable individual/role, conspicuous publication, publication with agreement, absence of a
no-unsolicited statement, and message relevance. Automatic heuristics collect evidence; only a
trained authorised reviewer applying an approved policy can confirm record-level inferred consent.
Own-domain appearance or sole-trader status does not automatically prove agreement/role.
The MVP inferred-publication path requires all record-level limbs pass. Express consent is a
separate supported basis with its own source, scope, timestamp and withdrawal evidence; it does
not need invented publication limbs. unknown/none blocks. Basis and verification expire after
90 days as business policy or sooner on withdrawal/evidence change. No override bypasses a block;
review creates a new evidence-backed decision. Message relevance belongs to each actual attempt.
Each assessment has an immutable monotonic assessment_seq per contact/channel/scope. Select
the highest sequence, including fail, unknown or withdrawn; never select an older
passing row instead. Updating the current pointer and appending the assessment is atomic and
invalidates prior action intents.

**R22 — Export decision.** Evaluate identity, group/endpoint suppression, active policy, privacy
gates, current basis/verification or phone wash, actor approval and channel. Never disclose a
blocked endpoint in a working contact column; show a reason and safe review action.
Labels: Email: needs send-time checks; Phone: check before calling; Do not contact; Needs review.
Never label a record simply OK to send. Export contains decision time, expiry, reason codes,
policy version and opaque record references. It is a candidate, not an authorisation.
Fail-closed tests must include an allowed fixture so an always-empty system cannot pass.

**R23 — Manual DNCR wash.** Pilot uses an authorised operator web-uploading a reviewed phone
batch and importing the result/receipt into the system. Store batch digest, account/provider,
receipt digest, matching number count, result per normalised endpoint and UTC wash time.
Reject malformed/mismatched receipts, future times, duplicate conflicting rows and unsupported
formats. Select the latest valid observation (timestamp plus monotonic import sequence), not
any earlier clear result. A later listed/error observation blocks. Require clear and
now < washed_at +30 days. Every phone is washed as a conservative business policy.
Direct SOAP/SFTP is disabled: official documents require subscription D or above; the currently
displayed table shows B A$126/year and D A$5,058/year. Confirm actual signup terms/costs before
purchasing. A priced third-party automation adapter is a future option, not an assumed bargain.

**R24 — Action-time authority.** A separately built sender/dialler MUST query the live control
service for the exact contact, channel, campaign, template digest and actor immediately at
dispatch. It rechecks suppression, current permission, expiry, caller time window and required
message fields. A single-use attempt ID cannot be reused for another endpoint/template or replayed.
Do not release a reusable send-authorisation token into a sheet. Service failure blocks action.
Manual callers must open the current check before dialling; static Sheets/CRM contact actions stay
disabled until an approved workflow enforces this. Part1-only installation cannot claim end-to-end
prevention for uncontrolled third-party sends. Define the linearisation boundary and record an
already-dispatched request separately; no promise that an opt-out can retract a message already sent.

**R25 — Immediate suppression.** Provide an authenticated synchronous opt-out endpoint and
prominent reviewer action. Success means database commit of entity/group and all known endpoint
blocks, audit event and downstream invalidation outbox. Target commit within5 seconds; on failure
show a visible unconfirmed state and prohibit further action. Weekly write-back is not the primary
opt-out route. Resynchronise sheets/CRM within60 seconds when available; all local authorisations
block immediately after commit even if external propagation fails.
Persist global organisation-wide endpoint suppression, lead/group suppression and aliases for
Maintain Media/MaintainAI/QuoteMax. Each external system must integrate/certify this authority before
cross-system coverage is claimed. Reactivation never clears unsubscribe/complaint blocks.
ABN cancellation is an entity block; a later reviewed reactivation may resolve only that reason.
Suppression cannot be deleted through routine retention or restored-away by backups.

**R26 — Security and audit.** Authentication identifies each human/service; enforce least privilege
on every read/write. Roles and scopes are in the interface contract. Encrypt endpoints at rest and
transport; use versioned HMAC-SHA-256 lookup tokens for low-entropy endpoint identifiers, with keys
separate from DB/backups and encryption keys. Treat tokens as personal/pseudonymous information,
not anonymous data. Rotate keys with dual lookup and explicit migration, preserving suppression.
Prior lookup keys cannot be destroyed while erased token-only restrictions depend on them:
retain them encrypted with lookup-only service access, never for new token creation. Retire a key
only after every dependent restriction has an equivalent matchable replacement or an approved
lawful end of retention. Never rehash an old HMAC as if it were the original endpoint. Key compromise
freezes affected actions pending incident handling; it cannot silently discard opt-outs.
No personal data/secrets in logs, source control, public report or public evidence URLs. Private
evidence objects use short-lived authorised access. Audit policy changes, reads of evidence,
merges, export decisions, overrides/reassessments and opt-outs.

**R27 — Law and notices as reviewed policy.** Before live personal-data collection, the owner
records a qualified assessment of Privacy Act applicability, source terms/licences, necessity,
APP5 notice strategy/timing, channel-specific APP7 interaction, and overseas disclosure.
APP7 is not blindly layered over every channel: assess its statutory exceptions alongside the
Spam/DNCR rules. Public availability is not consent. The crawler's address-harvesting position
requires explicit review; heuristics cannot settle it. Approved notices identify the actual sources
used (QBCC or ABR or website, not an inaccurate universal sentence), purpose, business identity,
privacy policy, complaint/source-request contact and actual recipient countries.
Source attribution and licence links accompany outputs. No live collection gate is satisfied by
this document or its score.

For the exact QBCC-PILOT-2026-09-11, WEBSITE-PHONE-PILOT-2026-09-11,
GHL-DND-PILOT-2026-09-11 or ABR-EARLY-VALIDATION-2026-09-11 scope and
interval above, use its own recorded delegated-owner policy decision instead of
claiming a qualified assessment. The absent adviser/notice assessment remains
explicit; all other uses retain the ordinary R27/G1 requirements. The website
amendment requires the specific public notice and phone-only/retention controls;
the older QBCC decision cannot substitute for website approval. The ABR amendment
separately requires its specific source notice, complete-publication controls,
validation-only phase and genuine precision evidence before qualification; it
does not give ABR records the earlier website/CRM onward permissions.

**R28 — Calling and downstream contracting.** Default business calling policy: weekdays9–18,
Saturday9–17 in confirmed recipient timezone, no Sundays or applicable public holidays.
The stricter weekday18 cutoff is business policy, not a statement that telephone sales law
requires it. Unknown timezone/locality blocks phone eligibility until reviewed; postcode-only
timezone inference must be checked at border cases. Current licence review and DNCR wash do not
replace these rules. Require caller identity, purpose, CLI presentation and termination on request.
Record invitation state as invited/uninvited/unknown with evidence; never infer invitation from
a meeting booking. Downstream contracting must assess unsolicited-consumer-agreement applicability
and its disclosure, written-agreement, cooling-off/payment/service controls. Those functions remain
Part2 release gates, not hidden Part1 implementation.

**R29 — Finite retention and restoration.** Default maximum schedules, subject to the recorded
necessity/retention approval before live collection: full raw ZIPs30 days; full ABR/QBCC analytical
snapshots90 days; current/previous accepted snapshots must fit within that limit (if publication
stalls beyond it, expire and require a new baseline); derived minimal event metrics24 months;
unworked identifiable profiles180 days since last qualifying event, with no clock reset from a
routine crawl; ordinary non-selected page captures90 days; selected contact/consent/action evidence
seven years from last relevant attempt/assessment, with a documented purpose. Delete unnecessary
profile fields within30 days of suppression/disqualification; retain only restricted required evidence
and suppression tokens/aliases. Seven years is a proposed defensibility policy, not a claim that all
records legally require it. Legal holds require reason, scope, owner and next review date.
The dated website-phone pilot instead prohibits seven-year archival, retains its
ordinary 90-day page limit even for worklist records, and adds a 24-hour encrypted
pending-request limit, as set out in its scoped amendment and policy.
Encrypted backups expire35 days. Restore into quarantine, replay latest suppression/erasure ledger,
run overdue deletion, reconcile keys and only then reopen access/outbound actions.
No indefinite full-register archive. HMAC-only history is not assumed to retain all business-field
diff capability; historical replay is limited by retained artifacts and documented as such.

**R30 — Residency.** Select AU-region database, analytical storage, evidence and backups with a
contractual region commitment. Do not treat an Oceania hint as an AU guarantee.
Record actual countries/subprocessors for VA, Sheets/Drive, CRM, SERP, verification, telemetry
and support access, with disclosure basis and safeguards. Unknown vendor country/terms blocks
that adapter in production. AU storage does not mean all processing stays in Australia.
The dated QBCC and website-phone pilot amendments separately record limited
acceptance of the existing AWS/Vercel/Clerk/admin architecture and its unverified support/access countries;
they are not Australian-only processing certifications or new-vendor approvals.
The separate GHL DND amendment records the user's bounded onward-disclosure
decision for that named account, with United States/India handling and explicit
routing/backup uncertainty; it does not approve another vendor or outreach.

### Delivery, operation and success

**R31 — Worklist usability.** Private Google Sheet with protected immutable IDs, version and
computed columns; only allowed outcome fields editable. No public-link sharing. Rows show plain
business name, cautious signal wording, source age, review action, gate reason and final score.
Use Australian English and unambiguous dates/timezones. Business explanations must not claim
actual turnover from proxies. Branded report follows existing Maintain Media tokens; keyboard
readable, meaningful text status (not colour alone), usable at360px, table download available.
Contact details exist only in authorised candidate fields after export policy passes.

**R32 — Write-back.** Each row binds worklist_id, lead_id/group_id and version; never spreadsheet
row number as identity. Accept a closed outcome vocabulary: not_started, no_usable_contact,
attempted_no_answer, contacted_not_interested, contacted_nurture, meeting_booked, meeting_held,
disqualified, do_not_contact_requested. Store nonnegative attempts, dated activity, invitation
evidence and notes with length limit. Authenticated writes carry idempotency/event ID, expected
version, actor and timestamp. Conflicts return a reviewable error; reordered/duplicated rows
cannot mutate another lead. Meeting state derives from dated events, not conflicting booleans.
An opt-out status must use R25 immediately; periodic import is a repair path and alarms on delay.

**R33 — CRM approval and outbox.** Only selected, human-approved tier A worklist groups enter
a durable outbox. Map internal business group to location/contact ID; never retry solely on ABN
because it can be missing. Record desired field projection, version, request ID, attempts and remote
result. A timeout with uncertain create result enters reconcile state before another create.
Shared endpoints do not authorise merging distinct businesses; unresolved remote match is held.
Use documented GoHighLevel v2 adapter semantics, current rate-limit responses, jitter and bounded
retries; preserve unrelated tags via add/remove operations. No campaign automation or messages.
Suppression cancels pending exports and prioritises removal/block updates. Vendor outage cannot
erase a committed source run. Credentials/custom field IDs/location settings are environment config.
The dated GHL DND pilot additionally enforces phone-only projection, DND, a current
all-Draft workflow inventory before every mutation, and separately continuing
minimum-removal authority. Its owner approval never supplies an individual row
decision or missing phone checks.

**R34 — Reports and metrics.** Each run has an immutable manifest and summary: source metadata/
freshness, validation counts, stage states, baseline/no-op status, event/tier/geography/classification
counts, eligible/blocked/deferred/carried groups, enrichment denominators and hit rates by tier,
reserved/settled spend, wash credits/manual time, CRM results, timing/RSS/disk and alarms.
Do not expose personal data in public summaries. Report missing data and sample sizes.
Conversion metrics use distinct contacted business groups per tier and actual attempt/meeting dates;
state treatment of multi-signal groups and duplicates before pilot comparison.

**R35 — Ops and alarms.** Linux systemd timers run the same documented CLI available to operators;
one scheduler, no dual cron schedule. Durable stage locks plus recovery prevent overlap.
Alarms: source stale>10 days(ABR), mismatched>48h/escalation7d, integrity/schema/count/duplicate
failure, field-fill breach, unexpected disappearance, member-count change(informational),
classification drift>3 percentage points once comparable runs exist, volume deviation>50% of
four comparable non-baseline publications (zero median uses explicit absolute thresholds),
hit-rate deterioration vs approved measured baseline, budget/quota stop, disk/memory threshold,
unconfirmed/delayed suppression, invalid receipt, write-back conflict, CRM reconciliation pending,
expired policy, failed backup/restore and missed timer heartbeat. Baseline/no-op exceptions are
explicit. Alerts redact endpoints, are deduplicated by run/reason and have owner/runbook links.
Notify through configured operations channels only when deployed; no sends during this review.

**R36 — Capacity and stack.** Chosen baseline: Python3.12, uv-managed dependencies, DuckDB/Arrow
Parquet, PostgreSQL16, static HTML parsing, wildcard-aware robots parser, AU phone normaliser,
small authenticated control API and systemd. Exact packages/versions get a tested lockfile during
implementation; no version is described as latest without verification.
A4vCPU/8GiB AU host is a benchmark candidate, not proven capacity. Start DuckDB at512MiB buffer
limit/two threads with bounded spill and an OS process memory limit; RSS can exceed DuckDB's
buffer setting. Full-register analytics stay in Parquet; PostgreSQL holds promoted/current lead
state and controls, not a mandatory20M-row duplicate of every snapshot.
Preflight measured input+staging+spill+DB+backup needs plus25GiB headroom; fail before exhausting disk.
Targets: representative20.5M-row diff <=60s as stretch target; complete processing <=6h, RSS<=2GiB
per ingest/diff worker and no OOM. Measure actual query including output, not a join count only.
If targets fail, profile/resize/revise approved plan before release; never cite historical9.1s as proof.

**R37 — Test/release evidence.** CI uses synthetic fixtures and an actual isolated PostgreSQL16.
Cover migrations, deferred/composite FKs, allowed/blocked eligibility, snapshots/republish/repartition,
crash points/replay, normalisation, SSRF/DNS redirects, stale basis/wash, latest listed overriding old
clear, immediate opt-outs, alias merge, budget concurrency/month rollover, row conflicts, uncertain
CRM create and restore suppression. Inject faults at provider/database boundaries; do not mock
away the gate itself. Each acceptance result includes revision, command, environment and artifact.
Real source smoke tests and vendor sandbox contract tests are separately recorded; no credentials/
live outreach required to pass unit tests. Production requires the gates below, not just CI.

**R38 — Commercial pilot.** Phase0 includes necessary security, provenance, permission, wash import,
suppression, worklist and outcome foundations before live QBCC work. The earlier1–2-day claim
covered a CSV demo, not this complete foundation; obtain an estimate from the task breakdown.
Work for four measured weeks; if no booked meetings, pause expansion and review sample size,
contactability, execution and offer rather than conclude one cause as fact.
Ordinarily, build ABR phase1 after the owner records the pilot decision. The dated
ABR-EARLY-VALIDATION-2026-09-11 amendment permits early private source validation,
baseline/comparison and genuine rule review before four measured weeks, without
claiming that those weeks or commercial acceptance occurred. Operational classification
still needs R9 evidence and separate exact-release admission. Over eight outreach
weeks report attempts, contacts, booked/held meetings,
time and fully loaded cost by cohort. If B has zero bookings while A has bookings, default to
pause B enrichment and document the decision and denominators. Do not promise sales or income.
Measure the count of actual transitions from two snapshots; a single GST effective-date filter
is only a proxy and cannot validate event volume.

**R39 — Handover.** Provide a README, environment-variable reference, rules/decision register,
one-command fixture run, deployment guide, role/access guide and runbooks for late/mixed source,
parse failure, budget stop, wash import, opt-out failure, partial CRM export, source replay,
backup/restore, key rotation and retention. Another developer must complete a fixture cycle and
recovery unaided. Operator instructions explain each blocked state and who can resolve it.

**R40 — Factual accuracy.** Source claims carry checked date, official URL and scope of evidence.
Historical counts/prices/timings are labelled historical or unverified, never passed forward as
new tests. Recheck source licences/terms, rate limits, prices and signup requirements at release.
Do not infer industry/revenue/consent from a proxy. Missing legacy files are a named dependency.

**R41 — Migration and authority.** New source normalisation, hash algorithm, key, rules or contract
version has a migration note and fixtures. A parser/hash change builds an explicit compatible
baseline comparison or rebaseline; it must not manufacture business events. Rebaseline emits zero
ABR lead events and records why. Canonical spec, feature spec, plan and vault mirror share a version
and source hash; verification reports drift. Prior versions remain archives, not active authority.

**R42 — Exclusions.** No sending/dialling/payment/client-delivery app, address-list purchases,
Google Places/Maps enrichment, automated job-board scraping, social messaging, resale, undeclared
headless browser or production integration enabled by default. No new dashboard/framework beyond
the small control service needed for timely suppression. No unsupported non-trade taxonomy expansion.

**R43 — Traceability.** Rn maps to FR-nnn in Spec Kit and to tasks plus an acceptance scenario.
Requirements-quality checks are separate from implementation checkboxes and from legal/commercial
release gates. Every review score names the version and what was actually reviewed.

## Release gates and dependencies

| Gate | Owner | Required evidence | Safe work while closed |
|---|---|---|---|
| G1 Source and collection policy | Owner + qualified adviser; delegated owner within a named dated pilot amendment | Source terms/licences, necessity, notices, harvesting and channel applicability, retention and any onward CRM purpose approved in its own decision record; narrow amendments explicitly record the absent adviser assessment and separate website/CRM notice and scope requirements | Synthetic data and adapter fixtures |
| G2 Rules and source fixtures | Owner/developer | Recover and hash intended30 rules or expressly approve a replacement; dated source schema/count fixtures | Synthetic classifier and QBCC adapter |
| G3 Security and hosting | Developer/owner | AU commitments, credentials/access roles, backup/restore/key tests, capacity evidence; the dated QBCC and phone-only website pilots separately accept verified existing encryption/access and bounded storage while explicitly deferring full DR/independent custody, without a general production pass | Local isolated controls/tests |
| G4 Phone/email action integration | Owner/reviewer/developer | Valid wash account/import, reviewer policy, sender identity/unsubscribe/template controls, certified live action gate | Candidate-only records, no outreach |
| G5 Vendor hand-off | Owner/developer | Actual processor countries/terms, CRM field mapping, duplicate/retry/suppression sandbox tests | Mock Sheets/CRM outbox |
| G6 Pilot and expansion | Owner | Ordinarily four-week pilot outcomes and recorded expansion decision; the dated ABR early-validation amendment separately permits that limited earlier sequence without claiming measured outcomes, classifier accuracy or operational qualification | Offline ABR development; specifically authorised private validation after its own source/security/release admission |
| G7 Production release | Owner/developer | Passing relevant acceptance suite, runbook drill, all applicable prior gates, exact release revision | Documentation and development |

Gate state is recorded per capability, environment, revision and expiry in the
authoritative database and dated execution receipts. A scoped decision does not
activate a capability or pass another scope's gate; unapproved capabilities remain OFF.
A9–10 specification-quality rating is possible while deployment evidence remains outstanding; it is
not a certification of legal compliance or production readiness.

## Cost model

Maintain a dated budget table per vendor: billing currency, unit tariff, minimum credit purchase,
tax, FX+buffer, subscription/cash commitment and measured usage. Monthly cash cost is hosting+
storage/backups/requests/egress+enrichment+DNCR(subscription amortisation)+Sheets/CRM/licences+
operator/developer time. A$150 is only the enrichment ceiling.
At60 numbers/week, repeated wash credits and rechecks count; Type B's20,000-credit allowance is a
planning option, not a promise of account approval. Direct D costs A$5,058/year at the checked
published table, making it materially different from manual B A$126/year.
No current VPS/storage/vendor quote has been selected or verified in this review.
Purchase decisions require actual terms and owner approval.

## Acceptance overview

The detailed executable scenarios and task links live in the feature package. Completion requires:
- One coherent publication is accepted exactly once; partial, mixed and same-date corrected sources
  behave correctly and recovery never loses suppression or duplicates events.
- Qualified pilot groups have identity/provenance evidence; unknown contact permission is blocked.
- A permitted synthetic candidate exports; an expired/suppressed one does not; old exported rows
  cannot bypass the live action gate.
- Acknowledged opt-outs block every future controlled action and survive restore/key migration.
- No concurrent billable request escapes the cap; failed/uncertain billing remains accounted for.
- Worklists contain at most60 distinct groups, with deterministic fairness and correct write-back.
- Operator time, resource use and commercial results are measured honestly.
- Unimplemented software and uncompleted release gates remain visibly unchecked.

## Primary references

See [[ABR Lead Engine - Source Checks|source checks]] for checked details and access limitations.
- [ABN Lookup bulk extract](https://abr.business.gov.au/Tools/BulkExtract)
- [ATO GST registration](https://www.ato.gov.au/businesses-and-organisations/gst-excise-and-indirect-taxes/gst/registering-for-gst)
- [QBCC maximum revenue](https://qbcc.qld.gov.au/running-your-business/financial-requirements/maximum-revenue)
- [DNCR subscriptions](https://www.donotcall.gov.au/Industry/Subscription-Overview)
- [DNCR SOAP](https://www.donotcall.gov.au/industry/washing-process-overview/soap)
- [DNCR SFTP](https://www.donotcall.gov.au/industry/washing-process-overview/sftp)
- [OAIC Australian Privacy Principles](https://www.oaic.gov.au/privacy/australian-privacy-principles/read-the-australian-privacy-principles)
- [ACMA avoid sending spam](https://www.acma.gov.au/avoid-sending-spam)
- [ACCC telemarketing](https://www.accc.gov.au/business/selling-products-and-services/telemarketing-and-door-to-door-sales)
- [DuckDB memory limits](https://duckdb.org/docs/current/guides/performance/oom)
- [PostgreSQL16 table constraints](https://www.postgresql.org/docs/16/sql-createtable.html)

Source attribution: Australian Business Register, Commonwealth of Australia, CC BY3.0 AU;
QBCC Licensed Contractors Register, State of Queensland, CC BY4.0. Source-specific terms and
licence metadata must be reconfirmed and recorded before live ingestion.
