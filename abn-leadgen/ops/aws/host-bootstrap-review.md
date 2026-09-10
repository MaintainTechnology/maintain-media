# Host bootstrap implementation and review

10 September 2026. Scope: [host-bootstrap-spec.md](host-bootstrap-spec.md).
The first review covered locally prepared scripts. The later execution section
below records application to the approved Sydney server and actual host evidence.

## Coverage

- [x] H1 implemented: explicit `--apply`, public IPv4 and non-root admin validation,
  root/Ubuntu/systemd guard, current SSH connection match, existing key metadata.
- [x] H2 implemented: Ubuntu Python 3.12/venv and PostgreSQL 16/client packages;
  managed IPv4-loopback PostgreSQL config and default-database/role verification.
- [x] H3 implemented: system non-login identity and empty private install/config/state
  directories with separate ownership and permissions; foreign contents/links refused.
- [x] H4 implemented: effective public-key-only SSH checks for both admin and root,
  validation before reload, rollback of a newly invalid policy, operator-only UFW
  rule, IPv4/IPv6 default incoming denial, no firewall reset.
- [x] H5 implemented: host/operator-bound non-secret marker, exclusive bootstrap
  lock, immutable managed-file checks, restricted resume of the fresh default cluster.
- [x] H6 implemented: independent read-only verifier with individual results and
  explicitly unverified capacity, actual placement, second SSH login and live release.
- [x] H7 respected: no AWS commands, application source/config/secret installation,
  engine database/schema, gateway/worker, engine unit/timer, add-on or backup activation.
- [x] Actual Ubuntu execution and all 11 foundation verification checks passed.
- [x] A second successful SSH login and sudo check passed after final bootstrap.

## Executed local verification

- `uv run --frozen pytest ops/aws/test_host_bootstrap.py -q`: **72 passed** after Linux fixes.
- Focused Ruff on `host_contract.py`, `bootstrap_host.py`, `verify_host.py` and
  `test_host_bootstrap.py`: **passed**.
- Mypy `--platform linux` on the three operational modules: **passed**.
- Review-only CLI run returned `review_only` without host operations.
- The verifier run on this Windows machine returned `blocked / ROOT_REQUIRED`,
  no observed resource certification and `live_engine_enabled: false`.

Linux targeting is deliberate: these scripts use Linux account, permission,
systemd, SSH and firewall APIs. A Windows-target type check cannot establish those
platform interfaces. Tests mock command execution and do not exercise a real UFW,
PostgreSQL service restart or fresh Ubuntu package installation.

## Review improvements and rubric

The first implementation passed 41 local tests. Independent review found that an
interruption after package installation could leave PostgreSQL listening on `::1`,
preventing an otherwise safe owned retry; admission now permits only that owned
loopback default until configuration, while final verification requires 127.0.0.1.
Review also found that password-disabled SSH alone did not establish public-key-only
authentication; the exact authentication method is now set and checked, including
separate root Match context. Additional checks cover immutable PostgreSQL managed
file resume, SSH rollback and wrong-platform admission before POSIX imports.

| Area | First review | Revised local result | Maximum |
| --- | ---: | ---: | ---: |
| Scope and fresh/resumed host admission | 20 | 25 | 25 |
| SSH/firewall and PostgreSQL boundaries | 20 | 30 | 30 |
| Runtime and filesystem/service contract | 20 | 20 | 20 |
| Tests and runtime verification | 19 | 19 | 25 |
| **Total** | **79** | **94** | **100** |

Independent re-review found no additional local blocker after these fixes.

Local score trajectory: **79 → 94 → 94** for this bootstrap package. At this local-only
stage, six points remained withheld because actual Ubuntu installation, effective
firewall/database behaviour and a new SSH session had not been observed. These scores do not rate the complete lead engine
or close any production gate. The approved AWS purchase and hosting decision remain
recorded separately; local script verification does not request or imply new approval.

## Actual Ubuntu execution and final review

Executed against `maintain-media-abn-engine` in Sydney on 10 September 2026.
The three transferred scripts were checked against their local SHA256 hashes.
Real Ubuntu output exposed two overly strict parser assumptions: `ss` appends
`%lo` to its local resolver address, and UFW displays `disabled (routed)` when
kernel forwarding is disabled. Admission and verification were corrected with
regressions. Numeric-address classification still rejects public/engine listeners;
disabled routing now requires both kernel forwarding switches at zero and IPv4/IPv6
INPUT and FORWARD DROP. No firewall boundary was widened to obtain a pass.

The owned partial bootstrap resumed successfully. Python 3.12.3 and PostgreSQL
16.15 are installed; PostgreSQL listens only at 127.0.0.1:5432. The independent
verifier returned **host_foundation_verified: 11/11 checks passed** at 14:36:03 UTC.
A new SSH connection at 14:36:18 UTC returned `ubuntu`, and passwordless sudo
returned UID0. The kernel reported no reboot-required marker. Reboot recovery and
engine capacity were not tested and are not certified by this foundation contract.

Receipts: `../acceptance/aws/host-foundation.json` and `server-deployment.json`.
The verifier's own `second_ssh_login_verified: false` remains unchanged because
that process cannot prove a new connection; the separate deployment receipt records it.

Under the rubric written before implementation, the actual evidence supplies the
six previously withheld runtime points: **79 → 94 → 94 → 100/100** for H1–H7 only.
This narrow foundation now passes its review. Live source ingestion, integrations,
TLS, scheduler, backup and pilot acceptance remain outside this score and unfinished.
