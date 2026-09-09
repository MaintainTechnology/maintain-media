"""Prepare anonymised randomly ordered prior reviews for a native fallback judge."""
from pathlib import Path
import hashlib
import json
import random
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'llm-council/runs/20260908-abr-adjudication'
OUT.mkdir(parents=True, exist_ok=True)
reviews=[] if '--manifest-only' in sys.argv else list((ROOT/'llm-council/runs/20260908-abr-precision').glob('plan-reviewer-*.md'))
random.SystemRandom().shuffle(reviews)
for i,p in enumerate(reviews,1):
    body=p.read_text(encoding='utf-8')
    body=re.sub(r'\b(?:codex|claude|gemini|opencode|openai|anthropic|gpt-[\w.-]+)\b','[MODEL REDACTED]',body,flags=re.I)
    (OUT/f'anonymous-review-{i}.md').write_text(body,encoding='utf-8')
files=[ROOT/'specs/abr-lead-engine.md',ROOT/'specs/abr-review-source-checks.md',
       ROOT/'.specify/memory/constitution.md',*sorted((ROOT/'specs/001-abr-lead-engine').rglob('*.md'))]
manifest={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
(OUT/'input-manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
print('Prepared',len(reviews),'anonymous prior reviews and',len(files),'source hashes.')
