# Maintain Media GoHighLevel setup

This is an installation procedure, not a source, privacy or vendor approval.
The intended location is **Maintain Media / `xHZFHMOE476t5CxY9vCG`**.
Keep CRM capability and `allow_writes` disabled until actual installation checks
and the current release decisions pass. Empty custom-field setup contains no
business records.

**Current checkpoint — 11 September 2026:** the GHL account connection enabled
in release 009b remains enabled in the [verified release 010](../ops/acceptance/aws/cleanup010-host-20260911.json)
under the separate delegated-owner decision. The
[actual activation](../ops/acceptance/aws/ghl-dnd-pilot-activation-receipt-20260911.json)
and [service/account readback](../ops/acceptance/aws/ghl-sydney-account-verification-20260911.json)
are complete. The [provider contract test](../ops/acceptance/live-integration-20260910/ghl-live-account-contract-20260911.json)
passed and both synthetic contacts were removed. This is account-level readiness:
the database still has **zero selected worklist rows and zero real CRM transfers**.
The live DNCR receipt-format adapter is not implemented; real phone clearance,
verification/locality, qualification and individual reviewer approval remain
required. Google publishing and outreach remain disabled. See the
[current full-tool status](../../specs/001-abr-lead-engine/implementation-status.md).

The phone-only hand-off runtime requires `allowed_channels: ['phone']` and
`workflow_inventory_sha256` in the non-secret account configuration. The
installation receipt binds the exact configuration bytes; the current CRM G5
decision binds that installation receipt and its approving actor. Missing or
changed evidence keeps writes closed. The token additionally needs
`workflows.readonly` for the documented
[2023-02-21 workflow inventory](https://marketplace.gohighlevel.com/docs/2023-02-21/ghl/workflows/get-workflow/).

Before every contact, field or tag mutation, the adapter reads the complete
bounded account workflow inventory, requires every workflow to remain Draft,
and compares its canonical ID/location/status/version/update-time digest with
the reviewed configuration. It then checks current local authority again.
Changed, published, unknown or incomplete inventory blocks that mutation,
including suppression cleanup. An operator must review the changed account and
renew the configuration, installation and G5 evidence before cleanup can resume;
the durable removal job remains pending. No workflow is changed automatically.
This request-boundary check cannot prevent an account administrator publishing
a workflow between the inventory read and the next request. Restricting account
administration remains part of the reviewed installation.

Enabling the account does not select or approve businesses. A current tier A
worklist row, explicit reviewer approval, current identity/licence and a clear
phone wash with reviewed recipient timezone/locality remain mandatory. Candidate
records are written with Do Not Disturb enabled. A successful hand-off receipt
means the candidate projection was read back; it gives no permission to call or
send a message. Isolated account tests use clearly labelled synthetic companies,
never a real business's contact details, through a separately reviewed operator
procedure. The actual 11 September duplicate test used the explicitly approved
fictional telephone endpoint recorded in its acceptance plan; it supplied no
real email or phone contact. Do not relax candidate admission for an account test.

The account search index can lag a successful contact create. An empty group
search after an uncertain create is not proof that nothing was created. The
worker keeps that operation uncertain, records the next exponential-backoff
attempt, and performs no second create. Five unresolved attempts hold the job in
dead letter for operator review. When an update already has a known remote ID,
the worker reads that exact ID and verifies its group even if search is empty;
it never replaces that uncertainty with a new create.

### Historical metadata-only setup

The observations below preceded the separately approved contact tests and
release 009b activation. They do not describe the current five-scope connection.

Initial setup observed on **11 September 2026** (Manila): the new private
integration token was securely installed on the Sydney service, and the metadata
installer read back all **13** expected fields at **2026-09-10 16:52:15 UTC**.
The local receipt records zero contact calls and no pending field create.
At **2026-09-10 16:56:16 UTC**, the owner verified all 13 fields in the named
folder and read back the saved integration with only `locations.readonly` and
`locations/customFields.readonly`. The temporary field-definition write scope
was removed; metadata reads still passed. No contact permission was granted,
business records imported or release approval created. See
`ops/acceptance/live-integration-20260910/ghl-browser-installation-20260911.json`,
`ops/acceptance/live-integration-20260910/ghl-installation-observation.json` and
`ghl-field-metadata.json` in that directory.

A subsequent owner read-only inventory saw six **Draft** workflows in the
**Marketing Workflows** folder, each showing zero total/active enrolments. The
All workflows filter and blank search were visible, but pagination completeness
was not established. No trigger definitions, contacts or execution histories were
opened. This supports only the six displayed statuses; account-wide automation
and future contact-test safety remain unverified. See
`ops/acceptance/live-integration-20260910/ghl-workflow-list-observation-20260911.json`.
Recheck the current workflow definitions and other automations before an approved
isolated contact test; this observation is not G5 acceptance.

The initial local form rejected valid browser submissions because
`Referrer-Policy: no-referrer` changes a native form POST's Origin to `null`.
It now uses `same-origin`, preserving exact Origin/Host/CSRF checks. A new isolated
Chromium context reproduced the old 403 and verified the corrected submission;
the final setup suite passed **89 tests**. These tests used synthetic tokens.
The actual token was subsequently accepted and its installation confirmed.
[Browser form Origin rules](https://fetch.spec.whatwg.org/#origin-header).

### Initial metadata installation procedure

1. In the intended sub-account, create a dedicated private integration. For this
   metadata-only setup grant `locations.readonly`, `locations/customFields.readonly`
   and temporarily `locations/customFields.write`. Do not grant contacts,
   conversations, campaigns or workflows access at this stage. Scopes can be
   changed later without generating another token. A newly generated token is
   shown only once. [Official private integration setup](https://marketplace.gohighlevel.com/docs/Authorization/PrivateIntegrationsToken/index.html)
2. The owner-created **Contact** folder is `Maintain Media ABN Lead Gen`.
   The initial **ABN Engine Group ID** field must remain TEXT with actual ID
   `C17XY6QzLsYssEnb1gUz`. The installer validates that identity before creating
   anything. ABNs remain text, and only Score uses NUMERICAL.
3. Upload the reviewed `ops/aws/provision_ghl.py` to the approved Sydney host at
   `/home/ubuntu/abn-host-bootstrap-20260910/provision_ghl.py`.
   On the local Windows workspace run
   `.venv\Scripts\python.exe ops\aws\provision_ghl_client.py --receive`.
   Open the printed one-use localhost URL. Use the GHL **Copy** button for the
   newly generated token, then keyboard-paste it into the password field and
   select **Save and install token**. Do not read the clipboard, paste into chat,
   capture the token with a screenshot, or put it in a command argument.
4. The receiver makes a separate current-user DPAPI recovery copy outside the
   repository and sends the new token through pinned SSH stdin. The root helper
   creates only `ghl.env` and three environment-file drop-ins. It does not read
   existing environment files, change approvals, call a vendor, reload systemd
   or start a service. If installation is uncertain after saving the encrypted
   copy, retry `provision_ghl_client.py --resume` with that same copy. Never
   generate a replacement token to work around an uncertain installation.
5. Run `.venv\Scripts\python.exe ops\aws\provision_ghl_fields.py --apply`.
   This uses only the new setup's encrypted token and location metadata APIs.
   It creates at most 12 additional empty fields, validates exact names/types,
   preserves matching existing fields and refuses conflicting definitions.
   Every create has a durable pending record; an uncertain result is not blindly
   retried. A successful run records only allowed field IDs/names/types/keys in
   `ops/acceptance/live-integration-20260910/ghl-field-metadata.json`.
6. The pinned create API documents `name`, `dataType` and `model`, but no folder
   parameter. The owner must select the new fields and move them into the
   existing folder in the UI. Then remove the temporary
   `locations/customFields.write` scope and confirm the remaining metadata reads
   still work. [Create custom field API](https://marketplace.gohighlevel.com/docs/2023-02-21/ghl/locations/create-custom-field/),
   [field and folder controls](https://help.gohighlevel.com/support/solutions/articles/155000008466-creating-and-managing-custom-fields-for-better-data-organization).

The runtime adapter needs `contacts.readonly`, `contacts.write` and
`workflows.readonly` in addition to the two metadata read scopes. Those five
scopes were saved and verified for the current pilot. The contact-write permission also
covers contact campaign/workflow endpoints, so scope selection alone does not
guarantee that a credential cannot trigger outreach. The application does not
call those endpoints. [Official scope table](https://marketplace.gohighlevel.com/docs/Authorization/Scopes/index.html).

Keep the current global **Allow Duplicate Contacts = OFF** setting. Do not use
contact upsert as a workaround: its `createNewIfDuplicateAllowed` switch is
ignored when duplicates are disabled. The create-contact API does not document
a conditional rejection guarantee for endpoint collisions. Before actual lead
writes, prove in an isolated test that a duplicate email/phone cannot change an
existing CRM contact. A returned group-ID check occurs after a request and is
not that proof. [Upsert behavior](https://marketplace.gohighlevel.com/docs/2023-02-21/ghl/contacts/upsert-contact/),
[create-contact contract](https://marketplace.gohighlevel.com/docs/2023-02-21/ghl/contacts/create-contact/).

Review published Contact Created, Contact Changed, Contact Tag and Contact DND
workflows and connected external automations before contact writes. Require
explicit engine-record exclusions or positive customer eligibility before send,
campaign, workflow, DND-disable and paid actions. Preserve existing customer
workflows. DND does not establish whole-workflow isolation. Engine identifiers
are the mapped group field, source `Maintain Media reviewed candidate`, and
tags `maintain-media:candidate` / `maintain-media:suppressed`. Account-specific
execution logs, group search, uncertain-create recovery, suppression clearing,
unrelated-tag preservation and processor-country review remain activation
requirements. [API-created contact triggers](https://help.gohighlevel.com/support/solutions/articles/155000002486-workflow-trigger-contact-created),
[tag triggers](https://help.gohighlevel.com/support/solutions/articles/155000002482-workflow-trigger-contact-tag).
