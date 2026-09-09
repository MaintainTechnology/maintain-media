# Enrichment integration review 1

Reviewed before the durable worker build against R15, R19 and T020.

1. The pure worker transitions are useful but have no persistent attempt, stage or provider-operation authority. A restart can repay a successful lookup and cannot distinguish an unbilled request from an uncertain response.
2. The pipeline directly seeds contacts while preparing a report, bypassing candidate leases and budget reservation/settlement entirely.
3. No transaction releases locks before transport and reacquires current suppression authority before applying results. A suppression during a provider call has no tested boundary.
4. Completed and exhausted discovery failures have no durable 90-day cache shared across candidates for the same business. Budget and quota stops need resumable state rather than an exhausted cache.

Build requirements: persist claims and bounded leases; commit server-priced reservations before dispatch; retain stable operation IDs and encrypted result receipts; reconcile uncertain operations without redispatch; apply results under current authority; keep synthetic permission in an explicitly named fixture approval adapter. Production provider adapters remain gated.

Build completed in migration017 and `enrich/worker.py`, with retention follow-up migrations018/020.
The pipeline invokes the fixture-only `drain_one` boundary before report construction. Per-stage
reservations and dispatch intent commit before the injected transport. Current policy, geography,
tier, merge authority and suppression are checked again before dispatch and applying results.
Completed/exhausted attempts retain a 90-day family cache; budget, quota and billing holds do not
set last_attempt_at or completion cooldown. Final lead and queue scores use current identity and
verified contact evidence. Payloads are encrypted and subject to finite retention.

Ten real PostgreSQL integration cases passed in 54.53 seconds: stage receipt replay, lead-wide
cooldown, nonzero budget stop, suppression during provider I/O, quota/uncertain/exhausted distinction,
concurrent claim exclusion, policy revocation after verification with zero repeated provider calls,
and stale lease response reconciliation. The independent retention review then identified erased
merged-family cache linkage and expired partial-stage payload handling; these are fixed using an
opaque retained group link and a specific STAGE_EVIDENCE_EXPIRED hold without repurchase. Their
independent regression evidence is recorded in enrichment-worker-review-1.md.

Final follow-up: eleven worker cases passed in 91.01 seconds, including preserved exhausted
discovery across a policy hold. The independent worker/retention reviewer reported 39 passing
cases in 153.25 seconds; quarantine, expired evidence and erased-family cooldown regressions
all passed. Unresolved attempts on another member of a merged family require reconciliation
before new purchase. No live enrichment adapter is enabled.
