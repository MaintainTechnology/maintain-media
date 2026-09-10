# Gated weekly discovery and finite maintenance

The weekly scheduler now calls the live durable QBCC runtime. It does not call the fixture pipeline. `live-schedule-weekly --config /etc/abr-engine/pilot.yaml` takes the current time from PostgreSQL, finds Monday 00:00 UTC of that week, and derives one request UUID from the environment, schema, issuer and week. Concurrent or repeated invocations reuse that job. The existing one-minute source worker executes queued jobs using the same source, schema, cursor, suppression and review checks as dashboard requests.

`abr-engine-qbcc-weekly.timer` runs Monday at 00:00 UTC with persistent catch-up. Restarting after several missed weeks admits only the current week; it does not invent historical observations. A gate-closed week is stored as held and stays held. After approvals change, staff can explicitly request a new run through the dashboard; the next weekly period has a new identity. A timer never silently overrides a recorded hold. G1/G2/G3/G7 collection evidence and collection capability remain required before any source HTTP.

The schedules are separate from the priority control worker (15 seconds) and source recovery worker (one minute):

| Timer | UTC schedule | Command |
| --- | --- | --- |
| `abr-engine-qbcc-weekly.timer` | Monday 00:00 | `live-schedule-weekly --config /etc/abr-engine/pilot.yaml` |
| `abr-engine-qbcc-review-cleanup.timer` | Daily 03:05 | `live-maintenance --kind review-staging --execute --config /etc/abr-engine/pilot.yaml` |
| `abr-engine-retention.timer` | Daily 03:20 | `live-maintenance --kind retention --execute --config /etc/abr-engine/pilot.yaml` |

All three units run as `abr-engine`, use the existing private runtime configuration, restrict writes to the state directory and allow only Unix sockets. This matches the installed local PostgreSQL socket and prevents these admission/deletion jobs from calling source or vendor HTTP. Remote-source work belongs to the existing source worker. Do not change the configuration to a TCP database without explicitly reviewing that service boundary.

Preview maintenance first by omitting `--execute`. Both commands preserve the YAML's live mode, use current database time, produce redacted structured receipts, and return a nonzero held status when policy or holds block work. There is no live fixture fallback or operator-controlled future time.

`review-staging` only handles the existing declared pair of unreferenced QBCC intake files, seven-day expiry, interrupted-writer recovery and explicit holds. It cannot delete accepted snapshots, follow links, adopt another path or decrypt business rows. Withdrawal of collection permission does not block this already scoped finite cleanup. `retention` applies the separately approved live retention policy and current G1/G3/G7 retention gates, preserves required restriction aliases and evidence holds, and requires separate external-system/backup receipts. A complete primary cleanup is not confirmation of deletion from Google Sheets, GHL or backup storage.

The six AWS unit files are reviewable installation artifacts. The implementation did not install or enable them. On the approved host, validate with `systemd-analyze verify`, install the matching service/timer pairs, and keep weekly discovery and general retention disabled until their actual evidence is recorded. The units also declare conflicts with their older generated equivalents. Check for cron/manual duplicates before enabling one authoritative timer set. Do not enable both the AWS units and the `ops/production/prepare.py` generated set.

Engineering verification uses actual isolated PostgreSQL with synthetic records and an explicit mock publisher transport. It checks concurrent weekly admission, repeat replay, zero HTTP/key loads under closed acquisition gates, live retention after collection withdrawal, legal holds and owned seven-day staging cleanup. Linux unit acceptance, enabled-state evidence and actual scheduled live runs remain deployment checks; the tests do not supply approval records.
