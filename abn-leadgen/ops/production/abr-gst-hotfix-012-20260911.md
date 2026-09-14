# ABR hold fix (UNKNOWN_GST_STATE) — release 012 hand-off, 11 September 2026

## What was wrong

Every live ABR run on 11 September (12:13, 12:40, 12:43, 12:49) ended **Held /
UNKNOWN GST STATE**. The public parser (`src/abr_engine/ingest/abr_public.py`)
accepted only GST status `ACT`, `CAN` or an empty node. The actual ABN Lookup
bulk extract published on 9 September 2026 uses three dated GST states:

| GST status | Records in first 62,189 of `20260909_Public01.xml` | Date |
| --- | --- | --- |
| `NON` (not registered) | 26,627 | always `19000101` |
| `CAN` | 25,725 | real date |
| `ACT` | 9,837 | real date |

The sixth record in the file is `NON`, so the parser raised on every attempt and
the worker recorded the run as held. No accepted ABR data was replaced; that
protection worked as designed. The publisher's XSD (`bulkextract.xsd`, identical
to the pinned copy) types `status` as a free string, so schema validation
could not catch this earlier.

## What changed

- `abr_public.py`: `NON` is accepted and stored verbatim; only `ACT` ever counts
  as registered downstream (diff events, qualification and promotion compare
  against `ACT` only). Undated or unknown states still hold the run.
- Unit tests for the three published states plus the held cases; an integration
  test that baselines a `NON` record and then observes `gst_registered`.
- Website: a completed QBCC run now explains that leads are created only after
  a reviewer records a licence and identity check, and the Reports column says
  "Source receipt only" for completed live runs instead of "No current report".

Evidence: 78 parser unit tests pass; the real 62,189-record sample parses
completely with the fix (`ACT` 9,837 / `CAN` 25,725 / `NON` 26,627, no other
source error); ABR live-runtime integration tests pass against isolated
PostgreSQL 16.

## Why QBCC shows "Complete" with one Tier A lead

That is the designed pilot behaviour, not a fault. A QBCC run accepts the
register snapshot and lists Category 1–2 licences for review; it never
qualifies a lead automatically. The single Tier A lead is the one licence a
reviewer has recorded. More leads appear only as reviewers record checks in
**QBCC source review**.

## Deploy the engine fix (operator, needs the AWS deployment key)

The release archive is built from the fixed tree:

- `release.tar.gz` sha256 `59becff14e88de6748fbeb58508a573b0ab589e7146eed0ef03e87aad49cb404`
- `RELEASE-MANIFEST.json` sha256 `03073e611e12e41c6790521858a907a7ab2c84f00a4757b50695889c9d39ca8a`
- 164 files, `uv.lock` unchanged (`c7c7a582…`)

Rebuild any time with `python abn-leadgen/ops/aws/prepare_release.py build --root abn-leadgen --output <new dir>`.

1. Copy `release.tar.gz`, `receipt.json` and `ops/aws/prepare_release.py` to
   `ubuntu@3.104.119.142` (host `abn-engine.maintainmedia.com.au`) using the
   recorded key and `StrictHostKeyChecking=yes`.
2. On the host follow `ops/aws/release-install.md`, extracting to a **new**
   stage directory `/opt/abn-leadgen-live-20260911-012-stage` and running the
   frozen `uv sync` and offline checks there.
3. Stop the engine units, then cut over with the same staged/previous pattern as
   release 011 (`activate_live_source.py`): current → `/opt/abn-leadgen-live-20260911-011-previous`,
   stage → `/opt/abn-leadgen`, verifying the old and new manifest hashes.
   Configuration, gates, policy and the ABR observation config are untouched.
4. Start the units, then submit one ABR run from the dashboard (Setup → ABR →
   Check ABR updates). Expect `Discovering → Downloading → Validating → Parsing →
   Diffing → Promoting → Complete` with "ABR baseline accepted" and zero events
   and zero leads. The full 20-file publication can take a few hours within the
   six-hour run budget.

## Deploy the website wording

Commit and push `website/src/components/abn-lead-gen/{readiness.ts,dashboard.tsx}`;
the Vercel project deploys `main`. No engine change is needed for this part.
