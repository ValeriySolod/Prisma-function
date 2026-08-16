# AGENTS.md — Prisma-function repository rules

These rules apply to every contributor and automation working in this repository.

## Source of truth

Before changing the project:

1. Read this file, CLAUDE.md, ROADMAP.md, and the newest approved Prisma Function specification.
2. Inspect relevant production code, tests, configuration, packaging files, recent history, remotes, and Git status.
3. Resolve conflicts in this order: newest explicit customer decision; newest approved specification; current ROADMAP.md; implementation evidence; other documentation.
4. Never import requirements from Prisma Function Mini or another project.

Code, identifiers, comments, UI text, CSV content, technical documentation, branches, and commit messages must be English.

## Active product contract

Prisma Function is a single-user Windows desktop application built with PySide6.

- The user independently downloads one or more official PRISMA Export CSV files and selects them locally with Select CSV.
- Prisma Function never opens, controls, or downloads from the PRISMA website. Browser automation and Playwright must not be restored.
- Input PRISMA CSV is the official 34-column, semicolon-delimited Windows-1252 contract. Detection is header-based, never filename-based.
- Every selected CSV must be read to end-of-file. The application must not impose a 5,000-row limit.
- Multiple distinct CSV files for the same source date or period are valid and must be accepted.
- Exact re-import and partial overlap must be idempotent. Deduplicate at the persisted row identity boundary, never by filename, whole-file hash, or source date.
- Previously accepted data persists across sessions and new accepted rows are added atomically.
- Retain only auctions with normalized booked capacity of at least 1 MWh.
- Mapping contains exactly the ordered 12 fields defined in CLAUDE.md and remains vertically and horizontally scrollable without a row limit.
- Output is UTF-8, semicolon-delimited, and uses the same ordered 12-field contract.
- Dates and times use the approved Europe/Berlin CET/CEST contract.
- Tariff and premium prices are EUR/MWh/h. Currency normalization uses the calendar date from Start of Auction, with official ECB rates and the approved prior-reference-date fallback.
- Market and storage values may use only exact, side-specific, Auction-ID-linked approved evidence. No fuzzy, geographic, TSO, EIC, substring, cross-side, or name-based inference.
- Runtime data belongs under %LOCALAPPDATA%\PrismaFunction\. User-facing published output belongs in the approved Documents directory.
- PDF input, live monitoring, scheduling, notifications, and managed PRISMA acquisition are outside the active product.

## Implementation workflow

- Implement one bounded increment on one English feature branch.
- Make the smallest complete change and preserve module boundaries.
- Keep business logic outside UI and infrastructure layers.
- Validate input at system boundaries and preserve useful error context without exposing sensitive data.
- Preserve atomicity, retry behavior, security, auditability, and backward compatibility.
- Do not include unrelated refactoring, cleanup, formatting, or dependency changes.
- Stop for customer direction only when a missing decision materially changes behavior, architecture, data, security, or scope.
- Do not start the next increment until the current increment is completed and merged.

## Verification and documentation

- Add or update focused regression tests for changed behavior.
- Run focused tests, the complete test suite, the documented Python compilation check, relevant packaging validation, and git diff --check.
- Never claim a check passed unless it was run against the current state.
- Real Windows behavior must be validated on Windows; automated tests do not replace required manual acceptance.
- Update current documentation when behavior, configuration, contracts, status, or dependencies change.
- Keep historical implementation narratives in CHANGELOG.md; do not copy obsolete reports into active rules or the roadmap.
- Do not create final-review.diff artifacts unless the user explicitly requests one.

## Git safety

Do not commit, push, pull, merge, rebase, force-push, create or delete branches, open pull requests, release, or publish unless the user explicitly authorizes the operation. Stage only files belonging to the approved increment. Never commit credentials, tokens, private data, generated output, local databases, logs, caches, or review artifacts.

## Definition of Done

An increment is complete only when its agreed scope is implemented, required checks pass, required manual acceptance is recorded, documentation is current, no critical finding remains, the change is merged to main, and explicitly approved branch cleanup is complete.
