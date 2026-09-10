# ABR Lead Engine — staff workflow installation

Updated 11 September 2026 (Manila). This records completed setup, not permission
to collect or publish business information.

## What is installed

The private [ABN Worklist](https://docs.google.com/spreadsheets/d/1-PEySaH7AAod3hoFqZZf7zMYMWyQ3qIAWQzxnrq6K58/edit#gid=2107750955)
has 29 protected columns and its edit/repair scripts. The original ABN tab is
preserved. The workbook and standalone script are Restricted to
`jeph@quotemax.com.au` alone. No business rows were added by this setup.

The Google script now has the real engine address and two matching connection
keys. The owner saved and checked all eight settings. Both keys matched the same
pair installed securely on the Sydney service; values were not printed or saved
in this vault. The temporary local display was cleared afterward.

Google's `ENABLED` setting is still `false`. Its server reader list is a disabled
draft with no approval or role grants, and the live reader-list setting remains
unset. The connection is prepared; automatic business-list publishing is off.

GoHighLevel's Maintain Media location has a dedicated integration and all 13
empty engine fields in the **Maintain Media ABN Lead Gen** folder. The owner
verified that its only remaining permissions read location and field settings.
The temporary permission to create fields was removed. No permission to read or
write contacts was granted, and no customer workflows were changed.

The owner later saw six Draft workflows in GHL's Marketing Workflows folder,
each with zero total and active enrolments. Only the visible first page was
checked. The rules inside those workflows, any other pages and other automations
remain unverified, so this does not yet prove a test contact cannot trigger a
message.

## Backup setup — 11 September 2026

The private Sydney backup storage is now installed. At 02:05 Manila, the owner
verified a complete round trip with a random test value: encrypt it, upload it,
download and decrypt it, delete it, then check that it was gone. No database or
business information was used. This proves that the storage connection works;
it is not a completed production database backup or restore.

Release 005 and migration 026 are installed. The normal API and three recovery
timers are active, with zero leads. Seven backup units are installed, but their
three timers remain disabled. A manual test without the required authority was
correctly refused and recorded a local alarm. It did not prove outside alerts or
automatic detection when a timer stops.

The private recovery key is encrypted with Windows DPAPI inside Codex's
virtualized Windows profile. The owner confirmed its actual resolved location,
and the key is not on the Sydney source server. An independent person's ability
to recover that key after this Windows profile is lost still needs testing.
See [[ABR Lead Engine - Backup Setup 2026-09-11]].

## What still needs evidence

The source/privacy decisions and each vendor's processing countries and terms
still need the responsible owner's and adviser's review. The targeting defaults
already approved do not replace those decisions.

The real staff tests still need to show that edits identify the correct person,
remain safe after sorting or an outage, and remove contact details quickly enough
after a stop request. GHL also needs its duplicate-contact, workflow-isolation and
suppression tests. These checks must pass before the corresponding release scope
can be enabled. The draft approval pack remains **not approved**.

Backups still need approved authority and independent key recovery, a real
isolated restore, proof of the newest stop/deletion records after recovery,
measured recovery loss and timing, stopped-timer monitoring and outside alerts.
A fresh staff Clerk browser login, the 100-business accuracy review and measured
QBCC pilot also remain unverified. Installed storage does not replace these checks.

## Evidence in the project

- `abn-leadgen/ops/acceptance/live-integration-20260910/google-connection-preparation-20260911.json`
- `abn-leadgen/ops/acceptance/live-integration-20260910/ghl-browser-installation-20260911.json`
- `abn-leadgen/ops/acceptance/live-integration-20260910/ghl-workflow-list-observation-20260911.json`
- `abn-leadgen/integrations/LIVE-INSTALLATION.md`
- `abn-leadgen/ops/production/approval-pack.md`
- `abn-leadgen/ops/acceptance/aws/backup-storage-installation-20260911.json`
- `abn-leadgen/ops/acceptance/aws/live-service-release-005-20260911.json`

Related: [[ABR Lead Engine - Build Hub]], [[ABR Lead Engine - Implementation Status]].
