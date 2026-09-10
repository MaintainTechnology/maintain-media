# Live QBCC runtime and reviewer workflow

Implemented on 10 September 2026. This is engineering evidence from synthetic
publisher rows and real isolated PostgreSQL 16. It is not a source/privacy
approval, real-business pilot result, or claim that live collection has begun.

## Operator path

1. An authenticated operator submits a QBCC run. The durable job is recorded
   before the worker starts. Missing approvals produce a visible held result and
   make no publisher HTTP requests.
2. With current collection gates, the worker reads the official catalogue,
   downloads only its mapped QBCC CSV resource, checks metadata again, stages
   encrypted review evidence and accepts a verified immutable snapshot.
3. The source review list displays the actual publisher modification date when
   available. Unknown licence status remains unknown. The first accepted list
   creates backlog observations, not automatically qualified businesses.
4. A reviewer records an explicit current licence/status and identity check
   against the exact current source row. Category 1/2, geography, suppression,
   identity grouping and freshness decide qualification. Negative or changed
   evidence removes previous action authority. Inactive and suspended remain
   distinct facts.
5. For a qualified business, a reviewer can confirm its own website using the
   existing identity review. A dated site-terms review must permit collection.
   The website job uses the real IP-pinned bounded crawler and stores actual
   encrypted page/contact evidence. It neither searches a paid provider nor
   invents deliverability or permission.
6. Newly collected endpoints require the separate permission workflow. Email
   remains unverified until genuine verification evidence exists; phones require
   a current manual DNCR wash and the calling-policy facts. This build sends
   nothing.

## Integration contract

`abr_engine.live.runtime.QBCCRuntime(settings)` provides:

- `submit_run({"source":"qbcc","request_id":"UUID"}, actor)` — durable admission.
- `execute_job(job_id)` — gated worker, safe result on transport failure.
- `get_job(job_id)` — durable phase, reason codes and receipt.
- `execute_pending(limit=1)` — queued jobs and workers stale for an hour.

`abr_engine.live.qbcc` provides the approved operator-file acceptance path,
`list_qbcc_reviews`, the closed `QBCCLicenceReview` model and
`review_qbcc_licence`. Source cursor compare-and-swap and current source row
hashes prevent stale writes. Repeated request IDs replay their original result;
changed bodies conflict.

`abr_engine.live.enrichment` provides `WebsiteCollection`,
`submit_website_collection`, `execute_website_collection`,
`get_website_collection` and `execute_pending_websites`. The encrypted queued
request expires after 24 hours and is removed from the job when it finishes or
is held. Every crawler request checks authority before and after network I/O;
no suppression lock spans that network request. Successful and exhausted
attempts enforce the 90-day group cooldown. Contact permission remains separate.

The scheduler must run both pending-worker functions. Process and database locks
serialize source writes. Source downloads have five attempts, explicit deadlines,
size limits, verified lengths, no redirects and no inherited proxy credentials.
The website crawler retains its public-IP pinning, TLS verification, robots,
same-domain, page/request/redirect and response-size bounds.

## Retention admission

General live retention now has a positive permitted path. It requires all of:

- A managed live key store and non-fixture database configuration.
- `capabilities.retention: true`.
- Current evidenced `G1`, `G3` and `G7` gates for scope `retention` and the exact
  configured environment.
- The latest policy has approved state, scope equal to `pilot` or `production`,
  current dates, an actor and an evidence reference. Its `settings.retention`
  contains `approved: true`, `schedule_version: "abr-v4-defaults"` and a valid
  `evidence_sha256` for the actual approved retention record.

These fields describe required records. They must not be populated from this
engineering note or by interpreting broad build authorization as policy approval.
Collection permission can be withdrawn while separately approved deletion stays
available. Ordinary cleanup is blocked during restoration quarantine. Only a
validated latest-ledger replay, with `restore_enabled: true` in the retention
policy, can perform its required minimisation while remaining quarantined.
Future live deletion dates are rejected.

New source review records use an append-only ledger. Unselected ordinary evidence
expires after 90 days; selected evidence follows the existing restricted-evidence
and profile-erasure rules. Review/snapshot/group holds are respected. Lookup keys
cannot be retired while referenced by that ledger. Profile erasure preserves
minimal independent suppression aliases and events. Expiry of a 30-day raw CSV
does not discard its still-valid 90-day normalized snapshot cursor.

## Verified boundaries and remaining inputs

Tests cover approved positive source ingestion, unknown status, current reviewer
qualification, no contact permission fabrication, source no-ops, changed metadata,
tampered artifacts, closed/revoked gates, concurrent review replay, atomic failed
promotion, source transfer bounds, real crawler protocol, restrictive terms,
mid-request withdrawal, safe background error receipts, independent live
retention approval and restore quarantine. The existing retention regression
suite is also exercised. The JUnit result is recorded alongside this note.

The source/privacy/vendor/retention approval records are still required. Real
automatic website discovery and email verification also require approved vendor
accounts and tariffs; the manual own-website path works without those paid
providers. Manual DNCR receipts, staff pilot measurements, approved backups and
the ABR expansion decision cannot be substituted with synthetic test results.

Cross-source profiles already owned by an ABR lead are held for explicit profile
review by this QBCC pilot path. Broader ABR activation remains a separate phase.
