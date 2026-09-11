# HighLevel review for the proposed DND-only hand-off

Research checked on 11 September 2026. This is a factual vendor review and a
proposed operating boundary, not a signed contract, legal opinion, installation
certificate or release approval. The user has expressly delegated the decision
to enable a limited GHL hand-off; waiting for Jon is not a requirement for that
delegated decision. Actual account safeguards and per-record approval still matter.

## Published vendor facts

| Source | Observed fact | Limit of this evidence |
| --- | --- | --- |
| [HighLevel terms](https://www.gohighlevel.com/terms-of-service), updated June 2026 | The terms govern business use, allocate customer responsibilities for lawful data use, and describe third-party and AI features. | We have not verified Maintain Media's contracting entity, an account-specific acceptance record or a separately signed agreement. This review does not sign or accept a contract. |
| [Customer Data Processing Addendum](https://www.gohighlevel.com/data-processing-agreement), updated July 2026 | The published DPA covers customer data, includes an Australian jurisdiction provision, provides processor safeguards and deletion arrangements, and excludes isolated backup copies from its deletion section. | These are provider commitments, not our security test results. No definite provider backup expiry was found. The engine's 35-day backup setting does not apply to GHL's backups. |
| [Subprocessor list](https://www.gohighlevel.com/sub-processors), last modified September 2025 | Google Cloud and AWS data storage are listed in the **United States**. HighLevel India provides service/support in **India**; LeadConnector provides communication/support in the **United States**. The list also includes US communications, analytics, support, payments and AI vendors. | It describes subprocessors that may be used, not this account's actual routing. No Australian-only CRM storage commitment is evidenced. Further subcontractor and support-access locations are not fully verified. |
| [OAIC APP 8 guidance](https://www.oaic.gov.au/privacy/australian-privacy-principles/australian-privacy-principles-guidelines/chapter-8-app-8-cross-border-disclosure-of-personal-information) | Overseas handling requires consideration of applicable disclosure safeguards and accountability. | Owner delegation is not an individual's consent, an APP exception, or a finding that the Privacy Act does not apply. No qualified applicability or compliance assessment has been obtained. |

The earlier successful page inspection supports the subprocessor facts above;
two later refresh attempts timed out. Do not substitute a guessed country or
claim continuous availability. Recheck the published list when finalising the
account decision and when its current evidence expires.

## DND and automation are separate controls

[HighLevel's DND guide](https://help.gohighlevel.com/support/solutions/articles/48001214849)
describes global and channel-specific settings and distinguishes outbound from
inbound restrictions. Its [DND workflow action](https://help.gohighlevel.com/support/solutions/articles/155000003270-workflow-action-dnd-contact)
can enable **or disable** DND. DND is therefore one safeguard, not proof that a
record cannot enter automation or reach another processor.

API-created records can start a [Contact Created workflow](https://help.gohighlevel.com/support/solutions/articles/155000002486-workflow-trigger-contact-created).
Adding or removing tags can start [Contact Tag workflows](https://help.gohighlevel.com/support/solutions/articles/155000002482-workflow-trigger-contact-tag).
The narrow installation must demonstrate that its record creation, changes,
engine tags and DND changes cannot start a send, call, AI action, webhook,
campaign, workflow enrolment or paid activity. Six previously visible Draft
workflows are bounded historical evidence, not an account-wide current pass.

Use the adapter's documented [2023-02-21 Create Contact contract](https://marketplace.gohighlevel.com/docs/2023-02-21/ghl/contacts/create-contact/).
The unversioned page now defaults to v3; it must not silently change the installed
API version. Global duplicate handling must remain unchanged. An endpoint match
must never authorise modifying another business. A response check after a
possibly merging request cannot undo a wrong update.

## Proposed narrow disclosure and controls

Only an individually approved, selected tier-A worklist row may leave the engine.
Its current row version, business identity, suppression, phone verification,
locality/timezone and genuine current DNCR evidence must pass the existing
rules. No test or delegated vendor decision may invent these facts. Phone-only
scope must be enforced in the live adapter; a setting or a UI label alone is
insufficient. Approval remains internal research hand-off, never permission to
call or message, and HighLevel DND remains enabled.

Transfer only the mapped business summary, a single eligible phone, opaque
engine identity and cautious review metadata. Do not transfer email values,
full website HTML, private evidence excerpts, full-register snapshots, physical
addresses, invented personal names or unrelated contact fields. Do not enable
Google Sheets, communication services, AI, enrichment or another integration.
HighLevel's ordinary internal processing still follows its service terms; the
absence of an explicit AI request is not a warranty about every internal vendor.

Before any actual business record: verify the exact location and 13 field IDs;
current complete automation inventory and isolation; group lookup; non-mutating
collision handling; uncertain-create reconciliation; unrelated-tag preservation;
actual clearing of the owned projection; and DND readback. Record these against
the exact configuration, release, actor, time and expiry. Synthetic checks must
use no real person's endpoint and cannot activate outreach. A metadata-only token
cannot provide this evidence.

Removal must preserve the engine group identity and minimum suppression state,
clear unnecessary marketing fields, and verify the remote result. It must remain
available after new hand-offs are disabled. Keep the existing 180-day unworked
profile clock and 30-day unnecessary-field limit after suppression or
disqualification; do not reset them by exporting. Local page evidence stays
under the existing 90-day/no-seven-year-archive policy. Verify the actual remote
cleanup path separately, and never claim complete provider-backup erasure.

The public business research notice must first describe the limited GHL recipient,
United States and India, the routing/backup uncertainties, retained engine
control and the existing request contact. A public page is not proof that each
person received notice or that APP 5 requirements are satisfied.

The [draft owner decision](ghl-dnd-pilot-owner-draft-20260911.json) and
[proposed canonical amendment](ghl-dnd-pilot-amendment-draft-20260911.md)
remain pending account controls, tests and public notice readback. They must not
be registered as passed release gates.
