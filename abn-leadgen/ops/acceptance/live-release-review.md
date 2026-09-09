# Live release review — 9 September 2026

**Full-spec verdict: INCOMPLETE. The dashboard still uses fixture data.**

The user authorised live implementation and approved the targeting direction during
this task. Real source ingestion, live account installation, production service
activation and the measured pilot have not been completed. No register rows,
websites or contacts were collected, no Google/GHL data was written, no service
was installed remotely, no hosting was purchased and no outreach occurred.

## What is now implemented

| User outcome / spec | Completed in this pass | Remaining before live use |
| --- | --- | --- |
| 1. Real business data — R2/R5/R9/R12/R40 | Executable bounded official catalogue checks; actual current metadata receipts; authentic QBCC 11-column parser; gated operator-file intake with encrypted review records, immutable raw custody, replay, seven-day cleanup and crash recovery; recovered all 30 original ordered trade regexes. | Approved collection/storage context; actual publisher file acquisition/schema/count smoke; protected current licence/identity review, suppression checks and accepted promotion into the live dashboard/worklist. ABR generation coherence and G6 remain separate. |
| 2. Matching — R9/R10/R11/R14 | User approved all 30 recovered categories, QLD plus NSW 2450–2490, QBCC Categories 1–2 and 60 businesses/week. Exact source/rule hashes and migration differences recorded. | An actual 100-business stratified accuracy review, unresolved/false-positive decisions and production classifier approval. The recovered file remains inactive. |
| 3. Staff workflow — R25/R26/R31–R33 | Real GHL transport and metadata preflight, exact location/group identity checks, bounded errors, no create retries, DND and owned-tag operations; standalone restricted Sheets installer with protected columns and actual-trigger checks. | Correct Maintain Media Google account/private Sheet and GHL location/field IDs; real editor/JWT/HMAC registry and installation; sandbox duplicate/uncertain-create/clearing/suppression receipts; combined live outbox and propagation integration. |
| 4. Production and pilot — R26/R29/R30/R35–R39 | Redacted read-only release check, closed nonsecret deployment plan, reproducible uninstalled systemd bundle, host/code/permission checks, backup receipt validator and quarantine/restore runbook. Pilot bundle excludes ABR scheduling. | Actual AU host and storage contract, credentials/roles, live API/dashboard runtime, backup creation/provider verification, real Linux timer/access/recovery drills, measured capacity, current G1–G7 evidence and four/eight-week pilot results. |

The live writer blocks in the existing pipeline, dashboard, CRM worker and
suppression propagation remain in place. Removing only an enabled flag would not
connect the missing runtime paths and could allow a partial hand-off. T071 records
the required integration work. These are actual code gaps as well as account and
approval dependencies; they are not being described as configuration alone.

## Decisions and evidence

- [Targeting approval](live-sources/targeting-approval-2026-09-09.json): explicit user
  approval, limited to targeting direction. The 100-record review count remains zero.
- [Rule approval packet](live-sources/rules-approval-packet.md), [rule provenance](live-sources/rules-review-decision.json)
  and [QBCC mapping migration](live-sources/qbcc-mapping-migration.md).
- [Official source metadata/schema check](live-sources/source-check-2026-09-09.json).
  QBCC data is dated 18 May 2026 and includes suspended licence holders; it is
  discovery evidence. Current ABR catalogue ZIP resources are dated 8 September
  2026; matching catalogue dates do not establish inner publication coherence.
- Executed CLI receipts: [QBCC](live-sources/catalogue-qbcc.json) and
  [ABR](live-sources/catalogue-abr.json), both successful metadata observations;
  [pilot](live-sources/release-pilot.json) and [production](live-sources/release-production.json)
  release checks both correctly blocked with exit 6. The real local PostgreSQL
  authority was available, and no approvals were written.
- [Vendor installation guide](../../integrations/LIVE-INSTALLATION.md) and
  [production preparation guide](../production/README.md) describe executable
  interfaces and the uncompleted installation obligations.
- [QBCC intake/cleanup guide](live-sources/qbcc-intake.md) describes the new partial
  T071 path. It has not processed real rows and cannot produce an accepted lead.
- [Reviewed prepared bundle manifest](production-preparation-20260909-reviewed/deployment-manifest.json)
  contains eleven uninstalled pilot units and the reviewed source digest. Its
  [local host check](production-preparation-20260909-reviewed/host-check.json) correctly
  returns blocked; no host, source, vendor or backup operation was performed.
  Earlier `-v1` and `-final` bundles are superseded preparation evidence.

The connected Google Drive account is for a different organisation. It was used
only for bounded profile/worklist-metadata discovery; no Maintain Media data was
transferred. No existing `.env` or credential file contents were read or printed.

