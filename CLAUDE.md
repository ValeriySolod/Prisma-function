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

P.36 was the authoritative forward roadmap through P.36.22. **P.38 (2026-08-16,
customer-approved revision) supersedes P.36's managed-download design.**
PrismaFunction no longer opens, controls, or downloads anything from the
PRISMA website. The user downloads the official PRISMA Export CSV
independently; Select CSV (the completed `P.36.4` manual-selection path) is
now the sole and primary acquisition path, not a fallback. The managed
browser/download product code — `browser.py`, `prisma_lifecycle.py`,
`prisma_download.py`, `prisma_page.py`, `date_range_selection.py`, the Open
Prisma/Close Prisma/date-range/download-folder UI and controller wiring in
`app.py`, and their dedicated tests — was removed by P.38; do not restore it.
`playwright` is no longer a dependency anywhere in the codebase or packaging
configuration. See `ROADMAP.md`'s P.38 entry for the full scope and the
disposition of every superseded P.36 sub-increment (P.36.2, P.36.3's
managed-download support, P.36.8's managed-download trigger, P.36.13,
P.36.14, P.36.20, P.36.22).

- P.36.1, P.36.4, P.36.5, P.36.8 (mapping display), P.36.15
  (`prisma_output.write_prisma_output`), P.36.16
  (`prisma_publication.publish_cumulative_output`), P.36.19 (historical ECB
  rate to EUR in Mapping), and P.36.21 (strict EUR normalization) remain
  implemented and in active use; P.38 did not change their scope. P.36.5's
  PDF-scope decision (PDF input/processing excluded) still stands; its
  separate 14-column/four-field-split output decision remains withdrawn.
- P.36.6, P.36.7, and P.36.9 are suspended/superseded. The old 14-field
  P.36.6 prompt must not be executed.
- P.36.10 (removal of the superseded monitoring/scheduler product flow and
  obsolete dependencies) is implemented, automated-tested, and merged to
  `main` via PR #65 (merge commit `d6dd456`).
- **P.39 (2026-08-16) correction:** Select CSV is the single user action.
  `app.py`'s `_select_manual_csv()` validates the chosen local file, refreshes
  the Mapping preview, and — if that preview succeeded — immediately calls
  `_process_selected_csv()` on a background thread; there is no separate
  "Import PRISMA Export" button, export-date picker, or two-step selected-
  file/import state anymore. `_process_selected_csv()` calls
  `prisma_import_workflow.run_prisma_import_workflow`, which itself calls
  `prisma_publication.publish_cumulative_output` (P.36.16) to produce the
  active, EUR-confirmed 12-column result, merged into cumulative storage
  without duplicates (`prisma_source_updates`/`storage.py`, unchanged).
  `source_date` is always `datetime.now().date()` (today) now that there is
  no UI date picker — the same fallback the pre-P.39 code already used when
  no date was supplied. `prisma_output.write_prisma_output` (P.36.15, the
  independent per-import single-file writer) is still not called from
  `app.py` anywhere. Never assume a module is reachable from the running
  application merely because it exists — verify the actual call graph before
  relying on it.
- `price_normalization.py` is the one place a row's price is converted to
  EUR/MWh/h; never add a second conversion or rate-selection implementation.
  A Finished auction's rate resolves only from `storage.AuctionStorage`'s
  durable per-Auction-ID cache (`rate_resolution.py`): since P.38 removed all
  browser/PRISMA-website access, there is no live transport left, and
  `prisma_auction_lookup.PrismaAuctionLookup` fails closed
  (`PrismaAuctionDetailTransportError`) whenever no explicit `fetcher` is
  supplied — which is always true in the running application. A
  never-before-resolved Finished auction therefore blocks EUR normalization
  for its whole batch (P.36.21's existing fail-closed contract, unchanged);
  a previously resolved auction keeps working from cache indefinitely. The
  pre-P.36 Excel pipeline (`storage.export_excel`/
  `AuctionStorage.EXCEL_COLUMNS`) is dormant, intentionally unconverted,
  independently tested compatibility code — it is never called by the active
  workflow.
- The active `Prisma_Output_Published_EUR.csv` is published directly into the
  approved publication directory: `app.py`'s `main()` resolves and validates
  the current user's Documents folder once at startup
  (`download_directory.default_download_directory()` +
  `validate_download_directory()`) and passes it to `PrismaMonitorApp` as
  `self._publication_directory` — the same `P.36.3` Documents-directory
  contract, never `%LOCALAPPDATA%`, and no longer user-reselectable (the
  "Choose Download Folder" control was removed by P.38 along with the
  managed-download workflow it existed for). There is no "Open Result"
  control (removed by P.39 along with `PrismaMonitorApp._last_output_path`);
  the published cumulative CSV in the approved directory is the durable,
  structured output — this is what a later monitoring-system integration
  reads, not anything the UI opens for the user. A processing operation
  resolves and normalizes prices exactly once
  (`price_normalization.normalize_prices_for_output`); the result is reused as
  `precomputed_normalization` when calling
  `prisma_publication.publish_cumulative_output`, which validates it belongs to
  the exact row batch before trusting it — never a second normalization pass
  for the same batch, and never a mismatched result silently accepted.
- Later increments must follow the dependency and status recorded in
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
- Published user-facing output files follow the approved Documents-directory
  contract (`P.36.3`), not `%LOCALAPPDATA%`.
- PrismaFunction never opens, controls, or downloads anything from the
  PRISMA website (P.38). The user acquires the official CSV export
  independently; do not reintroduce browser automation, Playwright, or any
  other PRISMA-website access.

## Claude Code efficiency

Use `/clear` between unrelated increments. Reference repository files with
`@filename` instead of pasting them. Default to `/model sonnet`; reserve Opus
for genuine architecture decisions.
