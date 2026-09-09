# Maintain Media ABN Lead Engine

Internal fixture-first Python pipeline for preparing a small, controlled Australian business review list. `abn-leadgen/` is the application directory; `abr_engine` is its Python package. The authority is [specification v4.0](../specs/abr-lead-engine.md), with the [interface contract](../specs/001-abr-lead-engine/contracts/interfaces.md).

Part 1 prepares evidence and records outcomes. It does not send email/SMS, dial, buy credits, take payments or enrol campaigns. The local operator dashboard provides a browser interface for the fixture workflow. ABR/GST/QBCC observations are discovery signals, not proof of actual revenue, buying intent or consent.

All [production release gates](ops/release-gates.md) remain **PENDING**. The intended legacy 30-rule corpus, current policy/source approvals, real vendor sandbox contracts, AU hosting evidence, approved capacity plan and live commercial pilot are outstanding. Local benchmark, recovery and fixture results are recorded separately in [acceptance evidence](ops/acceptance/). Synthetic tests cannot close production gates.

## Open the local dashboard

On this Windows computer, double-click **`Start-Dashboard.cmd`** in this directory. It installs the locked Python dependencies, starts the isolated fixture database, applies pending migrations, starts the dashboard in the background and opens **http://127.0.0.1:8767/**. You can close the launcher window after the page opens. Starting it again opens the existing dashboard. The PowerShell equivalent, from any directory, is:

```powershell
& 'C:\Users\dalig\Desktop\MaintainTech\MaintainOrg\maintain-media\abn-leadgen\Start-Dashboard.ps1'
```

The page uses **synthetic practice businesses**, not current live ABN registrations. Its latest records are the most recent local fixture results. The dashboard lets you inspect leads and runs, open generated report/CSV files, change supported fixture preferences and start a new fixture run. The setup page distinguishes configured local services from the live source, vendor and production prerequisites that remain pending. Saving dashboard preferences does not approve a live source or activate outreach.

Dashboard downloads hide contact details, including contacts that the underlying engine has approved for export. Names, sources, review reasons and row IDs remain available. The original private engine report files remain unchanged.

The [dashboard specification](dashboard-spec.md) defines this extension and its review rubric. Its [surface brief](../.impeccable/surfaces/leadgen-src-abr-engine-dashboard-static-index-html.md) records the built interface: preserve true counts, missing facts and demo labels; settings save only source preference and an A$0–150 enrichment usage ceiling for subsequent runs. Keep the inherited local font/logo and list/detail workflow, with stacked content and run cards on phones.

The dashboard binds only `127.0.0.1`. Keep it on this computer; do not forward this port or expose it through a public tunnel. It has local fixture access rather than production user authentication. The existing control API on port 8766 is separate; it does not need to be running to use the dashboard. `/report.html` on port 8767 remains an entry point for existing bookmarks.

To inspect or stop the dashboard, run these commands from this directory:

```powershell
uv run --frozen python ops/local_dashboard.py status
uv run --frozen python ops/local_dashboard.py stop
```

Stopping the dashboard leaves PostgreSQL running. Stop the database separately using `uv run python ops/local_postgres.py stop` when finished. Runtime ownership records and startup logs are stored in `.runtime/dashboard-8767.json` and `.runtime/dashboard-8767.log`. The helper checks process identity before stopping anything. If another program occupies port 8767, it reports the conflict and leaves that program running; close that application's preview, or launch `Start-Dashboard.ps1 -Port 8768` and use the new URL. Repeated start/stop requests are protected against concurrent launch attempts.

If the database stops, open the launcher again to recover the local services, then use **Refresh**. A warning about an unreadable run record leaves the rest of the dashboard usable and preserves the original record for investigation. Failed saves retain your edits so you can retry; use **Discard changes** to return to the saved defaults.

For a fresh machine, install uv and Python 3.12 and provision the PostgreSQL archive described below first. The launcher reports missing prerequisites and setup failures. It does not download a database archive, configure live credentials or close production release gates.

## Local setup

Use Python 3.12 and uv. Run the commands below from this directory. Resolve dependencies from the committed `uv.lock`; do not update versions during a reproduction.

```powershell
uv sync --frozen
uv run python ops/local_postgres.py start
uv run python ops/local_postgres.py status
```

The Windows PostgreSQL helper needs the official PostgreSQL 16 Windows binary archive already provisioned as `.runtime/postgresql.zip`. The helper extracts task-local PostgreSQL binaries and initialises `.runtime/data`; it does not install a Windows service or alter another database. It binds only `127.0.0.1:55432` and uses the synthetic `abr_fixture` database/user/password. These fixture credentials are intentionally non-secret and are forbidden for live data. The archive must be obtained and checked separately; no live source or vendor credentials belong in this setup. Stop this isolated instance with `uv run python ops/local_postgres.py stop` after work.

The following commands passed the [independent fixture handover](ops/acceptance/handover-drill.md) on the existing task-local PostgreSQL16 instance. Use a new run UUID for a new execution; use the same UUID for recovery.

