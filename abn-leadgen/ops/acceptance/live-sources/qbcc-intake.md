# QBCC file intake and review custody

This is a gated file-import and cleanup path, not the live lead worklist. It has
not been run on real business records. The website remains on its fixture bridge.

An authorised operator can stage an explicitly acquired official publisher CSV
after the current collection approvals and managed environment exist. Intake
preserves missing licence status as UNKNOWN. It creates no lead identities,
candidates, contacts, outreach or accepted source cursor. All non-quarantined
publisher records wait for current licence and identity review; quarantine records
remain separate within the encrypted review artifact.

## Required operator inputs

Run from the locked application environment. `abr-engine sources stage-qbcc --help`
lists these required options:

| Option | Actual value required |
| --- | --- |
| `--config` | Explicit private YAML for the approved pilot/production database, private storage and managed encrypted keys. Fixture mode/database are refused. |
| `--file` | An ordinary `.csv` file acquired from the approved QBCC resource. Credential paths, symlinks and Windows reparse paths are refused. |
| `--run-id` | A fresh UUID for this import attempt. |
| `--source-sha256` | Exact SHA-256 of the acquired CSV. |
| `--inventory-before-sha256`, `--inventory-after-sha256` | Equal source-inventory hashes observed around the acquisition. |
| `--mapping-evidence-ref`, `--mapping-evidence-sha256` | The exact current collection G2 approval record and hash covering the publisher schema. Targeting direction alone is insufficient. |
| `--retrieved-at` | Actual retrieval time, ISO 8601 with timezone, for example a timestamp ending in `Z`. New intake requires a fresh receipt. |
| `--expected-cursor-version` | The actual current accepted QBCC cursor version, or zero when no cursor exists. |

The command checks current collection G1/G2/G3/G7 before reading business bytes
or managed keys. It verifies CSV size/hash and the explicit 11-column publisher
schema. The source receipt is operator supplied; the command does not download
data or independently prove how that file was obtained. Do not invent receipt
values to get past the checks.

Its safe result contains counts and identifiers, `state: needs_review`,
`accepted: false`, zero candidates and no cursor advancement. Successful intake
returns exit 0. A refused intake returns a closed reason code and exit 3; invalid
configuration/request input returns exit 2. No business names or file contents
appear in the CLI receipt.

The exact successful request can be replayed with the same UUID and verified
artifacts without rereading the original CSV. Changed requests, damaged artifacts
and incomplete attempts cannot be presented as successful replays. A failed
attempt needs a fresh UUID after its cause is fixed.

## Storage and expiry

The command declares ownership before writing the immutable raw CSV and encrypted
review JSONL under `staging/qbcc/<run UUID>/`. The raw register requires the
approved private, encrypted storage contract; it is not application-encrypted.
The review projection uses the managed key store. Both files are bounded in size.
Their manifests record source/mapping hashes and the gate revisions used.

Before installing the source workflow, preview its narrow retention command:

```text
abr-engine sources cleanup-qbcc-review --config /etc/abr-engine/config.yaml
```

Add `--run-id <UUID>` to inspect one known intake. Add `--execute` only to apply
the reported recovery/expiry actions. It owns only QBCC review-intake artifacts;
it cannot delete accepted snapshots or other pipeline files. It respects run and
artifact holds, verifies paths and recorded bytes, and deletes unreferenced
staging after seven days. Interrupted writers become recoverable after a one-hour
grace period and after obtaining the same source lock. A changed artifact is held
for investigation, not silently deleted. Bounded batches rotate past held items
so they do not prevent later due work from being processed.

Cleanup does not require renewed permission to collect data. Managed key/restore
authority and private path checks still apply. Held failures produce a nonzero
CLI result. The production bundle includes a daily 03:05 UTC cleanup timer with
persistent catch-up; it has **not been installed**. A compiled timer does not
prove expiry happened. Host acceptance must exercise recovery, holds, actual
expiry and delivery of failures before collection starts.

## Remaining integration

The review artifacts still need a protected licence/identity review interface,
current suppression checks and accepted-snapshot promotion before a real business
can enter the worklist. The Next.js dashboard, Sheet editor bridge, live CRM
outbox and suppression propagation remain unconnected. This partial T071 step
does not close production release gates or start the measured pilot clock.
