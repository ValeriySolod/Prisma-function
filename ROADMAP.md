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

**Merge status correction:** P.37, P.40, and P.41 have since landed on `main` (PR #77, #78, #82 respectively); the note previously here gating further work on that merge is stale and removed.

### P.42 — ENTSOG-based network-point market reference

Status: implemented and automated-tested (2026-08-19) on branch `feature/entsog-network-point-market-reference`. Not yet merged to `main`.

Implemented result:

- New compact, local, versioned reference data under `src/prisma_function/resources/entsog/` (`operator_point_directions.json`, `operators.json`, `balancing_zones.json`, `interconnections.json`, `aggregate_interconnections.json`), fetched from the public ENTSOG Transparency Platform API on 2026-08-19 and trimmed to only the fields this application uses; the original XLSX/JSON exports are not bundled. See `docs/entsog_reference_data.md` for every source URL, exact field meaning, and the refresh procedure.
- New domain modules `entsog_reference_data.py` (resource loader) and `entsog_market_resolution.py` (`resolve_entsog_market_pair`), independent of UI, CSV parsing, and persistence, resolving one unidirectional row's Exit Market/Entry Market pair by the exact key Network Point EIC + TSO EIC/operatorKey + Direction, for PRISMA's own `BORDER_TRANSITION_POINT` and `RESERVOIR` `Network Point Type` values only.
- A versioned, exact alias table (`prisma_tso_aliases.json`) maps all 29 PRISMA `TSO Entry` display names confirmed observed across the two full 5,000-row checked-in PRISMA CSV samples to their ENTSOG `operatorKey`/`tsoEicCode`, by exact case-insensitive legal-entity-name identity only — never fuzzy, substring, country, or geographic matching. An alias for a TSO name PRISMA has not yet been observed with still simply leaves that row's Market blank (fail-closed) rather than being guessed.
- A curated, source-backed fallback table (`curated_fallback_routes.json`) supplies the 16 customer-approved routes (Dornum, Emden EPT/EMS-EPT variants, Dunkerque, Passo Gries/Masera-Passo Gries, Moffat, Ellund, Baumgarten AT/SK, Melendugno, Kipoi TAP, Kipi DESFA, Gorizia/Sempeter, Mazara del Vallo, Gela, Greifswald NEL/OPAL, Lubmin/Lubmin II) for points where the live ENTSOG export is missing a record, leaves the adjacent zone blank, or (Melendugno) carries inconsistent data across its two ENTSOG operator records; each entry is keyed by the exact Network Point EIC + operatorKey + Direction and carries its own source URL. Bacton Exit, North Sea Entry (NOSEE), and CONVERSION B VERS H remain the documented, unresolved exceptions.
- `processor._enrich_row` integrates the new resolver as an addition to the existing exact string-alias catalog (`prisma_references.DEFAULT_PRISMA_REFERENCES`), which is always tried first and always wins when it has a match — the smallest compatible change, preserving every previously-evidenced market/storage alias unchanged. The new resolver only engages as a fallback: for the row's own required side when the string catalog has no match, and to fill the opposite side (the adjacent balancing zone for a border point, or nothing at all for a RESERVOIR point, per the approved rule) purely from the required side's own EIC/TSO/Direction evidence — never inferred or cross-filled from the opposite side's own (blank) fields. A two-sided `Exit/Entry` bundle row is untouched: it keeps its existing direct per-side resolution and never reaches the new resolver.
- Every resolution failure (missing point EIC, unrecognized operator, no matching ENTSOG record, an ENTSOG record with both zones blank) leaves the affected side's Market blank without rejecting an otherwise valid row, preserving the application's existing fail-closed behavior.
- Verified against the two checked-in real PRISMA CSV samples: previously 78 of 138 capacity-eligible rows were accepted (60 rejected on an unknown/missing market reference); with this increment, 113 of 138 are accepted (25 rejected), and every remaining rejection is either a two-sided bundle row at a point absent from the string catalog (unchanged, pre-existing behavior) or the documented Bacton Exit exception.

Automated evidence: 621 passed, 1 skipped (the pre-existing platform-dependent symlink test); `python -m compileall`; `git diff --check`. Manual real-Windows acceptance remains outstanding.

**Same-day alias-table completion:** the initial implementation above shipped with 28 of the 29 alias-table names, having evidenced only 28 distinct blank-`TSO EIC Entry` names in the two checked-in PRISMA CSV samples. The customer subsequently confirmed the complete 29-name list observed across both full 5,000-row exports; comparing it against the table identified **TAG GmbH** as the missing name, mapping to ENTSOG operator `AT-TSO-0003` / TSO EIC `21X-AT-C-A0A0A-B` (already present in the bundled `operators.json`, so no live re-fetch was needed). Added to `prisma_tso_aliases.json` (bumped to `version: 2`); `docs/entsog_reference_data.md` and this entry updated to drop the now-resolved gap note. No other resolution behavior changed. Re-verified: 621 passed, 1 skipped; `python -m compileall`; `git diff --check`.

**Same-day RESERVOIR-market defect fix:** real Windows use surfaced a contract violation the automated evidence above did not catch: for a RESERVOIR row already matched by the legacy evidence-based string catalog (e.g. Epe/Xanten II, Speicher Epe, Zone UGS EWE, Speicherzone Nord, Jemgum, Nüttermoor — roughly 50 evidenced storage names), the catalog's self-referential STORAGE-classified canonical name (equal to the raw source value) was still being written directly into the row's own Exit/Entry Market column, before the ENTSOG fallback ever got a chance to run — the ENTSOG resolver only ever engaged when the legacy catalog had *no* match at all. This let a storage facility label leak into Market for every already-evidenced RESERVOIR point, violating the approved rule that Market must always be the transmission operator's own balancing zone (or blank) and never a storage label. `processor._enrich_row` now separates "what reference identifies this side" (`resolved`, returned as `exit_reference`/`entry_reference`, unchanged: still STORAGE-classified when the legacy catalog matches) from "what string is written into the Market column" (`market_values`, new): a STORAGE-classified catalog match is used only to confirm the point's identity — the affected Market column is populated exclusively by `resolve_entsog_market_pair`'s own-side balancing zone, and stays blank when ENTSOG cannot resolve it, without rejecting the row. A MARKET-classified match (BORDER_TRANSITION_POINT evidence) is unaffected and still populates Market directly, exactly as before. This applies uniformly to unidirectional and two-sided Exit/Entry bundle rows alike, since the underlying contract violation was direction-independent; the bundle row's own two-sided resolution *mechanism* (string catalog only, no ENTSOG fallback, no opposite-side fill) is otherwise unchanged. `Network Point Name` is untouched throughout and still fully carries the storage facility's own identity. Six tests in `test_prisma_references.py`, `test_prisma_output.py`, and `test_prisma_import_workflow.py` that asserted the old (incorrect) self-referential Market value were corrected to the new blank-Market expectation; one redundant bundle test was removed as covered elsewhere. Verified against the real checked-in sample: all 77 RESERVOIR required-side rows now resolve their own side to a real balancing zone (`DE THE BZ` for every German storage point observed) with zero storage-label leaks and the opposite side blank in every case. Re-verified: 621 passed, 1 skipped; `python -m compileall`; `git diff --check`.

### P.43 — Bacton Entry exception and French internal-auction exclusion

Status: implemented and automated-tested (2026-08-22).

Implemented result:

- **Bacton Entry exception:** `entsog_market_resolution.resolve_entsog_market_pair` now matches Bacton's exact `Network Point Name Entry`, `"BactonUKEn (48YBI-EC-------0)"`, ahead of every other resolution step and sets `Entry Market` to the combined `"TTF/ZTP"` label (the aggregated point can lead to either Belgium/ZTP or the Netherlands/TTF, per customer-approved decision), superseding P.42's "Bacton Exit... unresolved" note. The exact-name check is required, not optional: PRISMA's own point EIC for Bacton, `48YBI-EC-------0`, is also carried by ENTSOG's own operator-point-direction export for the unrelated Moffat (GB↔Ireland) interconnection under the same operator (National Gas Transmission PLC / `UK-TSO-0001`) and the same `"entry"` direction, which the existing curated-fallback table's `(point_eic, operator_key, direction)` key cannot disambiguate; keying on the name instead resolves Bacton correctly while leaving Moffat's existing resolution completely unchanged. North Sea Entry (NOSEE) and CONVERSION B VERS H remain the documented, unresolved exceptions. See `docs/entsog_reference_data.md`.
- **French internal-auction exclusion:** `processor._enrich_row` now excludes an auction whose resolved `Exit Market` and `Entry Market` are both `"TRF"` (the single French balancing zone label this application's market resolution ever produces) — it represents gas moving entirely within the French system, not a cross-border auction. The exclusion raises the same `_RowRejected` mechanism as the existing sub-1-MWh capacity filter, under a new `"french_internal_auction"` code that `import_prisma_export` counts as `filtered_count`, so it is reported through the existing filtering mechanism and applied before the row can be persisted or published, regardless of which resolution path produced the two `"TRF"` values. No other market-resolution behavior changed.

Automated evidence: 627 passed, 1 skipped (the pre-existing platform-dependent symlink test); `python -m compileall`; `git diff --check`. Manual real-Windows acceptance remains outstanding.

### P.44 — Mapping Booked Capacity display formatting

Status: implemented and automated-tested (2026-08-22).

Implemented result:

- `mapping_presentation.build_mapping_rows_from_output_records` now formats each row's Booked Capacity to exactly one decimal place for display (e.g. `1089601.0416666665` -> `1089601.0`) via a new `_display_booked_capacity` helper, following the same pattern as the existing Auction Date/Flow Start/Flow End display conversions: a blank or unparseable value is returned unchanged rather than raising.
- This is a presentation-only change in the Qt-independent `mapping_presentation.py` module: the stored/published Booked Capacity value, CSV output, calculations, filtering, sorting, and persistence are all untouched. `ui_components.MappingTableModel.data` sources every cell state (default, hovered, focused, selected) from the same `Qt.DisplayRole` value, so no separate formatting path was needed to cover those states.

Automated evidence: 629 passed, 1 skipped (the pre-existing platform-dependent symlink test); `python -m compileall`; `git diff --check`. Manual real-Windows acceptance remains outstanding.

## Next work

Select the next increment only after P.42, P.43, and P.44 land on `main` and their feature branches are cleaned up. Do not restore or continue superseded P.36 managed-download work. Future work must be derived from the newest approved specification and an explicit customer decision.
