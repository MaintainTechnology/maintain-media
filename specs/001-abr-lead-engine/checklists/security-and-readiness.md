# Security and Readiness Requirements Checklist: ABR Lead Engine
Created2026-09-08. Feature: [spec.md](../spec.md).
Reviewer-owned custom Spec Kit checklist. Generated unchecked; assess the writing, not software.
A checked item means its requirement is complete/consistent, never that its implementation passed.

- [x] CHK001 Are coherent generations and same-day corrections defined without date-only identity? [R2–R8] Evidence: R2-R8 and plan Observe/Seal define content manifests, UUIDs, coherent inventory and hold-on-uncertainty.
- [x] CHK002 Are rollback/crash/replay boundaries and durable delivery states specified? [R7/R33] Evidence: R7, plan Promote/Deliver and CRM outbox specify crash boundaries, CAS and reconciliation.
- [x] CHK003 Are rule recovery, deterministic ordering and a total ranking order specified? [R9/R14] Evidence: R9/R14 and plan Determinism specify missing-rule gate and one cross-source total ordering.
- [x] CHK004 Are website identity evidence and ambiguous-match behaviour explicit? [R16] Evidence: R16 distinguishes exact IDs from reviewed corroboration and blocks ambiguous matches; freshness follow-up is RV-03.
- [x] CHK005 Are SSRF, redirects, robots, DNS, size, time and crawl budgets bounded? [R17] Evidence: R17 bounds ports, IP/redirect/DNS safety, wildcard robots, deadlines, page sizes and request budgets.
- [x] CHK006 Are provenance relationships bound to the exact contact/channel? [R20] Evidence: Resolved RV-05: data model constrains contact/lead/channel and identity/lead/domain; T007 requires wrong-binding rejection.
- [x] CHK007 Are consent evidence, unknown outcomes and express/inferred branches distinct? [R21] Evidence: Resolved RV-02: immutable assessment_seq/current pointers select later blocking decisions; express and inferred paths differ explicitly.
- [x] CHK008 Do exports avoid implying reusable authority and require action-time checks? [R22/R24] Evidence: Resolved RV-03: R16/R24 and consume contract recheck current lead/domain identity, licence review, evidence and suppression; candidate labels are not authority.
- [x] CHK009 Does the phone policy specify latest wash, expiry, format/account dependency and cost? [R23] Evidence: R23/data model select latest wash; contract defines receipt import, normalized membership and disabled live adapter gate.
- [x] CHK010 Are acknowledged opt-outs durable across aliases, projections and restoration? [R25/R29] Evidence: Resolved RV-04: reason-specific append-only suppression and cancellation resolution preserve opt-outs; T028/T034 cover race and restore.
- [x] CHK011 Are authorisation, sensitive-data access and key rotation obligations specified? [R26] Evidence: R26 and API envelope require actor scopes, evidence-access audit, encryption and dual-token rotation.
- [x] CHK012 Are collection/notice/overseas obligations gated without claiming legal approval? [R27/R30] Evidence: R27/R30 and G1/G5 require actual source/notice/processor assessment; document explicitly disclaims approval.
- [x] CHK013 Are finite retention defaults consistent for each artifact and backup? [R29] Evidence: R29/data-model retention table set artifact limits, restricted evidence purpose, backup expiry and quarantined restore.
- [x] CHK014 Are concurrency, uncertain billing, FX, prepaid costs and rollover defined? [R19] Evidence: R19 and budget tables define atomic micro-AUD reservations, uncertainty, FX/tax/buffer and reservation-month ownership.
- [x] CHK015 Are immutable worklist identity, conflicting edits and opt-out routing explicit? [R31/R32] Evidence: PATCH contract binds immutable row IDs and expected version; opt-out survives stale-outcome conflict.
- [x] CHK016 Are CRM approval, uncertain-create reconciliation and shared endpoints covered? [R33] Evidence: R33/CRM contract bind human approval, reconcile uncertain create and hold shared-endpoint identity conflicts.
- [x] CHK017 Are capacity claims separated from unrun performance evidence? [R36/R37] Evidence: R36/R37 explicitly separate candidate capacity and stretch target from unexecuted evidence.
- [x] CHK018 Are pilot dependencies, time/cost measurement and expansion decisions defined? [R38] Evidence: Resolved RV-01: operator_activity plus API/T050 measure all work categories and union overlaps; sheet edits auxiliary; R38 defines pilot decisions.
- [x] CHK019 Do requirements map to concrete tasks and acceptance evidence? [R43] Evidence: tasks.md contains 59 unchecked tasks linked to all FR-001–043, story acceptance scenarios and evidence tasks T057–059; execution remains future work.
- [x] CHK020 Are historical claims, missing files and incomplete releases labelled honestly? [R40/R41] Evidence: R40/research inventory label absent corpus, historical counts/benchmarks and outstanding release evidence.



