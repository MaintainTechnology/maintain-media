# Dormant engine source release

## Scope and acceptance contract

This is the application installation step after the host foundation. It installs
reviewed code and locked Python dependencies, without starting an engine, reading
private configuration, creating a database/keys, collecting business records, or
enabling a timer, gateway, integration or backup. Keep the foundation verification
receipt and confirm a second SSH login **before** copying code: that verifier
deliberately requires empty application directories.

| Requirement | Acceptance evidence | Points |
| --- | --- | --- |
| R1: Copy only an explicit public code allowlist; never read private inputs | Filename/link refusal and excluded-file tests | 25 |
| R2: Immutable package identity and complete per-file SHA-256 manifest | Deterministic archive, trusted digest verification, tamper tests | 25 |
| R3: Extract only verified regular files into an empty directory | Traversal, duplicate/link/overwrite refusal tests | 20 |
| R4: Preserve source-relative paths and install locked dependency wheels | Linux module help, native-wheel and policy/gateway checks | 20 |
| R5: Keep real data and live services closed | No private config, no DB/server commands; offline blocked readiness result | 10 |

Local automated checks establish R1-R3. R4's Linux evidence and the host state
portion of R5 require the operator to run the commands below on the approved host.
Do not award those points from a Windows test run.

## Prepare and verify the public release

From the repository root, choose a **new directory outside `abn-leadgen`**. Its
parent must already exist. The builder refuses an existing output directory.

```powershell
python abn-leadgen/ops/aws/prepare_release.py build --root abn-leadgen --output C:/Users/dalig/AppData/Local/Temp/abn-engine-release-RELEASE_ID
```

The output contains `release.tar.gz` and `receipt.json`. Save the printed archive
SHA-256 through the already trusted operator channel. The receipt alone does not
authenticate a package. Copy these files plus the reviewed `prepare_release.py`
to a private temporary directory on the approved host, using verified SSH host
identity. Verify the helper's own SHA-256 against the local reviewed copy before
running it. Replace `ARCHIVE_SHA256` below with the saved digest.

The allowlist includes Python source, SQL migrations, report/dashboard templates,
the qualification policy, the public CRM field template, dependency lock and five
selected offline test modules. It excludes environment files, existing runtime
configuration, keys, data/output directories, source CSV/ZIP data, credentials,
AWS state, and the rest of the repository. `config/fixture.yaml` is generated as
the literal `mode: fixture`; the existing configuration file is never read.
The fixture identity/defaults in source are synthetic and install no database.

```bash
python3 prepare_release.py verify --archive release.tar.gz --sha256 ARCHIVE_SHA256
sudo python3 prepare_release.py extract --archive release.tar.gz --sha256 ARCHIVE_SHA256 --destination /opt/abn-leadgen
sudo chown -R root:abr-engine /opt/abn-leadgen
sudo find /opt/abn-leadgen -type d -exec chmod 0750 {} +
sudo find /opt/abn-leadgen -type f -exec chmod 0640 {} +
```

Extraction rejects symlinks/reparse points, a nonempty destination, duplicate
members, unknown paths, special files, malformed manifests and altered bytes.
It never replaces an existing file. An interrupted extraction is intentionally
not resumed or erased automatically; inspect and resolve its partial directory.

## Install the locked source runtime

Use a reviewed, pinned `uv` installation; the local preparation version is
`0.11.20`. Record the actual `uv --version` and `/usr/bin/python3.12 --version`.
Install tooling separately using an approved method; do not pipe an unreviewed
download into a root shell. Run dependency installation as the administrator,
with root-owned output, while the application service user remains unprivileged.

```bash
sudo /ABSOLUTE/PATH/TO/uv --directory /opt/abn-leadgen sync --frozen --no-install-project --no-build --python /usr/bin/python3.12 --no-python-downloads
sudo chown -R root:abr-engine /opt/abn-leadgen/.venv
sudo chmod -R g+rX,o-rwx /opt/abn-leadgen/.venv
```

This synchronizes the dependency versions/hashes from `uv.lock`, including dev
dependencies needed for verification. `--no-build` refuses source builds rather
than silently resolving additional build tools. If a compatible Linux wheel is
missing, stop and report the missing package. The project itself is **not** built:
its unconstrained `hatchling` backend is absent from the lock. The commands below
use the preserved source via `PYTHONPATH`; no `abr-engine` entry point is claimed.
This follows uv's documented [sync options](https://docs.astral.sh/uv/reference/cli/#uv-sync)
and avoids the separate [build dependency resolution](https://docs.astral.sh/uv/reference/settings/#build-constraint-dependencies).

Keep `/opt/abn-leadgen/src/abr_engine` in that layout. The engine resolves its
project root from the source file; configuration, migrations, integration mapping
and templates depend on it. A standalone wheel does not include those resources.
The project accepts Python 3.12; the repository's `.python-version` patch pin is
overridden explicitly by the host's supported `/usr/bin/python3.12` interpreter.

## Verify Linux without connecting sources or a database

Run these as the non-login `abr-engine` user through `sudo`. `unshare --net`
creates a temporary network namespace without external interfaces, adding an OS
boundary around the offline checks. It requires root only to create the namespace;
the interpreter then runs as the service user. No server or database is started.
The selected tests use synthetic in-memory values and temporary files; they do
not request the shared database fixtures in `tests/conftest.py`.

```bash
sudo unshare --net -- runuser -u abr-engine -- env -C /opt/abn-leadgen PYTHONPATH=/opt/abn-leadgen/src PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m abr_engine.cli --help
sudo unshare --net -- runuser -u abr-engine -- env -C /opt/abn-leadgen PYTHONPATH=/opt/abn-leadgen/src PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider --basetemp=/tmp/abr-release-RELEASE_ID tests/unit/test_qualification_policy.py tests/unit/test_publication_quality.py tests/unit/test_qbcc_publisher.py tests/unit/test_live_readiness.py tests/unit/test_dashboard_gateway.py
sudo unshare --net -- runuser -u abr-engine -- env -C /opt/abn-leadgen PYTHONPATH=/opt/abn-leadgen/src PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m abr_engine.cli release-check --mode pilot
```

The private install directory is deliberately inaccessible to the `ubuntu` user's
ordinary shell. Change working directory inside the privileged install command,
or after switching to the service identity, as above; do not loosen its permissions.
The last command must exit **6** with `status: blocked` on this dormant installation.

Use a fresh `RELEASE_ID` for the pytest temp directory: pytest clears an existing
`--basetemp` directory. Never point it at project, config or data storage. Retain
test output, Python/uv versions, the source receipt, and the blocked readiness
result. No smoke-test output should contain a real secret or business record.

The result is an installed, dormant source runtime. Source/privacy approvals,
publisher mapping and measured classifier review, real pipeline/dashboard/CRM
connections, private Sheet/GHL verification, production configuration, TLS/identity,
crawler egress controls, scheduled runs, backups and the measured pilot remain
separate work. No public engine port is opened by this procedure.
