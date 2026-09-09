# Bounded legacy input filename search

9 September 2026. Parent-authorised read-only filename search outside the current repository. No file contents, credentials, secrets, archives or unrelated source files were inspected. No frozen implementation/configuration/test files changed.

Searched these two roots with `rg --files --hidden --no-ignore`:

- `C:/Users/dalig/Desktop/MaintainTech`
- `C:/Users/dalig/Downloads`

Pruned directories named `node_modules`, `.git`, `.venv`, `venv`, `var`, `runtime`, `.runtime`, `largecache`, `.cache`, `cache`, `.next`, `__pycache__`, and the current `maintain-media` repository. The final pass used case-insensitive explicit filename filters:

```text
extract_new_abns.py
*abr*rule*
*abn*rule*
*30*rule*
*rule*30*
*legacy*rule*
rules.yaml
rules.yml
classification_rules.json
industry_rules.yaml
```

Command shape, repeated once for each root:

```powershell
rg --files --hidden --no-ignore `
  --glob '!**/node_modules/**' --glob '!**/.git/**' `
  --glob '!**/.venv/**' --glob '!**/venv/**' --glob '!**/var/**' `
  --glob '!**/runtime/**' --glob '!**/.runtime/**' --glob '!**/largecache/**' `
  --glob '!**/.cache/**' --glob '!**/cache/**' --glob '!**/.next/**' `
  --glob '!**/__pycache__/**' --glob '!**/maintain-media/**' `
  --iglob 'extract_new_abns.py' --iglob '*abr*rule*' --iglob '*abn*rule*' `
  --iglob '*30*rule*' --iglob '*rule*30*' --iglob '*legacy*rule*' `
  --iglob 'rules.yaml' --iglob 'rules.yml' `
  --iglob 'classification_rules.json' --iglob 'industry_rules.yaml' $legacySearchRoot
```

Both roots returned no matching paths, with `rg` exit1 (no matches) and no diagnostic errors. The final two-root search took2.35 seconds of shell execution. An earlier narrower case-sensitive pass also found no matches; the final case-insensitive pass supersedes it.

**Result: no candidate found within these filename/root/exclusion bounds.** This does not prove that the intended extractor or actual30-rule corpus is absent elsewhere, under a different filename, inside an excluded directory or archive, or on another device. No source provenance or30-rule match can be certified. T041/T065's actual legacy input dependency remains pending; synthetic rules are not substituted as recovered legacy material.
