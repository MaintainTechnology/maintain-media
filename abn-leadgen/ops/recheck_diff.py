"""Task-local repeat of the retained, synthetic sizing input after a query fix."""
import hashlib
import json
import platform
import threading
from datetime import UTC, datetime
from uuid import uuid4

import duckdb

from abr_engine.config import ROOT
from abr_engine.diff.events import diff_snapshots
from abr_engine.ops.capacity import measure_callable


def main():
    source = ROOT / "var/benchmark-3cf2633055484c90a0ea52bfc53000a1"
    work = ROOT / "var" / ("diff-recheck-" + uuid4().hex)
    work.mkdir()
    output = work / "events.parquet"
    peak_spill = [0]
    done = threading.Event()
    def monitor():
        while not done.wait(.1):
            try:
                peak_spill[0] = max(peak_spill[0], sum(p.stat().st_size for p in work.rglob('*') if p.is_file() and 'spill' in str(p.parent)))
            except FileNotFoundError:
                pass
    watcher = threading.Thread(target=monitor, daemon=True)
    watcher.start()
    try:
        result, metrics = measure_callable(lambda: diff_snapshots([source / 'previous.parquet'], [source / 'current.parquet'], output,
                snapshot_id=str(uuid4()), observed_at=datetime.now(UTC)), rows=20500000,
                runtime_version=platform.python_version(), output_paths=[output])
        con = duckdb.connect()
        try:
            con.from_parquet(str(output)).create_view('events')
            metrics['event_counts'] = dict(con.execute('SELECT event_type,count(*) FROM events GROUP BY event_type').fetchall())
        finally:
            con.close()
        metrics['status'] = 'complete'
        metrics['event_count'] = result.event_count
    except duckdb.Error as exc:
        metrics = {'status': 'failed', 'failure_type': type(exc).__name__, 'reason': str(exc).split('\n')[0]}
    finally:
        done.set()
        watcher.join()
    metrics.update({'input_root': str(source), 'output': str(output), 'peak_spill_bytes': peak_spill[0],
                    'diff_code_sha256': hashlib.sha256((ROOT / 'src/abr_engine/diff/events.py').read_bytes()).hexdigest(),
                    'lockfile_sha256': hashlib.sha256((ROOT / 'uv.lock').read_bytes()).hexdigest(),
                    'full_scale_certified': False, 'db_wal_measured': False})
    evidence = ROOT / 'ops/acceptance' / ('diff-recheck-' + uuid4().hex + '.json')
    evidence.write_text(json.dumps(metrics, indent=2))
    print(json.dumps({'evidence': str(evidence), **metrics}))


if __name__ == '__main__':
    main()
