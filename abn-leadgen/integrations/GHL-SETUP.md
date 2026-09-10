# Maintain Media GoHighLevel setup

This is an installation procedure, not a source, privacy or vendor approval.
The intended location is **Maintain Media / `xHZFHMOE476t5CxY9vCG`**.
Keep CRM capability and `allow_writes` disabled until actual installation checks
and the current release decisions pass. Empty custom-field setup contains no
business records.

Actual setup observed on **11 September 2026** (Manila): the new private
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

The runtime adapter eventually needs `contacts.readonly` and `contacts.write` in
addition to the two metadata read scopes. The contact-write permission also
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
