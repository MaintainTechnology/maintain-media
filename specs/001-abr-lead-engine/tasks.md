# Tasks: ABR Lead Engine v4.0

Input: [spec.md](spec.md), [plan.md](plan.md), [data-model.md](data-model.md), [interfaces](contracts/interfaces.md), [quickstart.md](quickstart.md). The user's later request authorises implementation in `abn-leadgen/`; original conceptual `abr_engine/` root paths below map to this folder. Some modules/tests were consolidated as recorded in [implementation status](implementation-status.md). Checked tasks require an executed evidence entry in `task-evidence.json`; partial and external obligations remain unchecked. Tests exercise real gates/database boundaries with mocked external I/O.

## Phase 1 — Setup

- [x] T001 Create Python3.12 package/CLI scaffold and pin exact supported runtime/dependencies in `abr_engine/pyproject.toml`, `abr_engine/.python-version` and `abr_engine/uv.lock`; verify frozen clean install. [FR-036, FR-039]
- [x] T002 [P] Add isolated PostgreSQL16 service and external-network-denying fixture harness in `abr_engine/ops/compose.test.yaml` and `abr_engine/tests/conftest.py`; prove live credentials/hosts rejected. [FR-001, FR-037, FR-042]
- [x] T003 [P] Define configuration schema, all environment variables, capability switches and redacted validation errors in `abr_engine/src/abr_engine/config.py` and `abr_engine/config/fixture.yaml`; missing live gates default off. [FR-001, FR-030, FR-039]
- [x] T004 [P] Create source/decision/rules provenance registry in `abr_engine/ops/decisions.md`; record absent legacy extractor, production rule-recovery blocker and synthetic-only replacement fixtures without claiming30 recovered rules. [FR-009, FR-040, FR-041]

## Phase 2 — Foundation before any live pilot

Goal: persistent controls and evidence exist before enrichment. Safe fixture development proceeds while G1–G7 remain pending.

- [x] T005 Implement ordered migration runner and source/identity/contact/provenance/consent/suppression schema in `abr_engine/migrations/001_foundation.sql`; use deferred same-contact/channel FKs and tri-state reviewed/express basis paths from data-model. [FR-013, FR-020, FR-021, FR-026, FR-041]
- [x] T006 Implement queue/budget/worklist/outbox/audit/receipt/action-intent migrations in `abr_engine/migrations/002_workflows.sql`; constrain allowed states, micro-AUD accounting, immutable IDs and optimistic versions. [FR-014, FR-019, FR-023, FR-024, FR-032, FR-033]
- [x] T007 Prove clean migration, deferred pair commit, wrong-contact/channel/lead/domain rejection, missing evidence failure and valid permitted record in `abr_engine/tests/integration/test_schema_constraints.py` using PostgreSQL16. [FR-020, FR-021, FR-037]
- [x] T008 [P] Implement actor/scopes, audit-safe logging and API error/idempotency middleware in `abr_engine/src/abr_engine/control/auth.py`; test unauthenticated/unauthorized access and changed-body key reuse. [FR-001, FR-026]
- [x] T009 [P] Implement encryption/HMAC key separation, opaque group UUID references, active encrypted source aliases, retained HMAC aliases and dual-token rotation in `abr_engine/src/abr_engine/compliance/keys.py`; matching survives rotation/erasure without plaintext aliases or logs. [FR-018, FR-025, FR-026, FR-029]
- [x] T010 [P] Implement reviewed policy registry and release-switch checks in `abr_engine/src/abr_engine/compliance/policy.py`; missing/expired source, legal, country or role approval blocks corresponding live operation. [FR-001, FR-021, FR-027, FR-030]
- [x] T011 Implement atomic micro-AUD reservations/settlements in `abr_engine/src/abr_engine/enrich/budget.py`; reserve tariff+tax+dated FX+10% contingency before every paid attempt, preserve unknown charges/reservation month. [FR-019]
- [x] T012 Test concurrent near-cap requests, zero cap, retries, uncertain billing and cross-month requests against real ledger in `abr_engine/tests/integration/test_budget.py`; prove cap cannot be bypassed. [FR-019, FR-037]
- [x] T013 Create scope/owner/evidence/expiry records for source terms, collection/harvesting, notices, retention, residency and contact controls in `abr_engine/ops/release-gates.md`; leave missing approvals visibly pending. [FR-001, FR-027, FR-028, FR-029, FR-030, FR-040]