```powershell
uv run abr-engine validate-config
uv run abr-engine db migrate
$runId = [guid]::NewGuid().ToString()
uv run abr-engine run --source all --mode fixture --run-id $runId
uv run abr-engine resume $runId --stage all --mode fixture
uv run abr-engine alarms check --run-id $runId --mode fixture
uv run abr-engine alarms drain --mode fixture
```

`run` executes the synthetic source/enrichment/worklist/report cycle. Identical source content is a no-op. Reports live under `var/reports/<run_uuid>/<generation_uuid>/` with immutable receipts under `var/runs/<run_uuid>/`. A missing report or changed current authority creates a fresh report generation on resume while preserving committed source results. The handover verified a missing-HTML recovery and both generations' hashes. This does not certify a fresh machine or live adapters.

Additional verified handover commands were `uv run abr-engine worklist build 2026-09-07 --mode fixture` (existing week replay) and `uv run abr-engine retention run --mode fixture` (preview only). Use `retention run --execute` only for an authorised deletion run. `serve`, fixture-only `token`, `crm drain`, `wash import`, `backup drill` and `benchmark` are implemented; inspect their `--help` and relevant evidence before operating them. `backup drill` accepts the absolute PostgreSQL16 binary directory through `ABR_FIXTURE_PG_BIN` (Linux CI: `/usr/lib/postgresql/16/bin`); Windows defaults to `.runtime/pgsql/bin`.

## Verification and evidence

The [dashboard operability review](ops/acceptance/dashboard-operability-review.md) records the latest control-by-control and recovery checks. The browser checks use the repository's installed Playwright and local dashboard. `node ops/dashboard_operability_check.cjs` runs all three fixture source options and restores the saved preferences; `node ops/dashboard_resilience_check.cjs` intercepts API calls to check failure handling without starting real runs. The separate `ops/dashboard_recovery_drill.py` deliberately stops and recovers the isolated fixture database, so run it only when no other local work needs that database.

```powershell
uv run python ops/verify.py
uv run pytest
uv run ruff check .
uv run mypy src/abr_engine
```

The output slice passed 39 synthetic tests, including permitted/blocked reports, injection, interval union/corrections, cohort denominators and a Node Apps Script test using the real generated CSV header. The monitor/summary regression run passed 12 tests against isolated PostgreSQL16 schemas. These are scoped builder results; consult the final acceptance record for package-wide checks. Node is required by the Apps Script harness; it reports an explicit skip if unavailable.

Record full-suite results and exact revision separately. Actual PostgreSQL constraint/race/recovery evidence, live source smoke tests, vendor sandbox certification, a Linux systemd drill, rendered 360px browser review and an independent unaided handover drill remain distinct checks. CSS contains responsive layout constraints, but structural template assertions alone do not certify browser accessibility.

## Configuration and access

`config/fixture.yaml` is validated by `Settings` with unknown fields rejected. The current supported configuration fields are:

| Field | Fixture default / meaning |
|---|---|
| `mode` | `fixture`; live modes require external managed keys and current capability gates |
| `database_url` | Loopback PostgreSQL port 55432, exact `abr_fixture` identity; fixture rejects remote databases and query overrides |
| `output_dir` | `var`, a private local artifact root |
| `monthly_cap_micro_aud` | 150000000 micro-AUD; integer usage ceiling, never purchasing authority |
| `issuer`, `audience` | `maintain-media-fixture`, `abr-engine-fixture` for short-lived fixture tokens |
| `live_credentials` | Empty mapping; fixture rejects supplied live credentials |
| `capabilities` | Empty mapping; fixture rejects enabled capabilities |
| `key_file` | None in fixture; live modes require an absolute externally managed key-store path |

Configuration is YAML-backed; do not assume arbitrary environment variables override it. CLI common options and any environment loader added in the final implementation must be documented with command evidence. Windows PostgreSQL helper sets `PGPASSWORD` inside its child-process environment to the known fixture password only. Never put live credentials in source, reports, logs, Sheets cells or this README.

Human permissions are explicit: owners approve policy and release; developers administer infrastructure but have no automatic marketing-review authority; trained reviewers assess evidence and approve eligible selected tier A CRM rows; operators record outcomes, request immediate suppression and perform authorised live checks; compliance administers erasure/evidence; a separately certified sender consumes a fresh action decision. A service credential cannot invent an editor's human scope.

## Outputs and integrations

`export.report.render_report(ReportContext(...), output_dir)` creates a new immutable UUID bundle containing `report.html`, `report.md` and `worklist.csv`. The pipeline nests each bundle under its run UUID. `ReportRow` carries opaque row/worklist/lead/group UUIDs and an expected version. Endpoint values appear only for an authorised operator with an explicitly allowed and unexpired export decision. The caller obtains that decision from current authoritative database state; the renderer does not grant eligibility.

Keep all output artifacts private with restricted filesystem/storage access; `noindex` is not authentication. Unix output modes are restrictive; configure equivalent Windows ACLs and private service access at deployment. Do not publish a report, CSV, contact field or evidence URL through public-link sharing. Blocked candidates display a reason and safe review action. Static contact labels always require send-time/call-time checks.

