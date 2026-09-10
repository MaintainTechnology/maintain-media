# Disabled Google connection preparation

This installs technical connection values only. It does not approve the source,
privacy basis, Google processing countries, actor roles or live worklist release.

The owner already verified the private empty worklist and standalone script.
The owner also added and read back
`API_BASE_URL=https://abn-engine.maintainmedia.com.au` on 11 September 2026
(Manila). At that point there were **six** properties: that URL plus
`ENABLED=false`, `INSTALLER_EMAIL`, `ALLOWED_EDITOR_EMAILS`, `SPREADSHEET_ID` and
`WORKLIST_SHEET_ID`. Their existing values must be preserved.

The subsequent owner handoff is now complete: **eight** saved properties were
read back, both new keys matched the original escrowed pair, and all six existing
values were preserved. `ENABLED=false`, the registry is still a disabled draft,
and `sheets_bridge_file` remains unset. The API has loaded the prepared environment.
See `ops/acceptance/live-integration-20260910/google-connection-preparation-20260911.json`.
The procedure below is the installation/recovery record; it is not a request to
repeat the completed handoff or to activate the bridge.

The exact setup targets are:

- Owner: `jeph@quotemax.com.au`.
- Workbook: `1-PEySaH7AAod3hoFqZZf7zMYMWyQ3qIAWQzxnrq6K58`.
- ABN Worklist tab: `2107750955`.
- Standalone script: `1DzYHoVQ_X2_CoC6Dw4LaTXaXAYPRWBH2qPc34rEpY8nKtOGJFR2ZOmdn`.
- Service origin: `https://abn-engine.maintainmedia.com.au`.

1. Review `ops/aws/provision_sheets.py`, `provision_sheets_client.py` and
   `provision_private_files.py` with their tests. Upload the remote wrapper and
   shared publisher to `/home/ubuntu/abn-host-bootstrap-20260910/` on the already
   approved Sydney host. No provider or Google call is made by the wrapper.
2. Run `.venv\Scripts\python.exe ops\aws\provision_sheets_client.py --prepare`
   locally. It generates two distinct random keys only when this setup has no
   encrypted record. The pair is saved in its own current-user DPAPI directory
   before it is sent through pinned SSH stdin. A retry reuses this same pair.
3. The remote publisher creates only `/etc/abr-engine/sheets.env`, a disabled
   `/etc/abr-engine/sheets-bridge.pending.yaml`, and one API service environment
   drop-in. It refuses to replace unrelated files. The registry has actual
   workbook/owner IDs but empty approval, evidence, date and scope fields; it is
   intentionally invalid for live authentication. `sheets_bridge_file` remains
   unset. No service reload/start or capability/approval change is performed.
4. Open the printed one-use loopback URL. Its initial page contains a **Load new
   setup values** button and no keys. Select that button only after confirming
   the correct local page. The response uses the browser-tested `same-origin`
   referrer policy with exact Host, Origin and CSRF checks.
5. Transfer only the two newly displayed values to the owner's standalone
   **Script Properties**: `SERVICE_SIGNING_KEY` and `BRIDGE_SECRET`. Keep values
   inside the local/browser handoff, without chat output, logs, screenshots,
   plaintext files or clipboard extraction. The displayed URL and ENABLED value
   are comparisons against the existing settings; do not replace the six known
   properties. Select **Clear this page** and close it after the transfer.
   The explicit reveal uses read-only text controls so the owner can copy these
   newly generated setup values. The initial page still has no keys. Password
   controls were rejected for this handoff because browser automation redacted
   their values and the attempted Google save correctly refused empty inputs.
6. Read back only non-secret state and match results. The final property count
   should be **eight**; both new values must match the newly escrowed pair,
   `ENABLED` must remain `false`, and owner/workbook/tab/URL must be unchanged.
   Record booleans and IDs, never key values. Do not run
   `enableVerifiedWorklistSync()` or install live pull timers.

If a handoff expires or the remote result is uncertain, rerun `--prepare` with
the same encrypted setup record. Do not rotate keys to work around uncertainty.
If Google contains a value from this same interrupted setup, compare it privately
to the original pair before proceeding; do not replace an unexplained existing
credential. No successful Google transfer is inferred merely because the local
display was opened.

After this preparation, the owner still needs genuine actor/write-back and
suppression measurements plus current approval evidence. Only then can an
approved, dated registry with explicit roles be installed, `sheets_bridge_file`
set, and the separate Sheets capability and Script ENABLED flag activated.
Prepared keys and an owner-only sheet are not that approval.

The native browser regression is opt-in through `ABR_GHL_TEST_CHROMIUM`, pointing
to an isolated Chromium executable. It uses synthetic keys and a new browser
context with network access restricted to its local test server. It verifies
initial key absence, explicit reveal into read-only text, matching values,
clearing, and no key values in form request bodies.