## Phase 3 — US1: Qualified pilot worklist (P1)

Independent test: synthetic QBCC input becomes a <=60-group reviewed candidate list with at least one permitted contact and explicit reasons for blocked contacts, without live network. Production pilot additionally requires US2 stop controls and US4 minimal write-back.

- [x] T014 [P] [US1] Add UTF16LE QBCC fixtures for class collapse, no ABN, shared ABN, conflicting scalar fields and malformed address in `abr_engine/tests/fixtures/qbcc/`; assert semantic counts instead of historical totals. [FR-012, FR-013]
- [x] T015 [US1] Implement QBCC BOM/header/ABN/address validation, collapse, content identity and baseline backlog in `abr_engine/src/abr_engine/ingest/qbcc.py`; quarantine conflicts and preserve source age. [FR-002, FR-012]
- [x] T016 [US1] Implement source aliases, canonical groups and reviewed merge in `abr_engine/src/abr_engine/qualify/identity.py`; propagate suppression before publishing merged state and never merge unrelated shared contacts. [FR-013, FR-025]
- [x] T017 [US1] Implement YAML qualification/scoring and durable fairness queue in `abr_engine/src/abr_engine/qualify/queue.py`; enforce geography, total score/time/UUID order, oldest10 reserve, eight-week expiry and event-only reactivation. [FR-010, FR-011, FR-014]
- [x] T018 [P] [US1] Build mocked SERP identity cases and private/IPv6/rebinding/redirect/robots fixtures in `abr_engine/tests/contract/test_crawl_safety.py`; assert unsafe HTTP never reaches network transport. [FR-016, FR-017, FR-037]
- [x] T019 [US1] Implement three-query discovery and evidence-based own-domain review in `abr_engine/src/abr_engine/enrich/identity.py`; exact ABN/licence or approved two-attribute corroboration required, no guessed suburb. [FR-016]
- [x] T020 [US1] Implement static crawler in `abr_engine/src/abr_engine/enrich/crawl.py`; enforce20s deadline,2MiB/page,6HTML pages,3redirects,20requests,1request/second/domain, wildcard robots and public-IP checks at every connection/redirect. [FR-017, FR-042]
- [x] T021 [US1] Implement normalization, deterministic one-email selection/verification and sourced400-character positioning excerpts in `abr_engine/src/abr_engine/enrich/endpoints.py`; other emails stay unverified and all endpoints commit with provenance. [FR-018, FR-020]
- [x] T022 [US1] Implement enrichment stage persistence/cooldown in `abr_engine/src/abr_engine/enrich/worker.py`; tierC/unknown geography/suppression emits no calls, failed discovery cools90days, budget interruption resumes without repay. [FR-015, FR-019]
- [x] T023 [US1] Implement trained-reviewer permission assessment/API and separate express-consent path in `abr_engine/src/abr_engine/compliance/basis.py`; monotonic assessment_seq/current pointer makes later fail/unknown/withdrawn override old pass, no heuristic grants consent. [FR-021, FR-027]
- [x] T024 [US1] Implement manual DNCR batch/receipt import and current QBCC licence review in `abr_engine/src/abr_engine/compliance/wash.py`; reject mismatches/future/conflicting rows and select latest timestamp/import sequence. [FR-012, FR-023]
- [x] T025 [US1] Implement candidate export gate in `abr_engine/src/abr_engine/compliance/export_gate.py`; exact lead/domain identity approved within90days, latest basis, current licence review30days, verification/wash/policy/suppression checks mask blocks and return reasons/expiry. [FR-016, FR-022, FR-023]
- [x] T026 [P] [US1] Prove allowed and blocked email/phone, latest-listed wash, licence expiry, permission expiry and200-to60 queue behavior in `abr_engine/tests/integration/test_pilot.py`. [FR-012, FR-014, FR-020, FR-021, FR-022, FR-023, FR-037]
- [x] T027 [US1] Render branded private report and immutable worklist schema in `abr_engine/templates/report.html.j2`, `abr_engine/templates/report.md.j2` and `abr_engine/templates/worklist_schema.json`; show safe signal meaning, source age and text gate reasons at360px. [FR-031, FR-034]

