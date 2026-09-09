# Final cross-module review — 9 September 2026

**Verdict: no confirmed high or critical defect in this bounded read-only review.**

Reviewed current `ops/costs.py`, `ops/propagation.py`, migrations022/023, their focused PostgreSQL
tests, and the connected summary, cash/time, retention, fixture CRM and reviewed-merge code.
This reviewer did not build either module. No code or tests were changed, and no tests or full
suite were run during this pass. Only this review record was written while root's frozen suite ran.

## Cost accounting

- Closed evidence requires a completed aware-time window, dated approval, nonblank source/receipt
  references and finite nonnegative monetary inputs. Native gross already includes declared tax;
  conversion does not add that tax again. AUD conversion is constrained to one.
- Statement identity is idempotent by digest. A second statement for the same exact window and
  optional cohort/tier is rejected under common authority and a database uniqueness constraint.
  Cohort allocation requires an existing selected fixed tier and is not added again to overall cash.
- Missing categories, rate or reviewed time coverage keep the relevant totals unknown. Budget
  reservations/settlements remain usage facts and are not counted as purchase cash. Activity time
  uses the existing per-actor interval union; ambiguous cross-tier unassigned activity is excluded.
- Migration022 makes facts immutable, permits only restricted one-way receipt erasure, and the
  retention integration removes receipt bodies at90 days and numeric statements at24 months.
  Fixture-only import performs no purchasing and makes no production financial-policy claim.
- Focused test source covers positive cash conversion and total, absent/partial evidence, exact
  period selection, separate cohort allocation, replay/conflict, future/invalid inputs and erasure.
  Builder-reported test results remain builder evidence; no new execution is attributed here.

## Suppression propagation

- Claims use durable outbox ownership, expiry, bounded attempts and due times. Provider I/O runs
  outside database/control locks, with current personal-data/quarantine authority checked before
  projection and each write. A stale lease cannot commit a completion receipt.
- The worker checks both mapped remote IDs and provider group lookup, refuses ambiguous/conflicting
  identity, checks the returned outer and payload group identity, and never creates a contact.
- The blocked projection clears engine-owned marketing values, retains opaque identity and
  unrelated metadata/tags, and adds the mapping-approved suppressed tag. The fixture provider
  preserves concurrently present unrelated tags when updating.
- A fetched exact resulting projection is required before completion. Unknown update outcomes
  retry by fetching current state; an already-applied stop needs no repeated write. Dispatched
  unresolved CRM create/update work prevents a success receipt even when lookup finds nothing.
  An approval blocked before dispatch correctly does not pretend a remote operation exists.
- Merge code blocks ordinary reviewed merge when a CRM mapping or in-flight/uncertain CRM work
  requires remote reconciliation, and enqueues new propagation for reviewed family changes.
  Suppression evidence is not removed or relaxed by this worker.
- Focused test source covers endpoint-only suppression, projection clearing/tag preservation,
  uncertain response, wrong remote identity, simultaneous worker/suppression activity, quarantine,
  exhaustion, and the dispatched/never-dispatched distinction. The saved independent CLI drill
  reports a verified synthetic stop in4.637317 seconds; this is local fixture evidence only.

## Boundaries

Live CRM/Sheets propagation, provider clearing/rate-limit contracts, deployment latency, notification
channels, actual purchased-cost evidence and production retention approval remain external gates.
The fixture adapter and drill do not certify those integrations. No new feature or speculative
requirement was added in this review. Root owns final package-wide tests and release status.

Reviewed SHA256 values:

| File | SHA256 |
|---|---|
| src/abr_engine/ops/costs.py | 29a211ceb0ec8d11e16bea2d4b3fd9b0743ebfc56e84ab9f2bc90e2db7cac366 |
| src/abr_engine/ops/propagation.py | 93ac32d5fc1703e38afdb53a37cd4645a74cfea1708ffa1472e0391292dfa350 |
| migrations/022_cost_evidence.sql | 904cb8db0be0646f823121ba8936acb8c8e2118f25366a6d5ef23c3ce1680551 |
| migrations/023_propagation_delivery.sql | 72d46b7da1e8117a9ec7a034b46e3ca3fb9dd6b554ef1b63e4688496d0f68d3a |
