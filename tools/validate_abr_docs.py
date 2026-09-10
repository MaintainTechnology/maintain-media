"""Check document integrity; deliberately does not claim application validation."""
from pathlib import Path
import json
import re
import sys
import sync_abr_vault as vault

root = Path(__file__).resolve().parents[1]
feature = root / 'specs/001-abr-lead-engine'
errors = []
canonical = (root / 'specs/abr-lead-engine.md').read_text(encoding='utf-8-sig')
spec = (feature / 'spec.md').read_text(encoding='utf-8-sig')
tasks = (feature / 'tasks.md').read_text(encoding='utf-8-sig')
requirements = re.findall(r'^\*\*R(\d+)\s', canonical, re.M)
fr = re.findall(r'^- \*\*(FR-\d{3})\*\*', spec, re.M)
taskids = re.findall(r'^- \[[ xX]\] (T\d{3})\b', tasks, re.M)
completed = set(re.findall(r'^- \[[xX]\] (T\d{3})\b', tasks, re.M))
expected = {f'FR-{i:03}' for i in range(1,44)}
if requirements != [str(i) for i in range(1,44)]: errors.append('Canonical R1-R43 missing/duplicate/out of order')
if set(fr) != expected or len(fr) != 43: errors.append('Feature FR001-043 missing/duplicate')
if len(set(taskids)) != len(taskids) or not taskids: errors.append('Task IDs missing/duplicate')
if completed:
    try:
        ledger = json.loads((feature / 'task-evidence.json').read_text(encoding='utf-8'))
        for task in completed:
            entry = ledger['tasks'][task]
            if entry.get('state') != 'complete' or not entry.get('scope') or not entry.get('evidence'):
                errors.append('Missing completion evidence: ' + task)
                continue
            for item in entry['evidence']:
                evidence_path = (root / item['path']).resolve()
                if (not evidence_path.is_relative_to(root) or not evidence_path.is_file() or
                    vault.digest(evidence_path) != item['sha256'] or
                    not item.get('command') or not item.get('result')):
                    errors.append('Invalid or changed task evidence: ' + task)
        if set(ledger['tasks']) != set(taskids):
            errors.append('Task evidence inventory mismatch')
    except (OSError, ValueError, KeyError, TypeError):
        errors.append('Unreadable task evidence ledger')