## Phase 4 — US2: Stop and opt-out controls (P1)

Independent test: seeded contact/alias plus an old worklist intent is blocked immediately after acknowledged suppression, including service outage, stale row edit and restore. US2 is mandatory before any live pilot contact.

- [x] T028 [P] [US2] Write live-gate/suppression race, future-endpoint alias and stale-opt-out-edit integration cases in `abr_engine/tests/integration/test_suppression.py`; exercise actual DB transactions. [FR-024, FR-025, FR-032]
- [x] T029 [US2] Implement synchronous reason-specific entity/endpoint suppression, cancellation-only reviewed resolution, pending-intent invalidation and propagation outbox in `abr_engine/src/abr_engine/compliance/suppression.py`;201 only after durable commit, target5s, visible failure/60s propagation alarm, no opt-out resolution. [FR-025, FR-026]
- [x] T030 [US2] Implement authenticated suppression API and narrowly scoped no-login unsubscribe utility in `abr_engine/src/abr_engine/control/suppression.py`; log receipts without exposing endpoints and test idempotent retry. [FR-025, FR-027]
- [x] T031 [US2] Implement reviewer-only email relevance assessment API, assessment-ID-based single-use intents and dispatch-result contract in `abr_engine/src/abr_engine/control/actions.py`; reject caller relevance flags, use phone script/wash branch without email basis, recheck current pointers under shared group/endpoint locks. [FR-021, FR-024]
- [x] T032 [US2] Implement recipient IANA timezone/holiday checks, licence review expiry and invitation-state policy in `abr_engine/src/abr_engine/compliance/calling.py`; unknown timezone blocks, weekdays9–18/Saturday9–17/no Sunday. [FR-012, FR-028]
- [x] T033 [US2] Implement finite retention/deletion jobs and restore quarantine replay in `abr_engine/src/abr_engine/compliance/retention.py`; raw30d/snapshots90d/profiles180d/pages90d/profile deletion30d/backups35d, scoped selected evidence7y. [FR-029]
- [x] T034 [US2] Prove deletion removes plaintext source aliases while HMAC group restrictions survive, backup expiry/tombstone replay/key rotation and both dispatch orderings in `abr_engine/tests/integration/test_restore_actions.py`; forged relevance denied, current phone allowed without email basis, in-flight external send never falsely recalled. [FR-024, FR-025, FR-026, FR-029, FR-037]

## Phase 5 — US3: Weekly ABR changes (P2; live expansion conditional)

Independent test: coherent synthetic baseline + update + same-day correction produce exact event set once, with no promotion after mixed/truncated/unsafe input. Production activation waits for G2 rules and G6 pilot decision; fixture engineering may proceed beforehand.

