# Live staff integration engineering evidence

10 September 2026. Scope: real-mode CRM approval/outbox/suppression wiring and
request-bound Sheets editor authentication. These are local engineering checks,
not proof that Google/GHL production integration has been installed or approved.

## Implemented

- Real account field mapping/location at approval, projection, dispatch and reconciliation.
- Non-secret typed installation evidence bound to exact config bytes and current G5 hash/actor.
- Current gates and per-mutation approval/version/suppression/lease checks, including tag updates.
- Durable uncertain-create reconciliation without blind duplicate creation and Retry-After scheduling.
- Removal-only suppression with DND and cleared-field readback; unrelated tags are preserved.
- No live provider in fixture workers and no mock fallback in live workers.
- Separate 60-second Sheets service JWTs, body/path/method/editor/workbook/tab bindings,
  HMAC/idempotency binding, named-editor scopes and per-request registry reload.
- Standalone owner-only Sheet setup that creates 29 protected contract headers,
  preserves other tabs/data and installs disabled edit/repair triggers without secrets.
- Dedicated `/v1/sheets/worklist` pull with actual pilot/production rows, closed
  field projection, separate `sheets` G1/G3/G5/G7 gates and exact registry SHA/actor.
- Every named reader is scope/assignment-checked before the owner timer can
  disclose a shared worklist; GHL installation evidence cannot approve Google.
- Five-minute full worklist pull and one-minute restriction refresh installed
  only by verified activation. Outcomes/UUIDs/unsaved versions survive refresh and
  sorting; withdrawn/failed projections mask contacts and verify the read-back.

## Passed checks

Executed from `abn-leadgen/`, Windows, Python 3.12 and the actual isolated local
PostgreSQL 16 fixture database. All remote HTTP I/O uses synthetic MockTransport.

```text
uv run pytest tests/unit/test_gohighlevel.py tests/unit/test_live_contract.py tests/unit/test_sheets_auth.py tests/unit/test_sheets_install.py tests/integration/test_crm_recovery.py tests/integration/test_live_crm.py tests/integration/test_propagation.py -q
111 passed in 235.01s

uv run pytest tests/unit/test_sheets_setup.py tests/unit/test_sheets_install.py tests/unit/test_sheets_auth.py -q
23 passed in 1.63s

uv run pytest tests/unit/test_gohighlevel.py tests/unit/test_live_contract.py tests/unit/test_sheets_auth.py tests/unit/test_sheets_install.py tests/unit/test_sheets_setup.py tests/unit/test_sheets_sync.py tests/integration/test_crm_recovery.py tests/integration/test_live_crm.py tests/integration/test_propagation.py tests/integration/test_live_sheets.py -q
137 passed in 144.99s

uv run pytest tests/unit/test_outputs.py::test_sheets_bridge_signed_reordered_row_and_immediate_optout -q
1 passed in 0.86s

uv run pytest tests/integration/test_live_sheets.py -q
12 passed in 26.37s
```

The first two commands were the earlier 113-test stage. The final command set
covers **140 distinct focused tests**: it adds the real-mode Sheets DB projection,
executable merge/timer/read-back checks and updates the original signed-opt-out
harness to independently validate the new 60-second JWT/HMAC contract. The final
12-test helper run includes two additional post-review cases for a registry-file
replacement race and approval expiry during projection. Both fail closed without
returning business fields; the earlier ten helper cases pass again. Ruff
passed changed sources/tests. Mypy passed `crm.py`, `live_contract.py`,
`gohighlevel.py`, `propagation.py`, `sheets_auth.py` and `sheets.py`.

The positive pilot-mode path uses the real GoHighLevel transport and actual
database transactions, with synthetic account/approval evidence created only in
disposable test schemas. It verifies create/readback and stop/clear/readback,
timeout-after-create, opt-out during lookup, revoked/changed installation,
Retry-After and revocation between a field update and a tag mutation. No real
account credentials, contacts or messages are involved.

Review found and fixed an overly narrow owned-tag comparison used for suppression:
suppression must verify the entire preserved projection, including unrelated tags.
The repaired implementation compares complete field projections and sorted tags;
the existing propagation regression suite passes.

The Sheets tests prove that approved pilot-mode rows are projected through actual
DB transactions, each closed G1/G3/G5/G7 decision removes business data from the
response, an unassigned reader blocks the owner's shared disclosure, and a current
suppression masks the contact. JS tests execute the reviewed bundle against a
minimal Google API harness: duplicate pulls, reordered UUIDs, stale/invalid/queued
outcomes, account/tab mismatches, malformed extra fields, formula strings, retired
rows, denied sharing, outage masking, missing read-back and idempotent activation.
No network or real vendor approval is substituted into those tests.

## Actual external evidence and limits

The initial read-only Google preflight found the supplied workbook with public
editing and the wrong connector account; see `google-preflight.json`. The root
operator subsequently used the owner's signed-in browser to change General access
to Restricted and verified owner-only sharing. That later observation supersedes
the initial sharing result. No business rows were published by this subtask.

The subagent could not take over the root browser: tab lookup returned not found,
the subagent's IAB inventory contained no tabs, and visible IAB tabs are not
supported in a subagent. The reviewed standalone bundle was handed to the root
operator for browser installation. This is a hand-off record, not an installation
receipt. Record the actual script project, tab ID, trigger/readback and genuine
editor tests separately after they complete.

The root operator subsequently completed the real Google installation at
2026-09-10T16:06:14Z. The final bundle was saved and read back equal after CRLF
normalization. `ABN Worklist` gid2107750955 has the exact 29 headers and protection;
the original ABN tab remains. Two triggers exist: `installedWorklistEdit` ON_EDIT
and `repairPendingEdits` CLOCK. Both workbook and standalone project are Restricted
to owner `jeph@quotemax.com.au`, with no other people listed. Five non-secret
properties were read back, including `ENABLED=false`; no endpoint or signing keys
are installed and no business rows were created. The full observed receipt is
`google-installation.json`. This supersedes the earlier browser hand-off state.

Actual API write-back, trigger timing, a confirmed available-system suppression
delay at or below 60 seconds, staff event-user availability, and approved external
retention/deletion remain live G5 evidence. A one-minute timer alone cannot certify
the propagation target; keep disclosure disabled if the measured account behavior
does not meet it. The completed OAuth/setup step does not need to be requested again.

GHL account metadata, scoped credential installation, workflow isolation, actual
custom-field search/null semantics and sandbox receipts remain unverified here.
G1/G3/G5/G7 decisions are not created by this code or its tests. Real collection,
CRM writes and outreach were not activated. The draft source/privacy/vendor pack
is at `ops/production/approval-pack.md` and must remain labelled unapproved.
