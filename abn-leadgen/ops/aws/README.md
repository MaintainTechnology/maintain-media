# Ubuntu host foundation for the approved Lightsail server

This package prepares one fresh Ubuntu 24.04 host for later engine installation.
The chosen Sydney Lightsail instance, account, bundle, image, price and Free Tier
status must be checked separately by the operator. The three host foundation modules
`bootstrap_host.py`, `verify_host.py` and `host_contract.py` make no AWS calls. The
separate AWS controller is documented in [deployment-session.md](deployment-session.md).

The only installed services are the existing SSH service and the distribution's
fresh PostgreSQL 16 service. Python 3.12 and its venv support are installed through
Ubuntu packages. The application directory remains empty. No live data, engine
database, password, application key/configuration, gateway, worker, application
timer, backup, paid add-on or external integration is installed or enabled.

## Review and run

Copy `bootstrap_host.py`, `verify_host.py` and `host_contract.py` together to a
temporary directory on the explicitly approved host. Do not copy the repository's
private data or environment files. Inspect the scripts and compare their hashes
against the reviewed local files before executing them.

Connect by SSH as the existing key-authenticated `ubuntu` administrator. Use your
current public **IPv4 address**, without `/32`. The following address is a placeholder
and must be replaced with the actual operator IPv4. Keep this SSH window open.

```bash
python3 bootstrap_host.py --operator-ip OPERATOR_IPV4 --admin-user ubuntu
sudo env SSH_CONNECTION="$SSH_CONNECTION" python3 bootstrap_host.py --operator-ip OPERATOR_IPV4 --admin-user ubuntu --apply
sudo python3 verify_host.py --operator-ip OPERATOR_IPV4 --admin-user ubuntu
```

The first command prints the scope only. The second changes the host. `sudo` must
preserve its normal `SUDO_USER`; `env` explicitly forwards only the non-secret
current SSH connection description. The script refuses a different operator IP,
root/direct-console execution, a nonstandard SSH port, missing admin public-key
metadata, foreign application contents, unexpected database clusters and unrelated
firewall rules. It never reads authorized-key contents or existing `.env` files.

After bootstrap, open **a second SSH connection** from the same public IPv4 and
confirm `sudo` works before closing the original connection. The verifier cannot
prove this second connection, so its receipt always marks that check unverified.
Lightsail's separate network firewall must also restrict port 22 to that same
operator IPv4; the scripts configure only the host's UFW firewall.

The host firewall blocks other inbound traffic, including HTTP/HTTPS and engine
ports. It permits outbound traffic for OS installation and later reviewed work;
this is not the crawler's required private-network/metadata egress policy. That
policy, TLS, gateway and live engine remain separate future work.

The root-owned non-secret marker in `/var/lib/abr-host-bootstrap/host.json` allows
the same inputs to resume a partial bootstrap. Changed operator IP, modified
managed files, nonempty application directories or new database objects cause a
review stop. There is no automatic reset or deletion path. The managed SSH policy
is tested before SSH reload; if it is invalid, only the new policy file created by
that attempt is removed, leaving the previous SSH service configuration in place.

Run verification before copying application code or creating engine configuration.
It deliberately requires the application directories and fresh database to remain
empty. A pass is `host_foundation_verified`, not production readiness, verified
Australian data residency, measured capacity, backups or an operating lead tool.
Ubuntu package patch versions may differ from the Windows test lock; record actual
versions and run the locked engine checks during the subsequent application release.

## Local evidence

From the `abn-leadgen` directory:

```powershell
uv run --frozen pytest ops/aws/test_host_bootstrap.py -q
uv run --frozen ruff check ops/aws/host_contract.py ops/aws/bootstrap_host.py ops/aws/verify_host.py ops/aws/test_host_bootstrap.py
uv run --frozen mypy --platform linux ops/aws/host_contract.py ops/aws/bootstrap_host.py ops/aws/verify_host.py
```

Local tests mock OS commands and use synthetic filesystem inputs. They do not
install packages, contact AWS, alter SSH/firewalls, read credentials or verify
Linux command output on the real server. Run the independent verifier there and
retain its output plus the second-SSH-login result as the host foundation evidence.