- [x] T035 [P] [US3] Create baseline/change/republish/repartition/unsafe XML and fault-boundary fixtures in `abr_engine/tests/fixtures/abr/`; include escaped names, absent GST and one-ABN multi-event transitions. [FR-003, FR-004, FR-005, FR-008]
- [x] T036 [US3] Implement resource discovery/coherence checks and resumable validated downloads in `abr_engine/src/abr_engine/ingest/abr_download.py`; re-read metadata, verify complete part inventory, hold uncertain generation. [FR-002, FR-003, FR-004]
- [x] T037 [US3] Implement hardened namespace-aware streaming parser and bounded Arrow writes in `abr_engine/src/abr_engine/ingest/abr_parse.py`; validate enums/counts/unique ABNs/canaries and clear siblings. [FR-005, FR-006]
- [x] T038 [US3] Implement immutable snapshot manifest/readback/upload lifecycle in `abr_engine/src/abr_engine/ingest/snapshots.py`; hash exact mapped-label/uncompressed-member projection from precision.md, exclude ZIP/retrieval metadata, prove current-cursor recompression no-op, same-date correction, historical A-to-B-to-A fresh occurrence and idempotent occurrence retry. [FR-002, FR-006, FR-041]
- [x] T039 [US3] Implement full-set output-bearing DuckDB diff in `abr_engine/src/abr_engine/diff/events.py`; baseline/no-op zero, new/reactivated exclusive, GST prior-row condition, cancellation observation and disappearance quarantine. [FR-008, FR-036]
- [x] T040 [US3] Implement reviewed deterministic rule loader/classifier in `abr_engine/src/abr_engine/classify/rules.py`; sorted BN/main/TRD, excludedOTN, literal evidence, synthetic mode and explicit production corpus gate. [FR-009]
- [ ] T041 [US3] Recover and review actual legacy corpus or obtain approved replacement, commit rules/evidence/100-record stratified precision sample in `abr_engine/config/rules.yaml` and `abr_engine/tests/fixtures/classification/`; keep production disabled until evidence exists. [FR-009, FR-040]
- [x] T042 [US3] Implement completed-month age proxy and ABR tiering in `abr_engine/src/abr_engine/qualify/abr.py`; future dates excluded and output never labels date as business creation or GST as turnover proof. [FR-010, FR-011, FR-040]
- [x] T043 [US3] Implement compare-and-swap source promotion, lock/lease ownership and crash resume in `abr_engine/src/abr_engine/ops/promotion.py`; transaction covers events/lead changes/cursor, Parquet holds full register. [FR-007, FR-035, FR-041]
- [x] T044 [US3] Prove all source crash points, concurrent source independence, parser-version rebaseline and byte-identical classification in `abr_engine/tests/integration/test_abr_recovery.py`; capture cursor/event counts after every injected fault. [FR-003, FR-005, FR-006, FR-007, FR-008, FR-009, FR-037, FR-041]

## Phase 6 — US4: Review, CRM and outcomes (P2)

Independent test: sort a synthetic sheet, send stale/duplicate edits and opt-out, then approve one tierA row; exactly that business exports once to mock CRM despite uncertain create. Implement T045–T047 before starting live pilot outcomes; CRM may remain disabled.

- [x] T045 [P] [US4] Add row-sort/version/idempotency and CRM uncertain-create/shared-endpoint cases in `abr_engine/tests/contract/test_delivery.py`. [FR-032, FR-033, FR-037]
- [x] T046 [US4] Implement immutable-row outcome API with closed vocabulary, dated meeting events and tri-state invitation evidence in `abr_engine/src/abr_engine/control/outcomes.py`; stale ordinary edits409, opt-outs commit despite conflict. [FR-028, FR-032]
- [x] T047 [US4] Implement protected Sheet columns, signed edit bridge, save acknowledgement and repair polling in `abr_engine/integrations/sheets_bridge.gs`; no endpoint/secret in activity log, opt-outs route immediately. [FR-025, FR-031, FR-032]
- [x] T048 [US4] Implement selected-tierA version-bound approval and CRM identity/outbox service in `abr_engine/src/abr_engine/export/crm.py`; no auto-enrolment, no endpoint-only merge, reconcile uncertain create before retry. [FR-013, FR-033, FR-042]
- [x] T049 [US4] Define/test all typed custom-field mappings and engine-owned tag add/remove behavior in `abr_engine/integrations/crm_fields.yaml` and `abr_engine/tests/contract/test_crm_mapping.py`; live values require sandbox gate. [FR-033]
- [x] T050 [US4] Implement distinct-group cohort attribution, dated attempts/meetings, activity ledger/API covering calls/research/wash/review/admin and full cash/time metrics in `abr_engine/src/abr_engine/export/metrics.py`; union overlapping time, sheet gaps auxiliary only; multi-signal group retains selected originating signal/fixed tier per cohort. [FR-034, FR-038]
- [ ] T051 [US4] Record four measured QBCC pilot weeks and owner expansion decision, then eight-week A/B decision in `abr_engine/ops/pilot-results.md`; pending data remains pending, zero-booking rules preserve denominators. [FR-038]

## Phase 7 — US5: Operator recovery and handover (P2)

Independent test: another developer performs one fixture run, repairs an interrupted source/CRM run and restores an isolated backup from documented commands; no live credentials required.

