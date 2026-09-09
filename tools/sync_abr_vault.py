"""Synchronise the reviewed ABR documentation into the local Obsidian vault."""
from pathlib import Path
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parents[1]
VAULT = ROOT / 'MaintainMedia'
FEATURE = ROOT / 'specs/001-abr-lead-engine'
MAPPING = {
    ROOT / 'specs/abr-lead-engine.md': 'ABR Lead Engine',
    ROOT / 'specs/abr-review-source-checks.md': 'ABR Lead Engine - Source Checks',
    ROOT / 'specs/abr-lead-engine.v3.5.backup.md': 'ABR Lead Engine - v3.5 Archive',
    ROOT / '.specify/memory/constitution.md': 'ABR Lead Engine - Constitution',
    ROOT / 'llm-council/runs/20260908-abr-adjudication/judge.md': 'ABR Lead Engine - Final Judge',
    ROOT / 'llm-council/runs/20260908-abr-adjudication/final-plan.md': 'ABR Lead Engine - Final Review Plan',
}
for filename, title in {
    'spec.md':'Product Specification', 'plan.md':'Technical Plan',
    'data-model.md':'Data Model', 'research.md':'Research and Decisions',
    'contracts/interfaces.md':'Interface Contracts', 'quickstart.md':'Developer Quickstart',
    'contracts/precision.md':'Build Contract Precision',
    'tasks.md':'Build Tasks', 'analysis.md':'Consistency Analysis',
    'council-review.md':'Council Review', 'reviewer-notes.md':'Reviewer Notes',
    'workflow-status.md':'Spec Kit Status', 'checklists/requirements.md':'Specification Checklist',
    'implementation-status.md':'Implementation Status',
    'checklists/security-and-readiness.md':'Security and Readiness Checklist',
}.items():
    MAPPING[FEATURE / filename] = 'ABR Lead Engine - ' + title

def transformed(source, body):
    def link(match):
        label, target = match.groups()
        if '://' in target or target.startswith('#'):
            return match.group(0)
        clean = target.split('#', 1)[0]
        resolved = (source.parent / clean).resolve()
        title = MAPPING.get(resolved)
        if title:
            return '[[' + title + '|' + label + ']]'
        if resolved.is_file():
            return '[' + label + '](' + resolved.as_posix() + ')'
        return match.group(0)  # Proposed application paths remain plainly documented.
    return re.sub(r'\[([^\]\n]+)\]\(([^)\n]+)\)', link, body)

def render(source):
    body = source.read_text(encoding='utf-8-sig')
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    title = MAPPING[source]
    meta = '\n'.join([
        '---', 'title: ' + json.dumps(title), 'project: Maintain Media',
        'version: "4.0"' if 'Archive' not in title else 'version: "3.5"',
        'synced: 2026-09-09', 'source: ' + json.dumps(source.relative_to(ROOT).as_posix()),
        'source_sha256: ' + digest, 'tags: [abr-lead-engine, maintain-media]', '---',
        '> Synced from the repository; local document links adapted for Obsidian.',
        '> [[ABR Lead Engine - Build Hub|Open the build hub]]', '',
    ])
    return meta + '\n' + transformed(source, body)

def sync():
    missing = [str(p.relative_to(ROOT)) for p in MAPPING if not p.is_file()]
    if missing:
        raise SystemExit('Missing documentation: ' + ', '.join(missing))
    for source, title in MAPPING.items():
        dest = VAULT / 'Specs' / (title + '.md')
        dest.write_text(render(source), encoding='utf-8')
    print('Synced', len(MAPPING), 'reviewed source documents into MaintainMedia/Specs.')

if __name__ == '__main__':
    sync()
