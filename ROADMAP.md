# Prisma-function Roadmap

`ROADMAP.md` records implementation history and the current dependency-ordered product plan.
`workflow_p.md` defines detailed engineering rules, validation requirements, and the Definition of Done.
The newest explicitly approved customer requirements supersede older roadmap text when a conflict is recorded below.

## Status legend

- ✅ Completed
- 🟡 In progress / partially completed
- 🟨 Documentation/contracts in progress
- ⬜ Planned
- 🚫 Suspended / superseded; must not be implemented
- ❌ Cancelled

## Product direction

`Prisma Function.odt` is the authoritative business specification. The customer clarifications recorded on 2026-08-02 establish this current workflow:

1. The user opens PRISMA from Prisma Function.
2. The user selects a start date and an end date inside Prisma Function. There is no first-day-of-month restriction.
3. The user initiates the official PRISMA CSV download through Prisma Function.
4. Prisma Function uses a download directory created under the user's Documents directory or another existing directory explicitly selected by the user.
5. Prisma Function validates and processes the downloaded CSV inside the application.
6. As a fallback only, the user may explicitly select a previously downloaded CSV through the completed P.36.4 path.
7. Prisma Function transforms accepted rows into the exact 12-column output CSV contract defined below.
8. Prisma Function publishes the processed result using a publication mechanism that must be explicitly approved before P.36.16 implementation.
9. The user closes the application-owned PRISMA session with the Close Prisma control when finished. Manual browser closure must also be detected safely.

The new workflow replaces the live-monitoring dashboard, scheduler, and automated monitoring product flow. Their completed records remain historical evidence; their removal is planned separately.

## Authoritative output CSV contract

The processed output contains exactly these 12 columns, in this exact order and spelling:

1. `Auction Date`
2. `Exit Market`
3. `Entry Market`
4. `Capacity Type`
5. `Network Point Name`
6. `Product Type`
7. `Flow Start`
8. `Flow End`
9. `Booked Capacity`
10. `Flow Duration Hours`
11. `Tariff Price`
12. `Premium Price`

Contract rules:

- `Exit Market` contains the resolved exit market or exit storage name.
- `Entry Market` contains the resolved entry market or entry storage name.
- There are no separate `Exit Storage` or `Entry Storage` output columns.
- The mapping presentation in the UI does not add, remove, rename, or reorder output CSV columns.
- The mapping presentation uses exactly this hierarchy and order: `Exit Market`, `Entry Market`, `Network Point Name`, `TSO Name Exit`, `TSO Name Entry`.
- Mapping values must come only from approved authoritative evidence. No fuzzy, substring, geographic, identifier-only, TSO-name, cross-side, or other inferred matching is permitted.
- PDF input and runtime PDF processing remain excluded from the current version. Historical PDF evidence already accepted for mapping-catalog entries remains valid.
- Existing approved requirements for the booked-capacity threshold, supported normalization, timestamps, decimal representation, typed rejection, and preservation of source error context remain authoritative unless a later explicit customer decision supersedes them.

## Completed and historical roadmap

| ID | Stage | Status | Current result / disposition |
|---|---|---|---|
| P.1–P.9 | Project, UI, CSV, browser, monitoring, and scheduling foundations | ✅ Completed | Historical foundations implemented. The monitoring product direction is superseded by P.36, but completion history is preserved. |
| P.10–P.11 | Error handling, cleanup, and automated coverage | 🟡 Partially completed | Existing coverage remains useful. Remaining work must be evaluated against the final P.36 architecture. |
| P.17–P.19 | Default-browser and PySide6 decisions | ✅ Completed | Manual browser selection removed; Windows default Chrome/Edge and PySide6 selected. |
| P.20 | PySide6 migration | 🟡 Partially completed | Foundation is complete; any remaining integration must follow the final P.36 UI. |
| P.20.1 | PySide6 GUI foundation | ✅ Completed | Base GUI and application structure exist. |
| P.20.2 | Complete legacy PySide6 monitoring UI integration | 🚫 Superseded by P.36 | Do not complete the superseded monitoring UI as a separate product objective. |
| P.22–P.22.1 | Packaged-browser validation and diagnostics | 🟡 Partially completed | Diagnostics exist; final physical validation belongs to the final P.36 package. |
| P.23–P.25 | Live monitoring, persistence, and notifications | ✅ Completed; product flow superseded | Preserve implementation history and reusable components, but do not extend the live-monitoring product flow. |
| P.26–P.32 | Runtime paths, packaging, CI, dashboard, installer, and release foundations | ✅ Repository-side foundations completed | Revalidate packaging, installer, and clean-Windows behavior after the P.36 dependency set is final. |
| P.33–P.33.8 | PRISMA CSV import, persistence, publication, enrichment, and mapping foundations | ✅ Completed | Reuse only compatible, tested business and safety boundaries. Do not restore superseded output shapes. |
| P.34.1 | Safe auction deduplication | ✅ Completed | Existing identity, conflict, and audit behavior is available for reuse if the approved P.36 publication design needs it. |
| P.34.2 | Maximize managed browser window | ✅ Completed | Real-Windows behavior validated. |
| P.35–P.35.1 | Authoritative mapping catalog expansion | ✅ Completed | Preserve exact side-specific evidence and regression rules. |
| P.35.2–P.35.5 | Paired CSV/PDF acquisition line | ❌ Cancelled | Do not restore the cancelled paired-source or PDF-processing design. |

Detailed historical records and test counts remain in `workflow_p.md` and Git history. This summary must not be used to claim that an unrun current test suite has passed.

## P.36 implementation roadmap

### Completed foundations

| ID | Stage | Status | Current result / current role |
|---|---|---|---|
| P.36.1 | Adopt the authoritative specification | ✅ Completed | Documentation baseline created. Its obsolete 14-column interpretation is superseded by the 2026-08-02 12-column clarification. |
| P.36.2 | Open Prisma / Close Prisma lifecycle | ✅ Completed | Application-owned PRISMA session, safe close behavior, and manual-closure detection implemented. |
| P.36.3 | Documents-based or user-selected download directory | ✅ Completed | Existing accessible directory selection is implemented and session-scoped. Managed-download integration and the application-managed default directory are addressed by P.36.14 (see its "Decision gate — resolved" entry); this row's original Documents-based default remains available via `default_download_directory()` for any other caller, unchanged. |
| P.36.4 | Manual CSV selection and validation | ✅ Completed as fallback | Exact official-export validation exists. Manual selection is a fallback path, not the primary product workflow. |
| P.36.5 | PDF-scope decision | ✅ Completed in part; output-shape decision superseded | Runtime PDF input remains excluded. The former 14-column output decision is withdrawn and must not guide implementation. |

### Suspended obsolete increments

| ID | Former stage | Status | Disposition |
|---|---|---|---|
| P.36.6 | Filtering/calculation/mapping for a 14-column output | 🚫 Suspended / superseded | The old P.36.6 prompt must not be executed. Replaced by P.36.15. |
| P.36.7 | 14-column output CSV writer | 🚫 Suspended / superseded | Replaced by P.36.15. |
| P.36.9 | Accumulation/deduplication/atomic publication under the withdrawn design | 🚫 Suspended / superseded | Publication is redefined by P.36.16 after its decision gate. |

P.36.8 is implemented, automated-tested, and merged to `main` via PR #64 (merge commit `5e3f309`; see
its dated entry below). P.36.10 is implemented, automated-tested, packaging-validated, and merged to
`main` via PR #65 (merge commit `d6dd456`; see its dated entry below). P.36.11 is substantially complete
(2026-08-05, see its own dated section below); P.36.12 remains planned. They must be scheduled only when
their dependencies below are satisfied and must use the 12-column contract.

### P.36.13 — Date-range selection inside Prisma Function

**Status:** ✅ Completed. Merged to `main` via PR #59 (merge commit `ff07b68`), containing
implementation commit `fb0cc89`. The `feature/p36-13-date-range-selection` branch has not been
deleted yet; branch cleanup remains a separate open action and does not change this increment's
completed status.
**Dependencies required before implementation:** P.36.2 completed.

**Objective:** Let the user select and validate a start date and an end date inside Prisma Function.

**Implemented result:** `date_range_selection.py` adds a Qt-independent, immutable `DateRange(start,
end)` value, a typed `DateRangeOutcome` enum (`ACCEPTED`, `MISSING_START_DATE`, `MISSING_END_DATE`,
`END_BEFORE_START`), `validate_date_range(start, end)`, `describe_rejection()`, and a session-scoped
`DateRangeSelection` tracker whose `current` starts at `None` (no current-date default) and only
advances to the validated `DateRange` on an accepted candidate; a rejected candidate never changes
`current`. Checks run in a fixed order — missing start, then missing end, then end-before-start — so
a candidate missing both dates deterministically reports `MISSING_START_DATE`. Neither the module nor
its validation boundary reads the system clock; both dates are caller-supplied. `app.py`'s
`PrismaMonitorApp` adds a "DATE RANGE" sidebar group (placed directly under "PRISMA EXPORT CSV") with
`start_date_edit`/`end_date_edit` (`QDateEdit`, using Qt's own default minimum date as a "Not set"
special-value sentinel so a genuinely missing date is representable and testable without inventing a
new date limit) and one explicit "Validate Date Range" button wired to `_validate_date_range()`. On
acceptance, both date controls are set to the accepted values and a read-only `date_range_label`
shows `"Accepted: YYYY-MM-DD to YYYY-MM-DD"`; on rejection, a stable English `QMessageBox` (title
"Date Range") reports the typed outcome's message, the previous accepted range and both controls'
current values are left untouched, and the controls remain enabled for correction and retry. One
`DateRangeSelection` instance is owned by the window, matching the existing `DownloadDirectorySelection`
/`ManualCsvSelection` session-scoped-state pattern. This increment performs no browser, Playwright,
PRISMA-page, filesystem, CSV, transformation, mapping, persistence, output-writing, or publication
operation, and the accepted range is not wired into Open Prisma, Close Prisma, Select CSV, the legacy
importer, or any download workflow; the completed P.36.2–P.36.4 behavior is unchanged.

**Included scope:**

- Qt-independent date-range value and validation boundary;
- start-date and end-date controls in the application;
- validation that both dates are present and the end date is not earlier than the start date;
- stable English validation messages and deterministic UI state;
- safe retry after correction.

**Excluded scope:**

- first-day-of-month restriction;
- PRISMA navigation, form automation, or download;
- CSV transformation, mapping, output writing, or publication;
- invented PRISMA-specific date limits not present in authoritative requirements.

**Acceptance criteria and focused tests:**

- valid same-day and multi-day ranges are accepted;
- missing and reversed ranges are rejected without changing the last accepted range;
- UI controls reflect the accepted range and remain retryable after errors;
- no browser or file operation occurs;
- relevant focused tests, full regression tests required by project rules, compilation, and `git diff --check` pass;
- `workflow_p.md` and this roadmap record the final implemented behavior and exact executed validation results.

