# Staff workflow installation

Current state, checked 11 September 2026 (Manila): the user identified the ABN Leads Gen
Sheet (`1-PEySaH7AAod3hoFqZZf7zMYMWyQ3qIAWQzxnrq6K58`), its owner
`jeph@quotemax.com.au`, and GHL location `xHZFHMOE476t5CxY9vCG`. The read-only
Google metadata check initially found public link editing (`anyone: writer`) and a
connector account from a different organisation. The owner subsequently signed in
directly in the browser. General access was changed to **Restricted** and owner-only
sharing was read back. The wrong connector is not used. No business data or remote
contacts were published by this integration subtask and no messages were sent.
See the dated evidence under `ops/acceptance/live-integration-20260910/`; actual
browser installation evidence now supersedes the historical preflight.

At **2026-09-10 16:06:14 UTC** (11 September, 00:06 Manila), the owner-run
`prepareMaintainMediaWorklist()` completed in the standalone Google project
[Maintain Media ABN Worklist Bridge](https://script.google.com/home/projects/1DzYHoVQ_X2_CoC6Dw4LaTXaXAYPRWBH2qPc34rEpY8nKtOGJFR2ZOmdn/edit).
The protected **ABN Worklist** tab is `gid=2107750955`; all 29 headers were read
back, the original ABN tab was preserved, and the edit/repair triggers are installed.
Both workbook and standalone script are Restricted to Jeph alone. The saved Google
source matches the reviewed full bundle after line-ending normalization.
Exactly five non-secret properties were read back, including `ENABLED=false`.
At that first installation, no endpoint, signing secrets, live pull triggers or
business rows were installed.
See `ops/acceptance/live-integration-20260910/google-installation.json`.

The owner subsequently added and read back
`API_BASE_URL=https://abn-engine.maintainmedia.com.au`, bringing the known
properties to six while preserving `ENABLED=false` and the original five values.
Connection preparation subsequently completed on both the Sydney host and
Google. The owner saved and read back **eight** properties: both new signing
values matched the same escrowed pair, were 64 characters and distinct, and the
original owner/workbook/tab/URL values were preserved. `ENABLED` remains `false`.
Only match results were recorded; the local display was cleared and the Google
tab was moved away from secret settings. The API loaded the prepared environment,
but `sheets_bridge_file` remains unset and its draft registry remains disabled,
without approval evidence or actor scopes. No live pull or business disclosure
was activated. See `google-connection-preparation-20260911.json` in the acceptance
directory. The 155-test setup suite and subsequent 21-test copyable-reveal
regression are engineering evidence separate from this actual owner read-back.

## Google Sheet

1. Sign in directly as the correct Maintain Media Google owner. No connector
   connection is needed for the browser installation. Record the Sheet ID, tab ID,
   owner and named reviewers/operators. Keep general access **Restricted**; do not
   grant domain-wide or public-link access. Record processor/support countries and
   the reviewed disclosure basis required by specification R30/G5.
2. Use the reviewed `maintain_media_standalone.gs` bundle. Run
   `prepareMaintainMediaWorklist()` as `jeph@quotemax.com.au` to create only the
   empty `ABN Worklist` tab and 29 protected contract headers. Other tabs/data are
   preserved. No business rows, credentials or approval records are fabricated.
3. Create a **standalone Apps Script project** owned by the service operator, with
   no reviewer edit access to the script. The standalone bundle combines
   `sheets_bridge.gs`, `sheets_install.gs`, `maintain_media_setup.gs` and
   `sheets_sync.gs`. A reviewer-editable bound script would expose privileged
   code and Script Properties to its editors; do not use that deployment model.
4. Set non-secret Script Properties `INSTALLER_EMAIL`, `SPREADSHEET_ID`,
   `WORKLIST_SHEET_ID`, and `ALLOWED_EDITOR_EMAILS` (a JSON array of named allowed
   users). `INSTALLER_EMAIL` must also be the Sheet's actual owner; another owner
   could always bypass protected ranges. `WORKLIST_SHEET_ID` is a canonical
   decimal string (`0` is valid, blank is not). Secret properties are
   `SERVICE_SIGNING_KEY` and `BRIDGE_SECRET`; set the
   HTTPS `API_BASE_URL` to the actual restricted control endpoint. Never put
   secrets in cells, source control, edit logs or a public web app.
5. As the configured owner, run `installPrivateWorklist()`. It checks named-only
   sharing, protects engine columns, creates at most one mapped edit trigger and
   one five-minute repair trigger, and leaves `ENABLED=false`.
6. Install the server's non-secret bridge registry as `sheets_bridge_file`, listing
   its actual `owner_email` and every named workbook reader in `editors`. The
   field includes any named viewers too: every person who can read this shared
   worklist needs a recorded role. An operator must be assigned to the current
   worklist; a reviewer/compliance role permits workspace review. A timer runs as
   the actual owner and does not impersonate individual reviewers. Inject
   the matching secrets as `ABR_SHEETS_SIGNING_KEY` and
   `ABR_SHEETS_BRIDGE_SECRET`. `control/sheets_auth.py` reloads the dated named-editor
   registry for every request. The script generates a 60-second service JWT bound
   to the method, path, exact body, editor, workbook and tab; a separate HMAC binds
   its idempotency key. The validated callback returns the actual editor's limited
   scopes, never an admin/service identity. No permanent service bearer token or
   periodic manual token renewal is needed. Genuine event-user availability and
   the actual installation still require the next step's receipts.
7. Verify genuine editor identity in an isolated test Sheet. Google may omit the
   edit-event user under some account/security conditions. Missing identity must
   keep the edit unsaved; do not substitute the trigger owner's email. Test one
   valid edit, sorted rows, stale versions, duplicate UUIDs, denied actors,
   duplicate event replay, outage/recovery and immediate suppression receipt.
   Measure actual propagation latency. Enable only after these receipts and the
   corresponding policy decisions exist.
8. Record account-specific G1/G3/G5/G7 evidence in the **`sheets` scope**, and enable
   the `sheets` capability only after approval. Its current G5 decision must bind
   the exact bridge-registry YAML SHA256 and approving actor. CRM has its own
   `crm` scope and installation hash; a GHL receipt cannot authorize Google
   disclosure. Workbook/tab/readers or registry changes require renewed evidence.
9. With actual HTTPS endpoint and matching protected keys installed, run
   `enableVerifiedWorklistSync()`. It confirms private sharing and the current
   server approvals, performs a real worklist pull, and creates at most one
   five-minute full refresh plus one one-minute restriction refresh. Failure
   leaves `ENABLED=false`; the script does not invent a successful activation.

The exact authenticated GET `/v1/sheets/worklist` returns only the current
worklist's 29 safe projection fields. It never returns encrypted records, endpoint
tokens, raw source captures or unselected candidates. All mapped readers must be
entitled to the list before the owner's timer can publish it. Gate closure returns
a redaction response; network, identity or sharing failures also hide contact
details locally. Contact writes are read back before a local application receipt
is saved. A local receipt is not proof that the provider installation passed G5.

Timers update computed fields by immutable UUID. Existing staff outcome cells are
never overwritten. Queued or differing outcomes retain their version and show a
conflict for comparison with the dashboard. Previous worklist rows retain their
outcomes with business/contact display fields cleared. The owner must archive
reviewed history before the bounded 2,000-row limit; unsaved outcomes are never
silently deleted to make space. Archives must follow the approved retention policy.

The one-minute timer is a recovery/check mechanism, with provider scheduling
jitter. It does **not** establish the spec's available-system suppression latency
target by itself. Measure that target in the actual account; if it fails, keep
live disclosure disabled and use a verified push/redaction path. Immediate Sheet
stop edits still call the synchronous suppression API, and pending local stops
remain masked even if a later pull has not yet observed their receipt.

The final live-pull bundle is now saved and the owner-authorized empty worklist
installation has completed. No further Google OAuth step is being requested for
that completed setup. Matching API credentials are now prepared. Genuine staff
write-back, current vendor approvals and measured suppression behavior remain separate activation
requirements. Do not rerun preparation to represent those unfinished checks as
complete; preparation deliberately keeps the bridge disabled.

## GoHighLevel

Actual preparation has now succeeded in the intended Maintain Media location.
The newly created private-integration token was installed through the reviewed
local handoff, and all **13** empty engine field definitions were read back at
**2026-09-10 16:52:15 UTC**. The metadata installer made zero contact calls and
has no pending create. See `ghl-field-metadata.json` and
`ghl-installation-observation.json` under the dated acceptance directory.
The owner then verified all 13 fields in **Maintain Media ABN Lead Gen**, removed
the temporary field-definition write scope, reopened the saved integration to
verify only `locations.readonly` and `locations/customFields.readonly`, and passed
metadata reads again. The dated `ghl-browser-installation-20260911.json` records
that final read-back. No contact permission was granted.
This is credential/field preparation. Contact workflow isolation, collision
behavior, CRM operations and vendor approval are still unverified.

The owner also inspected **All workflows** with a blank search. Home showed a
**Marketing Workflows** folder; its observed first page listed six workflows,
all **Draft**, each with zero total and active enrolments. The names cover new
lead nurture, appointment reminders, no-shows, sale review requests, long-term
nurture and stale leads. The next-page control was not explicitly disabled in
the accessibility output, so this is a bounded visible inventory, not proof of
account-wide completeness. Trigger/action definitions and other automations were
not inspected. See `ghl-workflow-list-observation-20260911.json`; it does not
certify G5 or authorize a contact test. Recheck current definitions and isolation
before any approved test write.

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

### Implemented worker wiring and remaining account verification

`export/live_contract.py` loads the absolute non-secret `ghl_config_file` and
`ghl_installation_file` paths. The installation binds the exact config bytes,
environment, location, dated account checks and approving actor. The current G5
database decision must name that installation file's SHA256 and actor; a YAML
enable flag alone cannot open the gate. G1/G3/G5/G7 and the CRM capability are
rechecked for acquisition. The fixture map remains unchanged.

`export.crm.drain_live_one` constructs the real HTTP adapter for one durable
outbox intent. The live mapping/location are used at human approval, current
projection, dispatch and reconciliation. Each HTTP mutation, including tag
changes, rechecks its exact approval, revision, policy, suppression and lease.
Uncertain creates reconcile by group identity without a blind second create;
Retry-After values extend durable retry scheduling.

`ops.propagation.drain_propagation` selects the real provider in pilot/production,
clears engine-owned fields, preserves unrelated tags and confirms clearing/DND by
fetching the remote record. Removal remains possible with acquisition disabled,
but still requires current hosting and the approved vendor installation. A
failed clearing response stays pending and cannot produce a success receipt.
Fixture workers reject live providers; live workers never fall back to mocks.

These paths now pass isolated PostgreSQL and HTTP contract tests. Actual GHL
account location/field metadata is verified. Automation isolation, custom-field search/null semantics,
duplicate/retry/suppression sandbox observations and processor approvals are
still required before the account-specific installation can be certified.

## Local verification

The dated engineering review records the focused Python/PostgreSQL/HTTP and
executable Apps Script results, including actual pilot-mode gates, mapped readers,
safe worklist projection, suppression masking, unsaved outcome preservation,
formula safety, read-back failure, and idempotent timer activation. The untouched
GHL template fails before network access. These are engineering checks, not
Google/GHL account installation or legal approval receipts.

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
