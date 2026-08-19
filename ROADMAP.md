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

1. Auction Date — DD-MM-YYYY, derived from Start of Auction
2. Exit Market — from the approved exact side-specific mapping for the exit side, populated regardless of Direction; blank when its own mapping is unavailable, never inferred or cross-filled from Entry Market
3. Entry Market — from the approved exact side-specific mapping for the entry side, populated regardless of Direction; blank when its own mapping is unavailable, never inferred or cross-filled from Exit Market
4. Capacity Type — entry, exit, or bundle
5. Network Point Name
6. Product Type — WD, Day Ahead, Month, Quarter, or Year
7. Flow Start — DD-MM-YYYY HH:mm
8. Flow End — DD-MM-YYYY HH:mm
9. Booked Capacity — kWh/h
10. Flow Duration Hours
11. Tariff Price — EUR/MWh/h; a bundle row's exit-side and entry-side tariff are each normalized independently, then summed
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

### P.41 — Mapping format and Exit/Entry Market correction

Status: implemented and automated-tested (2026-08-19) on branch `feature/mapping-format-market-price-corrections`. Not yet merged to `main`.

Implemented result:

- `Auction Date` in Mapping/published output is formatted `DD-MM-YYYY`, derived from Start of Auction; `Flow Start`/`Flow End` are formatted `DD-MM-YYYY HH:mm` (`prisma_datetime.format_mapping_auction_date`/`format_mapping_flow_timestamp`, applied only in `prisma_output.transform_row`'s final Mapping/output formatting step). The internal `YYYY-MM-DD`/`YYYY-MM-DD HH:mm` representation `processor.py` produces and `storage.py`'s ECB-rate keying, cumulative-row dedup, and the dormant Excel export already consume is unchanged.
- `Exit Market`/`Entry Market` are each resolved from their own exact, side-specific field (`Network Point Name Exit`/`Network Point Name Entry`) regardless of Direction (`processor._enrich_row`): a side not required by the row's Direction is now also attempted, but a blank field or an alias with no approved catalog match on that side only leaves that one market blank — it never rejects the row and is never inferred or cross-filled from the opposite side. The side Direction actually requires keeps its existing reject-on-blank/unknown behavior unchanged.
- `Capacity Type`/`Network Point Name` direction-selection rules (`processor._direction_and_network`) are unchanged.
- Tariff Price/Premium Price EUR/MWh/h normalization, independent per-side bundle conversion before summation, and the existing source-unit conversion factors (including ÷24 for `.../d/Runtime` units) were already correct and required no code change; verified by the existing `price_normalization.py`/`processor.py` test coverage.
- `mapping_presentation._flow_start_sort_key` now parses `Flow Start` using the corrected `DD-MM-YYYY HH:mm` format instead of `datetime.fromisoformat`.
- **Same-day regression fix:** the cumulative published file is never rewritten, so it durably mixes rows written before this format correction (legacy `YYYY-MM-DD`/`YYYY-MM-DD HH:mm`) with rows written after it (new `DD-MM-YYYY`/`DD-MM-YYYY HH:mm`); the initial `_flow_start_sort_key` change above only accepted the new format and raised on any legacy row, making the whole Mapping display fail (caught by `app.py`'s `_refresh_mapping_display_from_output` as a generic error, clearing the table). `mapping_presentation._parse_flow_start` now tries both formats and never raises: a blank or unparseable Flow Start (either format) sorts after every row with a valid Flow Start instead of blocking display, and `sorted()`'s stability keeps such rows in their original relative order. New rows continue to be written only in the new format (`prisma_output.transform_row`); no previously published row is rewritten, migrated, or deleted.
- **Same-day display-format follow-up fix:** `Auction Date`/`Flow Start`/`Flow End` were still passed through unchanged for display, so a legacy stored/published row kept showing its original `YYYY-MM-DD`/`YYYY-MM-DD HH:mm` values in Mapping even though sorting already treated it correctly. `mapping_presentation.build_mapping_rows_from_output_records` now converts each of the three fields to the current `DD-MM-YYYY`/`DD-MM-YYYY HH:mm` display format regardless of which contract the underlying record was written under (`_display_auction_date`/`_display_flow_timestamp`, parsed the same dual-format way as `_parse_flow_start`); a blank or unparseable value is still displayed unchanged rather than raising. This is purely an in-memory presentation conversion — the published CSV file and all persisted records are never rewritten, migrated, or otherwise modified.

Automated evidence: 603 passed, 1 skipped (the pre-existing platform-dependent symlink test); `python -m compileall`; `git diff --check`. Manual real-Windows acceptance of the corrected Mapping display (including a cumulative file mixing legacy and new date formats) and published CSV remains outstanding.

## Next work

Select the next increment only after this merge (P.37, P.40, and P.41 together) lands on `main` and all feature branches are cleaned up. Do not restore or continue superseded P.36 managed-download work. Future work must be derived from the newest approved specification and an explicit customer decision.