**Verified evidence (2026-08-02, merged via PR #59, merge commit `ff07b68`):** `tests/test_date_range_selection.py` (17 tests) and
the 10 focused P.36.13 tests in `tests/test_app.py` passed; the complete suite passed with 592 tests
(up from 565) in 15.33s; project-wide `compileall` (excluding `.venv`, `build`, `.git`, `__pycache__`)
exited 0, with one pre-existing, unrelated `.pytest_tmp` permission warning predating this increment;
and `git diff --check` passed. See `workflow_p.md`'s P.36.13 completion record for the full detail. No
real-browser, real-PRISMA, filesystem, CSV-processing, publication, or later-increment behavior was
added or exercised by this increment.

**Fresh packaging evidence (2026-08-02, final-review follow-up).** The prior packaging check above
validated a pre-existing `dist/PrismaFunction` build that predated this increment's `app.py` and
`date_range_selection.py` changes. `python -m PyInstaller --clean --noconfirm PrismaFunction.spec` was
rerun to produce a fresh distribution from the current P.36.13 source (`PrismaFunction.exe` rebuilt
2026-08-02, replacing the stale 2026-07-19 build), and `python validate_package.py` then passed against
that fresh distribution. A smoke check launched the fresh `PrismaFunction.exe` with an isolated
`LOCALAPPDATA` and a working directory outside the repository: the process started, reached a live main
window (`MainWindowHandle` non-zero, title `PRISMA Monitor v1.0.0`, `Qt6Widgets.dll` loaded, confirming
`PrismaMonitorApp.__init__` — including its `date_range_selection` import and "DATE RANGE" widget
construction — completed without error), and then shut down cleanly via `CloseMainWindow()` (process
exit code `0`, no forced kill needed). No `chrome.exe`, `msedge.exe`, or `node.exe` process was spawned
by the smoke run, no `PrismaFunction.exe` process remained afterward, and the only filesystem writes
were the isolated smoke `LOCALAPPDATA`'s log file — no writes reached the repository, `dist/PrismaFunction`
itself, or a real Documents directory. No real PRISMA session, network activity, CSV selection, or
manual Windows workflow beyond this isolated startup/shutdown smoke check was performed.

### P.36.14 — User-initiated, application-managed PRISMA CSV download

**Status:** ✅ Implemented and automated-tested; merged to `main` via PR #61 (merge commit `36b7615`). Real-PRISMA validation on 2026-08-02 progressed through three corrections: (1) a wrong, guessed reporting-page URL, fixed and live-confirmed; (2) a wrong, guessed date-filter locator (`get_by_label(/from date/i)`), replaced with the real live-verified Active-Filter-panel/test-id contract and live-confirmed (`Open Prisma` fills and applies both dates successfully); (3) a customer correction to the decision gate itself — the original gate had the user manually press PRISMA's own download control, which is now known to be wrong: PrismaFunction must activate that control itself, with the user's only action being the existing in-application control. A same-day follow-up diagnostic round found two further real-site defects — a cookie-consent banner blocking the CSV click, and the download listener missing a download opened in a new tab — both now fixed and individually live-verified (see the dated entry below), but that same round also found the date-filter selectors from correction (2) apparently no longer matching the live site (external PRISMA UI drift, out of that round's scope to fix). A later same-day round (see the dated entry further below) re-verified the date-filter contract fresh against the live site, added the required applied-filter verification and large-result-modal handling, and found the "drift" was most likely intermittent PRISMA-side A/B variance rather than a permanent change — but also found a new, orthogonal blocker: the Playwright "download" event is not reliably observed when driving the real installed Chrome/Edge executable (regardless of headless/headed mode), even though the browser's own UI confirms the download completed. **Still not live-verified end-to-end** (no full live download has yet been completed with zero manual browser interaction). Do not mark this ✅ Completed until that full live pass is recorded. A separate real-Windows UI defect — the DATE RANGE controls initializing to Qt's minimum date instead of a usable date — was found and fixed on 2026-08-03 (see this section's dated entry below); full manual Windows validation of that fix is still outstanding. A further real-Windows defect was also found and fixed the same day: the managed download completed in Chrome under a temporary UUID-like name but never reached the configured directory, because the browser was never told to download there (`downloads_path` was not set) — see this section's matching 2026-08-03 dated entry; full manual Windows validation of that fix is likewise still outstanding.
**Dependencies required before implementation:** P.36.2, P.36.3, and P.36.13 completed.

**Decision gate — resolved (2026-08-02, customer-approved):**

1. **File naming.** Preserve the original PRISMA/browser-suggested filename, but append the selected
   filter date range before the extension, in ISO format: `<original-stem>_<start>_<end>.csv` (e.g.
   `Auction_overview_2026-08-01_2026-08-31.csv`).
2. **Filename collision.** If the resulting name already exists in the target directory, append an
   incrementing numeric suffix before the extension (`..._2.csv`, `..._3.csv`, ...). An existing file is
   never overwritten; the reservation is race-safe (exclusive file creation, not a check-then-write).
3. **Download directory.** The application has an installer-or-first-run default download directory at
   `<User Downloads>\PrismaFunction`, created idempotently by the application if the installer does not
   reliably create it. The user may override this default with any other existing, writable directory
   through the existing P.36.3 folder-selection workflow. Only this one application-managed default
   directory is ever auto-created; a user-selected directory is never created automatically.
4. **Completion detection / browser mechanism — corrected 2026-08-02 (customer correction).** Reuse the
   existing Playwright browser/page already owned by `PrismaLifecycleController` (P.36.2) — no second
   browser or context. After the approved PRISMA URL loads, the session fills PRISMA's own date filter
   with the accepted range, applies it, registers a Playwright `"download"` event listener, and then
   **activates PRISMA's own CSV download control itself.** The original text of this item ("The user
   always presses PRISMA's own download control manually; PrismaFunction never clicks it.") was an
   incorrect assumption about the authoritative user workflow and is superseded: the single explicit
   in-application action (pressing the existing "Open Prisma" control with an accepted date range and
   download directory already configured) is the user's entire interaction — they select the dates and
   the destination folder in PrismaFunction, then press one control in PrismaFunction; they never select
   dates or press anything on the PRISMA website itself. Completion is still detected purely from the
   Playwright `"download"` event (`suggested_filename`, `failure()`, `save_as()`) plus a wall-clock
   timeout — no filesystem polling loop. The download listener is always registered before the CSV
   control is activated, so the resulting event can never be missed.

Do not restore P.35.2–P.35.5.

**Objective:** On an explicit user action, use the application-owned PRISMA session and accepted date range to obtain the official CSV in the approved download directory.

**Included scope:**

- one explicit user-triggered download action;
- exact approved date-range transfer to PRISMA;
- download destination integration with P.36.3;
- bounded completion/failure handling, cancellation, safe retry, and no orphaned browser/file state;
- validation of the downloaded file through the existing official-export boundary.

**Excluded scope:**

- background scheduling, live monitoring, hidden downloads, login/credential automation, PDF acquisition, or paired staging;
- transformation, mapping, result publication, or speculative duplicate policy.

**Acceptance criteria and focused tests:**

- no download can begin without an accepted date range and valid destination;
- exactly one user action starts one managed attempt;
- success identifies one complete validated official CSV; partial/temporary files are never accepted;
- errors preserve actionable internal context without exposing sensitive paths/data and allow retry;
- manual selection through P.36.4 remains available only as fallback;
- focused state-machine, directory, date-transfer, completion, cancellation, failure, and retry tests pass;
- approved real-Windows/real-PRISMA validation is recorded before completion;
- documentation records the approved mechanism and exact executed validation results.

**Implemented result.** `prisma_download.py` is a new, Qt- and Playwright-session-independent
orchestration module: `validate_download_configuration(date_range, download_directory)` is the
Open-Prisma precondition gate (typed `PrismaDownloadValidationOutcome`: `ACCEPTED`,
`MISSING_DATE_RANGE`, `MISSING_DOWNLOAD_DIRECTORY`, `INVALID_DOWNLOAD_DIRECTORY`, with stable English
messages via `describe_validation_rejection()`); `build_dated_filename()` and
`reserve_unique_download_path()` implement the approved naming/collision rule (the latter using
`os.O_CREAT | os.O_EXCL` exclusive creation, so the reservation itself cannot lose a race, and returns a
self-created placeholder path the caller then overwrites via `Download.save_as()`); and
`PrismaDownloadOrchestrator` exposes two synchronous steps — `configure(page, date_range)` (no navigation:
the already-open PRISMA Auctions page is the reporting page; opens the real Active Filter panel, fills and
verifies the date-range controls, applies the filter, locates and registers a `"download"` listener on, then
activates, the real CSV control — see the date-filter and decision-gate-correction records below for the
exact live-verified contract) and `await_and_finalize(waiter, date_range, download_directory, cancel_event,
deadline=...)` (non-blocking: returns `None` while nothing has happened yet, so the caller can interleave it
with its own polling instead of blocking exclusively on it) — plus a typed
`PrismaDownloadOutcome`/`PrismaDownloadResult` covering only the post-`configure()` phase (`SUCCESS`,
`DOWNLOAD_TIMEOUT`, `DOWNLOAD_CANCELLED`, `DOWNLOAD_INTERRUPTED`, `NOT_CSV`, `SAVE_FAILED`) with stable
English messages via `describe_download_failure()`; pre-configuration failures (session/authentication,
filter panel, date controls, rejected date values, listener registration, download-control location/activation)
are raised as specific exceptions instead (`PrismaAuthenticationRequiredError`, `PrismaInvalidSessionError`,
`PrismaDateFilterPanelError`, `PrismaDateFilterControlsNotFoundError`, `PrismaDateValueRejectedError`,
`PrismaDownloadListenerError`, `PrismaDownloadControlError`).

`prisma_lifecycle.py`'s `PrismaLifecycleController` (P.36.2) is extended, not replaced:
`open(*, date_range=None, download_directory=None)` stays backward compatible (omitting both preserves
the exact pre-P.36.14 behavior — proven by the existing `FakePage.__getattr__` guard in
`tests/test_prisma_lifecycle.py`, unchanged). When both are supplied, after the approved PRISMA URL
loads, the worker thread calls `PrismaDownloadOrchestrator.configure()` (a `configure()` failure is
reported through the existing "open failed" event path, exactly like a navigation failure — satisfying
"Open Prisma must fail ... if download configuration fails" without a new failure channel), then
announces the existing `kind="open"` success event (browser now under user control), then folds
`await_and_finalize()` into the *existing* `cancel_event.wait(0.1)` idle loop that already polls for
manual closure — so the bounded download wait never blocks Close-Prisma responsiveness or manual-closure
detection, and no second competing wait mechanism or filesystem polling loop was added. Resolution
(success or a typed failure) is published as a new, separate `kind="download"`
`PrismaLifecycleEvent(generation, success, error, kind="download", csv_path=...)`; the PRISMA session
itself stays open regardless of the download outcome (Close Prisma remains the only way to end it).

`app.py` wires this without new permanent UI: `_open_prisma_session()` calls
`validate_download_configuration()` before touching the browser at all (failing fast with a `QMessageBox`
titled "Open Prisma" and never invoking `prisma_lifecycle.open()` if the date range or directory is
missing/invalid), then calls `prisma_lifecycle.open(date_range=..., download_directory=...)`.
`_poll_prisma_lifecycle()` routes `kind="download"` events to `_handle_download_event()`, which — on
success — reuses the existing P.36.4 `ManualCsvSelection` boundary (`self._manual_csv_selection.select(csv_path)`)
so the downloaded file passes through the same exact-contract validation as a manually selected CSV
before it updates the existing "PRISMA EXPORT CSV" label/status/activity; a file that fails that contract
(or a typed download failure) shows a stable English error via the existing `_show_error()` helper and
never touches the CSV selection. This is the "expose the downloaded CSV path to the next processing
stage" mechanism: `self._manual_csv_selection.current` is the same boundary P.36.15 will consume. No CSV
parsing, transformation, mapping, or publication happens in this increment.

`download_directory.py` adds the approved application-managed default: `default_downloads_directory()`
resolves the current user's Downloads folder (Shell Folders registry GUID
`{374DE290-123F-4565-9164-39C4925E467B}`, then `%USERPROFILE%\Downloads`, then `Path.home()`, mirroring
`default_download_directory()`'s existing Documents resolution exactly); `default_managed_download_directory()`
appends `PrismaFunction`; `ensure_directory_exists()` idempotently creates only that one path (`mkdir(parents=True,
exist_ok=True)`) and then re-validates it — a user-selected directory is never auto-created. `app.py`'s
`main()` now calls `ensure_directory_exists(default_managed_download_directory())` as the initial
`DownloadDirectorySelection` value instead of the former Documents default; the user can still change it
through the unchanged P.36.3 "Choose Download Folder" control. `default_download_directory()` (Documents)
itself is untouched and remains available/tested for any other caller.

**Included-scope status:** one explicit user-triggered download action (Open Prisma) — done; exact
approved date-range transfer to PRISMA's date filter — done (ISO-formatted fill); download destination
integration with P.36.3 — done (same tracked `DownloadDirectorySelection`); bounded
completion/failure/cancellation handling with no orphaned browser/file state — done (single-generation
Playwright session, existing cleanup path unchanged); validation of the downloaded file through the
existing P.36.4 official-export boundary — done. Background scheduling, hidden downloads, login/credential
automation, PDF acquisition, paired staging, transformation, mapping, publication, and speculative
duplicate policy remain excluded, matching this increment's excluded scope.

**Automated evidence (2026-08-02, `feature/p36-14-managed-prisma-download`, not yet merged).** New
`tests/test_prisma_download.py` (29 tests) covers configuration validation (accepted; missing date range
takes precedence over missing directory; nonexistent/file/non-writable directory), the naming/collision
rule (exact name when free, `_2`/`_3` deterministic increment, never overwriting an existing file),
`configure()` (navigation + ISO date fill + listener registration, and each of the three failure modes),
and `await_and_finalize()` (not-yet-resolved, timeout, cancellation-before-download, successful save with
the dated name, collision-safe save, non-CSV rejection without saving, cancelled/interrupted
classification from `Download.failure()`, save failure, and a failure reported only after `save_as()`).
`tests/test_prisma_lifecycle.py` gained 9 focused integration tests (46 total, up from 37): the
backward-compatible no-managed-download path; reporting-page navigation and ISO date fill; a
`configure()` failure reported as a normal open failure with resources cleaned up; a successful download
event with the saved path; not-CSV, cancelled, and interrupted typed failure events; a timeout event; and
proof that the bounded download wait does not block manual-closure detection (a browser
`"disconnected"` event during the wait is still detected and reported). `tests/test_download_directory.py`
gained 9 tests (27 total) for the Downloads-folder resolution tiers, the managed-default subdirectory, and
`ensure_directory_exists()` (creation, idempotency, rejecting a file at the target path, wrapping a
creation failure). `tests/test_app.py` gained 6 tests (87 total) for the Open-Prisma validation gate
(missing date range; a download directory that became invalid after selection) and the `"download"` event
UI wiring (success; typed failure; a downloaded file that fails the P.36.4 CSV contract; routing through
`_poll_prisma_lifecycle()` without disturbing the open session), plus 4 existing P.36.2 tests updated for
`prisma_lifecycle.open()`'s new keyword arguments (an intentional, in-scope extension of Open Prisma's own
call contract, not unrelated churn).

The complete pytest suite passed with **645 tests (up from 592, the exact +53 expected from this
increment: +29 new, +9 in `test_prisma_lifecycle.py`, +9 in `test_download_directory.py`, +6 in
`test_app.py`)**. Project-wide `python -m compileall` (the same file list as `BUILDING.md`, plus
`prisma_download.py`) exited `0`. `git diff --check` passed. All tests use fakes/mocks for Playwright,
the filesystem-writable-directory checks use `tmp_path`, and no real browser or real PRISMA session was
exercised.

`python -m PyInstaller --clean --noconfirm PrismaFunction.spec` was rerun and succeeded, producing a
fresh `dist/PrismaFunction/PrismaFunction.exe`; `prisma_download.py` required no `.spec` change, since
`Analysis(["app.py"], ...)` performs static import discovery and picked up the new module automatically
through `prisma_lifecycle.py`'s import (the same pattern P.36.13 recorded for its own new module).
`python validate_package.py` then passed against that fresh distribution. No packaged-executable launch,
real-browser, or real-PRISMA validation was performed beyond this static packaging check.

**Real-site validation attempt and correction (2026-08-02).** The packaged application was launched
against the live, public `https://app.prisma-capacity.eu` site (real default browser, real
`Downloads\PrismaFunction` directory, real accepted date range) by driving the actual shipped
`PrismaLifecycleController`/`PrismaDownloadOrchestrator` code. `Open Prisma` reached the real PRISMA
auctions page exactly as P.23.1–P.23.3 already established, but the P.36.14-added second navigation used
a guessed, never-approved literal (`.../reporting/reports/short-and-long-term-auctions`) that resolved to
PRISMA's own navigation shell with no matching content — not a hard 404 status, but a page with no "From
date"/"To date" fields — so `Locator.fill()` correctly timed out after 30s and the whole `Open Prisma`
attempt failed exactly as designed (`DOWNLOAD_CONFIGURATION_FAILED`, surfaced as a normal typed open
failure). This is the exact `download configuration fails` failure path the increment's validation
requirements describe, and it worked correctly — but it proved the guessed URL itself was wrong, per
customer correction: **the approved reporting page for short-and-long-term auctions is the same page
`PrismaLifecycleController` already opens** (`browser.PRISMA_AUCTIONS_URL`,
`https://app.prisma-capacity.eu/reporting/auctions/short-and-long-term-auctions`) — there is no separate
"reporting" URL. `prisma_download.py`'s `DEFAULT_REPORTING_URL` previously duplicated a different, wrong
literal; it now imports and re-exports `browser.PRISMA_AUCTIONS_URL` directly (`DEFAULT_REPORTING_URL is
PRISMA_AUCTIONS_URL`), so there is exactly one canonical URL constant in the codebase and both
`PrismaLifecycleController`'s initial navigation and `PrismaDownloadOrchestrator.configure()`'s
reporting-page navigation always target it. `tests/test_prisma_download.py` gained 4 tests: the exact
approved URL string; that `DEFAULT_REPORTING_URL` is the same object as (not merely equal to)
`browser.PRISMA_AUCTIONS_URL`; that a default-constructed orchestrator uses it; and a regression guard
that scans every repository-root production `.py` file and fails if the stale `/reporting/reports/...`
literal ever reappears. `tests/test_prisma_lifecycle.py`'s managed-download navigation test now pins both
`goto()` calls to the exact approved URL string rather than only comparing the two (previously
independent) constants to each other. The complete suite passed with 649 tests (up from 645, +4), and the
package was rebuilt and revalidated (see below).

