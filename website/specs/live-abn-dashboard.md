# Live ABN dashboard handover

The staff page remains `/abn-lead-gen/dashboard`. It uses the current Maintain Media Clerk session, checks the session and server-managed account role again on every API request, and calls the Australian Python service from the Next.js server.

## Connection and authority

The Next.js server needs `ABN_ENGINE_MODE` set to `pilot` or `production`, `ABN_ENGINE_TRANSPORT=remote`, an explicit HTTPS DNS origin in `ABN_ENGINE_ORIGIN`, and the separate `ABN_ENGINE_ASSERTION_KEY`. The engine uses the same dedicated assertion key. Existing Clerk and CSRF configuration is also required. No key belongs in a `NEXT_PUBLIC_` variable or browser bundle.

Each service assertion lasts at most 60 seconds and binds the current Clerk user ID, granted scopes, HTTP method, path, exact request body, request ID and idempotency key. Browser cookies and Clerk credentials are not forwarded to the engine. Responses reflecting an assertion or service key are rejected.

A server-managed `role: admin` grants dashboard administration and operator actions. Additional `leadGenScopes` values `reviewer`, `compliance` and `owner` must be explicitly assigned in Clerk public metadata. User-editable metadata cannot grant access. Reviewer authority is required for licence, identity, permission and CRM decisions.

The private Google Sheet has a separate installed authority. Only its workbook-bound identity may call `GET /v1/sheets/worklist`; website assertions cannot use that endpoint. The existing Sheet write routes use its actual named editor, separate signing and HMAC secrets, a current registry, and per-operation authorization.

## Implemented staff workflow

- Read actual stored business records, source timestamps, restrictions, worklist outcomes, durable run state and readiness. An empty database stays empty. Closed approvals remain visible as blocked.
- Save the default source and spending ceiling. The saved ceiling also constrains new paid budget reservations; lowering it does not erase prior reserved or settled spending.
- Request and follow one durable QBCC or ABR run. The runtime decides admission using current source and environment evidence; a closed gate returns a held receipt without source collection. Combined live runs are unavailable; the synthetic fixture workflow keeps its combined option.
- Load accepted QBCC records in pages of 100 and record an explicit current licence check against the snapshot and row digest.
- Record a website identity decision with independent supporting references; request a bounded phone-only collection from that approved website after an explicit dated terms review. The live form requires the engine's current policy to permit only mobile and landline fields; missing, expired or unrecognised policy does not enable submission. It never supplies a request-side channel override.
- Inspect private captured evidence as escaped text and record an inferred email-permission assessment. Collected email addresses still need delivery verification; public availability does not create permission. Phone details still need the separately configured DNCR workflow.
- Record version-bound worklist outcomes and explicit CRM approvals; download the current masked worklist CSV.
- Record an immediate do-not-contact restriction. Until a durable suppression receipt is confirmed, other actions for that business pause and the same request can be retried.

Outcome, identity and contact-permission forms retain the revisions that accompanied their drafts. Background refreshes do not silently authorize overwriting a later reviewer decision. Users can explicitly reload the latest saved form values.

The reviewer first opens QBCC source review, checks the current active licence against the exact business, then saves the website domain decision. The website form asks for an HTTPS homepage ending in `/`, a terms evidence reference and a review time within 30 days. The backend also enforces current identity, geography, queue, cooldown and restriction checks. Collection does not establish permission to call or produce an outreach-ready worklist.

Each business can carry its last saved `website_job` receipt. The form restores this receipt after reopening or refreshing the dashboard and resumes polling queued/running work; a saved active request disables duplicate submission. Specific website errors explain the relevant review step, and validation errors do not incorrectly refer to the spending limit. Phone-only extraction does not imply that ordinary encrypted page captures contain no incidental email text.

GoHighLevel hand-off has a visible per-business status even before a worklist row is selected. Its reviewer-only `crm_handoff` projection carries current eligibility, allowed approve/reject decisions, restrictions and the saved outbox status; it contains no endpoint, provider URL or credentials. Missing or unknown status cannot enable approval. The form binds the explicit decision and required reason to the selected row and opening version. Approval saves a request for the worker, not a browser-side dispatch. Pending, uncertain, failed and verified transfers are labelled separately. A verified transfer does not mean a message was sent or a call is permitted. Enabling the account does not individually approve the existing discovery records or make an unverified phone contact eligible.

