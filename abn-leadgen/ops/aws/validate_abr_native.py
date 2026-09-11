"""Run synthetic release tests in an already isolated Linux network namespace.

Requires only loopback, an unprivileged identity, a caller-verified source tree,
and the installed PostgreSQL16 binaries. Never reads live configuration.
"""
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET


SUITES = [
    "tests/unit/test_abr_public.py", "tests/unit/test_sources.py",
    "tests/unit/test_publication_quality.py", "tests/unit/test_live_readiness.py",
    "tests/unit/test_diff_bounds.py", "tests/unit/test_analytical_guard.py",
    "tests/unit/test_live_contract.py", "tests/unit/test_gohighlevel.py",
    "tests/integration/test_live_abr_runtime.py", "tests/integration/test_abr_recovery.py",
    "tests/integration/test_pipeline.py", "tests/integration/test_live_dashboard.py",
    "tests/integration/test_live_crm.py", "tests/integration/test_live_website_collection.py",
    "tests/integration/test_live_scheduled_operations.py", "tests/integration/test_retention.py",
    "tests/integration/test_live_abr_cleanup.py", "tests/integration/test_artifact_retention_seals.py",
]


def command(args, *, timeout=120, env=None):
    return subprocess.run(args, check=True, timeout=timeout, capture_output=True, text=True, env=env)


def main():
    root = Path(sys.argv[1]).resolve(strict=True)
    if os.geteuid() == 0 or sorted(name for _, name in socket.if_nameindex()) != ['lo']:
        raise ValueError('ISOLATED_UNPRIVILEGED_NAMESPACE_REQUIRED')
    if not root.name.startswith('abn-leadgen-live-20260911-011-validation'):
        raise ValueError('EXACT_VALIDATION_TREE_REQUIRED')
    if any(not (root / name).is_file() for name in SUITES):
        raise ValueError('VALIDATION_FILES_MISSING')
    os.umask(0o077)
    temporary = Path(tempfile.mkdtemp(prefix='abr011-native-'))
    pg = Path('/usr/lib/postgresql/16/bin')
    database = temporary / 'database'
    sockets = temporary / 'sockets'
    sockets.mkdir()
    pg_log = temporary / 'postgres.log'
    xml = temporary / 'tests.xml'
    output = temporary / 'pytest.log'
    env = {'PATH': '/usr/bin:/bin', 'HOME': str(temporary), 'LANG': 'C.UTF-8',
           'PYTHONPATH': str(root / 'src') + ':' + str(root), 'PYTHONDONTWRITEBYTECODE': '1'}
    start_attempted = False
    try:
        command([str(pg/'initdb'), '-D', str(database), '-U', 'abr_fixture',
                 '--auth-local=trust', '--auth-host=trust', '--encoding=UTF8', '--no-locale'], env=env)
        start_attempted = True
        command([str(pg/'pg_ctl'), '-D', str(database), '-l', str(pg_log), '-w', 'start',
                 '-o', '-F -p 55432 -h 127.0.0.1 -k '+str(sockets)], env=env)
        command([str(pg/'createdb'), '-h', '127.0.0.1', '-p', '55432', '-U', 'abr_fixture', 'abr_fixture'], env=env)
        os.chdir(root)
        with output.open('w') as stream:
            try:
                result = subprocess.run([sys.executable, '-m', 'pytest', '-q', '-p', 'no:cacheprovider',
                    '--tb=short', '--basetemp='+str(temporary/'pytest'), '--junitxml='+str(xml), *SUITES],
                    stdout=stream, stderr=subprocess.STDOUT, env=env, timeout=900, check=False)
                exit_code = result.returncode
            except subprocess.TimeoutExpired:
                exit_code = 124
        document = ET.parse(xml).getroot() if xml.is_file() else None
        suites = ([document] if document.tag == 'testsuite' else list(document.findall('testsuite'))) if document is not None else []
        if not suites and exit_code == 0:
            exit_code = 2
        stats = {key: sum(int(s.attrib.get(key, 0)) for s in suites)
                 for key in ('tests', 'failures', 'errors', 'skipped')}
        print(json.dumps({'status': 'passed' if exit_code == 0 else 'failed',
            'exit_code': exit_code, 'stats': stats, 'scope': 'synthetic isolated PostgreSQL16 and offline HTTP transports',
            'source_root': str(root), 'uid': os.geteuid(), 'interfaces': ['lo'],
            'source_manifest_sha256': hashlib.sha256((root/'RELEASE-MANIFEST.json').read_bytes()).hexdigest(),
            'xml_path': str(xml) if xml.is_file() else None,
            'xml_sha256': hashlib.sha256(xml.read_bytes()).hexdigest() if xml.is_file() else None,
            'log_path': str(output), 'live_database_access': False, 'external_network_available': False}))
        if exit_code:
            print(output.read_text()[-16000:])
        return exit_code
    finally:
        primary_error_pending = sys.exc_info()[0] is not None
        if start_attempted:
            state = subprocess.run([str(pg/'pg_ctl'), '-D', str(database), 'status'],
                capture_output=True, text=True, env=env, timeout=30, check=False)
            if state.returncode == 0:
                try:
                    command([str(pg/'pg_ctl'), '-D', str(database), '-m', 'fast', '-w', 'stop'], env=env)
                except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                    print(json.dumps({'cleanup': 'fixture_stop_failed', 'database_path': str(database)}))
                    if not primary_error_pending:
                        raise ValueError('FIXTURE_CLEANUP_FAILED') from None


if __name__ == '__main__':
    raise SystemExit(main())
