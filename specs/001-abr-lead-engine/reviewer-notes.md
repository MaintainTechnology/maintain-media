# Independent requirements review — ABR Lead Engine v4.0

Reviewed 8 September 2026. Scope: canonical specification, Spec Kit spec/research/plan/data model/interface contract and the custom readiness checklist. This reviews the written design only. No application, database, performance, legal or live-source acceptance test was performed.

## Findings sent for correction

| ID | Priority | Finding | Required resolution |
|---|---|---|---|
| RV-01 | Medium | Interface spreadsheet activity metric calls gaps under 15 minutes “worked time”, while R38/SC-008 require calls, research, wash and administration to be measured too. | Treat edit activity as auxiliary telemetry; define an actual activity/time ledger and aggregate all operator work. |
| RV-02 | Medium | `contact_basis` says latest supersedes prior without a deterministic current-assessment rule. An older pass must not survive newer fail, unknown or withdrawal evidence. | Add immutable assessment order/current pointer and require latest applicable assessment at export/consume, with negative test. |
| RV-03 | Medium | `domain_identity.expires_at` lacks a stated default/selection rule; current identity and positive QBCC licence review are not individually explicit in both API gate paths. | Define identity freshness and exact lead/domain binding; both export and consume require it, with positive QBCC status/identity review no older than 30 days. |
| RV-04 | Medium | `do_not_market` model states cancellation never disappears on reactivation, whereas canonical R25 permits reviewed resolution of cancellation-only restriction. | Model individual restriction reasons; only a reviewed cancellation resolution can remove that reason, never opt-out/complaint. |
| RV-05 | Medium | Composite contact/channel provenance keys are good, but `domain_identity_id` is not explicitly bound to the provenance contact's lead/domain. | Constrain identity/lead/domain together and validate captured-page domain; wrong-lead identity cannot establish permission. |
| RV-06 | Pending authoring | `tasks.md` was not yet present on this review pass. | Review requirement-to-task/acceptance traceability once authored; do not mark CHK019 satisfied merely from the planned filename. |

## Source and legal truth assessment

The revised writing incorporates the material corrections from [primary-source checks](../abr-review-source-checks.md): GST and licence signals no longer assert actual turnover, DNCR automation cost is disclosed, manual wash is an explicit pilot choice, 6pm is correctly labelled business policy, APP7 interactions and APP5 timing require reviewed policy, and public email/verification are not treated as consent. Historical source counts and benchmarks are no longer newly verified claims. These corrections are satisfactory as written; they do not approve a live collection or marketing activity.

The control design properly separates a candidate export from a single-use action check, acknowledges external dispatch races, treats consent as evidence-backed with unknown states, and preserves opt-outs through recovery. The findings above concern completing that design consistently across its contracts.

## Rating method

This independent review does not substitute its own number for the LLM Council rating. A final specification-quality score of 9 or above should be assigned only after substantive findings and traceability gaps are resolved and the reviewed revision is identified. Application readiness and legal/commercial release remain unproved regardless of document score.

## Resolution pass

Completed after author corrections on 8 September 2026. Re-read canonical R16/R20/R21/R25, data-model identity/provenance/basis/suppression/activity entities, revised API contracts and all 59 tasks.

- **RV-01 resolved:** operator activity ledger/API and T050 include calling, research, wash, review and administration, with overlapping intervals unioned. Spreadsheet edits are auxiliary telemetry.
- **RV-02 resolved:** immutable assessment sequence and transactional current pointer prohibit older passes overriding newer blocking decisions; reviewer API and T023 make this explicit.
- **RV-03 resolved:** exact lead/domain identity has 90-day maximum freshness; both export and consume require the current approval and positive QBCC licence/status identity evidence no older than 30 days.
- **RV-04 resolved:** reason-specific suppression records and cancellation-resolution endpoint preserve every unrelated opt-out/complaint block.
- **RV-05 resolved:** provenance constrains contact/lead/channel and identity/lead/domain, validates the captured domain, and T007 requires wrong-binding rejection on real isolated PostgreSQL during implementation.
- **RV-06 resolved:** all 59 tasks are present and unchecked; task references cover all 43 feature requirements. Story scenarios, specific positive/negative/recovery test tasks and T057–059 define future acceptance evidence.

**Disposition:** all 20 custom checklist criteria are satisfied as requirements-writing checks. No unresolved substantive defect from this review remains. This is a review of the specified design, not proof that its controls work. The implementation, integration, production, legal and commercial gates remain pending.
