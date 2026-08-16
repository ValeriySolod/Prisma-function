# Prisma-function roadmap

This file contains only the current product direction and active work. Historical implementation records are preserved in CHANGELOG.md.

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
- Deduplication: row-level persisted identity; never filename, file hash, source date, or whole-file identity.
- Persistence: old accepted data remains across sessions; new distinct data is added atomically.
- Filtering: normalized booked capacity must be at least 1 MWh.
- Time: Europe/Berlin CET/CEST, including typed rejection of ambiguous or nonexistent local timestamps.
- Currency: EUR/MWh/h, keyed by the calendar date from Start of Auction; official ECB rate, explicit quotation direction, prior available reference-date fallback.
- Mapping evidence: exact Auction-ID-linked and side-specific only.
- Published output: UTF-8, semicolon-delimited, exact 12 columns.
- Runtime storage: %LOCALAPPDATA%\PrismaFunction\.
- User-facing publication: approved Documents directory.

## Current increment

### P.37 — Start-of-Auction ECB normalization and cumulative Mapping correction

Status: In progress; not merged.

Required acceptance:

- EUR, GBP, CZK, and CHF source prices normalize to EUR/MWh/h using Start of Auction.
- Each unique date/currency rate is resolved once and persisted for reuse.
- ECB weekends and holidays use the latest prior available reference date.
- Mixed-currency bundle sides normalize independently before summation.
- Every row in every selected CSV is processed, including rows after 5,000.
- Multiple CSV files for the same date are accepted.
- Exact retry and partial overlap are idempotent.
- Mapping shows all cumulative accepted rows using the exact 12-column contract.
- Real Windows validation is recorded before completion.

## Next work

Select the next increment only after P.37 is accepted, merged into main, and its feature branch is cleaned up. Do not restore or continue superseded P.36 managed-download work. Future work must be derived from the newest approved specification and an explicit customer decision.