The public `/business-research-notice` route is linked from the site footer and the live workspace. It uses the existing published Maintain Media contact, describes QBCC plus manually reviewed own-domain website research, the phone-only/no-outreach scope and finite retention. An individually approved eligible GoHighLevel transfer is limited to a business summary and one reviewed phone, with Do Not Disturb on. The notice identifies published US storage and US/India support, uncertain optional-provider routing, and the absence of a verified provider-backup expiry. Transfer does not restart engine retention periods or create a seven-year evidence archive; unnecessary engine-owned CRM fields are cleared without claiming immediate erasure from all provider backups. Google Sheets transfers remain disabled. The notice does not claim all-Australian processing, a registered legal entity, individual notification, legal certification or adviser approval. Publication and actual policy activation remain separately verified release steps.

## Blocked setup guidance (R39)

Each blocked source, GoHighLevel and broader ABR row explains its next step and the responsible person. A disabled capability alone does not identify missing approvals: the UI says the engine has not checked their details in that response. When specific closed gates are returned, it explains those reported checks. Exact engine details remain available in an expandable section; unknown states and reasons stay unverified. The separate delegated early ABR validation decision can permit source validation before the later measured pilot finishes. It does not waive the 100-record matching review or provide the required live implementation, capacity and recovery checks. Readiness descriptions cannot enable a feature, change its approval or alter action availability.

Responsibility is expressed by role rather than requiring a named individual. Collection guidance supports the business owner's authorised delegate and the limited QBCC-only pilot; website, vendor and ABR decisions remain separate. An approved state and its explanation come from the engine, without a frontend claim that further owner evidence is missing.

A held job with `QBCC_SOURCE_HTTP_REJECTED` explains that the publisher did not return a usable file for that run and no records from that run were accepted. Run history and request failures share this explanation. It does not describe an approval failure, remove earlier records, imply a permanent publisher outage or substitute demo data.

Accepted nonfixture QBCC snapshots and stored QBCC leads display attribution in the worklist and source card: State of Queensland (Queensland Building and Construction Commission), a link to the official Licensed Contractors Register resource, [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/), and a formatting/filtering and no-endorsement note. Fixture or uncollected records do not receive that provenance claim. The existing source catalogue contract accepts only the reviewed CC-BY-4.0 licence identifier; a changed licence requires source review before acceptance.

## Validation and limits

### ABR source validation UI, 11 September 2026

Every live run control and its request handler requires the selected source's explicit `can_run: true`, an empty current `reason_codes` list and an available worker. Missing fields cannot borrow another source's authority. Setup displays genuine accepted record counts, publication dates and source attribution. When the publisher supplies an extract time without a timezone, the raw value is labelled as such; the frontend never invents UTC.

Persisted job and run receipts retain phase, result and reasons after refresh. A committed first baseline with zero events and candidates is labelled as a starting reference list, not newly formed businesses. Unchanged publications, later registration differences and missing result details have separate explanations. Classification disabled stays distinct from collection enabled. Expired prior analytical files require explicit authorised baseline recovery; no automatic rebaseline or false new-business events are offered in the dashboard.

The public notice was extended and published before ABR intake to disclose the public ABN Lookup bulk fields, possible individual names, private validation/baseline/comparison and matching review, ABR attribution under CC BY 3.0 Australia, raw30-day/analytical90-day/abandoned7-day retention, and absence of ABR phone/email or new website/vendor permission. Existing phone-only, GoHighLevel and no-outreach limits remain separate.

The live API tests use isolated PostgreSQL, synthetic test keys and explicitly synthetic records. They cover real persistence, individual actor attribution, suppression commit/replay, scope denial, empty live state, restore quarantine, request tampering, Sheet authority separation and effective spending limits. Frontend tests cover fresh Clerk authority, request-bound assertions, restricted routes, credential reflection, honest live/fixture rendering and concurrent permission drafts. Production compilation and linting are separate checks.

These checks are engineering evidence. They do not establish source/privacy/vendor approval, a successfully installed private Sheet or GHL account, a signed-in production browser journey, backup restore evidence, a measured pilot, or permission to send messages or make calls. Those remain separately verified rollout requirements. Fixture mode continues to use its existing synthetic gateway and cannot be accepted as a live response.
