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

- Read `AGENTS.md` completely. It defines repository-wide engineering
  rules: source-of-truth precedence, scope control, validation/testing/
  packaging requirements, the review-and-correction workflow, Git safety
  rules, and the Definition of Done. This file (`CLAUDE.md`) does not repeat
  that content.
- Read `ROADMAP.md` completely.
- Read the architecture and technical documentation referenced by those files.
- Inspect relevant production code, tests, configuration, and packaging files.
- Run `git status --short --branch` before starting.
- Priority when sources conflict: the newest explicitly approved customer
  decision, then the newest authoritative specification (`Prisma
  Function.odt`), then the corrected `ROADMAP.md`, then implementation
  evidence in the repository, then `AGENTS.md`/this file.

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
  obsolete dependencies) is implemented, automated-tested, and merged to
  `main` via PR #65 (merge commit `d6dd456`).
- P.36.13–P.36.16 (date-range selection, application-managed download,
  transformation into the 12-column contract, and publication) are each
  implemented and merged to `main`; each still requires manual real-Windows/
  real-PRISMA validation before it can be marked fully complete — see the
  current status recorded in `ROADMAP.md`. P.36.8 (mapping display) is
  implemented, automated-tested, and merged to `main` via PR #64 (merge
  commit `5e3f309`).
- `app.py`'s "Import PRISMA Export" button calls
  `prisma_import_workflow.run_prisma_import_workflow`, which itself calls
  `prisma_publication.publish_cumulative_output` (P.36.16) to produce the
  active, EUR-confirmed 12-column result. `prisma_output.write_prisma_output`
  (P.36.15, the independent per-import single-file writer) is still not
  called from `app.py` anywhere. Never assume a module is reachable from the
  running application merely because it exists — verify the actual call
  graph before relying on it; this exact gap (P.36.15/16 unreachable from
  `app.py`) was found and partially corrected by P.36.21 — see `ROADMAP.md`.
- P.36.19 (historical ECB rate to EUR in Mapping) and P.36.21 (strict EUR
  normalization of `Tariff Price`/`Premium Price`, fail-closed, wired into
  the real active processing path) are implemented and automated-tested; see
  `ROADMAP.md` for exact merge status. `price_normalization.py` is the one
  place a row's price is converted to EUR/MWh/h; never add a second
  conversion or rate-selection implementation. The pre-P.36 Excel pipeline
  (`storage.export_excel`/`AuctionStorage.EXCEL_COLUMNS`) is dormant,
  intentionally unconverted, independently tested compatibility code — it is
  never called by the active workflow.
- The active `Prisma_Output_Published_EUR.csv` is published directly into the
  approved download directory (`app.py`'s `DownloadDirectorySelection.current`,
  snapshotted before the processing worker starts — the same `P.36.3`
  Documents-directory-or-user-selected-directory contract, never
  `%LOCALAPPDATA%`). `RuntimePaths.published_directory` was removed (P.36.21
  third-pass correction, 2026-08-13) after this fix — it had no remaining
  legitimate runtime-data purpose. "Open Result" opens the exact
  `PrismaWorkflowResult.output_path` of the most recent successful processing
  run (`PrismaMonitorApp._last_output_path`), never a guessed or reconstructed
  path, and a later failed attempt never overwrites it. A processing operation
  resolves and normalizes prices exactly once
  (`price_normalization.normalize_prices_for_output`); the result is reused as
  `precomputed_normalization` when calling
  `prisma_publication.publish_cumulative_output`, which validates it belongs to
  the exact row batch before trusting it — never a second normalization pass
  for the same batch, and never a mismatched result silently accepted.
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

`Tariff Price`/`Premium Price` must be confirmed EUR/MWh/h (P.36.21) in every
active processing path, including the real "Import PRISMA Export" button. A
processing operation must fail closed — create, replace, or append nothing,
and never finalize as accepted — when any otherwise-publishable row lacks a
confirmed EUR conversion; never publish a source-currency value as if it
were EUR, and never guess a currency. The pre-P.36 `auctions` SQLite
table/Excel export (`storage.export_excel`/`AuctionStorage.EXCEL_COLUMNS`)
is dormant, unreachable from the active workflow, explicitly out of this
contract's scope, and still stores/labels the unconverted source-currency
price under its unchanged legacy names.

## Non-negotiable product rules

See `AGENTS.md` for repository-wide engineering rules (language, scope
control, testing/packaging, review workflow, Git safety, Definition of
Done). The rules below are specific to the Prisma Function product:

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
- Never bypass PRISMA authentication, anti-bot protection, or terms.

## Claude Code efficiency

Use `/clear` between unrelated increments. Reference repository files with
`@filename` instead of pasting them. Default to `/model sonnet`; reserve Opus
for genuine architecture decisions.
