"""Finite reconciliation of pre-owned ABR working namespaces after interruption.

No source or provider I/O occurs here. The worker lock excludes all ABR writers;
large hashes run outside the control lock, followed by short current-retention
and inode/ledger checks. Normal artifact retention performs the later deletion.
"""
from __future__ import annotations

import os
import re
import stat
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

from psycopg.types.json import Jsonb

from abr_engine.compliance.keys import load_keys
from abr_engine.compliance.policy import gate_reasons
from abr_engine.compliance.retention import _execute_gate, _held
from abr_engine.control.service import DomainError, Service, json_safe
from abr_engine.db import transaction
from abr_engine.ingest.common import SourceError, digest_file
from abr_engine.ops.abr_analysis import identity
from abr_engine.ops.promotion import declare_artifact, source_lock_key
from abr_engine.pipeline import _session_lock, process_lock, safe_root

MAX_ATTEMPTS = 5
MAX_FILES = 20_000
MAX_BYTES = 48 * 1024**3


def _sync_directory(path):
    if os.name != 'nt':
        descriptor = os.open(path, os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


def _safe(path, root, *, directory=False):
    """Check the original path before resolution; never follow a link."""
    path, root = Path(path), Path(root)
    if not path.is_absolute() or '..' in path.parts or path == root or not path.is_relative_to(root):
        raise SourceError('ABR_NAMESPACE_OUTSIDE_ROOT')
    chain = [path, *path.parents]
    for item in chain:
        if item == root.parent:
            break
        if item.is_symlink() or (hasattr(item, 'is_junction') and item.is_junction()):
            raise SourceError('ABR_NAMESPACE_UNSAFE_PATH')
        if item.exists():
            current = item.lstat()
            if item == path and not directory:
                if not stat.S_ISREG(current.st_mode) or current.st_nlink != 1:
                    raise SourceError('ABR_NAMESPACE_UNSAFE_PATH')
            elif not stat.S_ISDIR(current.st_mode):
                raise SourceError('ABR_NAMESPACE_UNSAFE_PATH')
            if hasattr(os, 'geteuid') and current.st_uid != os.geteuid():
                raise SourceError('ABR_NAMESPACE_WRONG_OWNER')
    if path.resolve() != path or not path.resolve().is_relative_to(root):
        raise SourceError('ABR_NAMESPACE_OUTSIDE_ROOT')
    return path


def reserve_attempt(settings, job_id, root):
    """Commit reservation, create an empty private directory, then seal its inode."""
    attempt_id = uuid4()
    relative = Path('staging') / 'abr-live' / str(job_id) / str(attempt_id)
    directory = _safe(root / relative, root, directory=True)
    if directory.exists():
        raise SourceError('ABR_NAMESPACE_ALREADY_EXISTS')
    with transaction(settings) as conn:
        row = conn.execute('SELECT * FROM pipeline_run WHERE run_id=%s FOR UPDATE', (job_id,)).fetchone()
        if not row or row['mode'] != settings.mode or row['state'] != 'running' or row['manifest'].get('kind') != 'abr_live_job':
            raise SourceError('ABR_JOB_NOT_ACTIVE')
        attempts = row['manifest'].get('attempt_namespaces', [])
        if not isinstance(attempts, list) or len(attempts) >= MAX_ATTEMPTS:
            raise SourceError('ABR_ATTEMPT_LIMIT')
        entry = {'attempt_id': str(attempt_id), 'relative_directory': relative.as_posix(),
                 'created_at': Service.now(conn).isoformat(), 'state': 'reserved'}
        conn.execute('UPDATE pipeline_run SET manifest=manifest||%s WHERE run_id=%s',
                     (Jsonb({'attempt_namespaces': [*attempts, entry]}), job_id))
    directory.mkdir(parents=True, mode=0o700, exist_ok=False)
    _safe(directory, root, directory=True)
    inode = directory.stat()
    if list(directory.iterdir()):
        raise SourceError('ABR_NAMESPACE_NOT_EMPTY')
    _sync_directory(directory)
    _sync_directory(directory.parent)
    entry = {**entry, 'state': 'owned', 'device': inode.st_dev, 'inode': inode.st_ino}
    with transaction(settings) as conn:
        row = conn.execute('SELECT manifest FROM pipeline_run WHERE run_id=%s FOR UPDATE', (job_id,)).fetchone()
        if not row:
            raise SourceError('ABR_NAMESPACE_RESERVATION_CHANGED')
        attempts = row['manifest']['attempt_namespaces']
        if attempts[-1]['attempt_id'] != str(attempt_id) or attempts[-1]['state'] != 'reserved':
            raise SourceError('ABR_NAMESPACE_RESERVATION_CHANGED')
        conn.execute('UPDATE pipeline_run SET manifest=manifest||%s WHERE run_id=%s',
                     (Jsonb({'attempt_namespaces': [*attempts[:-1], entry]}), job_id))
    return directory


def _namespace(root, run, entry):
    if not isinstance(entry, dict):
        raise SourceError('ABR_NAMESPACE_INVALID')
    try:
        attempt_id = str(UUID(entry['attempt_id']))
        expected = Path('staging') / 'abr-live' / str(run['run_id']) / attempt_id
        created = datetime.fromisoformat(entry['created_at'])
        if (entry['relative_directory'] != expected.as_posix() or created.tzinfo is None
                or created < run['started_at'] or created > datetime.now(UTC) + timedelta(seconds=1)):
            raise ValueError('invalid reservation')
    except (KeyError, ValueError, TypeError):
        raise SourceError('ABR_NAMESPACE_INVALID') from None
    path = _safe(root / expected, root, directory=True)
    if not path.exists():
        return path, created
    info = path.stat()
    if entry.get('state') == 'reserved':
        # No writer is permitted before the durable inode seal. A killed mkdir
        # can leave only an empty directory; populated unsealed paths are held.
        if list(path.iterdir()) or (os.name != 'nt' and stat.S_IMODE(info.st_mode) & 0o077):
            raise SourceError('ABR_NAMESPACE_NOT_SEALED')
        return path, created
    if (entry.get('state') != 'owned' or entry.get('device') != info.st_dev
            or entry.get('inode') != info.st_ino):
        raise SourceError('ABR_NAMESPACE_IDENTITY_CHANGED')
    return path, created


def _files(directory, root, check):
    if not directory.exists():
        return []
    pending, output, directories, total = [(directory, 0)], [], 0, 0
    while pending:
        check()
        folder, depth = pending.pop()
        directories += 1
        if depth > 8 or directories > 2_000:
            raise SourceError('ABR_RECONCILIATION_LIMIT')
        _safe(folder, root, directory=True)
        for path in sorted(folder.iterdir()):
            check()
            if re.fullmatch(r'[A-Za-z0-9_.-]{1,180}', path.name) is None:
                raise SourceError('ABR_NAMESPACE_UNSAFE_PATH')
            if path.is_symlink() or (hasattr(path, 'is_junction') and path.is_junction()):
                raise SourceError('ABR_NAMESPACE_UNSAFE_PATH')
            info = path.lstat()
            if stat.S_ISDIR(info.st_mode):
                pending.append((path, depth + 1))
            else:
                _safe(path, root)
                total += info.st_size
                output.append(path)
                if len(output) > MAX_FILES or total > MAX_BYTES:
                    raise SourceError('ABR_RECONCILIATION_LIMIT')
    return output


def _authority(settings, service):
    with transaction(settings) as conn:
        conn.execute("SET LOCAL lock_timeout='2s'")
        conn.execute("SET LOCAL statement_timeout='5s'")
        _execute_gate(conn, service)


def _reconcile_run(settings, service, root, run, *, execute, check):
    with transaction(settings) as conn:
        conn.execute("SET LOCAL lock_timeout='2s'")
        conn.execute("SET LOCAL statement_timeout='1500ms'")
        _execute_gate(conn, service)
        run = conn.execute('SELECT * FROM pipeline_run WHERE run_id=%s FOR UPDATE', (run['run_id'],)).fetchone()
        if not run:
            raise SourceError('ABR_JOB_NOT_TERMINAL')
        attempts = run['manifest'].get('attempt_namespaces', [])
        if not isinstance(attempts, list) or not 0 <= len(attempts) <= MAX_ATTEMPTS:
            raise SourceError('ABR_NAMESPACE_INVALID')
        if _held(conn, 'run', run['run_id']) or _held(conn, 'pipeline_run', run['run_id']):
            raise SourceError('ARTIFACT_ACTIVE_OR_HELD')
        now = Service.now(conn)
        if run['state'] == 'running':
            committed = run['manifest'].get('promotion_results', {}).get('abr')
            if committed and run['manifest'].get('prepared'):
                if not execute:
                    return {'run_id': str(run['run_id']), 'state': 'preview_recovery', 'registered': 0}
                if execute:
                    from abr_engine.live.abr import ABRRuntime

                    result = ABRRuntime._result(committed, run['manifest']['prepared']['manifest'])
                    conn.execute("UPDATE pipeline_run SET state='complete',finished_at=clock_timestamp(),manifest=manifest||%s WHERE run_id=%s",
                        (Jsonb({'phase': 'complete', 'result': result, 'reason_codes': []}), run['run_id']))
                run = {**run, 'state': 'complete'}
            elif run['started_at'] > now - timedelta(hours=6):
                return {'run_id': str(run['run_id']), 'state': 'active', 'registered': 0}
            else:
                if not execute:
                    return {'run_id': str(run['run_id']), 'state': 'preview_interruption', 'registered': 0}
                if execute:
                    conn.execute("UPDATE pipeline_run SET state='held',finished_at=clock_timestamp(),manifest=manifest||%s WHERE run_id=%s",
                        (Jsonb({'phase': 'held', 'reason_codes': ['ABR_RUN_DEADLINE']}), run['run_id']))
                run = {**run, 'state': 'held'}
        if run['state'] not in {'held', 'failed', 'complete'}:
            raise SourceError('ABR_JOB_NOT_TERMINAL')
    registered = 0
    for entry in attempts:
        directory, created = _namespace(root, run, entry)
        for path in _files(directory, root, check):
            check()
            with transaction(settings) as conn:
                rows = conn.execute("SELECT * FROM artifact_manifest WHERE local_path=%s", (str(path),)).fetchall()
                if any(row['run_id'] != run['run_id'] or row['source'] != 'abr' for row in rows):
                    raise SourceError('ARTIFACT_STILL_REFERENCED')
                row = rows[0] if len(rows) == 1 else None
                if len(rows) > 1:
                    raise SourceError('ARTIFACT_OWNERSHIP_MISMATCH')
                if row and row['state'] == 'deleted':
                    raise SourceError('ARTIFACT_PREVIOUSLY_DELETED')
                if row and (row['snapshot_id'] is not None or row['state'] == 'referenced'):
                    continue
                if row and (_held(conn, 'artifact', row['artifact_id'])):
                    continue
                if row and row['state'] in {'verified', 'orphan'} and len(row['content_digest']) == 64:
                    # Keep previously verified bytes/age intact; never overwrite an
                    # integrity failure or shorten legitimate completed-source retention.
                    continue
                if row and row['state'] not in {'writing', 'orphan'}:
                    raise SourceError('ARTIFACT_NOT_OWNED')
            before = identity(path)
            checksum = digest_file(path, check=check)
            if identity(path) != before:
                raise SourceError('ANALYSED_ARTIFACT_CHANGED')
            age = max(created, datetime.fromtimestamp(path.stat().st_mtime, UTC))
            with transaction(settings) as conn:
                conn.execute("SET LOCAL lock_timeout='2s'")
                conn.execute("SET LOCAL statement_timeout='1500ms'")
                _execute_gate(conn, service)
                current = conn.execute('SELECT * FROM pipeline_run WHERE run_id=%s FOR UPDATE', (run['run_id'],)).fetchone()
                if (not current or current['state'] == 'running' or current['manifest'].get('attempt_namespaces') != attempts
                        or _held(conn, 'run', run['run_id']) or _held(conn, 'pipeline_run', run['run_id'])):
                    raise SourceError('ARTIFACT_ACTIVE_OR_HELD')
                _namespace(root, current, entry)
                _safe(path, root)
                if identity(path) != before:
                    raise SourceError('ANALYSED_ARTIFACT_CHANGED')
                if age > Service.now(conn) + timedelta(seconds=1):
                    raise SourceError('ABR_NAMESPACE_INVALID')
                latest = conn.execute("SELECT * FROM artifact_manifest WHERE local_path=%s FOR UPDATE", (str(path),)).fetchall()
                if latest != rows:
                    raise SourceError('ARTIFACT_OWNERSHIP_MISMATCH')
                if row and (_held(conn, 'artifact', row['artifact_id'])
                            or row['snapshot_id'] and _held(conn, 'snapshot', row['snapshot_id'])):
                    raise SourceError('ARTIFACT_ACTIVE_OR_HELD')
                if execute:
                    owned = row or declare_artifact(conn, run['run_id'], 'abr', path, artifact_class='manifest')
                    conn.execute("UPDATE artifact_manifest SET state='orphan',content_digest=%s,byte_count=%s,"
                        "verified_at=clock_timestamp(),created_at=%s WHERE artifact_id=%s",
                        (checksum, before[2], row['created_at'] if row else age, owned['artifact_id']))
            registered += 1
    if execute:
        with transaction(settings) as conn:
            conn.execute("SET LOCAL lock_timeout='2s'")
            conn.execute("SET LOCAL statement_timeout='1500ms'")
            _execute_gate(conn, service)
            conn.execute('UPDATE pipeline_run SET manifest=manifest||%s WHERE run_id=%s',
                         (Jsonb({'abr_cleanup_checked_at': Service.now(conn).isoformat()}), run['run_id']))
    return {'run_id': str(run['run_id']), 'state': 'reconciled' if execute else 'preview', 'registered': registered}


def reconcile_attempts(settings, *, execute=False, job_id=None, limit=10):
    """Schedule-safe: no adoption outside recorded namespaces, no source authority."""
    if settings.mode not in {'pilot', 'production'} or not 1 <= limit <= 100:
        raise SourceError('LIVE_MODE_REQUIRED')
    with transaction(settings) as conn:
        runs = conn.execute("SELECT * FROM pipeline_run WHERE mode=%s AND manifest->>'kind'='abr_live_job' "
            "AND manifest ? 'attempt_namespaces' AND (%s::uuid IS NULL OR run_id=%s) "
            "ORDER BY manifest->>'abr_cleanup_checked_at' NULLS FIRST,started_at,run_id LIMIT %s",
            (settings.mode, job_id, job_id, limit)).fetchall()
        if not runs:
            return {'status': 'complete' if execute else 'preview', 'runs': []}
        reasons = gate_reasons(conn, settings, 'retention', Service.now(conn))
        if reasons:
            return {'status': 'held', 'reason_codes': reasons, 'runs': []}
    service = Service(settings, load_keys(settings))
    _authority(settings, service)
    root = safe_root(settings)
    started, last_authority = time.monotonic(), 0.0
    def check():
        nonlocal last_authority
        if time.monotonic() - started > 300:
            raise SourceError('ABR_RECONCILIATION_DEADLINE')
        if time.monotonic() - last_authority >= 2:
            _authority(settings, service)
            last_authority = time.monotonic()
    results = []
    try:
        with (process_lock(root / 'abr-live-worker.lock'),
              _session_lock(settings, source_lock_key('abr-live-worker', settings.schema_name))):
            for run in runs:
                try:
                    check()
                    results.append(_reconcile_run(settings, service, root, run, execute=execute, check=check))
                except (SourceError, DomainError, OSError) as error:
                    code = error.code if isinstance(error, (SourceError, DomainError)) else 'ABR_RECONCILIATION_IO_FAILURE'
                    results.append({'run_id': str(run['run_id']), 'state': 'held', 'reason_codes': [code]})
                except Exception:  # noqa: BLE001 -- do not expose private database/file exception text.
                    results.append({'run_id': str(run['run_id']), 'state': 'held',
                                    'reason_codes': ['ABR_RECONCILIATION_FAILED']})
    except (SourceError, DomainError) as error:
        return {'status': 'held', 'reason_codes': [error.code], 'runs': results}
    return json_safe({'status': 'complete_with_holds' if any(r['state']=='held' for r in results) else 'complete' if execute else 'preview', 'runs': results})
