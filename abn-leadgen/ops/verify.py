"""Reproducible local/CI gates with immutable revision/environment evidence."""
import hashlib
import json
import platform
import subprocess
import sys
import time
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]


def revision_digest():
    inventory = {}
    for folder in ('src', 'migrations', 'tests', 'config', 'integrations', 'templates', 'ops'):
        for path in sorted((ROOT / folder).rglob('*')):
            if path.is_file() and '__pycache__' not in path.parts and 'acceptance' not in path.parts:
                inventory[path.relative_to(ROOT).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    for name in ('uv.lock', 'pyproject.toml', '.python-version', 'README.md'):
        inventory[name] = hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
    for path in sorted((ROOT.parent / 'specs/001-abr-lead-engine').rglob('*')):
        if path.is_file() and path.suffix in {'.md', '.json'}:
            inventory['../' + path.relative_to(ROOT.parent).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    for name in ('specs/abr-lead-engine.md', '.specify/memory/constitution.md', 'tools/validate_abr_docs.py', 'tools/sync_abr_vault.py', '.github/workflows/abr-engine.yml'):
        inventory['../' + name] = hashlib.sha256((ROOT.parent / name).read_bytes()).hexdigest()
    return hashlib.sha256(json.dumps(inventory, sort_keys=True).encode()).hexdigest(), inventory


def main():
    manifest = json.loads((ROOT / 'tests/requirements.json').read_text())
    assert {r['requirement'] for r in manifest['requirements']} == {f'FR-{n:03d}' for n in range(1,44)}
    for requirement in manifest['requirements']:
        assert requirement['scope'] and requirement['tests']
        assert all((ROOT / path).is_file() for path in requirement['tests'])
    revision, inventory = revision_digest()
    run = ROOT / 'ops/acceptance' / ('verify-' + uuid4().hex)
    run.mkdir()
    commands = [['uv', 'sync', '--frozen'], ['uv', 'run', 'ruff', 'check', 'src', 'tests', 'ops'],
                ['uv', 'run', 'mypy', 'src'], ['uv', 'run', 'python', '../tools/validate_abr_docs.py', '--vault'],
                ['uv', 'run', 'pytest', '-q', '--junitxml=' + str(run/'pytest.xml')]]
    results = []
    for index, command in enumerate(commands):
        started = time.perf_counter()
        log = run / f'command-{index+1}.log'
        with log.open('w', encoding='utf-8') as stream:
            try:
                result = subprocess.run(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT, timeout=1800, check=False)
                code = result.returncode
            except (subprocess.TimeoutExpired, OSError) as exc:
                code = 124 if isinstance(exc, subprocess.TimeoutExpired) else 127
                stream.write(type(exc).__name__ + ': check did not complete\n')
        results.append({'command': command, 'exit_code': code, 'elapsed_seconds': time.perf_counter()-started, 'log': str(log)})
        print(json.dumps(results[-1]), flush=True)
    after, _ = revision_digest()
    passed = all(r['exit_code'] == 0 for r in results) and revision == after
    evidence = {'status': 'passed' if passed else 'failed', 'code_tree_sha256': revision, 'unchanged_during_checks': revision == after,
                'environment': platform.platform(), 'python': platform.python_version(), 'commands': results,
                'files': inventory, 'scope': 'Offline engineering checks. Production gates and live pilot remain separate.'}
    (run / 'result.json').write_text(json.dumps(evidence, indent=2))
    print(json.dumps({'status': evidence['status'], 'evidence': str(run/'result.json')}))
    return 0 if passed else 1


if __name__ == '__main__':
    sys.exit(main())
