# CLAUDE.md — Prisma-function 

Auto-loaded every session. Keep short — re-read on every turn.

## Project identity

PrismaFunction is a single-user Windows desktop application built with PySide6.
It processes official PRISMA Export CSV files into a transformed, published
output. The former live-monitoring dashboard, scheduler, and automated
monitoring flow were superseded by the P.36 workflow below and their
product-flow code (`BrowserController`, `monitoring.py`, `monitoring_storage.py`,
`scheduler.py`, `notifications.py`, `auction_csv.py`, and the matching UI) was
removed by P.36.10.

Do not import requirements, contracts, or roadmap items from Prisma Function
Mini (`Prisma-function-mini`) or any other unrelated or deleted project.

## Source of truth — read before any change

- Read every applicable `AGENTS.md`.
- Read `ROADMAP.md` and `workflow_p.md` completely.
- Read the architecture and technical documentation referenced by those files.
- Inspect relevant production code, tests, configuration, and packaging files.
- Run `git status --short --branch` before starting.
- Priority when sources conflict: the newest explicitly approved customer
  decision, then the newest authoritative specification (`Prisma
  Function.odt`), then the corrected `ROADMAP.md` and `workflow_p.md`, then
  implementation evidence in the repository, then this file.

`Prisma Function.odt` is the sole authoritative business specification for the
P.36 line. Never infer missing requirements.

## Current roadmap state

Completed work includes P.1–P.9, P.17–P.19, P.20.1, P.23–P.27, P.29–P.35.1,
subject to the remaining manual validation explicitly recorded in
`ROADMAP.md`.

P.10, P.11, P.20.2, P.22, and P.28 remain incomplete or partially complete.
Never claim P.22 or P.28 passed.

P.35.2–P.35.5 were cancelled on 2026-07-28. Do not restore their automated
CSV/PDF pairing, staging, fingerprinting, or browser-driven source-acquisition
design.

P.36 is the authoritative forward roadmap. Its current workflow is: the user
selects a date range in Prisma Function, the application performs a
user-initiated, application-managed PRISMA CSV download, the downloaded CSV is
transformed into the 12-column output contract below, and the result is
published. Manual selection of an already-downloaded CSV (`P.36.4`) is a
fallback path only, not the primary workflow.

- P.36.1–P.36.5 are complete. P.36.5 resolved the PDF-scope question — PDF
  input/processing stays excluded from the current version — but its separate
  14-column/four-field-split output decision was withdrawn by a 2026-08-02
  customer correction and must not guide implementation.
- P.36.6, P.36.7, and P.36.9 are suspended/superseded. The old 14-field
  P.36.6 prompt must not be executed.
- P.36.10 (removal of the superseded monitoring/scheduler product flow and
  obsolete dependencies) is implemented and automated-tested on its feature
  branch; see `ROADMAP.md` for merge status.
- P.36.13–P.36.16 (date-range selection, application-managed download,
  transformation into the 12-column contract, and publication) are each
  implemented and merged to `main`; each still requires manual real-Windows/
  real-PRISMA validation before it can be marked fully complete — see the
  current status recorded in `ROADMAP.md`. P.36.8 (mapping display) is
  implemented and automated-tested, not yet merged.
- Later P.36 increments must follow the dependency and status recorded in
  `ROADMAP.md`.

## Separate CSV contracts — never conflate

Monitoring CSV is UTF-8 and comma-delimited, with columns `auction_id`,
`auction_url`, `lot_number`, `item_name`, `expected_status`,
`last_known_status`, `check_interval_seconds`, and `enabled`. Its loader and
the live-monitoring dashboard/scheduler flow that consumed it were removed by
P.36.10; the contract is retained only in `csv_contracts.py` so a
Monitoring-shaped CSV is still detected and clearly rejected when selected
where a PRISMA Export CSV is expected.

The legacy PRISMA Export CSV contract is cp1252, semicolon-delimited, and has 34
fixed columns. Detection is header-based, never filename-based.

The P.36 target output is a separate UTF-8, semicolon-delimited CSV contract
with exactly these 12 columns, in this order: `Auction Date`, `Exit Market`,
`Entry Market`, `Capacity Type`, `Network Point Name`, `Product Type`,
`Flow Start`, `Flow End`, `Booked Capacity`, `Flow Duration Hours`,
`Tariff Price`, `Premium Price`. `Exit Market`/`Entry Market` hold the
resolved market or storage name for their own side; there are no separate
`Exit Storage`/`Entry Storage` output columns. A UI mapping presentation may
additionally show `Network Point Name`, `TSO Name Exit`, and `TSO Name Entry`,
but must never add, remove, rename, or reorder the 12 output columns. Do not
reuse the Prisma Function Mini contract by assumption.

## Non-negotiable rules

- Only auctions with booked capacity at or above the authoritative threshold
  after unit normalization are relevant. For P.36, follow the approved 1 MWh
  contract exactly.
- Market/Storage mapping may come only from exact Auction-ID-linked official
  PRISMA evidence. Never use fuzzy, geographic, TSO, EIC, substring, or
  name-based inference.
- Entry and Exit evidence are side-specific. Never assume a mapping is valid on
  the opposite side.
- Every catalog expansion is an independently reviewed batch with regression
  tests for exact-side resolution and no cross-side leakage, plus recorded
  SHA-256 evidence digests.
- General application runtime data (SQLite, logs, import state) belongs only
  under `%LOCALAPPDATA%\PrismaFunction\`. Never write it to the installation
  directory, current working directory, or a hidden staging path.
- P.36 downloaded and published user-facing files follow the approved
  Documents-directory-or-user-selected-directory contract (`P.36.3`), not
  `%LOCALAPPDATA%`.
- Code, identifiers, comments, UI text, CSV headers and values, technical
  documentation, branch names, and commit messages must be English.
- Never bypass PRISMA authentication, anti-bot protection, or terms.
- Preserve validation, auditing, error context, atomicity, recovery, security,
  and backward compatibility.

## Working style

- One increment equals one bounded branch and one independently tested task.
- Do not include unrelated refactoring, cleanup, formatting, or dependency
  updates.
- Prefer tests over production changes when existing behavior only needs proof.
- Run focused tests, the complete test suite, Python compilation, relevant
  packaging validation, and `git diff --check`.
- Update documentation and `ROADMAP.md` when behavior, configuration,
  contracts, conditions, or status change.
- Implementation executor may be Claude Code or Codex, but both use the same
  roadmap, branch boundaries, requirements, and Definition of Done.
- Review may use GitHub Copilot without allowing it to edit files.
- Never commit, push, merge, rebase, force-push, release, or delete a branch
  without explicit user authorization. The user creates and merges pull
  requests.

## Definition of Done

The increment contains only the agreed scope; English UI and CSV contracts are
preserved; errors, retry, and cleanup are handled; focused and full tests pass;
authoritative requirements remain intact; no critical review finding remains;
documentation is current; the change is merged to `main`; and the feature
branch is deleted.

## Claude Code efficiency

Use `/clear` between unrelated increments. Reference repository files with
`@filename` instead of pasting them. Default to `/model sonnet`; reserve Opus
for genuine architecture decisions.
