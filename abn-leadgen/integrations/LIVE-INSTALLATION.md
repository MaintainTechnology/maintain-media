# Staff workflow installation

Current state, checked 9 September 2026: the local fixture worklist and outcome
control API work, but no Maintain Media private Google Sheet or GoHighLevel
sub-account has been identified and installed. No remote contacts or messages were
created during this work. The available Google Drive connector belongs to a
different organisation; it must not receive Maintain Media business data.

## Google Sheet

1. Connect the correct Maintain Media Google account. Record the Sheet ID, tab ID,
   owner and named reviewers/operators. Keep general access **Restricted**; do not
   grant domain-wide or public-link access. Record processor/support countries and
   the reviewed disclosure basis required by specification R30/G5.
2. Populate a private Sheet from the actual generated `worklist.csv` contract.
   Do not change immutable UUID/version columns or invent review outcomes.
3. Create a **standalone Apps Script project** owned by the service operator, with
   no reviewer edit access to the script. Add `sheets_bridge.gs` and
   `sheets_install.gs`. A reviewer-editable bound script would expose privileged
   code and Script Properties to its editors; do not use that deployment model.
4. Set non-secret Script Properties `INSTALLER_EMAIL`, `SPREADSHEET_ID`,
   `WORKLIST_SHEET_ID`, and `ALLOWED_EDITOR_EMAILS` (a JSON array of named allowed
   users). `INSTALLER_EMAIL` must also be the Sheet's actual owner; another owner
   could always bypass protected ranges. `WORKLIST_SHEET_ID` is a canonical
   decimal string (`0` is valid, blank is not). Secret properties are
   `SERVICE_TOKEN` and `BRIDGE_SECRET`; set the
   HTTPS `API_BASE_URL` to the actual restricted control endpoint. Never put
   secrets in cells, source control, edit logs or a public web app.
5. As the configured owner, run `installPrivateWorklist()`. It checks named-only
   sharing, protects engine columns, creates at most one mapped edit trigger and
   one five-minute repair trigger, and leaves `ENABLED=false`.
6. Install the server's bridge registry: HMAC secret plus actual editor-to-scope
   mapping. The present `control/api.py` reads `app.state.bridge` but no production
   loader supplies it yet. The live authentication key/JWT issuance path must be
   implemented and verified before the bridge can run. A service token alone must
   never stand in for a reviewer identity.
7. Verify genuine editor identity in an isolated test Sheet. Google may omit the
   edit-event user under some account/security conditions. Missing identity must
   keep the edit unsaved; do not substitute the trigger owner's email. Test one
   valid edit, sorted rows, stale versions, duplicate UUIDs, denied actors,
   duplicate event replay, outage/recovery and immediate suppression receipt.
   Measure actual propagation latency. Enable only after these receipts and the
   corresponding policy decisions exist.

The current installer is local source, not an installed remote project. Google
Drive document tools can create/format a Sheet but do not install or authorise Apps
Script triggers. Owner OAuth and the correct account are still required.

## GoHighLevel

The real `export/gohighlevel.py` transport is implemented separately from the
fixture worker. It uses the documented `2023-02-21` API version on
`services.leadconnectorhq.com`. The unversioned official documentation currently
defaults to v3; changing versions requires renewed contract tests and a sandbox
receipt rather than silently changing the request header.

Prepare the intended location's **Private Integration Token** in a secret manager
with location metadata, contact read/write and contact custom-field read scopes.
Supply it to the process as `ABR_GHL_TOKEN`. The adapter and preflight do not load
`.env` files and never echo credentials or vendor response bodies.

Create 13 contact custom fields in the isolated location. Map `group_id`,
`contact_id`, `channel`, `abn`, `signal`, `tier`, `industry`, `entity_class`, `state`,
`website`, `positioning_notes`, and `basis_summary` as TEXT or LARGE_TEXT; `score`
must be NUMERICAL. Preserve ABNs as text. The extra contact/channel identifiers
allow an independently fetched record to be reconciled against the exact approved
internal projection. Store the actual IDs in a restricted copy of
`gohighlevel.example.yaml`, keeping `allow_writes: false`.

Run metadata verification from `abn-leadgen/`:

```text
uv run python ops/ghl_preflight.py --config /etc/abr-engine/gohighlevel.yaml
```