- [x] T052 [US5] Implement CLI exit/output/resume contracts and immutable redacted run manifest in `abr_engine/src/abr_engine/cli.py` and `abr_engine/src/abr_engine/ops/manifest.py`; every staged/deferred result accounted for. [FR-034, FR-039]
- [ ] T053 [P] [US5] Create single-scheduler systemd timers/services and host/DB lock/heartbeat handling in `abr_engine/ops/systemd/`; verify overlapping run exits safely and crash frees lock. [FR-007, FR-035]
- [x] T054 [US5] Implement complete alarm inventory, deduplicated delivery outbox and baseline/no-op exceptions in `abr_engine/src/abr_engine/ops/alarms.py`; each alarm gets one mocked trigger and runbook owner. [FR-035, FR-037]
- [ ] T055 [US5] Build disk/RSS preflight and20.5M-row synthetic benchmark in `abr_engine/tests/performance/benchmark.py`; measure full diff output/spill/promotedDB/WAL and25GiB headroom, not just join count. [FR-036]
- [x] T056 [US5] Write operator/developer recovery, retention, key rotation, access and environment guide in `abr_engine/README.md` and `abr_engine/ops/runbook.md`; execute independent fixture/recovery drill and attach evidence. [FR-026, FR-029, FR-035, FR-039]

## Phase 8 — Cross-cutting validation and release

- [x] T057 Add requirement-to-test manifest and CI checks in `abr_engine/tests/requirements.json` and `abr_engine/ops/verify.py`; all FR001–043 covered, no completed box without command/revision/result evidence, spec mirrors/hash consistent. [FR-037, FR-041, FR-043]
- [ ] T058 Complete applicable source smoke/vendor sandbox/security/capacity/legal/operational gates in `abr_engine/ops/acceptance/` and `abr_engine/ops/release-gates.md`; keep outreach/production off while any required evidence is missing. [FR-001, FR-027, FR-030, FR-036, FR-037, FR-040]
- [x] T059 Conduct independent final build review against constitution and `specs/001-abr-lead-engine/checklists/`, fix actual findings and rerun affected checks; record result in `abr_engine/ops/acceptance/release-review.md`. [FR-037, FR-041, FR-043]

## Dependencies and implementation strategy

Setup -> Foundation -> US1 synthetic pilot. US2 may be developed against seeded identities after Foundation; complete US2 and US4 minimum outcomes before live pilot. US3 synthetic development can run after Foundation but production activation waits for actual rule recovery and G6. US4 CRM waits for current export gate and US2; US5 documentation/alarms may proceed against fixtures, final drill follows implemented stories. Release waits for applicable gates, not a rating.

Parallel examples after their prerequisites: US1 T018 crawl safety fixtures and T014 QBCC fixtures touch separate files; US2 T028 suppression tests can accompany T032 calling logic; US3 T035 source fixtures can accompany T040 synthetic classifier; US4 T045 contract fixtures can accompany T049 mapping specification; US5 T053 systemd definitions can accompany T055 performance harness. `[P]` marks independently editable work once phase prerequisites are met, not permission to skip dependencies.

MVP is US1+US2+minimal US4 write-back on synthetic data, followed by the authorised QBCC pilot. US3 is not required for that pilot. Original59 tasks: Setup4, Foundation9, US1=14, US2=7, US3=10, US4=7, US5=5, final3. Coverage references map directly to canonical Rn through FR-nnn and the implementation acceptance manifest. A completed engineering task never closes a separate legal, vendor, infrastructure or commercial gate.

## Required contract supplement
[contracts/precision.md](contracts/precision.md) binds the existing tasks listed in each section. Implement its named negative/positive fixtures; do not create duplicate tasks for these already-mapped requirements.

## Phase 9: Convergence

Assessed 2026-09-09 after the authorised fixture implementation. Inventory:43FRs,17story scenarios,7technical success criteria,8plan decisions,5constitution principles. Six partial gaps (3buildable high,2buildable medium,1external high); no newly identified scope addition. Full production review remains incomplete. The application-root substitution `abn-leadgen/` follows the user's later explicit instruction.

