# T036 injected discovery composition

9 September 2026. New `src/abr_engine/ingest/discovery.py` composes the existing resumable downloader and archive parser. No live source URL, credentials, transport or publisher schema is supplied by default; `production=True` fails before filesystem creation or reader/transport invocation. The existing runnable fixture pipeline remains unchanged.

`discover_publication(attempt_dir, contract=PublisherMapping(...), mapping=ABRMapping(...), metadata_reader=..., transport=...)` validates an explicit exact publisher field mapping, dataset identity, HTTPS hosts, unique resource/part/URL inventory and all declared sequences. It creates an exclusive attempt directory with generated filenames, downloads every resource using the existing five-attempt strong-validator range protocol, binds known publisher validators/digests/lengths to the actual responses, enforces a cumulative byte ceiling even for unknown source lengths, and rereads metadata before parsing. Metadata drift holds without parsing or publishing a successful manifest. Actual archive/member/CRC/parser/coherence checks then run; inner generation must match the discovery generation before an exclusive publication manifest is written. This helper performs no database promotion.

The manifest includes contract/review/licence references, dataset/resource URLs and IDs, retrieval times, explicit unknown publisher timestamp where absent, metadata before/after digests, downloaded-content hashes, actual ZIP response validators, inventory and inner generation. Source-owner independent review identified that the injected JSON-only metadata reader has no HTTP header receipt. The final manifest now explicitly records its metadata response validators as unavailable with null ETag/Last-Modified, and a test asserts that state. Real metadata response header capture and actual publisher schema approval remain adapter/release obligations; ZIP validators are not presented as metadata validators.

The root read the full composition and reported no confirmed high finding. The source owner separately reviewed the files, reported no high/critical coherence/download defect, and identified the metadata-evidence correction above. Those reviews are bounded, not external source certification. The writer built this module and its tests.

Final focused commands, executed locally with Python3.12 and the frozen uv environment:

```powershell
uv run ruff check src/abr_engine/ingest/discovery.py tests/unit/test_discovery.py
uv run mypy src/abr_engine/ingest/discovery.py
uv run pytest -q tests/unit/test_discovery.py tests/unit/test_sources.py
```

Results: Ruff clean; mypy one source file clean; **58 passed in4.52s** (17 new discovery cases plus41 existing source cases). Tests use actual synthetic ZIP bytes and the real parser: complete multipart success, interrupted/resumed range, five metadata-drift variants with fresh-attempt recovery, invalid inventory/schema/dataset/host before download, response-validator mismatch, digest and inner-generation mismatch, bounded metadata/download retry, cumulative unknown-length byte exhaustion, safe generated paths and pre-I/O live rejection. No full suite was run for this subtask.

T036's original local implementation can be checked after the root's new frozen combined verification. Actual publisher contract/smoke, response-header capture and installed source polling stay pending under T053/T058/T065; this work does not open G1/G6 or claim production acceptance.