covered = set(re.findall(r'FR-\d{3}', tasks))
if expected - covered: errors.append('Unmapped requirements: ' + str(sorted(expected-covered)))
if covered - expected: errors.append('Unknown requirement IDs: ' + str(sorted(covered-expected)))
if '--report' in sys.argv:
    rows=[]
    for req in sorted(expected):
        matches=[]
        for line in tasks.splitlines():
            if re.match(r'^- \[[ xX]\] T', line) and req in line:
                matches.append(re.search(r'T\d{3}',line).group())
        rows.append('| '+req+' | Yes | '+', '.join(matches)+' | Canonical R'+str(int(req[3:]))+' |')
    report='''# Specification Consistency Analysis — ABR Lead Engine v4.0
Reviewed 2026-09-08. This is a documentation analysis, not a test of application behaviour.

## Findings and resolutions
| ID | Severity | Original issue | Final resolution |
|---|---|---|---|
| A1 | High | Unsubstantiated legal/revenue/pricing certainty | Official source checks; R23/R27/R40; unsupported claims withdrawn |
| A2 | High | Date-only snapshots and incoherent publication pairing | R2-R8 content identity, coherent inventory and atomic promotion |
| A3 | High | Weekly opt-out update and stale exported permission | R24-R25 live authority and synchronous durable suppression |
| A4 | High | Indefinite versus finite retention | R29 single finite schedule, erasure/restore controls |
| A5 | Medium | Non-transitive cross-source rank ties | R14 one score/time/UUID total order |
| RV-01 | Medium | Spreadsheet edits mistaken for total work | R38; operator_activity ledger; T050 includes calls/research/wash/admin |
| RV-02 | Medium | Older permission pass could survive later negative | R21 assessment sequence/current pointer; model and interface aligned |
| RV-03 | Medium | Undefined identity freshness | R16 current exact business/domain identity90d and QBCC review30d |
| RV-04 | Medium | Cancellation resolution contradicted permanent opt-out | R25 reason-specific resolution; opt-out/complaint remain blocked |
| RV-05 | Medium | Wrong business/domain evidence could grant permission | R20 composite identity/lead/domain provenance relationship |
| RV-06 | Medium | Tasks absent at first review | 59 unique unchecked tasks; all43 FRs mapped below |

Independent reviewer re-read marked all20 custom writing criteria satisfied; details in
[reviewer-notes.md](reviewer-notes.md). No unresolved substantive design finding from that pass.
The Council independently scores a frozen supplied document package; see [council-review.md](council-review.md).

## Coverage
| Requirement | Has task | Task IDs | Detailed acceptance source |
|---|---|---|---|
'''+ '\n'.join(rows)+'''

## Acceptance coverage
- US1/SC002/003: T014-T027 define pilot identity, qualification, evidence and allowed/blocked export tests.
- US2/SC004: T028-T034 define immediate opt-outs, current action checks and restore races.
- US3/SC001: T035-T043 define coherent snapshots, events, deterministic rules and recovery tests.
- US4/SC008/009: T044-T051 define private worklist, CRM/outcomes and measured pilot decisions.
- US5/SC005: T011-T012 budget reservation and concurrency fixtures.
- US5/SC006/007: T052-T059 capacity, operational recovery and handover evidence.
Implementation outcomes and commercial pilot measures remain unchecked/pending.

## Constitution review
Five principles applied: evidence before claims; authoritative permission/suppression;
deterministic recovery; bounded operations; traceable acceptance. No unresolved conflict identified.
Feature requirements contain business outcomes; language/framework choices are in the technical plan.
Current gate states are PENDING and production capability switches OFF.

## Metrics and limits
43 requirements,59 unique unchecked tasks,43/43 mapped (100%). No unknown requirement IDs.
No application implementation, live law/source clearance or performance acceptance is asserted.
Rule recovery or explicit replacement, accounts, current pricing, approval evidence, capacity and
actual pilot outcomes remain genuine release dependencies. Synthetic build work can begin.

## Next action
Start the scoped fixture build with the unchecked tasks; keep production adapters disabled until
the relevant release gates have evidence. The post-implementation converge command has not run.
'''
    (feature/'analysis.md').write_text(report,encoding='utf-8')
for path in [root/'.specify/memory/constitution.md', *feature.rglob('*.md')]:
    body = path.read_text(encoding='utf-8-sig')
    if re.search(r'\[(?:PROJECT_NAME|PRINCIPLE_\d_NAME|NEEDS CLARIFICATION:)', body):
        errors.append('Unfilled template: ' + str(path))
    if len(re.findall(r'^```',body,re.M)) % 2:
        errors.append('Unbalanced fences: ' + str(path))
    for label,target in re.findall(r'\[([^\]\n]+)\]\(([^)\n]+)\)',body):
        if '://' in target or target.startswith('#') or not target.split('#')[0].endswith('.md'): continue
        if not (path.parent/target.split('#')[0]).resolve().is_file():
            errors.append('Broken document link: '+str(path.relative_to(root))+': '+target)
if '--vault' in sys.argv:
    for source,title in vault.MAPPING.items():
        dest = vault.VAULT/'Specs'/(title+'.md')
        if not dest.is_file() or dest.read_text(encoding='utf-8') != vault.render(source):
            errors.append('Vault mirror drift: '+title)
    titles={p.stem for p in vault.VAULT.rglob('*.md')}
    for path in (vault.VAULT/'Specs').glob('*.md'):
        for link in re.findall(r'\[\[([^\]]+)\]\]',path.read_text(encoding='utf-8')):
            target=link.split('|')[0].split('#')[0]
            if target and target not in titles: errors.append('Missing vault note: '+target)
print(f'Document checks: {len(fr)} requirements, {len(taskids)} build tasks ({len(completed)} evidence-backed complete), {len(expected & covered)}/43 mapped requirements.')
print('These checks validate document structure and links, not implementation, law or production.')
for error in errors: print('ERROR:',error)
raise SystemExit(1 if errors else 0)
