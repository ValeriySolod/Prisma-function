# CLAUDE.md — Prisma-function

Auto-loaded by Claude Code. Read AGENTS.md and ROADMAP.md completely before every task.

## Product

Prisma Function is a single-user Windows PySide6 application for processing official PRISMA Export CSV files.

The user downloads CSV files independently and selects them with Select CSV. Selection validates and processes the file, merges accepted rows into cumulative persistent data without duplicates, publishes the result, and refreshes Mapping. Prisma Function must never open, control, or download from the PRISMA website.

## Data contracts

Input is the official 34-column PRISMA Export CSV: Windows-1252, semicolon-delimited, and detected by headers. Read every row to end-of-file; never impose a 5,000-row application limit. Accept multiple files for the same date or period. Deduplicate persisted records at row level (see the exact composite key below), never by filename, file hash, or source date.

After booked-capacity normalization, retain auctions with at least 1 MWh.

Mapping and published output use exactly these columns in this order:

1. Auction Date
2. Exit Market
3. Entry Market
4. Capacity Type
5. Network Point Name
6. Product Type
7. Flow Start
8. Flow End
9. Booked Capacity
10. Flow Duration Hours
11. Tariff Price
12. Premium Price

Mapping must show all cumulative accepted rows and support unrestricted vertical and horizontal scrolling. Published CSV is UTF-8 and semicolon-delimited.

Dates and times follow the approved Europe/Berlin CET/CEST contract. Prices are EUR/MWh/h. Resolve currency conversion by the calendar date from Start of Auction, use the official ECB reference rate with the latest prior available reference date for weekends and holidays, and handle quotation direction explicitly.

Market/storage mapping is exact, Auction-ID-linked, side-specific, and evidence-based. Never infer it from geography, TSO, EIC, substrings, names, or the opposite side.

Deduplication of persisted, published rows uses the exact composite key **Auction ID + Network Point Name + Capacity Type**; PRISMA data is immutable, so a row whose key already has a recorded counterpart is skipped outright, never updated or merged, even if its other field values differ. Source provenance (source date, filename, or whole-file sha256) never gates or deduplicates an import: distinct CSV files sharing a source date are always independently accepted, and exact-retry/partial-overlap idempotence is provided exclusively by the composite key.

PDF input, managed browser/download automation, Playwright, live monitoring, scheduling, and notifications are excluded.

## Execution

- Implement only the approved increment with the smallest complete change.
- Preserve business-logic boundaries, validation, atomicity, error context, security, and backward compatibility.
- Update only documentation directly affected by the change.
- Do not create review diff artifacts unless explicitly requested.
- Do not perform Git writes without explicit authorization.
- Use English for code, identifiers, comments, UI text, documentation, branches, and commits.
- Default to /model sonnet; reserve Opus for genuine architecture decisions.
