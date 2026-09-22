# Source records workspace

The new-business discovery and saved-research extension is documented in [Prospect research](prospect-research.md). It adds recent ABN status-date filters and keeps first-registration verification and digital-presence findings separate from publisher records.

ABR and QBCC accepted publications have a separate Source records tab. Opening it automatically loads the selected source. Latest leads keeps its own All sources / ABR / QBCC lead filters. Completed run links open the exact source and run in Source records.

The table exposes every currently stored normalized field: 14 for ABR and 17 for QBCC, including all published names, nested licence types/classes/grades, review flags and provenance hashes. It does not claim to reconstruct publisher fields discarded during the original parse. Current ABN links open official ABN Lookup; current trade licence checks remain with QBCC. Publisher status and imported registration status are labelled separately from current verification. Missing publisher timezone is never inferred.

Search covers the entire accepted publication. Eleven-digit ABNs support spaces and hyphens and match exactly. Names also search alternate ABR names. Source-specific filters include state/territory, postcode, ABN/GST status, entity class/type and QBCC financial category. Apply filters submits a server query; Clear filters restores the full publication. Fixed 50-row pages remain bound to the accepted run, and late responses cannot replace a newly selected source/run. Publication and filtered counts are separate. Tables contain their own horizontal/vertical scrolling at mobile and desktop sizes.

CSV actions download either the entire selected publication or every matching record, independently of the visible page. Every stored field is included. Nested fields are JSON CSV cells; formula-like text receives a spreadsheet-safe prefix. The authenticated website issues a short-lived, one-use ticket scoped to the staff actor, immutable snapshot, filters and website origin. A browser POST sends the ticket directly to the engine, avoiding a multi-gigabyte JavaScript Blob or Vercel response. Tickets never enter URLs. Interrupted streams must fail and cannot be recorded as completed exports.

The source reader uses immutable Parquet metadata and filtered row-group count caching. It enforces source/run binding, staff scopes, personal-data authority, retention and file integrity before and after reads; CSV rechecks between batches. Reads and exports are audited. No source collection, matching, qualification or outreach is triggered.

Verification covers live source performance and full CSV row counts, authenticated bridge/query/export boundaries, stale responses, filtered-vs-full export requests, nested-field fidelity, source navigation, empty/expired states, browser form transport and responsive layout. Publishing requires the complete frozen website upload and narrowly scoped engine modules to pass their checks.