This reads only location and field metadata. It reports missing/wrong-type fields
and never calls contact create/update, enrolment, messaging or workflow endpoints.
A successful preflight is **not** a production release receipt.

Before enabling contact writes, review the isolated sub-account's **Contact
Created**, **Contact Changed**, **Contact Tag** and **Contact DND** triggers and
connected automations. HighLevel explicitly documents that API contact creation
and tag changes can trigger workflows. Setting `dnd=true` and avoiding enrolment
endpoints do not prove that no remote workflow will run. Record an account-specific
isolation decision and observed sandbox execution logs.

The transport keeps DND enabled, creates instead of endpoint-based upsert, checks
the returned location/group identity, and uses add/remove tag endpoints to preserve
unrelated tags. It never automatically retries a create. A transient write or
unknown response must return to the durable outbox for reconciliation. Group
search uses the configured custom-field equality filter, requires a complete
response, and validates every returned group ID. The current advanced-search docs
delegate the detailed body to an external ClickUp document; the exact field filter
and null-clearing behaviour still need a real account sandbox receipt.

### Required worker wiring before production

- Extend the typed mapping loader to validate approved live field IDs, location,
  pinned contract version and current G5 evidence. The old `crm_fields.yaml`
  remains a fixture mapping; changing it to `live_enabled=true` is insufficient.
- Thread the selected mapping through `projection`, approval and dispatch. Replace
  the hard-coded `fixture` location only after the approved mapping is available.
- Construct `GoHighLevel` with a current `write_guard` that rechecks the precise
  outbox approval/version, policy, suppression and account automation isolation
  before **every** HTTP mutation, including tag changes. A token or an enabled flag
  alone cannot permit writes.
- Wire the real provider into **both** CRM outbox and suppression propagation,
  including account-specific null-clearing and read-back receipts. Existing
  `LIVE_CRM_DISABLED`, `CRM_SANDBOX_MAPPING_PENDING` and
  `LIVE_PROPAGATION_DISABLED` remain deliberately enforced until this combined
  path is verified. Do not remove only the CRM guard.
- Make durable retry scheduling respect `GHLRetryableError.retry_after`, preserve
  uncertain dispatched operations, and bound dead-letter attempts. The adapter
  applies at most three bounded retries to read-only calls, including contact
  search; mutations receive exactly one network attempt.
- Test allowed tier A, denied/revoked approval, wrong location/group, duplicate or
  shared endpoint, timeout after actual create, incomplete search, mapping drift,
  unrelated tag preservation, failed clearing and suppression during dispatch.
  Verify the actual remote record before reporting success. Then record G5/G7.

## Local verification

The implementation passed 39 focused tests on 9 September 2026: 38 mocked HTTP
cases and one executable Apps Script harness covering owner authority, private
sharing, immutable protections, repeated installation and exact workbook/tab
dispatch. Ruff and mypy passed for the new Python source. The preflight command
with the untouched template returned `GHL_CONFIGURATION_INVALID` before network
access. These are engineering checks, not Google/GHL installation receipts.

## Official contract references

Checked 9 September 2026:

- [Create contact](https://marketplace.gohighlevel.com/docs/2023-02-21/ghl/contacts/create-contact/)
- [Update contact and tag replacement behaviour](https://marketplace.gohighlevel.com/docs/2023-02-21/ghl/contacts/update-contact/)
- [Get contact](https://marketplace.gohighlevel.com/docs/2023-02-21/ghl/contacts/get-contact/)
- [Custom field metadata](https://marketplace.gohighlevel.com/docs/2023-02-21/ghl/locations/get-custom-fields/)
- [Contact search](https://marketplace.gohighlevel.com/docs/ghl/contacts/search-contacts-advanced/)
- [Rate limits](https://marketplace.gohighlevel.com/docs/2023-02-21/other/rate-limits/index.html)
- [Contact-created workflow behaviour](https://help.gohighlevel.com/support/solutions/articles/155000002486-workflow-trigger-contact-created)
- [Contact-tag workflow behaviour](https://help.gohighlevel.com/support/solutions/articles/155000002482-workflow-trigger-contact-tag)
- [Installable Apps Script triggers](https://developers.google.com/apps-script/guides/triggers/installable)
- [Apps Script event user restrictions](https://developers.google.com/apps-script/guides/triggers/events)
- [Bound scripts inherit container access](https://developers.google.com/apps-script/guides/bound)
