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
- Request and follow a durable QBCC run. The runtime decides admission using current source and environment evidence; a closed gate returns a held receipt without source collection.
- Load accepted QBCC records in pages of 100 and record an explicit current licence check against the snapshot and row digest.
- Record a website identity decision with independent supporting references; request a bounded collection from that approved website after an explicit dated terms review.
- Inspect private captured evidence as escaped text and record an inferred email-permission assessment. Collected email addresses still need delivery verification; public availability does not create permission. Phone details still need the separately configured DNCR workflow.
- Record version-bound worklist outcomes and explicit CRM approvals; download the current masked worklist CSV.
- Record an immediate do-not-contact restriction. Until a durable suppression receipt is confirmed, other actions for that business pause and the same request can be retried.

Outcome, identity and contact-permission forms retain the revisions that accompanied their drafts. Background refreshes do not silently authorize overwriting a later reviewer decision. Users can explicitly reload the latest saved form values.

## Blocked setup guidance (R39)

Each blocked source, GoHighLevel and broader ABR row explains its next step and the responsible person. A disabled capability alone does not identify missing approvals: the UI says the engine has not checked their details in that response. When specific closed gates are returned, it explains those reported checks. Exact engine details remain available in an expandable section; unknown states and reasons stay unverified. The first QBCC pilot does not inherit the later ABR four-week expansion decision or 100-record matching review. Broader ABR also needs its live feed completed and tested; approval alone does not provide that implementation. Readiness descriptions cannot enable a feature, change its approval or alter action availability.

## Validation and limits

The live API tests use isolated PostgreSQL, synthetic test keys and explicitly synthetic records. They cover real persistence, individual actor attribution, suppression commit/replay, scope denial, empty live state, restore quarantine, request tampering, Sheet authority separation and effective spending limits. Frontend tests cover fresh Clerk authority, request-bound assertions, restricted routes, credential reflection, honest live/fixture rendering and concurrent permission drafts. Production compilation and linting are separate checks.

These checks are engineering evidence. They do not establish source/privacy/vendor approval, a successfully installed private Sheet or GHL account, a signed-in production browser journey, backup restore evidence, a measured pilot, or permission to send messages or make calls. Those remain separately verified rollout requirements. Fixture mode continues to use its existing synthetic gateway and cannot be accepted as a live response.