- [x] T060 Add reviewer-visible likely-duplicate hints for shared domains/endpoints and corroborated names/addresses in `abn-leadgen/src/abr_engine/qualify/identity.py`, without automatic merging; exercise false and positive matches per FR-013/US1 (partial, HIGH).
- [x] T061 Finish actual monitor/API/pipeline observation wiring, redacted durable mock alarm delivery and current-month/expiry/retention regressions in `abn-leadgen/src/abr_engine/ops/monitor.py` per FR-034/FR-035/T054 (partial, HIGH).
- [ ] T062 Provision exact PostgreSQL16 native binaries for the CI restore drill and record bounded command failures/revision hashes in `abn-leadgen/ops/verify.py` per FR-036/FR-037/FR-039/T057 (partial, MEDIUM).
- [x] T063 Reconcile authorised implementation scope/root and executed task status with canonical/feature/plan/workflow/vault hashes, and update document validation to permit evidence-backed completion per FR-041/FR-043 (partial, MEDIUM).
- [x] T064 Execute the final combined checks, current report/API run and independent handover/recovery review; repair findings and record scored iterations in `abn-leadgen/ops/acceptance/` per FR-037/FR-039/SC-007/T059 (partial, HIGH).
- [ ] T065 Complete production-dependent adapter/source/host evidence once approved inputs exist: actual legacy or approved replacement rules, source schema/discovery smoke, vendor field/receipt contracts, AU host/capacity/security/Linux scheduler/access drill and G1-G7 authorisation per FR-001/FR-009/FR-027/FR-030/FR-033/FR-036/FR-040 (partial, HIGH; externally dependent; fixtures cannot satisfy it).

## Executed status closure

Final local verification: 408 tests passed, no failures/errors/skips; frozen install, Ruff, mypy and vault checks passed. 58 of 65 local engineering tasks are complete. The seven remaining tasks above retain their original obligations and are explicitly pending/partial in `task-evidence.json`. The [final build review](../../abn-leadgen/ops/acceptance/release-review.md) separates local engineering 92/100 from incomplete full-spec acceptance.

## Phase 10: Convergence

Live-release assessment, 9 September 2026: the user's request authorises implementing the remaining live capabilities. Existing G1–G7 evidence is still required; no approval or elapsed pilot time is inferred. Requirements-quality checklists pass (12/12 and 20/20). These tasks resolve concrete live gaps underneath T065; earlier fixture receipts remain historical.

- [x] T066 Implement bounded official QBCC/ABR catalogue inspection and a redacted executable release-readiness check in `abn-leadgen/src/abr_engine/ingest/catalogue.py`, `ops/readiness.py` and CLI; capture actual metadata separately from register-row ingestion per FR-002/FR-037/FR-040 (partial, HIGH).
- [x] T067 Implement explicit authentic QBCC schema mapping, missing-status handling, conservative category interpretation and migration regressions in `abn-leadgen/src/abr_engine/ingest/qbcc.py` per FR-005/FR-012/FR-041 (partial, HIGH).
- [x] T068 Recover the now-present literal legacy corpus without executing its extraction script; preserve exact order/hash and prepare the owner decision and 100-record precision review artifacts per FR-009/FR-040/T041 (partial, HIGH; owner review remains external).
- [x] T069 Implement and test a bounded GoHighLevel v2 transport and owner-restricted Sheet installation package; retain live writer blocks until actual identity, mapping and suppression sandbox evidence is available per FR-026/FR-031/FR-032/FR-033 (partial, HIGH).
- [x] T070 Prepare a reproducible production bundle using supported commands, one scheduler and explicit backup/restore/access dependencies; validate fail-closed preflight without claiming installation on an unselected host per FR-026/FR-029/FR-035/FR-039 (partial, HIGH).
- [ ] T071 Connect approved real ingestion, current licence/identity review, protected Next.js worklist, actual-editor bridge, CRM drain and suppression propagation end to end on the identified AU host; prove each represented live result and the full workflow per FR-001/FR-012/FR-025/FR-030/FR-031/FR-033/FR-037 (partial, HIGH; release 010 has actual QBCC intake/review, website-phone evidence, verified intake cleanup and an enabled GHL account with synthetic provider contract checks under separate delegated-owner decisions. No real business is selected or exported. Live DNCR receipt-format implementation, genuine phone clearance/qualification and individual approval, the disabled Google staff workflow, real CRM/suppression outcomes, independent custody/backup restore, broader ABR implementation/accuracy and measured pilot evidence remain required; see implementation-status.md).