**URL fix re-verified live (2026-08-02, same session).** After rebuilding the package
(`PyInstaller --clean --noconfirm` + `validate_package.py`, both passing), the live attempt above was
rerun unchanged except for the fix. Confirmed: `Open Prisma`'s managed-download navigation now lands
exactly on `https://app.prisma-capacity.eu/reporting/auctions/short-and-long-term-auctions` (page title
`"PRISMA"`, not a 404/error page) — the specific defect reported ("the application opens a PRISMA 404
page") is fixed and verified against the live site.

**Date-filter contract fix (2026-08-02, live-verified).** The guessed `get_by_label(/from\s*date/i)`
locator never matched the real page: the live site's rendered content — captured via `page.inner_text("body")`
— showed PRISMA's left-navigation shell and a banner promoting "the new PRISMA Platform design", but no
aria-labelled date fields at all. Live DOM inspection (screenshots plus a JS-injected element inventory,
capturing only non-sensitive structural attributes — no credentials, cookies, tokens, or account data) found
the real contract: a collapsed "Active Filter:" panel toggle (`role=button`, name matching `/^Active\s+Filter:/i`,
the same collapsed-filter-panel pattern `PrismaAuctionFilter` in `browser.py` already uses for the unrelated
Marketed Capacity field on this same page); two masked date-time inputs reached via `data-testid="startOfAuctionFrom"`/
`"startOfAuctionTo"` (format `DD.MM.YYYY HH:mm`, widened to a full-day window — `00:00`/`23:59` — so every
auction starting anywhere within the selected calendar range is included); and a "Filter" apply button
(`role=button`, exact name `Filter`). A live fill/read-back experiment then found a masked-input quirk:
filling the "from" field (which starts pre-populated with PRISMA's own default value) without first
clearing it only updates the date segment, leaving the time segment stuck at its placeholder ("HH:mm"),
which fails verification; clearing first (`Control+A` then `Delete`) before every fill made both fields
fill reliably regardless of whether they started empty or pre-populated. `prisma_download.py`'s
`configure()` was rewritten around this real contract (no second navigation — the already-open PRISMA
Auctions page *is* the reporting page); each failure mode raises a specific typed exception
(`PrismaDateFilterPanelError`, `PrismaDateFilterControlsNotFoundError`, `PrismaDateValueRejectedError`)
instead of a raw Playwright timeout. Live re-validation against the real site confirmed `Open Prisma`
now fills and verifies both dates and applies the filter successfully (`OPEN_EVENT ... success=True`),
fixing the defect reported as "the date-filter fill step does not match the real page's markup".

**Decision-gate correction: PrismaFunction activates the download, not the user (2026-08-02, customer
correction).** The approved decision gate (item 4 above) originally required the user to manually press
PRISMA's own download control on the PRISMA website; PrismaFunction only recognized the resulting
Playwright `"download"` event. Two live-acceptance attempts under that design reached `OPEN_EVENT
success=True` (dates filled, filter applied) but then timed out waiting for a download that never
arrived — first because the browser window was not visible on the interactive desktop (the diagnostic
harness had been launched under a sandboxed execution context that isolates GUI windows from the visible
session; rerunning with sandboxing explicitly disabled fixed window visibility), and a live report on the
second attempt made clear the manual-press premise itself was wrong: pressing a control on the PRISMA
website was never the intended user workflow. The customer corrected the authoritative workflow: the user
selects dates and a download directory in PrismaFunction, presses the single existing "Open Prisma"
in-application action, and PrismaFunction does everything else — including activating PRISMA's own CSV
download control — with no further user interaction on the PRISMA website. The real control was already
present in DOM evidence captured during the date-filter investigation above: a plain
`<button type="button">CSV</button>` (visible both before and after the Active Filter panel opens,
alongside an unrelated "PDF" button of the same shape) with no test id or ARIA attributes, so its
accessible name — computed natively from its own visible text — is the most stable available locator
(`get_by_role("button", name="CSV", exact=True)`; priority 2, since no test id exists for it).
`PrismaDownloadOrchestrator.configure()` now, after applying the date filter: waits (bounded, best-effort,
non-fatal) for PRISMA's own asynchronous filtered-results refresh via `wait_for_load_state("networkidle")`;
locates the CSV control; registers the Playwright `"download"` listener; and only then activates the
control — the listener is always registered strictly before the click, so the resulting event can never be
missed. Locating or activating the control raises a new typed `PrismaDownloadControlError` ("could not be
found" / "could not be activated") rather than a generic timeout. The stale `DOWNLOAD_TIMEOUT` message
("Press the PRISMA download button, then try again.") was rewritten, since the user no longer presses
anything on the PRISMA website. `PrismaLifecycleController` required no functional change — the new
activation is fully encapsulated inside `configure()`, so its docstrings were updated but its calling code
is unchanged. `app.py`'s existing "Open Prisma" action is reused unchanged as the single CSV-download
action (no new permanent UI); only the "Choose Download Folder" tooltip was corrected from "the manually
downloaded PRISMA CSV" to "the downloaded PRISMA CSV is saved".

`tests/test_prisma_download.py` gained 6 tests: exact-accessible-name activation of the CSV control;
registration-before-activation ordering (a locator records whether the listener was already registered at
click time); control-not-found and control-activation-failure typed errors; tolerance of a slow/unsupported
`networkidle` wait; and that the `DOWNLOAD_TIMEOUT` message no longer asks the user to press anything.
`tests/test_prisma_lifecycle.py` gained 2 integration tests for the same control-not-found/activation-failure
paths reported as typed open failures, and its existing managed-download test now also asserts the CSV
control was clicked exactly once. The complete pytest suite passed with **668 tests**. Project-wide
`python -m compileall` and `git diff --check` both passed. `python -m PyInstaller --clean --noconfirm
PrismaFunction.spec` was rerun and succeeded, and `python validate_package.py` passed against the fresh
distribution.

**Real-site diagnostic round and two narrowly scoped fixes (2026-08-02).** Two live diagnostic runs against
the shipped executable (no code changed during diagnosis) found two distinct defects in the corrected,
fully-automated flow: **Run A** — the CSV control click succeeded but no page-scoped `"download"` event
arrived; visual observation showed the export opens in a new browser tab. **Run B** — dates were filled and
applied and the CSV control was visible/enabled/stable, but the click failed because PRISMA's fixed
cookie-consent banner intercepted pointer events, correctly surfaced as a typed `PrismaDownloadControlError`
(proving the failure-handling design itself was sound). Two fixes were authorized and implemented, strictly
scoped to `PrismaDownloadOrchestrator`/`PrismaDownloadWaiter` (the canonical URL, date-selection behavior,
filename/collision contract, directory contract, UI workflow, and unrelated lifecycle logic were explicitly
out of scope and untouched):

1. **Deterministic cookie-banner handling before the CSV control is activated.** Live DOM inspection found
   the banner P.23.1 already named "research-consent banner" has no test id or ARIA landmark — a
   fixed-bottom panel ("Take part in PRISMA usability research") with plain `<button>` controls "Decline"
   and "Accept & Close". `_dismiss_cookie_consent_banner()` tries "Decline" first, falls back to
   "Accept & Close", treats absence as normal within a bounded 3s wait per candidate, never removes DOM via
   JavaScript (a supported control is always available here), and raises a new typed
   `PrismaCookieConsentBannerError` if the control cannot be clicked or does not close afterward.
   `_ensure_control_not_obstructed()` then verifies via `document.elementFromPoint()` that the CSV control
   truly receives pointer events — never `force=True` — before it is clicked; a live run of this check
   first produced a false positive (the control's bounding box sits below `window.innerHeight` on the real,
   ~2300px-tall results page, so an unscrolled `elementFromPoint` call always missed), fixed by calling
   `scroll_into_view_if_needed()` first, mirroring Playwright's own `click()` actionability protocol.
2. **Download observation across the existing `BrowserContext`, including a newly opened tab.** The
   `"download"` listener is now registered on `page.context` (not `page`) via
   `PrismaDownloadWaiter.attach()`/`context.on(...)`, with no second browser or context ever created. A
   second download event is rejected explicitly (best-effort cancelled immediately, and checked again both
   before and after `save_as()` to cover a mid-save race) via a new `PrismaDownloadOutcome.MULTIPLE_DOWNLOADS`
   outcome. `PrismaDownloadWaiter.detach()` idempotently removes the listener, called both the moment a
   download result resolves (success/timeout/typed failure) and unconditionally in
   `PrismaLifecycleController._run()`'s `finally` block, so cancellation-before-resolution and browser-close
   are covered too; Close Prisma's existing `cancel_event.wait(0.1)` responsiveness is unchanged.

**Automated evidence.** The complete pytest suite passed with **695 tests** (`tests/test_prisma_download.py`:
68; `tests/test_prisma_lifecycle.py`: 57), covering both fixes' success, absence, and failure paths (see
`workflow_p.md`'s matching entry for the full enumerated list). `python -m compileall` and `git diff --check`
both passed. `python -m PyInstaller --clean --noconfirm PrismaFunction.spec` was rerun and succeeded;
`python validate_package.py` passed against the fresh distribution; an isolated-`LOCALAPPDATA` smoke launch
of `PrismaFunction.exe` reached a live main window and shut down cleanly (exit code `0`, no forced kill, no
extra browser/Node process spawned).

**Live verification of the two fixes (2026-08-02, headless Chromium against the real public site, driving
the actual `PrismaDownloadOrchestrator` code).** The real cookie-consent banner was confirmed present,
dismissed via "Decline" (independently confirmed by PRISMA's own "Successfully saved cookie preference!"
toast), and the CSV control was confirmed genuinely reachable afterward. Context-level listener registration
and `detach()` were exercised directly against the real page/context objects and behaved as implemented.

**Newly confirmed, out-of-scope blocker: the date-filter automation no longer matches the live site.** While
attempting a full live single-click-download proof, the existing, unmodified `_open_filter_panel()`/
`_locate_date_fields()` step failed reproducibly against the live site today:
`data-testid="startOfAuctionFrom"`/`"startOfAuctionTo"` are no longer present anywhere in the DOM, before or
after the "Active Filter:" toggle click; live screenshots showed the click instead clears PRISMA's own
pre-populated default filter and surfaces PRISMA's own "Please specify auction interval start date"
validation toast. This reproduced identically with the cookie banner handled first, ruling out the banner as
the cause. This is drift in PRISMA's own live UI since the date-filter contract was originally verified, not
a defect in either fix delivered in this round; per this round's explicit scope it was left unfixed. A
diagnostic side effect of not being able to narrow the result set also surfaced a PRISMA-native "Your
download contains only 5000 of 10068 items" confirmation modal requiring a second click for large unfiltered
result sets — not expected with a real narrow date range, and not handled here since it is tied to the
same out-of-scope blocker. See `workflow_p.md` for the complete diagnostic record.

**Outstanding before this increment can be marked ✅ Completed:** because of the newly confirmed date-filter
blocker above, a full live pass of the corrected, fully-automated flow — including PrismaFunction itself
activating the CSV control and an actual CSV file being downloaded, named, and propagated to
`ManualCsvSelection` — still has not been recorded end-to-end with zero manual browser interaction.
Automated tests and package validation pass, and the two fixes in this round are individually live-verified,
but per the customer's explicit instruction this increment stays 🟡 until that full live download succeeds.

**Date-filter contract re-verification and large-result-modal handling (2026-08-02, later same-day
round).** This round was scoped to exactly the two items above: (1) re-verify the real live date-filter
contract, since it had been reported no longer matching, and fix whatever the current contract actually is;
(2) detect and confirm PRISMA's own large-result confirmation modal so a sufficiently wide date range no
longer blocks the automated flow.

*Part 1 finding: the previously implemented locators still match the live site today.* Fresh live DOM
inspection (headless Chromium, then cross-checked against the real installed Chrome executable) found
`data-testid="startOfAuctionFrom"`/`"startOfAuctionTo"` present and functional under the "Active Filter:"
panel exactly as originally documented, and the existing fill/clear/verify logic in
`PrismaDownloadOrchestrator._fill_field()` still worked unmodified. PRISMA's page also exposes a visible
"New Design"/"Deactivate New Design" toggle, which is evidence the site can serve more than one UI variant;
the most likely explanation for the previously reported "controls no longer present" finding is intermittent
PRISMA-side A/B variance rather than a permanent redesign — a later re-verification run in this same round
did reproduce a `PrismaDateFilterControlsNotFoundError` once, live, exactly as designed, supporting this
theory rather than contradicting the fix. No locator was guessed: every selector below was confirmed by
direct live DOM inspection before being used.

Since the underlying locators were already correct, the actual gap was the *missing post-application
verification* the task required ("verify after applying the filter that ... the filtered state is active
before export begins"). Live DOM inspection found PRISMA echoes the applied range back into a dedicated
filter-chip element, `data-testid="filter-startOfAuctionFrom"` (e.g. `"Start of Auction 01.08.2026, 00:00 -
02.08.2026, 23:59"`), once "Filter" is clicked. `PrismaDownloadOrchestrator._verify_filter_applied()` is a
new step, run immediately after `_apply_filter()` and before the download control is ever located: it waits
for that chip to become visible (`PrismaDateFilterPanelError` if it never does — "filter application
failure") and for its content to contain both formatted dates (`PrismaDateValueRejectedError` if it never
matches — "rejected date"), then checks for any visible `role="alert"` element as a stable, semantic
"no validation error" signal (also `PrismaDateValueRejectedError` if one is found). A live run during this
round caught a genuine timing bug in the first version of this check: PRISMA's chip re-render can lag
slightly behind the "Filter" click — the existing best-effort `networkidle` wait only waits for the network,
not PRISMA's own React re-render — so a single immediate `inner_text()` read intermittently observed the
pre-filter chip content and was misreported as a rejected date. The fix replaces the single read with
Playwright's own polling `wait_for` (`chip.filter(has_text=<pattern requiring both formatted dates>)`,
bounded at 5s), re-evaluated live against the DOM instead of read once; a follow-up live run through the
full `PrismaLifecycleController` pipeline (real Chrome, the exact production code path) confirmed the fix —
`Open Prisma` now reports `success=True` reliably, including the filter-chip verification step.

*Part 2: large-result confirmation modal.* Live DOM inspection (narrow one-day range, which still returned
over 11,000 line items for this particular date) reproduced PRISMA's own confirmation dialog:
`role="dialog"`, heading "Warning", body text `"Your download contains only 5000 of 11667 items."`, and its
own unattributed `<button type="button">CSV</button>` confirm control — the same accessible name as the
main page's CSV control, but only reachable by scoping the locator to the dialog. `configure()` now calls
`_confirm_large_result_modal_if_present()` immediately after activating the main CSV control: it waits up to
3s (bounded, best-effort, matching the existing cookie-banner detection pattern) for a
`role="dialog"` element whose text matches `/contains only [\d,]+ of [\d,]+ items/i`; absence within that
window is treated as normal (a sufficiently narrow range never shows it). When present, the dialog-scoped
"CSV" button is clicked to proceed with the truncated export; a new `PrismaLargeResultConfirmationError` is
raised if that control cannot be found or activated. The download listener registered on `page.context`
before the *first* CSV click remains in place throughout, so the resulting download — whether triggered
directly or via this confirmation — is still captured without a second listener registration. A live run
confirmed the complete sequence end-to-end (headless Chromium, real site): filter applied and verified,
modal detected, confirm button clicked, and the resulting Playwright `"download"` event captured with
`suggested_filename="Auction_overview.csv"`, which the existing naming/collision logic then dates and
reserves exactly as before. The date range itself is never altered to avoid the modal.

**New, orthogonal blocker found during this round: real-Chrome download-event delivery.** While proving the
above fixes through the exact production code path (`PrismaLifecycleController`, real installed Chrome
executable via `DefaultBrowserDetector`, driven directly — not reimplemented), `Open Prisma` succeeded
(dates filled, filter-chip verified, CSV control activated, and — when present — the large-result modal
confirmed), but no `"download"` event was ever observed by the controlling Python process, even though the
real Chrome window's own UI displayed its native "Download complete." toast. This was isolated, not guessed:
a minimal repro and several targeted variants (real Chrome executable vs. the Playwright-bundled Chromium
build; `headless=True` vs. `headless=False`; with and without an explicit `accept_downloads=True`) were run
directly against the real PRISMA CSV-download flow. The Playwright-bundled Chromium build in headless mode
reliably captured the download event across every attempt (including the full detect-modal-confirm-capture
sequence above); the real installed Chrome executable did not capture it in any attempt, regardless of the
headless flag, and no download artifact was ever found in Playwright's own managed temp/artifact
directories, indicating the real Chrome build's own download manager is completing the download through a
path that bypasses Playwright's CDP-based download interception in this environment. This is orthogonal to
both fixes in this round (neither touches download-event wiring, which is unchanged from the prior,
already-live-verified `PrismaDownloadWaiter`/context-registration design) and was not previously encountered
because no prior round had completed a full download capture through the real installed browser executable
end-to-end — prior live verifications of the cookie-banner and context-registration fixes were also
performed against the Playwright-bundled Chromium build in headless mode, not the real installed browser
(see this section's 2026-08-02 diagnostic-round entry above, "headless Chromium against the real public
site"). Root cause is not yet fully diagnosed; it did not block this round's authorized scope (the date-filter
contract and large-result-modal fixes are both independently proven correct via the headless runs above), but
it does block a full production-mode (`headless=False`, real browser) live-acceptance pass, so P.36.14 stays
🟡. A direct interactive-user validation pass on a normal Windows desktop (outside this automated coding
session) is recommended as the next step, since this class of headed-browser automation difference has
previously turned out to be environment-specific in this project (see the decision-gate-correction entry
above, where a sandboxed execution context initially hid the browser window and re-running without that
constraint fixed visibility) — though this round's diagnostics did not find disabling this session's own
sandboxing sufficient to resolve the download-capture gap by itself.

**Automated evidence (2026-08-02, this round).** `tests/test_prisma_download.py` gained tests for: the
applied-filter chip being checked before the download control is located; the chip never appearing
(`PrismaDateFilterPanelError`); the chip's content not matching the selected range
(`PrismaDateValueRejectedError`); a visible validation alert after applying the filter
(`PrismaDateValueRejectedError`, download control never clicked); a present-but-not-visible alert being
ignored; the large-result modal being absent (treated as normal); the modal being confirmed via its own
scoped "CSV" button; the modal's confirm control not found or not activatable
(`PrismaLargeResultConfirmationError`); the date range never being altered to avoid the modal; and a download
still being captured end-to-end after modal confirmation. `tests/test_prisma_lifecycle.py` gained integration
tests for: a filter-verification failure reported as a typed open failure; the large-result modal being
confirmed automatically during a full managed `open()`; the modal's confirm control failing reported as a
typed open failure; the modal's absence being normal; and the downloaded CSV still being captured, named, and
saved correctly when it followed a modal confirmation. The complete pytest suite passed with **711 tests**
(up from 695; `tests/test_prisma_download.py`: 79, up from 68; `tests/test_prisma_lifecycle.py`: 62, up from
57). Project-wide `python -m compileall` and `git diff --check` both passed (the same pre-existing,
unrelated `.pytest_tmp` permission warning noted in prior entries is the only compileall output).
`python -m PyInstaller --clean --noconfirm PrismaFunction.spec` was rerun and succeeded; `python
validate_package.py` passed against the fresh distribution; an isolated-`LOCALAPPDATA` smoke launch of
`PrismaFunction.exe` reached a live main window (`MainWindowHandle` non-zero, title `PRISMA Monitor
v1.0.0`, `Qt6Core`/`Qt6Gui`/`Qt6Widgets` loaded) and shut down cleanly via `CloseMainWindow()` (exit code
`0`, no forced kill, no `chrome.exe`/`msedge.exe` process left running by the smoke run itself).

**Outstanding before this increment can be marked ✅ Completed (updated):** the date-filter contract and
large-result-modal fixes are both implemented, unit-tested, and independently live-verified end-to-end
(including a full detect → confirm → capture pass for the large-result modal) using the Playwright-bundled
Chromium build in headless mode. The full production-mode pass — the real installed browser executable,
`headless=False`, exactly as `PrismaLifecycleController` launches it, with an actual CSV file downloaded,
named, and propagated to `ManualCsvSelection` — still has not been recorded, because of the newly found,
orthogonal real-Chrome download-event delivery gap described above. This increment stays 🟡 until that gap
is resolved and a full production-mode live pass succeeds.

**Approved production fallback: bounded filesystem observation (2026-08-03, customer decision).** Rather than
requiring the real-Chrome download-event delivery gap to be root-caused first, the customer approved
proceeding without relying exclusively on the Playwright `BrowserContext` `"download"` event. The Playwright
event remains the primary mechanism; if the real installed Chrome/Edge executable completes a download but no
Playwright event is delivered, bounded filesystem observation of the configured download directory is now an
approved production fallback, under explicit constraints: snapshot the directory before activating the CSV
control; consider only files created after that snapshot; ignore `.crdownload` partial files; accept only one
new `.csv` file; wait for its size to stabilize across multiple checks; verify it can be opened for reading;
reject zero files, multiple files, timeout, and interrupted downloads; remain cancellable so Close Prisma
stays responsive; use a fixed timeout and bounded polling interval; and never scan outside the configured
directory. The existing dated filename and collision rules apply identically to a file resolved this way.

`prisma_download.py`'s new `PrismaDownloadFilesystemWaiter` (`snapshot()`/`poll()`) implements exactly this
contract; `PrismaDownloadOrchestrator.configure()` gained an optional `download_directory` parameter that,
when supplied, snapshots the directory right after the Playwright listener is registered and strictly before
the CSV control is activated (omitting it — the pre-existing call shape — leaves the fallback disabled, so
this is purely additive); `await_and_finalize()` still checks the Playwright event first and only consults the
fallback when it has not fired, translating a stabilized, readable new `.csv` file into the same typed
`PrismaDownloadResult` outcomes the primary path already reports, finalized via the same
naming/collision rule (`os.replace()` into the reserved placeholder path, since there is no `Download` object
to call `save_as()` on for a file the fallback found on disk). `PrismaLifecycleController._run()` now passes
`download_directory` through to `configure()`; no second wait loop, thread, or filesystem-polling mechanism
was added — the fallback is polled from inside the exact same non-blocking `await_and_finalize()` call already
interleaved with the existing `cancel_event.wait(0.1)` idle loop, so Close Prisma's responsiveness is
unaffected. See `workflow_p.md`'s matching dated entry for the full implementation and test record.

**Automated evidence (2026-08-03).** The complete pytest suite passed with **725 tests** (up from 711;
`tests/test_prisma_download.py`: 91, up from 79, +12; `tests/test_prisma_lifecycle.py`: 64, up from 62, +2),
covering: directory-snapshot exclusion of pre-existing files; the fallback staying disabled when no directory
is supplied; `.crdownload` partials being ignored; size-stability gating; multiple-new-`.csv`-file rejection;
never scanning outside the configured directory; a full fallback success (dated name applied, source file
moved into place); a late Playwright event still winning over an already-ready fallback result; no-overwrite
of an existing dated-name file; multiple files rejected through `await_and_finalize()`; timeout parity with the
primary path; cancellation parity with the primary path; a full managed `open()` succeeding via the fallback
alone with the resulting `kind="download"` event correctly named and reported; and proof that an actively
polling fallback does not delay manual-closure detection. Project-wide `python -m compileall` and `git diff
--check` both passed.

**Real-Chrome production acceptance status.** This sandboxed development environment has no installed
`chrome.exe`/`msedge.exe` (`DefaultBrowserDetector` requires one of those two, read from the Windows default
HTTP-association registry key, and the executable file itself must exist) — only Playwright's own bundled
Chromium build is present, so `PrismaLifecycleController`'s real-browser production path cannot be exercised
end-to-end here. A full real-installed-Chrome acceptance pass — the specific scenario this fallback exists
for — still requires a normal interactive Windows desktop session with Chrome or Edge installed, consistent
with this section's prior recommendation. This does not affect the automated evidence above, which exercises
the fallback logic itself (`PrismaDownloadFilesystemWaiter`, `configure()`, `await_and_finalize()`) directly
against real filesystem behavior in `tmp_path`, independent of which browser executable is driving the page.

### P.36.14 — real-Windows defect fix: selected dates not actually applied to PRISMA (2026-08-03)

**Reported defect.** On real Windows, the start/end dates selected in Prisma Function were confirmed not to
actually be applied to the official PRISMA reporting page, despite the managed-download automation completing
without a reported error.

**Root cause, found via live DOM/network inspection against the real public site (headless Chromium, driving
the actual `PrismaDownloadOrchestrator` code, not a reimplementation) — two independent verification gaps in
`_fill_field`/`_verify_field_value`/`_verify_filter_applied`, not a fill-format or locator problem:**

1. **Missing time-of-day verification.** `_verify_field_value` and `_verify_filter_applied` checked only that
   the formatted *date* (`DD.MM.YYYY`) appeared in the masked text/applied-filter chip — never the `00:00`/
   `23:59` time-of-day segment `_fill_field` sets to widen the selection to a full calendar day. Since this
   exact masked input has a documented failure mode where the time segment can silently stay unset while the
   date segment updates (see this section's original clear-before-fill record), a value that *looked* accepted
   could still carry the wrong time — and hence the wrong effective range — without being caught.
2. **No verification of the framework's actual committed state.** Live DOM inspection found this field also
   exposes `data-test-iso-value`, an ISO-8601 UTC instant confirmed (via live network-request capture) to be
   the exact value later used in the real outbound PRISMA reporting/export request — i.e. the framework's
   actual committed state, not merely display text. The previous implementation only ever read
   `input_value()` (the visible masked text, which Playwright's `fill()` always sets synchronously regardless
   of whether the page's own component has processed the change), so a value that displayed correctly could
   still not have been committed to the state PRISMA's request actually uses.

**Fix, `prisma_download.py` (`PrismaDownloadOrchestrator`):**

- `_fill_field()` now blurs the field (`field.evaluate("(el) => el.blur()")`) immediately after `fill()`,
  before verification — the same interaction a real user performs by tabbing or clicking away — so any
  commit-on-blur logic in the page's own component runs deterministically instead of relying on an incidental
  later blur from focusing the next control.
- `_verify_field_value()` now independently requires both the date *and* the time-of-day substring in the
  masked text (not one combined string, since the real control pads its display text with extra internal
  whitespace a single formatted substring would not match), then calls the new
  `_verify_committed_field_state()`.
- `_verify_committed_field_state()` reads `data-test-iso-value` via `field.evaluate(...)` and compares the
  committed instant against the requested date/time. **A first version of this check computed the comparison
  using the browser's own local-timezone `Date` getters and was caught by further live testing to be
  incorrect**: launching the identical fill against the real page under four different browser timezones
  (`Europe/Berlin`, `America/New_York`, `Asia/Tokyo`, `UTC`) produced the *exact same* `data-test-iso-value`
  every time, proving PRISMA always interprets the typed local text as fixed Europe/Berlin time regardless of
  the machine's own configured timezone (sensible for a EU energy-market platform) — so converting the
  committed instant back using the *browser's* local timezone, as the first version did, would have produced
  false rejections on any real machine not already set to Europe/Berlin, i.e. a new machine-dependent defect
  masquerading as a fix. The corrected check instead computes, inside the browser via `Intl.DateTimeFormat`
  with an explicit `timeZone: 'Europe/Berlin'`, the UTC instant corresponding to the requested wall-clock
  date/time in that fixed zone (correctly handling the CET/CEST DST boundary, live-verified against both an
  August/CEST and a January/CET date) and compares that directly to the committed instant — never the
  machine's own local timezone. A future PRISMA build without this attribute is tolerated (returns without
  raising): the text-based date+time check already ran and is the fallback signal in that case.
- `_verify_filter_applied()`'s applied-filter-chip check now also independently requires both the start and
  end time-of-day substrings (previously dates only), closing the same gap at the post-Filter-click layer.
- Any of the above failing raises the existing `PrismaDateValueRejectedError` (the same typed managed-download
  failure path Open Prisma already surfaces), never continuing with a potentially wrong range. No unbounded
  sleep was added; all new waits reuse the existing bounded `_CONTROL_TIMEOUT_MS`.

**Scope.** Strictly confined to `_fill_field`/`_verify_field_value`/`_verify_committed_field_state`/
`_verify_filter_applied` in `prisma_download.py`. The canonical URL, cookie-consent handling, large-result-modal
handling, the naming/collision rule, the download-directory contract, the filesystem-observation fallback, the
12-column output contract, the manual CSV fallback, and unrelated UI are all unchanged and untouched.

**Automated evidence (2026-08-03).** `tests/test_prisma_download.py` gained 9 tests covering: both fields
filled with the exact requested date and time; the exact click→clear→fill→blur event sequence; blur failure
reported as a typed failure; a wrong time-of-day (date correct) caught by verification; a committed value that
does not match the visible text caught by verification; a field without the committed-value attribute tolerated
(fallback to the text-based check); the committed-value read itself failing reported as a typed failure; and
the applied-filter chip requiring both dates and times, including one test that used to incorrectly pass with
a wrong time and now correctly fails, and one confirming a fully matching chip still passes.
`tests/test_prisma_lifecycle.py` gained 1 full-trace integration test: a date not actually committed reported
through the existing typed open-failure path, with the CSV download control confirmed never activated. The
complete pytest suite passed with **735 tests** (up from 725; `tests/test_prisma_download.py`: 100, up from 91;
`tests/test_prisma_lifecycle.py`: 65, up from 64). Project-wide `python -m compileall` and `git diff --check`
both passed. `python -m PyInstaller --clean --noconfirm PrismaFunction.spec` was rerun and succeeded;
`python validate_package.py` passed against the fresh distribution.

**Live evidence (2026-08-03, headless Chromium, real public site, driving the actual fixed
`PrismaDownloadOrchestrator.configure()` code, not a reimplementation).** `configure()` completed without
raising and the real outbound CSV export request (`GET .../rest/auctions/report/csv?...`) carried exactly the
requested `startOfAuctionFrom`/`startOfAuctionTo` UTC instants for the selected local date range — confirming
the fix closes the reported gap end-to-end, not just at the field level. The same check was also run with the
browser's timezone forced to `America/New_York`, `Asia/Tokyo`, and `Pacific/Auckland` to confirm the corrected,
Europe/Berlin-fixed comparison does not produce the false-rejection regression the first (browser-local-time)
version of the check would have introduced; all three passed without a false rejection.

**Outstanding.** This sandboxed environment has no installed `chrome.exe`/`msedge.exe`, so the fix's live
evidence above was gathered with Playwright's own bundled Chromium build, not the real installed browser. Per
this increment's own instructions, manual validation is still required on a real Windows desktop against the
official PRISMA page: choose a clearly distinguishable start and end date in Prisma Function, start the
managed download, and confirm both exact dates appear in the PRISMA controls and that the resulting
request/download uses that range. This is in addition to, not a replacement for, the still-outstanding
real-installed-Chrome production acceptance pass recorded in this section's prior entry.

### P.36.14 — real-Windows defect fix: DATE RANGE controls initializing to Qt's minimum date (2026-08-03)

**Reported defect (real Windows, screenshot-confirmed).** Both `start_date_edit` and `end_date_edit`
initialized to values near Qt's minimum supported `QDate` (`1752-09-25` and `1752-09-29`) instead of a
usable application date, contradicting the intended `specialValueText("Not set")` presentation recorded
in P.36.13's implemented result.

**Root cause.** `PrismaMonitorApp.__init__` explicitly set each control's initial value with
`self.start_date_edit.setDate(self.start_date_edit.minimumDate())` (and the equivalent for
`end_date_edit`) — i.e. construction time set the visible value to the widget's own
implementation/platform-defined `minimumDate()`, not a meaningful default. `minimumDate()` is
implementation-defined by Qt/PySide6 per platform and is never guaranteed to render as the configured
`specialValueText`; on the real Windows target it rendered as the literal near-1752 date instead.

**Fix, `app.py`.** A new module-level `_current_local_date() -> date` (returns `date.today()`) is the
single, isolated seam through which `PrismaMonitorApp` reads today's date; both `start_date_edit` and
`end_date_edit` are now explicitly initialized to `QDate(today.year, today.month, today.day)` computed
from it, never to `minimumDate()`. No other default is specified by the authoritative P.36.13/P.36.14
requirements, so both controls default to the same current date (a valid, same-day range). The
`specialValueText("Not set")` call and the existing `_read_optional_date()` sentinel comparison against
`widget.minimumDate()` are both preserved unchanged, so a user who deliberately navigates a control back
to the calendar's minimum still reads as a missing date — only the construction-time default changed.
`DateRangeSelection.current` still starts at `None` and only advances on an explicit "Validate Date
Range" click, so Open Prisma's precondition gate (P.36.14) is unaffected: a default same-day range is
displayed, but nothing is accepted until the user validates it.

**Scope discipline.** Confined to the `start_date_edit`/`end_date_edit` construction block in
`PrismaMonitorApp.__init__` and the new `_current_local_date()` helper. PRISMA automation, the
managed-download orchestration, the download-directory contract, the output schema/mappings, and all
other UI are unchanged.

**Automated evidence (2026-08-03).** Two new regression tests in `tests/test_app.py`:
`test_date_range_controls_do_not_initialize_to_qts_minimum_date` (proves neither control equals its own
`minimumDate()`, and that both controls' initial year is greater than 1752) and
`test_date_range_controls_initialize_to_a_fixed_current_date` (constructs `PrismaMonitorApp` with
`app._current_local_date` monkeypatched to a fixed date and asserts both controls show exactly that
date). `test_date_range_initial_state_is_deterministic_and_unset` was updated to assert both controls
equal `QDate.currentDate()` instead of `minimumDate()`. The two existing missing-date tests
(`test_validating_with_missing_start_date_shows_error_and_preserves_state`,
`test_validating_with_missing_end_date_shows_error_and_preserves_state`) were updated to explicitly
select the untouched control's own `minimumDate()` sentinel value, since a genuinely missing date is no
longer the construction-time default; both still correctly reject with the unchanged
`MISSING_START_DATE`/`MISSING_END_DATE` messages. `test_date_range_controls_remain_enabled_and_retryable_after_error`
was updated to set an explicit reversed range so it still exercises an actual rejection, not a
now-accepted default. The complete pytest suite passed with **737 tests** (up from 735; `tests/test_app.py`:
89, up from 87). Project-wide `python -m compileall` (excluding `.venv`, `build`, `.git`, `__pycache__`)
exited 0, with the same pre-existing, unrelated `.pytest_tmp` permission warning recorded in P.36.13's
evidence. `git diff --check` passed. `python -m PyInstaller --clean --noconfirm PrismaFunction.spec` was
rerun to produce a fresh distribution from this fix, and `python validate_package.py` passed against it.

**Outstanding.** Full manual Windows validation — visually confirming both controls show today's date
(not `1752-09-25`/`1752-09-29`) on first launch, that the calendar popup and manual retype still work,
and that the fix carries through to a real managed download — has not yet been performed and remains
required before this fix can be considered validated end-to-end, in addition to P.36.14's
already-recorded outstanding real-installed-Chrome production acceptance pass.

### P.36.14 — real-Windows defect fix: managed download completed in Chrome but never reached the configured directory (2026-08-03)

**Reported defect (real Windows, confirmed).** `chrome://downloads` showed the PRISMA export completed
under a temporary, browser-generated (UUID-like) name, but the configured Prisma Function download
directory — which existed and was writable — stayed empty. The managed download never finalized into a
non-empty `.csv` file inside the selected directory, even with the approved bounded filesystem-observation
fallback (see this section's 2026-08-03 "approved bounded-filesystem-observation production fallback"
entry above) already in place.

**Root cause.** `PrismaLifecycleController._run()` launched the browser via
`playwright.chromium.launch(executable_path=..., headless=False, args=[...])` without a `downloads_path`.
Real Chrome/Edge's CDP-driven download interception (the "allowAndName" behavior Playwright configures)
writes the raw download artifact under a framework-generated, UUID-like name into whatever directory
Playwright itself manages when `downloads_path` is not supplied — an ephemeral, untracked temp location
with no relationship to the directory the user selected in Prisma Function. The previously added filesystem
fallback (`PrismaDownloadFilesystemWaiter`) was watching the *correct* configured directory, but Chrome was
never told to write there, so it always stayed empty: the fallback and the browser's actual write target
were simply two different directories. This is a distinct defect from, and builds on top of, the earlier
approved fallback itself, which correctly assumed Chrome's *own native* download manager would write to a
directory PrismaFunction controls, but did not yet force that directory via Playwright's own launch
configuration.

**Fix.**

1. `prisma_lifecycle.py`: `_run()` now passes `downloads_path=str(download_directory)` to
   `playwright.chromium.launch()` whenever a managed download is requested (`date_range` and
   `download_directory` both supplied). Omitting either argument (the pre-P.36.14/non-managed-download
   path) never sets `downloads_path`, preserving exact prior behavior. This forces the raw download
   artifact — whether ultimately captured via the primary Playwright `"download"` event or only ever
   observed via the fallback — to land directly inside the exact directory the user selected, never
   Chrome's own default Downloads folder and never an untracked Playwright temp directory. No hidden
   staging directory was introduced (P.35.2–P.35.5's cancelled staging design is not restored): the
   configured directory is the only directory ever written to.
2. `prisma_download.py`'s `PrismaDownloadFilesystemWaiter.poll()`: since the raw artifact Chrome/CDP now
   writes is browser/CDP-named (typically UUID-like, not `.csv`), a candidate is no longer required to
   have a `.csv` suffix — any newly appeared, non-partial file in the configured directory is now a
   candidate. Genuine completion is still decided exactly as before (size stability across
   `_FILESYSTEM_STABILITY_CHECKS` consecutive polls plus a successful open-for-read), never by name alone;
   `.crdownload`-suffixed partial files are still excluded from candidacy exactly as before, so the
   native-Chrome-with-a-suggested-filename flow is unaffected. The activity-tracking flag driving eventual
   `INTERRUPTED` classification after a candidate disappears without completing was broadened to fire on
   any candidate, not only a recognized `.crdownload` partial, so a cancelled UUID-named artifact is still
   correctly classified rather than silently timing out.
3. `_finalize_from_filesystem()` now forces a `.csv` extension explicitly (`f"{path.stem}.csv"`) rather
   than deferring to `build_dated_filename`'s suffix-preserving default, since the raw artifact's own name
   is never a trustworthy source of the final extension. Existing `.csv`-suffixed inputs are unaffected
   (`Path("Auction_overview.csv").stem` is `"Auction_overview"`, producing the identical name as before).
4. Both the primary (event) and fallback finalize paths now reject a **stable but empty** artifact rather
   than reporting success: `PrismaDownloadFilesystemWaiter._poll_candidate()` classifies a zero-byte,
   size-stable, readable file as `INTERRUPTED` instead of `READY`; `PrismaDownloadOrchestrator._finalize()`
   checks the saved file's size after a successful `save_as()` and reports `DOWNLOAD_INTERRUPTED` (deleting
   the empty artifact) if it is zero bytes. Neither path previously guarded against this.
5. `suggested_filename`'s existing sanitization (via `Path.stem`/`Path.suffix`, which already strip any
   directory components including `../` traversal segments before `build_dated_filename` assembles a flat
   filename) was confirmed correct and is now covered by an explicit regression test, rather than relying
   on it being incidentally safe.

**Scope discipline.** Confined to `prisma_lifecycle.py`'s browser-launch call and
`prisma_download.py`'s `PrismaDownloadFilesystemWaiter`/`PrismaDownloadOrchestrator._finalize()`/
`_finalize_from_filesystem()`. Date handling, the 12-column output contract, transformations, mappings, the
manual CSV fallback (P.36.4), the naming/collision rule itself, the download-directory contract (P.36.3),
and unrelated UI are all unchanged and untouched. The download-listener registration order (context-level,
strictly before the CSV control is activated) was inspected and confirmed already correct; no change was
needed there.

**Automated evidence (2026-08-03).** `tests/test_prisma_download.py` gained 7 tests: a UUID-named artifact
(no `.csv` suffix) recognized as a candidate; multiple new files rejected as ambiguous regardless of
extension; a stable-but-empty file classified as `INTERRUPTED`, never `READY`; exactly one dated output
produced when the Playwright event and the fallback both observe the same download (the primary path wins,
no duplicate); the fallback finalize path forcing a `.csv` extension on a suffixless artifact; a zero-byte
saved download (primary/event path) classified as `DOWNLOAD_INTERRUPTED` with the empty artifact removed;
and a path-traversal-shaped `suggested_filename` (`"../../evil.csv"`) confirmed to resolve only inside the
configured directory. `tests/test_prisma_lifecycle.py` gained 4 integration tests: `downloads_path` is
passed to `playwright.chromium.launch()` and equals the configured directory exactly when a managed
download is requested; `downloads_path` is never passed when date range/directory are omitted (backward
compatibility); the filesystem fallback finalizes a UUID-named artifact end-to-end into a correctly dated
`.csv`; and exactly one `kind="download"` success event (and exactly one dated output file) results when
both the filesystem artifact and the Playwright event are observed for what is conceptually the same
download. The complete pytest suite passed with **748 tests** (up from 737; `tests/test_prisma_download.py`:
107, up from 100; `tests/test_prisma_lifecycle.py`: 69, up from 65). Project-wide `python -m compileall`
(excluding `.venv`, `build`, `.git`, `__pycache__`) exited `0`, with the same pre-existing, unrelated
`.pytest_tmp` permission warning recorded in prior entries. `git diff --check` passed (the same
informational CRLF-normalization notice on `tests/test_prisma_lifecycle.py` noted in prior entries, not a
whitespace error, and predating this fix). `python -m PyInstaller --clean --noconfirm PrismaFunction.spec`
was rerun to produce a fresh distribution from this fix, and `python validate_package.py` passed against it.

**Outstanding.** Full manual Windows validation is still required and has not yet been performed: select
`Downloads\PrismaFunction` as the download folder, choose and validate a distinguishable date range, start
the managed PRISMA download in real Chrome, and confirm the selected directory receives exactly one final,
non-empty `.csv` file with a normal (dated, `.csv`-suffixed) final filename — and that no UUID-named or
partial file is ever left behind mistaken for the final result. This is in addition to, not a replacement
for, P.36.14's already-recorded outstanding real-installed-Chrome production acceptance pass and the DATE
RANGE control fix's own outstanding manual validation recorded in this section's immediately preceding
entry.

### P.36.15 — Transform into the exact 12-column output CSV contract

**Status:** 🟡 Implemented, automated-tested, and reviewed; merged to `main` via PR #62 (merge commit
`c84344f`). Final review found no remaining actionable code defects, but manual validation on real
Windows/real PRISMA data is still outstanding, so this stays 🟡 rather than ✅.
**Dependency required before implementation:** P.36.14 completed.

**Objective:** Transform the validated official PRISMA CSV into the exact 12-column contract defined in this roadmap.

**Included scope:**

- parsing only through the approved validated-input boundary;
- approved booked-capacity filtering and supported unit/price normalization;
- capacity-type, product-type, flow-start, flow-end, and duration calculation under existing authoritative rules;
- exact side-specific evidence-based resolution into the combined `Exit Market` and `Entry Market` fields;
- immutable typed row outcomes that account for accepted, filtered, and rejected source rows;
- deterministic `;`-delimited UTF-8 output serialization with exact header order and dot decimals.

**Excluded scope:**

- separate `Exit Storage` or `Entry Storage` fields;
- fuzzy/inferred/cross-side mapping;
- UI mapping presentation;
- publication destination, accumulation, deduplication, or recovery behavior not explicitly approved for P.36.16;
- PDF input.

**Acceptance criteria and focused tests:**

- header is exactly the 12 names above in the exact order, with no extra columns;
- storage names are written into the relevant Market field according to side, never into a separate storage field;
- every source row has one deterministic typed outcome;
- filters, conversions, timestamps, durations, price fields, mapping success, unresolved mapping, malformed input, and exact serialization are covered;
- no output is published on a failed transformation;
- focused tests, full regression tests, compilation, and whitespace validation pass;
- documentation records field-level source/transform rules and exact executed validation results.

**Implemented result.** New, Qt- and browser-independent module `prisma_output.py`. It performs no parsing,
normalization, filtering, enrichment, or side-specific resolution of its own: `processor.import_prisma_export()`
(P.33/P.36.4, unchanged) already implements and tests every one of those authoritative rules, including the
existing missing-side/unknown-alias typed rejection behavior; `prisma_output.py` only selects, renames, and
formats the already-enriched row shape into the approved 12-column contract, then writes it. Field-level
mapping from `processor.py`'s enriched row dict to the output contract: `auction_date`/`flow_start`/`flow_end`
pass through unchanged as the ISO 8601 strings already treated as authoritative elsewhere in the codebase
(`storage.py`'s SQLite/Excel export uses the same representation); `exit_market`/`entry_market` map directly
(each populated only from its own side's resolved evidence, exactly as `processor.py` already guarantees);
`direction` (`"entry"`/`"exit"`/`"bundle"`) maps to `Capacity Type` unchanged, matching the authoritative
specification's exact wording (`workflow_p.md` section 1.1, item 5); `network_point` maps to
`Network Point Name`; `product_type` maps to `Product Type`; `booked_capacity_kwh_h`, `runtime_hours`,
`tariff_eur_mwh_h`, and `premium_eur_mwh_h` map to `Booked Capacity`, `Flow Duration Hours`, `Tariff Price`,
and `Premium Price` respectively, each formatted via Python's own `str(float)` (always dot-decimal; no
rounding is applied, since no authoritative rounding/precision decision exists — the raw already-normalized
float from `processor.py` is preserved exactly).

`write_prisma_output(source_path, output_directory, *, reference_catalog=DEFAULT_PRISMA_REFERENCES)` is the
single entry point: it validates the destination directory first (existing, readable, and writable — reusing
`download_directory.validate_download_directory` plus a writability check, never touching the filesystem for
an invalid destination), then calls `import_prisma_export()` (a malformed/non-PRISMA source CSV fails with
`SOURCE_IMPORT_FAILED` and writes nothing), then transforms only the accepted rows and writes them
atomically: `prisma_download.reserve_unique_download_path()` (already-approved P.36.14 naming/collision rule,
reused unchanged rather than reimplemented) exclusively reserves a collision-free destination filename, the
full CSV is staged into a temporary file in the same directory and `fsync`ed, and only then `os.replace()`d
onto the reserved placeholder — so a write failure at any point leaves no partial file at the final published
name (verified by dedicated tests that fail `os.replace` and fail mid-write, both proving zero files remain in
the destination directory afterward). No customer-approved publication naming/collision policy exists yet
specifically for this transformed output (that decision is explicitly deferred to the blocked `P.36.16` gate);
`build_output_filename()` uses `"<source-stem>_transformed.csv"`, the safest available assumption consistent
with the `P.36.14`-established `"<stem>_<suffix>.csv"` template, documented here as an explicit assumption
rather than a customer decision. Every call is independent: two calls over the same source produce two
separate, independently-collision-numbered output files with no merging, accumulation, or cross-call state,
proving `P.36.16`'s accumulation/deduplication/state-tracking scope has not been introduced.

`PrismaOutputResult` (immutable, typed `PrismaOutputOutcome`: `SUCCESS`, `INVALID_OUTPUT_DIRECTORY`,
`SOURCE_IMPORT_FAILED`, `WRITE_FAILED`) carries the output path (on success) and the full
`processor.PrismaImportResult` (accepted/filtered/rejected counts and the typed per-row issue list), so every
source row's deterministic outcome remains inspectable; `describe_output_failure()` provides stable, English,
path-free messages matching the existing `describe_validation_rejection`/`describe_rejection` pattern used by
`prisma_download.py`/`manual_csv_selection.py`. No UI wiring was added: `app.py`, `PrismaFunction.spec`, and
all browser/lifecycle code are unchanged, since no P.36.15 acceptance criterion requires a UI trigger and
`self._manual_csv_selection.current` (already exposed by the merged P.36.14 work) is the exact boundary this
module is designed to consume once a later increment wires it in.

**Review fix (2026-08-04).** A review of the initial implementation found that both `WRITE_FAILED` paths in
`write_prisma_output()` (reservation failure and staging/atomic-replace failure) discarded the already-completed
`PrismaImportResult`, even though `import_prisma_export()` had already succeeded by that point — a caller
handling a write failure had no way to see which rows had been accepted, filtered, or rejected. Both paths now
pass `import_result=imported` unchanged, with no change to the outcome, message, or safe-error behavior.

**Automated evidence (2026-08-04, `feature/p36-15-output-writer`, not yet merged).** New
`tests/test_prisma_output.py` (26 tests) covers: the exact ordered 12-column header and exactly 12 fields per
row; UTF-8 encoding and `;` delimiter; a representative successful transformation with exact field-by-field
value assertions (including tariff/premium price summation); pure `transform_row()` field mapping; Exit/Entry
placement for entry-only, exit-only, and bundle directions, including one Market-classified and one
Storage-classified case; unresolved-alias and missing-required-side rows excluded from the written output
while still recorded as typed rejections in `PrismaImportResult`; below-threshold rows filtered and excluded;
a mixed accepted/rejected source producing only the accepted row in the output; zero accepted rows still
producing a valid header-only output (a successful transformation of an empty accepted set, not a failure);
a malformed/non-PRISMA source failing the transformation and writing nothing; stable non-empty messages for
every `PrismaOutputOutcome`; a nonexistent, a file-shaped, and a non-writable destination directory each
rejected without any filesystem write; the exact `"<stem>_transformed.csv"` naming rule; collision handling
never overwriting an existing file and using the approved incrementing-suffix rule; two independent calls
never merging or deduplicating; a destination-reservation failure and a simulated `os.replace` failure and a
simulated mid-write failure each leaving zero files (no partial output, no orphaned staging temp file) in the
destination directory, with each of the three write-failure tests also asserting `import_result` carries the
exact pre-computed accepted/filtered/rejected counts, rows, and issue reason codes from a mixed-outcome source
(one accepted, one filtered, one rejected row) rather than being discarded; a successful write leaving no
staging artifacts behind; and a caller-supplied `PrismaReferenceCatalog` being honored instead of the default.
The complete pytest suite passed with **774 tests** (up from 748, the exact +26 expected from this increment).
Project-wide `python -m compileall` (excluding `.venv`, `build`, `.git`, `__pycache__`, `dist`) exited `0`,
with the same pre-existing, unrelated `.pytest_tmp` permission warning recorded in prior entries. `git diff
--check` passed.

**Not run.** `python -m PyInstaller --clean --noconfirm PrismaFunction.spec` and `python validate_package.py`
were not rerun: `prisma_output.py` is not imported by `app.py` or referenced by `PrismaFunction.spec`, so
PyInstaller's static import discovery would not even bundle it and a rebuild would reproduce the identical
distribution already validated after the P.36.14 merge — this increment does not affect packaging.
`tests/test_packaging.py` is included in, and passed as part of, the 774-test full-suite run above. No real
Windows or real-PRISMA manual validation was performed or is required by this increment's own acceptance
criteria (it consumes only an already-on-disk validated CSV file; no browser, network, or PRISMA session is
touched), but end-to-end manual validation of the eventual wired-in workflow remains appropriate once a later
increment adds the UI trigger.

### P.36.16 — Publish the processed result

**Status:** 🟡 Decision gate resolved (customer-approved "option 2", 2026-08-04); implemented,
automated-tested, and merged to `main` via PR #63 (merge commit `daf4760`, confirmed in Git history).
Not yet manually validated on real Windows/real PRISMA data.
**Dependency required before implementation:** P.36.15 completed.

**Decision gate — resolved (2026-08-04, customer-approved "option 2"):** Publication accumulates
results across runs into exactly one cumulative CSV per publication directory, using the approved
Documents-directory-or-user-selected-directory contract (`P.36.3`) as the destination — never
`%LOCALAPPDATA%`. Duplicate identity is the complete, exact 12-field canonical output row (see
`prisma_output.transform_row`/`OUTPUT_CSV_COLUMNS`) — not a narrower business key such as Auction ID
(which is not one of the 12 output fields), and never fuzzy/substring/inferred matching or
update-in-place semantics. A duplicate row (against either the existing published rows or another row
within the same completed import) is silently dropped, never appended a second time. Existing unique
rows keep their original order; new unique rows are appended in their current import order. Recovery is
atomic stage-then-`os.replace()`, matching the existing `P.36.14`/`P.36.15` pattern: a failure at any
point before the final replace never loses, corrupts, or partially exposes the previous valid cumulative
file, and the completed `PrismaImportResult` (accepted/filtered/rejected evidence) is always preserved on
a publication failure. An existing cumulative file that is empty, malformed, wrongly delimited,
undecodable as UTF-8, or missing the exact 12-column header is a typed failure that leaves the existing
file completely unchanged — publication does not attempt to repair or reinterpret it. The user-visible
success artifact is the one cumulative file itself, growing across runs; no versioning, timestamped
snapshots, or per-run copies are created. No literal cumulative filename was dictated by the customer
decision itself (it approves the merge/dedup/atomic-publish *behavior*, not a specific name); the
implementation uses a fixed `Prisma_Output_Published.csv` name per publication directory, documented here
as an explicit assumption consistent with `prisma_output.build_output_filename`'s own precedent for an
undecided naming detail.

**Objective:** Publish a successfully transformed 12-column result atomically using the approved publication contract.

**Included scope:**

- atomic write/replace behavior (stage in the same directory, flush, `fsync` where supported, then
  `os.replace()`) appropriate to the approved destination;
- exact full-row deduplication and deterministic append ordering, both between the existing published
  rows and the current completed import, and within the current completed import itself;
- truthful typed success/failure outcomes and recoverable retry that never lose the completed
  `PrismaImportResult`'s accepted/filtered/rejected evidence;
- reuse of the existing `P.36.15` serializer/contract (`prisma_output.transform_row`,
  `prisma_output.OUTPUT_CSV_COLUMNS`) instead of a competing output format.

**Excluded scope:**

- inventing a narrower business key, fuzzy/substring/inferred matching, or update-in-place semantics;
- publishing partial or failed transformations;
- changing the 12-column contract;
- unrelated export formats or cloud services;
- UI wiring, browser/download behavior, or any change to `prisma_output.py`'s existing `write_prisma_output`
  callers.

**Acceptance criteria and focused tests:**

- publication exactly matches the approved decision-gate contract;
- interrupted or failed publication never exposes a partial final artifact;
- overwrite, collision, duplicate, retry, and recovery behavior is deterministic and tested where applicable;
- UI reports the real final state and artifact without leaking sensitive data;
- focused tests, full regression tests, compilation, and whitespace validation pass;
- documentation records the approved publication contract and exact executed validation results.

**Implemented result.** New, Qt- and browser-independent module `prisma_publication.py`. It performs no
parsing, filtering, normalization, or side-specific Market/Storage resolution of its own: it operates on
an already-completed `processor.PrismaImportResult` (the same object `processor.import_prisma_export()`
already produces and `prisma_output.write_prisma_output()` already threads through unchanged), reusing
`prisma_output.transform_row()`/`OUTPUT_CSV_COLUMNS` for row formatting so there remains exactly one
canonical serialization of the 12-column contract in the codebase. `prisma_output.py` itself is
completely unchanged by this increment — `write_prisma_output()` remains available, unmodified, as an
independent single-run writer for any existing caller, satisfying the backward-compatibility requirement
with a zero-diff guarantee rather than a narrow integration change.

`publish_cumulative_output(import_result, publication_directory)` is the single entry point. It validates
the destination directory first (existing, readable, writable — reusing
`download_directory.validate_download_directory` plus the same writability check
`prisma_output.py` already applies, never touching the filesystem for an invalid destination), then reads
the existing cumulative file at `<publication_directory>/Prisma_Output_Published.csv` if present: a
missing file means "create from the current import"; a symbolic link at that path (never followed, read,
or replaced), an unreadable, empty, undecodable, wrongly delimited, malformed-quoted, wrong-header, or
wrong-field-count file, a file containing a blank data row, or one repeating the exact header among its
data rows each returns a typed `INVALID_EXISTING_FILE` failure with the file left completely unchanged (no
repair or reinterpretation is attempted). A field's own correctly quoted value may legitimately contain an
embedded newline; parsing reads the decoded text through `io.StringIO(text, newline="")` with
`csv.reader(..., strict=True)` (never `text.splitlines()`, which would incorrectly split such a field into
two records) so the exact value round-trips and malformed quoting is rejected rather than silently
tolerated. Each accepted row in `import_result.rows`
is formatted via `transform_row()` into its exact 12-field tuple; a row already present among the existing
rows, or already emitted earlier in the same import, is dropped (deduplication is exact full-row equality
only — no Auction ID or other narrower key is consulted, since Auction ID is not one of the 12 output
fields). Existing rows keep their original order; new unique rows are appended in their import order. If a
valid existing file already covers every row in the current import (including the case where the import
has zero accepted rows), the file is left byte-for-byte unchanged rather than rewritten. Otherwise the
complete merged row set is staged into a temporary file in the same directory, flushed and `fsync`ed, and
finalized with `os.replace()` — the same stage-then-replace pattern `prisma_output.py`'s own `_write_rows`
already uses — so a failure at any point (staging, write, flush, fsync, or replace) never deletes or
overwrites the previous valid cumulative file, only the failed attempt's own staging artifact is removed,
and the caller always receives the complete already-computed `PrismaImportResult` regardless of outcome.

`PrismaPublicationResult` (immutable, typed `PrismaPublicationOutcome`: `SUCCESS`,
`INVALID_PUBLICATION_DIRECTORY`, `INVALID_EXISTING_FILE`, `WRITE_FAILED`) carries the published file path,
the appended-row and total-row counts, and the full `PrismaImportResult` on every outcome;
`describe_publication_failure()` provides stable, English, path-free messages matching the existing
`describe_output_failure()`/`describe_validation_rejection()` pattern. No UI wiring was added: `app.py` and
`PrismaFunction.spec` are unchanged, since no P.36.16 acceptance criterion in this increment requires a UI
trigger and a later increment is expected to wire a caller's completed `PrismaImportResult` (from either
`processor.import_prisma_export()` directly or `prisma_output.write_prisma_output(...).import_result`)
into this new boundary.

**Review fix (2026-08-04).** A review of the initial implementation found the existing-cumulative-file
validation was weaker than the approved contract required: it parsed the decoded text via
`text.splitlines()` (which would incorrectly split a correctly quoted field's own embedded newline into
two separate records), used the default non-strict `csv.reader` (silently tolerating malformed quoting
instead of rejecting it), silently skipped a blank data row rather than treating it as malformed, did not
reject the exact 12-column header if it reappeared among the data rows, and never checked whether the
target path was a symbolic link before reading through it (risking a read of, or an eventual `os.replace()`
onto, an unintended external target). `_read_existing_rows()` now: rejects a symlink at the target path
before any read is attempted; parses through `io.StringIO(text, newline="")` with `csv.reader(...,
strict=True)`, translating `csv.Error` into the existing `INVALID_EXISTING_FILE` outcome; and explicitly
rejects a blank data row and a data row equal to the exact header tuple, in addition to the existing
wrong-field-count check. Every rejection path still leaves the existing file completely unread-from/
unwritten-to; no write is ever attempted once `_read_existing_rows()` has raised.

**Review fix (2026-08-04, second round).** A further review found `publish_cumulative_output()`'s
`INVALID_PUBLICATION_DIRECTORY` return path (destination directory missing, not a directory, or not
writable) dropped the already-supplied `PrismaImportResult` instead of returning it, unlike every other
outcome (`INVALID_EXISTING_FILE`, `WRITE_FAILED`, `SUCCESS`), contradicting the documented contract that
this evidence is retained on every outcome. The `except DownloadDirectoryError` branch now passes
`import_result=import_result` unchanged, with no change to the outcome, message, directory-validation
order, or filesystem behavior (directory validation still happens before any read/write is attempted).

**Automated evidence (2026-08-04, `feature/p36-16-cumulative-output`, not yet merged).** New
`tests/test_prisma_publication.py` (28 tests, 27 passed and 1 platform-conditional skip) covers: first
publication creating the cumulative file from the current import; appending new unique rows to an existing
valid file; a duplicate against existing rows not being appended; duplicates within one import being
written once; a row differing in exactly one of the 12 fields remaining distinct; existing-row and
new-row order both being preserved across repeated runs; exactly one header line surviving three repeated
publish runs; an import with zero accepted rows (and one where every row already exists) leaving a
byte-identical, unmodified existing file (verified by both content and mtime); an empty existing file, a
wrong-delimiter existing file, a non-UTF-8 existing file, and a wrong-header existing file each failing
with `INVALID_EXISTING_FILE` and the file provably byte-identical afterward; a correctly quoted field with
an embedded newline round-tripping through publish/read without corruption, including proof that an exact
repeat of that same multiline row is recognized as a duplicate (not falsely re-appended) and that a
distinct-but-similar multiline value is still recognized as distinct; malformed quoting, a repeated header
among data rows, and a blank data row in an existing file each failing with `INVALID_EXISTING_FILE` with
the file provably byte-identical afterward; a target-path symlink pointing outside the publication
directory being rejected with its external target left byte-identical and unreplaced (skipped only when
the test platform/user genuinely cannot create a symlink — confirmed in this sandboxed Windows environment,
which lacks the required privilege); a simulated staging-reservation failure (`tempfile.mkstemp`), a
simulated `os.replace` failure, and a simulated mid-write failure each preserving the prior published
file's exact content and leaving zero staging artifacts — the reservation-failure test now uses a
mixed-outcome (one accepted, one filtered, one rejected) source and asserts `result.import_result` carries
the exact `imported_count`/`filtered_count`/`rejected_count`, the accepted row's data, and the
filtered/rejected issues' reason codes, not only the accepted-row count; a first-publication write failure
leaving zero files in the destination directory (no partial cumulative file ever appears); a target
directory listing after each publish containing only the one cumulative file (never a `.staging` leftover);
a decoy file of the same name in a sibling directory remaining untouched, proving no read or write escapes
the configured publication directory; a nonexistent, a file-shaped, and a non-writable destination
directory each rejected without any filesystem write; a nonexistent destination directory with a
mixed-outcome import proving `result.import_result` is the exact supplied object (identity, not just
equality) with its full accepted/filtered/rejected evidence intact and that no filesystem write occurs; and
stable non-empty messages for every `PrismaPublicationOutcome`. The complete pytest suite passed with
**801 tests passed, 1 skipped** (up from 800 passed/1 skipped; +1 net: one existing test strengthened in
place, one new test added). Project-wide `python -m compileall` (excluding `.venv`, `build`, `.git`,
`__pycache__`, `dist`) exited `0`, with the same pre-existing, unrelated `.pytest_tmp` permission warning
recorded in prior entries. `git diff --check` passed.

**Not run.** `python -m PyInstaller --clean --noconfirm PrismaFunction.spec` and `python
validate_package.py` were not rerun: `prisma_publication.py` is not imported by `app.py` or referenced by
`PrismaFunction.spec`, so PyInstaller's static import discovery would not even bundle it and a rebuild
would reproduce the identical distribution already validated after the P.36.15 merge — this increment
does not affect packaging, matching the exact rationale `P.36.15` recorded for the same situation.
`tests/test_packaging.py` (10 tests) is included in, and passed as part of, the 801-test full-suite run
above. No real Windows or real-PRISMA manual validation was performed or is required by this increment's
own acceptance criteria (it consumes only an already-computed `PrismaImportResult`; no browser, network,
filesystem download, or PRISMA session is touched), but end-to-end manual validation of the eventual
wired-in workflow remains appropriate once a later increment adds the UI trigger. The symlink-rejection
test's platform-conditional skip is also outstanding for real coverage: it should be re-run on a Windows
session with Developer Mode enabled (or elevated privileges) so the symlink path is actually exercised
rather than skipped.

### P.36.8 — Mapping display in the UI

**Status:** 🟡 Implemented, automated-tested, and manually validated on real Windows (2026-08-04) via manual
CSV selection; branched from `main` at merge commit `daf4760` (the P.36.16 merge via PR #63) and merged to
`main` via PR #64 (merge commit `5e3f309`). Real-Windows validation of the managed-download (P.36.14)
trigger path has not been performed.
**Dependency required before implementation:** P.36.15 completed.

**Decision made (2026-08-04, this increment):** nothing in `ROADMAP.md` or `workflow_p.md` wires a
completed P.36.15 import/transformation result into the UI yet — the "Next recommended increment" section
explicitly reserves "wiring a UI trigger for the complete P.36.14→P.36.15→P.36.16 pipeline" for later, so
P.36.8 could not simply reuse an existing trigger. Asked to choose between a new explicit "Preview Mapping"
button versus auto-populating on the two already-existing, already-approved CSV-selection success paths
(manual P.36.4 selection and managed P.36.14 download), the customer selected the latter: the mapping
display refreshes automatically whenever a PRISMA Export CSV becomes the current accepted selection, with
no new button and no new persistence or publication behavior.

**Objective:** Display the resolved mapping evidence for the current PRISMA Export CSV selection in the UI,
without changing the authoritative 12-column output CSV contract.

**Included scope:**

- a Qt-independent presentation boundary that selects and orders already-resolved evidence from one
  already-completed `processor.PrismaImportResult` into exactly the five approved fields;
- a Qt table view/model that renders those five fields in that exact order and never adds, removes,
  renames, or reorders them;
- refreshing the display from the two existing CSV-selection success paths (P.36.4 manual selection,
  P.36.14 managed download), with deterministic empty/failure/replacement behavior and no stale rows;
- reuse of the exact-side-specific, evidence-only resolution `processor.import_prisma_export` (P.33/P.36.4,
  unchanged, the same boundary `prisma_output.write_prisma_output` already uses for P.36.15) already
  implements — no new matching, inference, or cross-side logic.

**Excluded scope:**

- any change to the 12-column output CSV contract, `prisma_output.py`, or `prisma_publication.py`;
- a new `Exit Storage`/`Entry Storage` field;
- writing an output file, publishing, or any browser/network/download operation triggered by the display
  itself;
- reconnecting the superseded live-monitoring dashboard/scheduler workflow;
- P.36.10 cleanup, packaging finalization, or installer work.

**Implemented result.** New, Qt- and browser-independent module `mapping_presentation.py` exposes
`MAPPING_DISPLAY_FIELDS` (`"Exit Market"`, `"Entry Market"`, `"Network Point Name"`, `"TSO Name Exit"`,
`"TSO Name Entry"`, exact order and spelling), an immutable `MappingDisplayRow`, and
`build_mapping_rows(import_result)`, which selects `exit_market`/`entry_market`/`network_point`/
`tso_exit`/`tso_entry` straight through from each row in `import_result.rows` (the already-accepted,
already-enriched rows `processor.import_prisma_export` produces — filtered and rejected rows never reach
`rows` and so never reach the presentation) with no matching, inference, or cross-side substitution of its
own; a filtered/rejected-only import (or any import with zero accepted rows) yields an empty tuple, never
an error. `ui_components.py` adds `MappingTableModel(QAbstractTableModel)`, matching the existing
`AuctionTableModel` pattern: five fixed columns (`MAPPING_DISPLAY_FIELDS`), and `set_rows()` performs a
`beginResetModel()`/`endResetModel()` wholesale replace so a new selection can never leave a stale row from
a previous one.

`app.py` adds a new "Mapping" content panel (`self.mapping_table_model`, `self.mapping_table`, and
`self.mapping_empty_label`, shown/hidden deterministically by `_update_mapping_empty_state()`) alongside the
existing auction and activity panels; it changes no existing widget, label, or control. `_refresh_mapping_display(path)`
is the shared refresh boundary: it calls `processor.import_prisma_export(path)` — a read-only re-run of the
same P.36.15 import/enrichment boundary, writing no output file and touching no browser, network, or
publication behavior — and on success replaces the table's rows via `build_mapping_rows()`; on a typed
`PrismaImportError`/`CsvFormatError`/`OSError` it clears the table (`set_rows(())`) and shows a stable,
path-free English error ("The mapping evidence for the selected PRISMA Export CSV could not be displayed.")
via the existing `_show_error()` helper, rather than leaving stale rows from the previous selection.
`_select_manual_csv()` (P.36.4) and `_handle_download_event()` (P.36.14) each call
`_refresh_mapping_display(result.path)` exactly once, only after their own existing CSV-contract acceptance
check already succeeded; a rejected candidate at that existing boundary still short-circuits before ever
reaching the mapping refresh, exactly as before this increment. No other call site, workflow trigger,
persistence contract, or publication behavior was added.

**Automated evidence (2026-08-04, `feature/p36-8-mapping-display`, not yet merged).** New
`tests/test_mapping_presentation.py` (11 tests) covers: the exact `MAPPING_DISPLAY_FIELDS` order/spelling;
pure field mapping and row-order preservation from a directly constructed `PrismaImportResult`; an empty
accepted result and a filtered/rejected-only result both yielding an empty tuple; a regression proving an
entry-only row's exit-side fields stay exactly empty rather than being inferred from the entry side; and,
through the real `processor.import_prisma_export` boundary with the authoritative default reference
catalog, an exit-only row resolving a Market, an entry-only row resolving a Storage name, a bundle row
using the real evidenced dual-sided alias `"Arnoldstein Exit"` (which resolves to `CEGH` on the exit side
and `PSV` on the entry side) proving side-specific resolution is never swapped or cross-contaminated even
when the exact same source string appears on both sides, multi-row order preservation, and a
filtered+rejected-only source producing an empty presentation with zero exceptions raised.
`tests/test_app.py` gained 9 tests: exact mapping-table header order/labels; the initial empty/hidden
state; a header-only (zero-data-row) CSV selection leaving the display empty; a two-row CSV populating the
table with the exact expected Exit/Entry Market, Network Point Name, and TSO Name Exit/Entry values in
exact source order; a filtered+rejected-only CSV leaving the display empty; selecting a second, different
CSV fully replacing the first selection's rows (proving no stale-row retention); a simulated
`processor.import_prisma_export` failure clearing the table and showing the fixed, path-free error message
(proving no internal exception detail or file path leaks into the UI); the managed-download success path
(P.36.14) also populating the table; and a regression proving the refresh path never calls
`prisma_output.write_prisma_output` or `prisma_publication.publish_cumulative_output` and never adds a
mock call to the browser or PRISMA-lifecycle controllers, so rendering/refreshing the mapping view alone
triggers no output-writing, publication, browser, download, or monitoring operation. One pre-existing test,
`test_light_workspace_widgets_use_explicit_contrast_styles`, was updated in place to include the new
"Mapping" section label among the panel's expected section headings — an in-scope adjustment to an existing
assertion the new panel legitimately changes, not unrelated churn.

**Test-infrastructure fix required to keep the suite reliable (2026-08-04, this increment).** Adding the new
per-window `MappingTableModel`/`QTableView` (one additional Python-subclassed `QAbstractTableModel` per
`PrismaMonitorApp` instance, on top of the existing `AuctionTableModel`) made a pre-existing, previously
latent shutdown-time defect in `tests/test_app.py`'s `window` fixture reproduce reliably: `PrismaMonitorApp`
instances hold self-referencing `QTimer`-to-bound-method cycles (e.g. `self._browser_timer` connected to
`self._poll_browser_launch`), which plain reference counting never reclaims — only Python's cyclic garbage
collector does, and it was never invoked between tests. Across the ~90 `PrismaMonitorApp` instances the full
`test_app.py` suite creates and closes, this let unreachable-but-uncollected Qt object graphs accumulate and
eventually get torn down in one large, unordered batch at interpreter shutdown, which crashed the test
process with a Windows heap-corruption exit code (`STATUS_HEAP_CORRUPTION`, confirmed non-deterministically
reproducible before this fix and confirmed absent from the unmodified `main` baseline across multiple
repeated runs). The `window` fixture now explicitly drops its `widget`/`browser` references and calls
`gc.collect()` immediately after `_close_app(widget)`, so each window's cyclic garbage is reclaimed
promptly and individually instead of piling up for a single risky batch at process exit; this fully
eliminated the crash across repeated runs (4/4 clean runs of `tests/test_app.py` alone, and 4/4 clean runs
of the complete suite, both before and after this fix was isolated as the cause via a controlled
git-stash bisection against the unmodified `main` baseline). This is a test-infrastructure-only change
(`tests/test_app.py`'s fixture teardown); no production code changed as a result.

The complete pytest suite passed with **821 tests passed, 1 skipped** (up from 801 passed/1 skipped; +20,
the exact sum of the 11 new `test_mapping_presentation.py` tests and the 9 new `test_app.py` tests).
Project-wide `python -m compileall` (excluding `.venv`, `build`, `.git`, `__pycache__`, `dist`) exited `0`,
with the same pre-existing, unrelated `.pytest_tmp` permission warning recorded in prior entries. `git diff
--check` passed.

**Packaging evidence (2026-08-04).** Unlike `P.36.15`/`P.36.16`, this increment changes `app.py` itself
(the file `PrismaFunction.spec`'s `Analysis(["app.py"], ...)` statically analyzes), adding imports of the
new `mapping_presentation.py` module and `processor.import_prisma_export`/`PrismaImportError` and
`csv_contracts.CsvFormatError`, plus new widgets — so a packaging rebuild was required and performed, not
skipped. `python -m PyInstaller --clean --noconfirm PrismaFunction.spec` succeeded and produced a fresh
`dist/PrismaFunction/PrismaFunction.exe`; no `.spec` change was needed, since PyInstaller's static import
discovery picked up `mapping_presentation.py` automatically through `app.py`'s and `ui_components.py`'s own
imports (the same pattern prior P.36 increments recorded for their own new modules). `python
validate_package.py` then passed against that fresh distribution. No packaged-executable launch, real
browser, or real-PRISMA validation was performed beyond this static packaging check.

**Review fix (2026-08-04): a rejected CSV replacement left stale mapping rows visible.** Review found that
`_refresh_mapping_display()` only cleared the table on its own internal `import_prisma_export()` failure,
but both `_select_manual_csv()` and `_handle_download_event()` return immediately — without ever calling
`_refresh_mapping_display()` — when the existing `ManualCsvSelection`/P.36.4 CSV-contract check rejects the
new candidate (`result.accepted` is `False`). A user who successfully selected/downloaded a CSV (populating
the Mapping table), then selected or downloaded a second CSV that failed that existing contract check,
still saw the *first* CSV's mapping rows: a rejected replacement left stale evidence on screen, violating
the requirement that a failed replacement operation must never retain stale mapping rows. A new shared
helper, `_clear_mapping_display()` (wrapping the existing `set_rows(())`/`_update_mapping_empty_state()`
pair `_refresh_mapping_display()`'s own failure branch already used), is now also called from both
`_select_manual_csv()`'s and `_handle_download_event()`'s existing `if not result.accepted:` rejection
branches, immediately before their existing `_show_error()` call — every other line in both branches
(rejection message, `status` text, `_add_activity()` call, and the preserved `_manual_csv_selection.current`/
`manual_csv_label` state) is unchanged. Cancelling the manual file-selection dialog (`if not selected:
return`, before `ManualCsvSelection.select()` is ever called) is unaffected: no replacement operation
occurred, so the mapping table is correctly left untouched. `_handle_download_event()`'s separate
`event.success is False` branch (the managed download itself failed before any candidate CSV existed) is
also unaffected, since no CSV replacement was ever attempted there either — this fix is scoped exactly to
the existing CSV-contract rejection branches described in the finding.

New regression tests in `tests/test_app.py`: one that populates the mapping table via a valid manual CSV
selection, then selects a second CSV rejected by the manual contract check (wrong header), asserting the
table is now empty and the empty-state label is shown; a matching test using two `_handle_download_event()`
calls (first accepted and populated, second rejected by the same contract check), asserting the same
empty-and-hidden result; and the existing `test_cancelling_manual_csv_dialog_is_a_no_op` test is preserved
unmodified (it already proves cancellation is a no-op for the selection/label/error-dialog state; no
existing assertion needed to change since cancellation never reaches the mapping refresh path either
before or after this fix).

The complete pytest suite passed with **823 tests passed, 1 skipped** (up from 821 passed/1 skipped; +2, the
two new regression tests). Project-wide `python -m compileall` (excluding `.venv`, `build`, `.git`,
`__pycache__`, `dist`) exited `0`, with the same pre-existing, unrelated `.pytest_tmp` permission warning
recorded in prior entries. `git diff --check` passed. Since this fix changes `app.py` itself,
`python -m PyInstaller --clean --noconfirm PrismaFunction.spec` was rerun (succeeded, fresh
`dist/PrismaFunction/PrismaFunction.exe`) and `python validate_package.py` passed against it, matching this
increment's own established packaging-rebuild rationale above.

**Regression-coverage strengthening (2026-08-04): cancellation after a populated selection.** The existing
`test_cancelling_manual_csv_dialog_is_a_no_op` test only proved cancellation was a no-op starting from the
empty, nothing-selected state; it did not prove cancellation leaves an already-populated Mapping table
untouched. A new test, `test_cancelling_manual_csv_dialog_after_a_valid_selection_preserves_mapping_rows`,
selects a valid CSV first (populating the Mapping table with one row), then cancels the next manual
file-selection dialog, and asserts the previous selection/label/mapping-row-count/table-visibility all
remain exactly unchanged and `QMessageBox.critical` is never called — proving `_select_manual_csv()`'s
existing `if not selected: return` early-exit (before `ManualCsvSelection.select()` or
`_refresh_mapping_display()`/`_clear_mapping_display()` are ever reached) genuinely leaves a populated
Mapping table alone. The pre-existing empty-state test was left completely unmodified, so both starting
conditions now have dedicated coverage. No production code changed: this is a pure test-coverage addition,
confirming the existing cancellation code path already behaved correctly. The complete pytest suite passed
with **824 tests passed, 1 skipped** (up from 823 passed/1 skipped; +1, this new test). Project-wide
`python -m compileall` and `git diff --check` both passed. No packaging rebuild was required or performed:
this change is confined to `tests/test_app.py`, and no production module or `app.py` import changed.

**Real-Windows manual validation (2026-08-04, reported by the customer).** Prisma Function was run from
source (`python app.py`) on a real Windows desktop, not as the packaged executable: the packaged
`PrismaFunction.exe` was blocked by Windows Application Control on that machine, so this validation pass
exercised the same application code from source instead. The Mapping panel was exercised through the manual
CSV-selection (P.36.4) trigger path: the panel rendered the five columns — `Exit Market`, `Entry Market`,
`Network Point Name`, `TSO Name Exit`, `TSO Name Entry` — in this exact required order; selecting a valid
PRISMA Export CSV rendered its mapping rows successfully; replacement behavior was checked (selecting a
further CSV correctly refreshes the table); and selecting an invalid CSV showed the existing rejection
message and correctly cleared all previously displayed Mapping rows (confirming this section's "Review fix"
above on a real Windows session, not only in the automated suite). No issues were observed. This validation
exercised only the manual-selection (P.36.4) trigger path; the managed-download (P.36.14) trigger path
(`_handle_download_event`) was not exercised on real Windows and its real-Windows validation remains
outstanding. Validating the packaged executable itself (rather than a from-source run) also remains
outstanding, blocked by the Windows Application Control restriction noted above.

**Outstanding before this increment can be marked ✅ Completed:** real-Windows manual validation of the
managed-download (P.36.14) trigger path populating/refreshing/clearing the Mapping panel identically to
the now-validated manual-selection path; and validating the packaged `PrismaFunction.exe`
itself once the Windows Application Control restriction noted above is resolved or an approved machine is
available. Moving/deleting the selected file before a refresh was explicitly not tested and is not tracked
as outstanding: there is no user-accessible refresh action in the current UI (the Mapping display only
refreshes as a side effect of a new CSV selection/download succeeding), so this scenario is not
deterministically reproducible through the UI and was skipped rather than treated as a pending validation
item.

#### P.36.10. Remove superseded monitoring and obsolete dependencies — Implemented (2026-08-04)

**Objective:** Physically remove the superseded live-monitoring product flow (dashboard, scheduler,
"Load Monitoring CSV", "Open Browser"/"Stop Browser", "Start Monitoring"/"Stop Monitoring") and the
code/dependencies that became unreachable once the P.36 date-range → managed-download → transform →
publish workflow was completed, per the removal explicitly reserved for this increment by P.36.2 and
listed as `⬜ Planned` in the table below. This is code removal and documentation only; it does not
touch the 12-column output contract, transformations, mappings, threshold, date rules, download
mechanism, filename rules, collision behavior, publication semantics, or directory contract, and it
does not redesign the surviving P.36 UI beyond removing the now-dead panel/controls that described the
removed feature.

**Evidence-based reachability inventory (performed before any deletion).** Every candidate module was
grep-traced from `app.py` and from `prisma_lifecycle.py`/`prisma_download.py` (the P.36 runtime entry
points) to confirm whether it was still reachable:

- `monitoring.py` (`MonitoringEngine`, `MonitoringResult`), `monitoring_storage.py` (`MonitoringStorage`,
  `MonitoringStorageError`), `scheduler.py` (`MonitoringScheduler`), `notifications.py`
  (`StatusChangeNotification`), and `auction_csv.py` (`AuctionCsvRecord`, `load_auction_csv`,
  `CsvValidationError`, the Monitoring CSV loader) were reachable only from the legacy "Load Monitoring
  CSV" / "Start Monitoring" flow in `app.py` and from each other's tests — never from
  `prisma_lifecycle.py`, `prisma_download.py`, `prisma_import_workflow.py`, `processor.py`,
  `prisma_output.py`, or `prisma_publication.py`. Deleted outright, with their dedicated test modules
  (`tests/test_monitoring.py`, `tests/test_monitoring_storage.py`, `tests/test_scheduler.py`,
  `tests/test_notifications.py`, `tests/test_auction_csv.py`).
- `browser.py`'s `BrowserController`, `PrismaAuctionFilter` (the live-page "Marketed Capacity >= 1000"
  browser filter), `BrowserState`, `LaunchResult`, `_PageRequest`, and `_LaunchCancelled` were reachable
  only from the legacy "Open Browser"/"Stop Browser" flow and `MonitoringEngine`; the P.36 booked-capacity
  threshold is enforced in CSV processing (`processor.py`), not via a live browser-page filter, confirmed
  by `prisma_download.py`'s own comment distinguishing its independent date-filter control from
  `PrismaAuctionFilter`. Removed. `PRISMA_AUCTIONS_URL`, `DefaultBrowserDetector`, and
  `_ensure_subprocess_output_streams` remain — `prisma_lifecycle.py` imports all three directly and they
  have no monitoring-specific behavior.
- `prisma_page.py`'s `PrismaPageReader`, `LivePrismaStatusAdapter`, `PrismaAuctionRow`,
  `REQUIRED_TABLE_HEADERS`, `_STATUS_BY_KEY`, `normalize_page_text`, `normalize_prisma_status`,
  `resolve_required_columns`, `parse_auction_rows`, `match_auction_row`, and the exception types
  `PrismaPageStructureError`, `PrismaStatusParseError`, `PrismaAuctionMatchError`,
  `PrismaLookupTimeoutError`, `PrismaAuctionNotFoundError`, and `PrismaAuctionAmbiguousError` were
  reachable only from `BrowserController`/`MonitoringEngine`/their tests. Removed. `prisma_download.py`
  (P.36.14) imports only `PrismaAuthenticationRequiredError`, `PrismaInvalidSessionError`, and
  `PrismaSessionValidator` from this module — all three, plus the base `PrismaPageAdapterError` and
  `PrismaSessionState`, are kept unchanged; this reusable session-validation boundary was not touched
  merely because it originated in an older increment.
- `ui_components.py`'s `AuctionRow`, `AuctionTableModel`, `AuctionFilterModel`, `StatusDelegate`,
  `SummaryCard`, and `ArrowComboBox` backed only the legacy auction dashboard (search/filter, the
  auction table, and the summary cards) and the "Filter by status" combo box; none are used by
  `MappingTableModel` (P.36.8) or any other surviving widget. Removed, along with the CSS selectors
  tied one-to-one to their removed object names (`dashboardSubtitle`, `metric`, `metricLabel`,
  `monitorBadge`). `browserBadge` styling is kept because `prisma_badge` reuses that object name.
  `MappingTableModel` and `APP_STYLE` are otherwise unchanged.
- `csv_contracts.py` was left completely unmodified: `MONITORING_CSV_COLUMNS` and `CsvFormat.MONITORING`
  remain, because `manual_csv_selection.py`, `prisma_import_workflow.py`, and the managed-download path
  all still call `detect_csv_format`/`require_csv_format`, and a Monitoring-shaped CSV selected where a
  PRISMA Export CSV is expected must still be identified and named in the rejection message rather than
  reported as a generic "unsupported format" — this is active, reusable CSV-classification
  infrastructure, not part of the removed product flow.

**`app.py` changes.** Removed: the `BrowserController` instance and the entire legacy "Open
Browser"/"Stop Browser"/"Load Monitoring CSV"/"Start Monitoring"/"Stop Monitoring" sidebar controls
(previously hidden by P.36.2, now deleted, not just hidden); the "Monitoring dashboard" content panel
(title, subtitle, summary cards, auction table with search/filter, `browser_badge`, `monitor_badge`);
`select_csv`, `_display_csv_records`, `_update_summary`, `open_prisma`, `_poll_browser_launch`,
`_browser_start_failed`, `create_monitoring_engine`, `create_monitoring_scheduler`, `start_monitoring`,
`stop_monitoring`, `_monitoring_worker`, `_monitoring_results`, `_monitoring_failure_message`,
`_monitoring_finished`, `_set_monitoring_idle`, and `stop_work`; the `monitoring_results`/
`monitoring_finished` Qt signals; and the corresponding `_monitoring_thread`/`_monitoring_stop_event`/
`_browser_ready`/`_active_browser_launch`/`_auction_records` state and their handling in
`_update_controls()` and `closeEvent()`. The stale sidebar subtitle ("PRISMA auction monitoring") and
content-area header ("Monitoring dashboard" / "Track PRISMA auction states from your validated CSV
data.") — both describing the panel just removed — were updated to describe the surviving P.36 scope
("PRISMA Export processing" / "Select a date range, obtain a PRISMA Export CSV, and publish the
transformed output.") as a direct, necessary consequence of the removal; no panel was added, and no
surviving control was moved, renamed, or restyled. Preserved unchanged: the "PRISMA" (Open/Close Prisma),
"DOWNLOAD FOLDER", "PRISMA EXPORT CSV", and "DATE RANGE" sidebar groups; the "Import PRISMA Export"/"Open
Result" controls and `start_processing`/`_process_worker`/`_processing_finished`/`_finish_processing`/
`_processing_succeeded`/`_processing_failed` (a separate, still-active P.1–P.9 feature, not part of the
removed monitoring flow); the Mapping panel and its refresh boundary; the Activity panel; the Prisma
lifecycle open/close/download-event handling; and the shutdown sequencing for the owned PRISMA browser
session and any in-flight processing thread.

**`prisma_import_workflow.py` change.** The `CsvFormat.MONITORING` rejection message referenced the
now-deleted "Load Monitoring CSV" button ("Use Load Monitoring CSV for live monitoring."); the sentence
was removed so the message no longer promises a UI path that no longer exists, while the CSV-contract
rejection itself (`"Monitoring CSV cannot be imported as detailed PRISMA results."`) is unchanged.

**Documentation.** `CLAUDE.md`'s "Project identity" paragraph and "Separate CSV contracts" section were
updated to state the monitoring product-flow code is removed (not merely superseded-but-present) and
that the Monitoring CSV contract now exists only for format detection/rejection, not loading.
`BUILDING.md`'s `compileall` reproduction command was updated to drop the five deleted module names, so
it no longer fails with a missing-file error. `INSTALLER.md`'s manual-validation step 6 was reworded from
"exercise browser opening, CSV import, monitoring start and stop" to the actual current controls (Open
Prisma/Close Prisma, CSV selection or download, PRISMA Export import). `RELEASE_CHECKLIST.md` (a frozen
v1.0.0 release-specific checklist already referencing the pre-P.36 "PRISMA Monitor v1.0.0" title) and
`workflow_p.md`'s historical dated entries were left unchanged, preserving completed-increment history
per the task's explicit instruction not to rewrite it.

**Automated evidence (2026-08-04).** `tests/test_auction_csv.py`, `tests/test_monitoring.py`,
`tests/test_monitoring_storage.py`, `tests/test_notifications.py`, and `tests/test_scheduler.py` were
deleted with their production modules. `tests/test_browser.py` was reduced from covering
`BrowserController`/`PrismaAuctionFilter` to its two still-relevant `DefaultBrowserDetector` tests.
`tests/test_prisma_page.py` was reduced to its `PrismaSessionValidator` coverage (session/authentication
classification, safe-location redaction), dropping the page-reading/parsing/`LivePrismaStatusAdapter`
tests. `tests/test_prisma_import_workflow.py` was updated for the trimmed rejection message.
`tests/test_app.py` had roughly thirty legacy monitoring/browser-dashboard tests removed
(`test_p36_2_legacy_monitoring_controls_are_hidden_not_deleted`, CSV-load/summary/status-filter tests,
`open_prisma`/`_poll_browser_launch`/browser-result tests, and the full `start_monitoring`/
`_monitoring_worker`/`_monitoring_results`/`_monitoring_finished` group) and the remaining shared
fixtures/tests that referenced the removed `BrowserController` mock or `_monitoring_thread` state were
updated in place (`_build_app`/`window` fixture no longer patches `BrowserController`; the mapping-refresh
"no browser touched" test, the date-range "no browser/lifecycle/file operation" test, the Prisma-lifecycle
shutdown test, and the close-defers-while-workers-are-alive test now assert only against
`prisma_lifecycle` and the processing-thread state that still exists) — this is the P.36 application
composition still exposing its required controls and behavior, proving the removal didn't regress the
supported product flow. The complete pytest suite passed with **637 tests passed, 1 skipped** (down from
821 passed/1 skipped after the P.36.8 merge, consistent with removing five modules' worth of dedicated
tests plus ~150 legacy `test_app.py` tests while keeping all P.36 coverage). Project-wide
`python -m compileall` (excluding `.venv`, `build`, `.git`, `__pycache__`, `dist`, with the same
pre-existing, unrelated `.pytest_tmp` permission warning recorded in every prior entry in this file)
exited `0`. `git diff --check` passed on the actual working-tree changes (a set of pre-existing untracked
`*-final-review.diff` scratch files from earlier increments were left untouched, not part of this
increment's scope).

**Packaging validation.** `python -m PyInstaller --clean --noconfirm PrismaFunction.spec` completed
successfully (no `requirements.txt` or `PrismaFunction.spec` changes were needed: no dependency was
removed by this increment — `pandas`, `openpyxl`, `playwright`, and `PySide6` are all still used by the
surviving P.1–P.9/P.36 code paths — so the packaging inputs were unchanged; the rebuild instead confirms
PyInstaller's dependency graph still resolves cleanly after the module deletions). `python
validate_package.py` passed against the freshly built `dist\PrismaFunction\` directory.

**Merged.** This increment is merged to `main` via PR #65 (merge commit `d6dd456`). No real-Windows manual
validation was required specifically for this increment, since it removes unreachable code and adjusts
documentation without changing any preserved P.36 behavior, contract, or boundary; the existing outstanding
real-Windows validation items for P.36.8/P.36.14/P.36.15/P.36.16 recorded elsewhere in this document are
unaffected and remain separately tracked.

### P.36.11 — Windows packaging and installer validation

**Status:** 🟡 Substantially complete (2026-08-05). Every required automated and real-Windows
package/installer acceptance item in this section's scope passed, with one recorded, user-approved
deviation on the "unsigned installer build" item (see below) that keeps this increment from a clean ✅.
**Dependencies:** P.36.8, P.36.10, P.36.15, and P.36.16, all merged to `main` (confirmed via `git log main`:
`5e3f309`, `d6dd456`, `c84344f`, `daf4760`).

**Objective.** Validate, and only where a concrete defect was demonstrated minimally update, the Windows
PyInstaller onedir package and Inno Setup installer for the final post-P.36.10 dependency set. This
increment made no change to the P.36 workflow, the 12-column output contract, date-range selection,
managed-download acquisition, manual-CSV fallback, mapping rules, the Documents/user-selected-directory
publication contract, or `%LOCALAPPDATA%\PrismaFunction` runtime-data ownership.

**Defects found and fixed (packaging/documentation only; no production application-behavior code changed):**

1. `.github/workflows/windows-ci.yml`'s "Compile Python sources" step listed `auction_csv.py`,
   `monitoring.py`, and `scheduler.py` — all three deleted by P.36.10 — so CI's `compileall` step was
   broken against the current tree (it would fail or silently skip nonexistent paths). Fixed to the exact
   current 22-module root-level inventory plus `tests` (same module list as below).
2. `BUILDING.md`'s "Reproduce Windows CI locally" `compileall` command was missing eight modules added by
   P.36.8/P.36.13–P.36.16 (`date_range_selection.py`, `download_directory.py`, `manual_csv_selection.py`,
   `mapping_presentation.py`, `prisma_download.py`, `prisma_lifecycle.py`, `prisma_output.py`,
   `prisma_publication.py`). Updated to the full current module list.
3. `RELEASE_CHECKLIST.md`'s "Windows package validation" section still described the removed
   live-monitoring flow ("Start live PRISMA monitoring", "Stop Monitoring", "Stop Browser"). Rewritten to
   the current P.36 workflow (date-range selection, Open/Close Prisma managed download, P.36.4 manual
   fallback, 12-column publication).
4. `CLAUDE.md`, `ROADMAP.md` (this file), and `workflow_p.md` all contained multiple statements that
   P.36.10 was "not yet merged" / "on its feature branch" — stale since PR #65 (merge commit `d6dd456`)
   merged it to `main`. `CLAUDE.md` also had a stale "P.36.8 ... not yet merged" statement (P.36.8 merged
   via PR #64, `5e3f309`). All located instances were corrected in this increment (see each file's own
   history for the exact lines).
5. `INSTALLER.md`'s "Signing readiness" section stated "Unsigned local validation builds may omit
   `INNO_SIGNTOOL_NAME`" — demonstrated inaccurate by this increment's own installer build, since
   `SignedUninstaller=yes` is unconditional and Inno Setup's non-interactive CLI compiler hard-aborts
   without a configured `SignTool`, even for an unsigned local validation build. Corrected to state a
   `SignTool` must always be configured for a non-interactive build to complete (a local validation build
   without a real certificate may use an ephemeral, non-committed self-signed test certificate for that
   purpose). `PrismaFunction.iss` and its signing-ready configuration were not changed.

No change was made to `PrismaFunction.spec`, `PrismaFunction.iss`, `PrismaFunction.version`, `version.py`,
`build.bat`, `build-installer.bat`, `release.bat`/`release.ps1`, `validate_package.py`, or `requirements.txt`
— static inspection and every automated/real-Windows check below found these files correct as checked in.

**Automated evidence (2026-08-05).** Full pytest suite: **637 passed, 1 skipped** (down from the 725+ count
recorded at P.36.14 because P.36.10 deleted the monitoring/scheduler/notifications/auction_csv test
modules along with their production code). Project-wide `python -m compileall` against the corrected
22-module list (`app.py browser.py csv_contracts.py date_range_selection.py download_directory.py
manual_csv_selection.py mapping_presentation.py prisma_download.py prisma_import_workflow.py
prisma_lifecycle.py prisma_output.py prisma_page.py prisma_publication.py prisma_references.py
prisma_source_updates.py processor.py runtime_logging.py runtime_paths.py storage.py ui_components.py
validate_package.py version.py tests`) exited `0`. `git diff --check` passed. All three commands were rerun
a second time after every documentation/CI change in this increment, with identical results.

**Fresh PyInstaller build and validate_package.py (2026-08-05).** The checked-out `dist\PrismaFunction`
predated the P.36.10 removal by ~43 minutes (built 2026-08-04 20:13, before the P.36.10 removal commit
`a27acaa` at 20:51). `build.bat` (`python -m PyInstaller --clean --noconfirm PrismaFunction.spec`) was rerun
from the current branch and succeeded (exit `0`); the only PyInstaller warning was a pre-existing, unrelated
"Hidden import 'jinja2' not found" from Playwright's optional tracing-viewer hook, present before this
increment. `python validate_package.py` passed against the fresh distribution. Independent inspection (not
just `validate_package.py`) confirmed: no file or directory name matching `monitoring`, `scheduler`,
`notifications`, `auction_csv`, or `BrowserController` anywhere under `dist\PrismaFunction`; no `.py`,
`.pyc`, `.log`, `.csv`, or `.db` file and no `__pycache__`/`.pytest_cache`/`tests` directory (the two
matches for "tests" in a recursive filename search were third-party bundled files —
`numpy\_core\_multiarray_tests.cp314-win_amd64.pyd` and Playwright's
`driver\package\lib\cli\programWithTestStub.js` — not this project's test suite).

**Executable identity (2026-08-05).** `PrismaFunction.exe`: `FileVersion=1.0.0`, `ProductVersion=1.0.0`,
`ProductName=PRISMA Monitor`, `OriginalFilename=PrismaFunction.exe`, `FileDescription=PRISMA Monitor`,
`CompanyName=PrismaFunction` — matches `version.py`/`PrismaFunction.version` and `BUILDING.md`'s documented
verification exactly.

**Isolated-startup smoke checks (2026-08-05).** Three separate launches of the fresh
`dist\PrismaFunction\PrismaFunction.exe`, all from `%TEMP%` (outside the repository) with an isolated,
freshly created `LOCALAPPDATA`: (1) a normal isolated-`LOCALAPPDATA` launch reached `MainWindowHandle`
non-zero, title `PRISMA Monitor v1.0.0`, and closed cleanly via `CloseMainWindow()` (exit code `0`); (2) a
repeat with `VIRTUAL_ENV`/`PYTHONPATH`/`PYTHONHOME` stripped and `PATH` reset to the machine/user default
(no `.venv` on `PATH`) reached the same live window and exit code `0`, proving startup does not depend on
the active virtual environment; (3) the `dist\PrismaFunction\PrismaFunction.exe` SHA-256 hash was identical
before and after run (1), proving the distribution directory is unchanged by startup/shutdown. In both
runs, the only filesystem write under the isolated `LOCALAPPDATA` was
`PrismaFunction\logs\prisma-function.log` — no writes reached the repository, `dist\PrismaFunction` itself,
or any path outside the isolated root. No console window, no `chrome.exe`/`msedge.exe`/`node.exe` process,
and no leftover `PrismaFunction.exe` process after each run.

**Inno Setup installer build from a path containing spaces (2026-08-05).** `PrismaFunction.iss`,
`validate_package.py`, `version.py`, `build-installer.bat`, and the fresh `dist\PrismaFunction` (1,345
items, robocopy-verified identical count to the source) were staged under
`C:\Users\<user>\AppData\Local\Temp\Prisma Function Installer Build\` (a path containing spaces, outside the
repository). Inno Setup 6.7.3 (installed per-user via `winget install JRSoftware.InnoSetup`, landing at
`%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe` rather than the default-checked
`%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe`, so `INNO_SETUP_COMPILER` was set per `build-installer.bat`'s
own documented override) compiled `PrismaFunction.iss` from that space-containing path successfully.
`validate_package.py`, invoked internally by `build-installer.bat` against the staged copy, passed.

**Signing note — the one recorded deviation.** `PrismaFunction.iss` sets `SignedUninstaller=yes`
unconditionally (not gated by `#ifdef SignToolName`). Inno Setup's non-interactive CLI compiler was found
to hard-abort ("please attach your digital signature ... and compile again") whenever no `SignTool` is
configured — there is no code path that produces a literally zero-signature installer from this script via
a single non-interactive CLI invocation; this is a real, structural property of `SignedUninstaller=yes`, not
a defect. This demonstrated that `INSTALLER.md`'s previous "may omit `INNO_SIGNTOOL_NAME`" wording was
inaccurate — a non-interactive build cannot actually omit a configured `SignTool` — and that documentation
defect was fixed in this same increment (see "Defects found and fixed" item 5 above); `INSTALLER.md` now
states a `SignTool` must always be configured for a non-interactive build to complete. No
`signtool.exe`/Windows SDK was present on the validation machine, and installing one
was judged out of this increment's scope (`build-installer.bat`/signing-setup changes are explicitly
excluded). With the user's explicit approval, an ephemeral, non-committed, self-signed test certificate
(`CN=PrismaFunction Local Test`, 1-day validity, `Cert:\CurrentUser\My`) was generated locally and used only
as an ad hoc Inno Setup `/S<name>=<command>` sign tool (`Set-AuthenticodeSignature`, no `signtool.exe`
needed) to let the CLI compiler complete. The resulting installer's uninstaller stub carries this test
signature (`Get-AuthenticodeSignature` confirmed `SignerCertificate` = the test cert, `Status=UnknownError`
/ "terminated in a root certificate which is not trusted" — expected and correct for a throwaway,
non-trusted test certificate, not a real release signature). The certificate was deleted from the local
store and all staged build files were removed after validation; nothing was committed to the repository,
and `PrismaFunction.iss`'s checked-in signing-ready configuration (`SignedUninstaller=yes`, the
`#ifdef SignToolName` / `INNO_SIGNTOOL_NAME` mechanism) is unchanged. This satisfies the increment's intent
("without weakening the existing signing-ready configuration") but not the literal word "unsigned," which is
why this increment is recorded as 🟡 rather than ✅.

**Installer contents (2026-08-05).** A file-by-file diff of the installed tree
(`%LOCALAPPDATA%\Programs\PrismaFunction`, 1,225 files) against the source `dist\PrismaFunction` (1,222
files) showed exactly three differences: `unins000.exe`, `unins000.dat`, `unins000.msg` — Inno Setup's own
uninstaller files, added by the `[Files]`/uninstall machinery, not part of the source distribution. No
other file was added, removed, or renamed: the installer contains exactly the validated onedir distribution.

**Real-Windows install/upgrade/uninstall/relaunch validation (2026-08-05, standard non-administrator account
`desktop\portm`, confirmed via `IsInRole(Administrator) = False`).**

- **Per-user install, no elevation:** `/VERYSILENT /SUPPRESSMSGBOXES /TASKS=` exited `0`; installed to
  `%LOCALAPPDATA%\Programs\PrismaFunction` (the documented default); registered only under
  `HKCU\...\Uninstall\{9EA334E3-...}_is1` (no `HKLM` write, confirming no elevation was used); Start Menu
  shortcut created at `...\Start Menu\Programs\PRISMA Monitor\PRISMA Monitor.lnk`; no desktop shortcut
  (task left unchecked, matching the documented default).
- **Optional desktop shortcut:** a separate install with `/TASKS=desktopicon` created
  `%USERPROFILE%\Desktop\PRISMA Monitor.lnk`; removed after verification.
- **Launch/shutdown:** the installed `PrismaFunction.exe` reached a live main window
  (title `PRISMA Monitor v1.0.0`) and closed cleanly via `CloseMainWindow()` (exit code `0`).
- **In-place upgrade/reinstall:** rerunning the installer over the existing install exited `0`; the
  existing app-data SQLite file's SHA-256 hash was unchanged before/after.
- **Uninstall:** running `unins000.exe /VERYSILENT /SUPPRESSMSGBOXES` exited `0`; removed the install
  directory and the Start Menu shortcut; **did not** touch `%LOCALAPPDATA%\PrismaFunction` (16 runtime-data
  files before and after, byte-identical), confirming the checked-in `[UninstallDelete]` (intentionally
  empty) contract.
- **Reinstall reuses the preserved runtime-data baseline:** reinstalling after uninstall, then relaunching,
  produced no data migration and left the app-data SQLite hash unchanged from before the uninstall.
- One relaunch attempt during this sequence hit `RuntimePathError: Runtime-data migration is busy in
  another PrismaFunction process` — traced to a self-inflicted test artifact: an earlier launch was
  force-killed (`Stop-Process -Force`) before its main window appeared, while it still held
  `runtime_paths.py`'s migration lock directory inside its designed 10-second acquisition retry loop
  (`lock_timeout=10.0`) and well within the lock's 5-minute staleness window (`LOCK_STALE_SECONDS=300.0`,
  `runtime_paths.py:24`). This is the lock's intended crash-safety behavior (the error message itself says
  "Retry shortly"), not a packaging or application defect — removing the self-created stale lock and
  retrying with a longer, non-forceful wait reproduced a clean launch every time afterward. No production
  code was changed for this.

**Windows Application Control / signing blockers encountered:** none. No SmartScreen, AppLocker, or WDAC
block was observed for either the packaged executable or the installer at any point in this validation.

**Manual checks still outstanding:** validation on a second, genuinely separate 64-bit Windows machine
(clean-machine acceptance is P.36.12's scope, not this increment's); a real code-signed (not local
self-signed-test) installer build, which requires release signing credentials explicitly out of this
increment's scope.

**P.36.12 was not performed** by this increment (no regression/clean-Windows acceptance pass beyond what is
recorded above).

### Remaining support and finalization stages

| ID | Stage | Status | Dependencies and scope |
|---|---|---|---|
| P.36.8 | Mapping display in the UI | 🟡 Implemented, automated-tested, merged to `main` (PR #64); manually validated on real Windows (manual-selection path only) | Requires P.36.15 (met). See its own dated section above for the full implemented result and evidence. |
| P.36.10 | Remove superseded monitoring and obsolete dependencies | ✅ Implemented, automated-tested, packaging-validated, and merged to `main` via PR #65 (merge commit `d6dd456`) | See its own dated section above for the full implemented result and evidence. |
| P.36.11 | Windows packaging and installer validation | 🟡 Substantially complete (2026-08-05) | Requires the final dependency set after P.36.8, P.36.10, P.36.15, and P.36.16 (all merged, met). See its own dated section above for the full implemented result, defects fixed, and real-Windows validation evidence, including the one recorded signing deviation. |
| P.36.12 | Regression and clean-Windows acceptance | ⬜ Planned | Final gate after all required P.36 implementation and packaging stages. Run the full suite and the approved real-Windows end-to-end checklist. |

## Current blockers and risks

- P.36.14's decision gate is resolved and it is implemented, automated-tested, and merged to `main` via
  PR #61 (merge commit `36b7615`); its own acceptance criteria still require approved
  real-Windows/real-PRISMA validation before it can be marked ✅ Completed.
- Resolved 2026-08-02 (later same-day round): the previously reported date-filter selector drift
  (`data-testid="startOfAuctionFrom"`/`"startOfAuctionTo"`) was re-verified live and the locators still
  match the current live site; a required post-application filter-chip verification and a large-result
  confirmation-modal handler were added and both independently live-verified end-to-end (headless Chromium
  against the real site). See P.36.14's dated entry for the full record.
- New blocker confirmed 2026-08-02 (same round): driving the real installed Chrome/Edge executable (as
  `PrismaLifecycleController` always does) does not reliably deliver Playwright's download-completion event
  to the controlling process, even though the browser's own UI confirms the download completed; isolated to
  the real browser executable specifically (reproducible with both `headless=True` and `headless=False`),
  not reproducible with the Playwright-bundled Chromium build in headless mode.
- Resolved 2026-08-03 (customer decision): the blocker above no longer needs to be root-caused before
  P.36.14 can proceed. An approved bounded-filesystem-observation production fallback is implemented,
  tested, and documented (see P.36.14's dated 2026-08-03 entry above). The one remaining acceptance item is
  a full real-installed-Chrome production-mode pass, which this sandboxed development environment cannot
  perform (no `chrome.exe`/`msedge.exe` installed) — it requires a normal interactive Windows desktop
  session with Chrome or Edge installed.
- Resolved 2026-08-03 (real-Windows defect fix): the confirmed real-Windows defect where selected start/end
  dates were not actually applied to the official PRISMA reporting page is fixed (missing time-of-day
  verification plus a new framework-committed-state check, see P.36.14's matching dated entry above) and
  live-verified end-to-end against the real site via headless Chromium. Manual real-Windows validation of
  this specific fix (distinguishable dates, confirm both appear in the PRISMA controls, confirm the
  resulting request/download uses that range) remains outstanding, in addition to the still-outstanding
  full real-installed-Chrome production acceptance pass above.
- P.36.15 is implemented, automated-tested, reviewed, and merged to `main` via PR #62 (merge commit
  `c84344f`; see its dated 2026-08-04 entry above); final review found no remaining actionable code
  defects. It is not gated on the P.36.14 real-Windows validation item above, since it consumes only an
  already-validated on-disk CSV and touches no browser/PRISMA session itself; manual real-Windows/real-PRISMA
  validation of P.36.15 itself remains outstanding.
- P.36.16's decision gate is resolved (2026-08-04, customer-approved "option 2": cumulative file, exact
  full-12-field deduplication, atomic replace — see its dated entry above); it is implemented,
  automated-tested, and merged to `main` via PR #63 (merge commit `daf4760`, confirmed in Git history), and
  not yet manually validated on real Windows/real PRISMA data.
- P.36.8 (mapping display) is implemented, automated-tested, and manually validated on real Windows via the
  manual-selection (P.36.4) trigger path (2026-08-04, see its dated entry above); branched from `main` at
  merge commit `daf4760` and merged to `main` via PR #64 (merge commit `5e3f309`). Real-Windows validation
  of the managed-download (P.36.14) trigger path remains outstanding.
- `ROADMAP.md`, `workflow_p.md`, and `CLAUDE.md` must remain synchronized on the active 12-column contract and P.36 dependency order.
- Completed P.36.4 remains useful as fallback, but treating it as the primary flow would contradict the current specification.
- P.36.10 (superseded monitoring/scheduler removal) is implemented, automated-tested,
  packaging-validated, and merged to `main` via PR #65 (merge commit `d6dd456`, 2026-08-05; see its
  dated entry above).

## Next recommended increment

1. Complete and review the documentation correction across `ROADMAP.md`, `workflow_p.md`, and the auto-loaded `CLAUDE.md` so all active instructions agree on the 12-column contract and dependency order.
2. P.36.13 is implemented and merged to `main` via PR #59 (merge commit `ff07b68`); it is completed.
3. P.36.14's decision gate is resolved and it is implemented, automated-tested, and merged to `main` via
   PR #61 (merge commit `36b7615`); obtain the required real-Windows/real-PRISMA validation before it can be
   marked ✅ Completed.
4. The date-filter contract and large-result-modal fixes (2026-08-02, later same-day round) are complete and
   individually live-verified end-to-end in headless mode. The approved bounded-filesystem-observation
   fallback (2026-08-03) means the real-Chrome download-event delivery gap no longer blocks progress on its
   own terms; the remaining step is a full real-installed-Chrome production-mode acceptance pass on a normal
   interactive Windows desktop (outside this sandboxed development environment).
5. P.36.15 is implemented, automated-tested, reviewed, and merged to `main` via PR #62 (merge commit
   `c84344f`; see its dated 2026-08-04 entry above), with final review finding no remaining actionable code
   defects; manual real-Windows/real-PRISMA validation remains outstanding.
6. P.36.16's decision gate is resolved and it is implemented, automated-tested, and merged to `main` via
   PR #63 (merge commit `daf4760`; see its dated 2026-08-04 entry above); obtain manual
   real-Windows/real-PRISMA validation before wiring a UI trigger for the complete P.36.14→P.36.15→P.36.16
   pipeline.
7. P.36.8 is implemented, automated-tested, merged to `main` via PR #64 (merge commit `5e3f309`), and
   manually validated on real Windows via the manual-selection (P.36.4) trigger path (see its dated
   2026-08-04 entries above); obtain real-Windows validation of the managed-download (P.36.14) trigger
   path.
8. P.36.10 is implemented, automated-tested, packaging-validated, and merged to `main` via PR #65
   (merge commit `d6dd456`; see its dated entry above).
9. P.36.11 (Windows packaging and installer validation) is substantially complete (2026-08-05, see its own
   dated section above): fresh PyInstaller build, `validate_package.py`, executable identity, isolated
   startup/shutdown, Inno Setup installer build from a space-containing path, and the full real-Windows
   per-user install/upgrade/uninstall/relaunch/data-preservation lifecycle all passed. Not yet merged (the
   user creates and merges pull requests). Before this can be marked ✅ Completed, either obtain a real
   release code-signing tool to produce a genuinely signed (not local-self-signed-test) installer, or
   record an explicit customer decision that the local self-signed-test build satisfies the "unsigned local
   installer build" acceptance item permanently.
10. P.36.12 (regression and clean-Windows acceptance) remains planned; do not begin it until P.36.11 is
    merged and any remaining signing decision from item 9 is resolved.

The obsolete 14-column P.36.6 prompt must not be executed.

## Release target

- **Minimum usable P.36 version:** user selects dates, initiates a managed official CSV download, receives a correct published 12-column result, and can close/reopen the owned PRISMA session safely.
- **Stable Windows release:** completed mapping display, obsolete-code removal, final dependency packaging, installer validation, full regression suite, and real clean-Windows acceptance evidence.

## Maintenance note

Update statuses only after the increment is implemented, reviewed, merged, and its required tests/validation have actually passed. Preserve historical completion records while marking superseded requirements unambiguously.
