Backend release and CSV verification
===================================

The installed manifest is `4c7439686d5bc65f6c009ff4e1184e163fbab5985179a8a1c21663a293641c5f`, with 167 verified source entries. Exactly four Python modules changed. Only `abr-engine-api.service` restarted. The prior manifest, API module and source-record reader remain under `/opt/abn-source-query-rollback-b345ba43`; their hashes were verified after cutover.

`backend-https-readback.jsonl` records 24 completed checks against actual engine HTTPS. These include the user's explicit ABR/QBCC runs, first/second/last/latest pages, all stored columns, name and identifier filters, matched CSV counts, exact Origin enforcement and one-use tickets. It includes a complete 108,019-row QBCC CSV and a complete 108,908-row filtered ABR CSV. CSV content was parsed, hashed and discarded; no source rows or credentials are included in these receipts.

`full-abr-csv-verification.jsonl` records a complete staged read-only traversal of the retained ABR publication using the production CSV generator: 20,510,902 rows, 14 columns, 7,198,717,434 bytes, SHA-256 `b043d15c55c607aa6cbfe0c595e0fcde8b210ade6aa32c6e8bacde01f3446fb5`, 345.498 seconds. This measured processing and validation on the server, excluding download transfer time. It retained no CSV copy. Subsequent changes added an aggregate coalescing memory cap, cancellation cleanup and a transport deadline; the scalar CSV serializer and unfiltered source predicate were unchanged. Those final changes passed focused tests and the installed HTTPS export checks.

The export completion audit means the server generator finished yielding the CSV. It does not independently confirm that the browser saved the file successfully.
