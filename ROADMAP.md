# Prisma-function roadmap

This file contains only the current product direction and active work. Historical implementation records are preserved in `docs/CHANGELOG.md`.

## Current authoritative workflow

1. The user independently downloads one or more official PRISMA Export CSV files.
2. The user selects each local CSV with Select CSV.
3. Prisma Function reads the complete file without an application row limit.
4. The application validates and transforms every row.
5. Auctions below the normalized 1 MWh booked-capacity threshold are filtered out.
6. Prices are normalized to EUR/MWh/h using the calendar date from Start of Auction.
7. Accepted rows are merged atomically into cumulative persistent storage.
8. Exact re-import and partial overlap do not create duplicates.
9. Mapping reloads all cumulative accepted rows in the authoritative 12-column form.
10. Published UTF-8 semicolon-delimited output is available for monitoring-system integration.

Prisma Function does not access the PRISMA website. Managed browser/download automation, Playwright, PDF input, live monitoring, scheduling, and notifications are excluded.

## Authoritative Mapping and output contract

The Mapping table and published output contain exactly these fields in this order:

1. Auction Date — YYYY-MM-DD
2. Exit Market
3. Entry Market
4. Capacity Type — entry, exit, or bundle
5. Network Point Name
6. Product Type — WD, Day Ahead, Month, Quarter, or Year
7. Flow Start — YYYY-MM-DD HH:mm
8. Flow End — YYYY-MM-DD HH:mm
9. Booked Capacity — kWh/h
10. Flow Duration Hours
11. Tariff Price — EUR/MWh/h
12. Premium Price — EUR/MWh/h

Mapping supports unrestricted vertical and horizontal scrolling and has no preview or row-count limit.

## Active invariants

- Input: official 34-column, Windows-1252, semicolon-delimited PRISMA Export CSV.
- Input detection: exact header contract, never filename.
- Complete-file processing: read until EOF; no 5,000-row application cap.
- Same-date imports: multiple different files are accepted.
- Deduplication: exact composite key Auction ID + Network Point Name + Capacity Type (P.40); never filename, file hash, source date, or whole-file/full-row content equality. A key match skips the incoming row outright — PRISMA data is immutable, so the stored row is never updated or merged.
- Persistence: old accepted data remains across sessions; new distinct data is added atomically.
- Filtering: normalized booked capacity must be at least 1 MWh.
- Time: Europe/Berlin CET/CEST, including typed rejection of ambiguous or nonexistent local timestamps.
- Currency: EUR/MWh/h, keyed by the calendar date from Start of Auction; official ECB rate, explicit quotation direction, prior available reference-date fallback.
- Mapping evidence: exact Auction-ID-linked and side-specific only.
- Published output: UTF-8, semicolon-delimited, exact 12 columns.
- Runtime storage: %LOCALAPPDATA%\PrismaFunction\.
- User-facing publication: approved Documents directory.

## Completed increment

### P.37 — Start-of-Auction ECB normalization and cumulative Mapping correction

Status: implemented, automated-tested, and manually validated on real Windows on 2026-08-16; PR #77 pending merge.

Implemented result:

- EUR, GBP, CZK, and CHF source prices normalize to EUR/MWh/h using Start of Auction.
- Each unique date/currency rate is resolved once and persisted for reuse.
- ECB weekends and holidays use the latest prior available reference date.
- Mixed-currency bundle sides normalize independently before summation.
- Every row in every selected CSV is processed, including rows after 5,000.
- Multiple CSV files for the same date are accepted.
- Exact retry and partial overlap are idempotent.
- Mapping shows all cumulative accepted rows using the exact 12-column contract.
- Manual Windows acceptance confirmed same-date multi-file import, cumulative Mapping, and idempotent behavior.

Automated evidence reported for the final correction: 608 passed, 1 skipped; final source-update focused suite 21 passed; tracked Python py_compile passed; git diff --check passed with the existing CRLF warning for tests/test_prisma_publication.py.

### P.40 — Composite-key cumulative row deduplication

Status: implemented and automated-tested (2026-08-17) on branch `feature/p38-composite-row-deduplication` (branch name predates this numbering; see the numbering note below). Not yet merged to `main`.

**Numbering note:** this increment was requested under the label "P.38", but P.38/P.39 above already record different, completed, unrelated work (removing the managed PRISMA browser/download workflow, and collapsing Select CSV into the single processing action). It is recorded here as P.40, the next free slot, following the same correction pattern already used between P.36.21/P.37 and P.38/P.39.

Implemented result:

- Cumulative-output deduplication is redefined from exact-full-row-equality to the exact composite key **Auction ID + Network Point Name + Capacity Type** (`storage.AuctionStorage.published_output_row_keys`/`record_published_output_row_keys`, consulted by `prisma_publication.publish_cumulative_output`). A row whose key already has a durably recorded counterpart is skipped outright; PRISMA data is immutable, so the stored row is never updated or merged, even if the incoming row's other fields differ. Different rows sharing a source file, source date, product period, filename, or file hash remain independently acceptable.
- A real-Windows validation pass then surfaced a second, independent invariant: `prisma_source_operations`' source-date uniqueness (enforced by the now-removed `prisma_source_updates.py` and a `UNIQUE(source_date)` table constraint) still rejected a second, distinct CSV import sharing an already-accepted source date. This invariant is removed from the active import path entirely: `storage.AuctionStorage.begin_operation`/`operation_for_digest` key the source-operation ledger by `sha256` alone, never `source_date`, so distinct files sharing a source date are always independently accepted; a digest match against an in-flight or already-accepted ledger row still resumes/short-circuits reprocessing identical bytes as an internal bookkeeping optimization, never a rejection. Exact-retry and partial-overlap idempotence are provided exclusively by the composite row key above. `prisma_source_updates.py` and its dedicated tests are deleted; `prisma_import_workflow.py` computes and verifies the source digest directly.
- `AuctionStorage._ensure_source_operations_schema` migrates a database file created before this correction in place: it detects any pre-existing unique constraint over `prisma_source_operations` that still includes `source_date` (structurally, via `PRAGMA index_list`/`PRAGMA index_info`, covering both the original `UNIQUE(source_date)` shape and an intermediate `UNIQUE(source_date, sha256)` shape) and losslessly rebuilds the table under the corrected `UNIQUE(sha256)` identity, within the same transaction `_create_schema` already holds.
- A stale runtime-data migration lock left by a terminated process is now reclaimed immediately on the next launch: `runtime_paths._inspect_stale_lock` decides staleness from the recorded owner PID's liveness whenever a PID can be parsed, not from lock age alone — fixing a real-Windows regression where closing and immediately relaunching the application failed with a false "migration is busy" error.

Automated evidence: 623 passed, 1 skipped (the pre-existing platform-dependent symlink test); `python -m compileall`; `git diff --check`. Real-Windows validation surfaced and led to the two same-day regression fixes above (source-date invariant removal, stale migration-lock recovery); manual real-Windows validation of the corrected behavior, and of the original composite-key dedup itself, remains outstanding.

## Next work

Select the next increment only after this merge (P.37 and P.40 together) lands on `main` and both feature branches are cleaned up. Do not restore or continue superseded P.36 managed-download work. Future work must be derived from the newest approved specification and an explicit customer decision.