`integrations/sheets_bridge.gs` is an uninstalled Apps Script bridge. Protected immutable IDs survive sorting; ordinary edits use version checks, event IDs and actual editor context. Opt-outs call suppression synchronously before outcome patching. Save status must show a durable receipt or an explicit unconfirmed error. Five-minute repair is only recovery. Script properties are `ENABLED` (default disabled), `API_BASE_URL`, `SERVICE_TOKEN` and `BRIDGE_SECRET`; the actual-editor HMAC contract must be certified with the server before enabling. No public web app, public share link or secret-bearing cell is permitted.

`integrations/crm_fields.yaml` contains fixture-only typed field IDs and owned-tag add/remove rules. Live field IDs, location, current GoHighLevel contract/rate limits, processor countries and sandbox receipts remain pending. Only version-bound human-approved selected tier A intent may enter the durable CRM outbox. An uncertain create must reconcile first; shared endpoints do not establish one business identity. No automatic campaign enrolment is defined.

`export.metrics` unions explicit per-operator activity intervals and attributes dated outcomes to a fixed selected tier/signal. Distinct contacted business groups are the conversion denominator. Unknown costs/rates are reported as unknown. Fully loaded costs include every configured cash category and human time; A$150 is only the enrichment usage cap.

## Operation and recovery

Follow [the runbook](ops/runbook.md) for held sources, budget stops, wash imports, opt-outs, write-back conflicts, partial CRM results, replay, retention, restore and key rotation. [systemd templates](ops/systemd/README.md) use one scheduler and the same CLI; they are uninstalled and unverified on a Linux host. Do not add parallel cron schedules.

Large-run admission requires known remaining download/staging/snapshot/spill/DB/WAL/backup bounds plus 25 GiB free-space headroom. Existing allocations are already reflected in filesystem free space and are not charged twice. Start with bounded samples at >=2x observed per-row estimates. The [1,000-lead PostgreSQL sample](ops/acceptance/db-wal-sample-1000.json) records table/index growth and a concurrent cluster-wide WAL upper bound; it does not certify long-term retained WAL or an entire production workload. Full-register Parquet benchmark artifacts are separate from this database sample and from host/release approval.

The selected diff uses three DuckDB threads, a512MB buffer limit and400k-row partitions. Its synthetic20.5M-universe runs took58.4 and104.0 seconds; the paired two-thread repeat took116.5 seconds. Full event values matched the reference, but these local timings vary substantially and do not establish consistent compliance with the60-second stretch target. See the [thread comparison and confirmation](ops/acceptance/performance-thread-review.md).

`alarms check` records available source/control/resource facts and lists unknown inputs. `--observations <private.json>` accepts one or two closed `ops.monitor.Observation` records for the selected run; measured backup/restore/timer status needs an evidence UUID. `alarms drain --mode fixture` writes only redacted database mock receipts with bounded leases/retries; it sends no notifications. Source baselines, external timer receipts and missing costs remain unknown until measured. Redacted observation/mock-delivery records expire after 90 days unless held; minimal alarm dedupe authority remains.

`uv run abr-engine propagation drain --mode fixture` applies queued stops to the persistent fixture CRM, clears engine-owned contact/custom fields, removes its candidate tag and adds the configured suppressed tag. It preserves unrelated CRM fields/tags and confirms the update by fetching it before completing the job. `crm drain` processes these stops before and after its ordinary outbox work. The [single-command fixture drill](ops/acceptance/propagation-drill-444cf383-b386-46a9-bc93-a4df3e369a22.json) measured4.64 seconds from enqueue to verified update; real Google/GHL field clearing and propagation latency remain uncertified.

`uv run abr-engine cost-import <private-evidence.json> --mode fixture` accepts validated cost statements for exact declared start/end instants, with dated approval, receipt and tariff/FX evidence. It does no purchasing. Missing cash categories/rates/time coverage remain unknown; it never prorates into a guessed window or mixes cohort allocations into overall totals. Receipt bodies expire after90 days unless held; minimal numeric projections expire after24 calendar months. See the [cost input schema and tests](ops/acceptance/cost-input-review.md).

Profile erasure preserves minimal pseudonymous cohort, dated outcome and work-time facts for the finite reporting period. Names, contact details and notes are excluded from these metric tables. Corrections and merged businesses keep their original cohort attribution; expired facts cannot reappear through old activity rows. A scoped metric hold preserves its relevant facts while allowing the marketing profile to be erased. See the [erasure and reporting review](ops/acceptance/erasure-metrics-review.md).

`ingest.discovery.discover_publication` composes explicit publisher mapping, bounded resumable downloads, a second metadata read and complete archive validation. It accepts injected fixture metadata and transport, records unavailable metadata-response validators explicitly, and rejects live mode before I/O. The runnable fixture pipeline still uses its local publication fixtures. The [discovery review](ops/acceptance/discovery-review.md) distinguishes this tested composition from the approved live publisher contract and scheduler integration still needed for production.
