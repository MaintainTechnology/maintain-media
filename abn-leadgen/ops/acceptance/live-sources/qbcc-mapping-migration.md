# QBCC publisher mapping migration

9 September 2026. Mapping `qbcc-catalogue-11-column-v1` is available for explicit
parsing and review. It is **not** approval to collect or promote live records.

The [official catalogue](https://www.data.qld.gov.au/dataset/qbcc-licensed-contractors-register)
and its [zero-row datastore schema](https://www.data.qld.gov.au/api/3/action/datastore_search?resource_id=25608781-b28c-44f8-8545-0ab18d84082f&limit=0)
define 11 source columns. The dated, non-identifying metadata and enum observation
is in [source-check-2026-09-09.json](source-check-2026-09-09.json). Both the
catalogue API and schema API returned HTTP 200. No register row or CSV/ZIP file
was downloaded for this check.

The catalogue still identifies data last modified 18 May 2026. Its description
warns that suspended licensees are present, cancelled licensees are excluded and
current individual licence information requires the QBCC licence search. This
is aged discovery material, not a new-licence feed. CC BY 4.0 is the observed data
licence; collection/retention/privacy approval remains a separate G1 decision.

## Normalisation

- Explicitly use `QBCCMapping.publisher()`; the default stays
  `synthetic-qbcc-v1`. The parser never guesses a mapping from a header mismatch.
- Require the exact ordered 11-column header and the existing UTF-16LE BOM
  contract. The current downloaded CSV's encoding/bytes have not been checked;
  a mismatch must hold for investigation, not silently reinterpret the source.
- Preserve ABN/ACN, original address, category code/description, distinct
  class types, licence type code/description pairs and licence grades. Missing
  ABN remains null. Conflicting business identity, ABN, ACN, category or address
  quarantines the licence; class-related type/grade variation is aggregated.
- Validate the 14 observed category code/description pairs. `SCT1`, `EMR1-2`,
  `EMR3-7` and `N/A` are preserved, never silently converted into Category 1 or 2.
  Future unknown codes and mismatched descriptions quarantine the licence.
- The publisher provides **no status or entity class**. Store `UNKNOWN` and
  `unknown` respectively, and `licence_review_required: true`. Do not infer a
  company from its name or ACN. Existing qualification rejects unknown status;
  parser results alone emit no qualifying backlog event or enrichment request.
  A current, evidence-backed licence/identity review remains necessary.

## Artifact and history boundary

The publisher mapping adds ACN, category description, licence review requirement,
licence type pairs and grades to its Parquet schema. These fields participate in
the row digest. Synthetic mapping schemas/hashes remain unchanged. Record the
mapping version in every manifest. Begin a separate approved publisher baseline;
do not compare a synthetic fixture snapshot with a real publication or relabel
old snapshots. A change to mapping or canonical hashing requires a reviewed new
version and explicit rebaseline/history decision under R41.

## Verification and limits

`tests/unit/test_qbcc_publisher.py` uses synthetic records with the observed
headers and enums. It checks class collapse and deterministic hashes, nullable
ABN, conflicting values, invalid ABN, unknown enums, description mismatch,
encoding/header rejection, Parquet round-trip and blocked unknown status.
Existing fixture tests remain in `tests/unit/test_sources.py`.

This covers the parser part of R12 and the explicit migration part of R41.
Still needed: G1/G2 approval, actual CSV download/encoding/hash/count validation,
production source transport, reviewed candidate staging/promotion, current
licence checks, and production database/hosting. No live gate was changed.