## Build/review corrections

1. Replaced the assumed QBCC synthetic header with an explicit published schema;
   absent licence status and entity class stay unknown.
2. Recovered legacy rules without executing the old regex XML extractor; retained
   v4's deterministic name ordering and documented the behavioural difference.
3. Added controlled handling for oversized numeric metadata and deeply nested JSON.
4. Corrected GHL suppression to reject retained business names as well as endpoints;
   malformed provider replies remain reconcilable failures.
5. Corrected Sheet missing-tab and wrong-trigger cases that could silently drop
   edits; installation requires the actual owner and cannot expose script secrets
   to ordinary Sheet editors.
6. Added qualification rules to the release digest and checked immutable ownership
   throughout the installed code/configuration paths.
7. Allowed integrity-checked monitoring to report expired operational gates while
   source, retention and API execution remain release-gated.
8. Rejected private inventory parents, symlinks and Windows reparse points before
   content reads, so deployment hashing cannot accidentally read credential files.
9. Added narrow executable review-intake cleanup, stale-writer recovery and fair
   batches; an expired collection approval or 100 held imports cannot silently
   prevent later staging expiry. Holds and damaged files remain visible failures.
10. Bounded encrypted output and replay reads; decoded PostgreSQL connection
    identities before rejecting fixture databases. Shared current gate checks,
    clear CLI refusal codes and timezone-aware receipt parsing are tested together.

## Verification

The earlier [focused suite](live-sources/final-focused.xml) passed **132 tests**;
later focused passes cover 64 production preparation cases, 35 PostgreSQL intake
and cleanup cases, seven effective-database guard cases, and 15 CLI/gate cases.
The final independent review found no remaining actionable defects within the
implemented metadata, intake/cleanup, GHL/Sheets and deployment preparation slices.

The [final combined verification](live-sources/final-verification-v2/result.json)
passed: **641 tests, zero failures/errors/skips**, whole-package Ruff, mypy for all
60 application modules and the production preparer. The [JUnit receipt](live-sources/final-verification-v2/pytest.xml)
and logs cover the same frozen source; the before/after application and Python test
inventory is unchanged (`c28faa480a7c1553dbedcbef516490799e7213bbe1713f96e43359a6149e6651`).
The test run took 13 minutes 14 seconds and emitted two dependency deprecation
warnings. An earlier concurrent run had 516 passes
and one obsolete Sheet mock failure; the first combined verification stopped for
two now-corrected type errors. Neither intermediate attempt is counted as a final
pass. All database rows are synthetic and vendor responses are mocked; these
checks are not live installations.

A read-only HTTP check of the existing website returned 307 to `/sign-in` for a
signed-out dashboard request; the local fixture dashboard returned 200. No
signed-in production-data flow is inferred from those responses. The website
source and Clerk configuration were not changed in this pass.

## Score and weakest areas

The [rubric written before implementation](live-readiness-rubric.md) measures
evidenced progress towards **this live release**, separately from the earlier
fixture/dashboard/Clerk engineering scores. Scored milestones are
**0 → 15 → 20 → 25 → 30 → 30 → 30/100**: source metadata/schema plus rule recovery;
targeting approval; tested vendor transport; tested deployment preparation; final
review; then tested intake/cleanup with the same remaining live evidence gaps.
Allocation: sources 10/25, matching 10/15,
staff workflow 5/25, production 5/25, measured pilot 0/10. The score is release
progress, not a claim of production readiness. No elapsed pilot weeks, source
approvals or account receipts are inferred to improve it.

The largest remaining deductions are 20 points for the uninstalled private Sheet
and unverified real GHL account, 20 for actual host/timer/backup/release evidence,
and 15 for accepted real source data in the dashboard. Another five require the
100-business accuracy review and ten require elapsed measured pilot results.
Additional local intake safeguards do not earn the rubric's real-publication or
installed-workflow points. The accepted promotion, protected review interface and
live worker wiring also remain actual code gaps, not merely missing credentials.

## Inputs needed for the next live step

1. The existing Australian production server and domain, with the intended private
   database/storage/backup service identified. No host has been selected or purchased.
2. The Maintain Media Google Workspace account/private Sheet and GoHighLevel location.
   Names, URLs or IDs suffice; credentials belong in the approved secret manager.
3. The recorded source/privacy and vendor-processing approvals required by canonical
   G1/G5. The repository still has no completed records for those gates.

These were requested in the current task. Targeting direction was answered and
recorded; the environment/account and G1/G5 questions remain outstanding. Once
they are supplied, finish T071 and verify the real QBCC workflow on that target,
then start the four-week pilot clock. ABR expansion follows its measured decision;
sending and calling remain outside this build.
