# CLAUDE.md — Prisma-function

Auto-loaded by Claude Code. Read this file and `ROADMAP.md` completely before every task; see `docs/` for supporting documentation and `docs/CHANGELOG.md` for historical implementation records.

This is the single authoritative instruction file for the repository — it applies to every contributor and automation working here.

## Source of truth

Before changing the project:

1. Read this file, `ROADMAP.md`, and the newest approved Prisma Function specification.
2. Inspect relevant production code, tests, configuration, recent history, remotes, and Git status.
3. Resolve conflicts in this order: newest explicit customer decision; newest approved specification; current `ROADMAP.md`; implementation evidence; other documentation.
4. Never import requirements from Prisma Function Mini or another project.

Code, identifiers, comments, UI text, CSV content, technical documentation, branches, and commit messages must be English.

## Product

Prisma Function is a single-user Windows PySide6 application for processing official PRISMA Export CSV files.

The user downloads CSV files independently and selects them with Select CSV. Selection validates and processes the file, merges accepted rows into cumulative persistent data without duplicates, publishes the result, and refreshes Mapping. Prisma Function must never open, control, or download from the PRISMA website. Browser automation and Playwright must not be restored.

Previously accepted data persists across sessions; new accepted rows are added atomically. Runtime data belongs under `%LOCALAPPDATA%\PrismaFunction\`. User-facing published output belongs in the approved Documents directory.

## Data contracts

Input is the official 34-column PRISMA Export CSV: Windows-1252, semicolon-delimited, and detected by headers, never by filename. Read every row to end-of-file; never impose a 5,000-row application limit. Accept multiple distinct files for the same date or period. Deduplicate persisted records at row level (see the exact composite key below), never by filename, file hash, or source date. Exact re-import and partial overlap must be idempotent.

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

## Implementation workflow

- Implement one bounded increment on one English feature branch.
- Implement only the approved increment with the smallest complete change; preserve module boundaries.
- Keep business logic outside UI and infrastructure layers.
- Preserve business-logic boundaries, validation, atomicity, error context, security, and backward compatibility.
- Validate input at system boundaries and preserve useful error context without exposing sensitive data.
- Do not include unrelated refactoring, cleanup, formatting, or dependency changes.
- Stop for customer direction only when a missing decision materially changes behavior, architecture, data, security, or scope.
- Do not start the next increment until the current increment is completed and merged.

## Verification and documentation

- Add or update focused regression tests for changed behavior.
- Run focused tests, the complete test suite, the documented Python compilation check, and `git diff --check`.
- Never claim a check passed unless it was run against the current state.
- Real Windows behavior must be validated on Windows; automated tests do not replace required manual acceptance.
- Update only documentation directly affected by the change.
- Keep historical implementation narratives in `docs/CHANGELOG.md`; do not copy obsolete reports into active rules or the roadmap.
- Do not create review diff artifacts (e.g. `*-final-review.diff`) unless explicitly requested.

## Git safety

Do not commit, push, pull, merge, rebase, force-push, create or delete branches, open pull requests, release, or publish unless the user explicitly authorizes the operation. Stage only files belonging to the approved increment. Never commit credentials, tokens, private data, generated output, local databases, logs, caches, or review artifacts.

## Definition of Done

An increment is complete only when its agreed scope is implemented, required checks pass, required manual acceptance is recorded, documentation is current, no critical finding remains, the change is merged to main, and explicitly approved branch cleanup is complete.

## Tooling

- Use English for code, identifiers, comments, UI text, documentation, branches, and commits.
- Default to /model sonnet; reserve Opus for genuine architecture decisions.
