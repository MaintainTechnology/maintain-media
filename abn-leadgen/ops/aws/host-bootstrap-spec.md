# Approved Lightsail host foundation

Scope recorded before implementation, 10 September 2026: prepare reviewable scripts
for one fresh Ubuntu 24.04 Lightsail host in Sydney. The approved 8 GB bundle does
not approve live engine startup, data collection, add-ons or backups. AWS creation,
identity, cost approval, operator SSH access and publishing belong to the operator.

## Requirements

- H1: Bootstrap must explicitly require `--apply`, root, Ubuntu 24.04, a public
  operator IPv4 matching the current SSH connection and an existing non-root admin
  account with a regular nonempty authorized-keys file. Invalid inputs fail before
  changing the host. The bootstrap must not read key or environment-file contents.
- H2: Install the distribution Python 3.12/venv and PostgreSQL 16/client runtime,
  with PostgreSQL bound only to IPv4 loopback. Create no application databases,
  database passwords, engine configuration, credentials or key material.
- H3: Create the locked, non-login `abr-engine` service identity. Prepare
  `/opt/abn-leadgen` and `/etc/abr-engine` as root-owned directories readable by the
  service group but not writable by it, and `/var/lib/abr-engine` as private writable
  service state. Refuse foreign existing application data and unsafe links.
- H4: Require key authentication, deny root/password/interactive-password login,
  and disable SSH forwarding. Check effective configuration before reloading SSH.
  UFW must allow inbound SSH only from the supplied operator IPv4, with default
  inbound denial. Preserve an already working SSH session; unknown existing rules
  or a changed operator address require review instead of a firewall reset.
- H5: The fresh-host bootstrap may resume its own partial installation for the
  same host inputs. It must refuse existing application content, unexpected database
  clusters, non-default databases/roles and unrelated firewall rules. No recursive
  removal, database reset, role elevation or broad firewall reset is permitted.
- H6: A separate read-only verifier reports individual checks and a narrow
  `host_foundation_verified` result only after runtime, database listeners, file
  permissions, service identity, effective SSH policy, firewall and inactive engine
  checks pass. It records current disk availability without certifying capacity.
- H7: No AWS commands, live sources, application code installation, gateway/API
  startup, engine systemd services/timers, migrations, backup or secrets are included.
  Existing live release guards and G1–G7 remain authoritative.

## Rubric and definition of done

| Area | Points |
| --- | ---: |
| Explicit scope, fresh-host and repeat-run admission | 25 |
| SSH/firewall and PostgreSQL boundaries | 30 |
| Runtime and filesystem/service identity contract | 20 |
| Meaningful synthetic tests and clear runtime verification | 25 |

A lockout, credential disclosure, unintended deletion or live-startup defect
prevents passing. Local tests establish script behaviour only. The final host
verification and a second successful SSH connection must be recorded on the actual
approved host; synthetic tests cannot earn those runtime-verification points.

Implementation checklist: [x] H1 [x] H2 [x] H3 [x] H4 [x] H5 [x] H6 [x] H7.
Actual host acceptance passed on 10 September 2026. See `host-bootstrap-review.md`
for executed local and Linux evidence, review fixes and the separately bounded score.
