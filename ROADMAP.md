# Prisma-function Roadmap

`ROADMAP.md` tracks implementation progress and remaining work. `workflow_p.md` remains the detailed source for the development workflow, requirements, validation rules, and Definition of Done.

## Status legend

- ✅ Completed
- 🟡 In progress / partially completed
- 🟨 Documentation/contracts in progress (no application behavior change)
- ⬜ Planned
- ❌ Cancelled

## Roadmap

| ID | Stage | Status | Current result | Remaining work |
|---|---|---|---|---|
| P.1 | Base project structure | ✅ Completed | Core project layout and entry points exist. | None. |
| P.2 | Initial desktop UI | ✅ Completed | Initial desktop controls and status display exist. | None for this stage. |
| P.3 | CSV processing and validation foundation | ✅ Completed | CSV parsing and validation foundations are implemented. | None for this stage. |
| P.4 | Browser launch lifecycle and retry handling | ✅ Completed | Browser startup, cleanup, and retry lifecycle exist. | None for this stage. |
| P.5 | CSV contract | ✅ Completed | Required fields and validation contract are defined. | None. |
| P.6 | CSV loading and preview | ✅ Completed | CSV files can be loaded, validated, and previewed. | None for this stage. |
| P.7 | Monitoring engine foundation | ✅ Completed | Core monitoring abstractions and execution flow exist. | Live status retrieval is tracked under P.23. |
| P.8 | Monitoring scheduler | ✅ Completed | Interval-based monitoring scheduling exists. | None for this stage. |
| P.9 | Monitoring lifecycle integration | ✅ Completed | Start, stop, and lifecycle coordination are integrated. | None for this stage. |
| P.10 | Error handling and resource cleanup | 🟡 In progress / partially completed | Core failures and typed live-adapter failure boundaries are handled. | Complete session, timeout, DOM-change, unavailable-page, and manual-closure recovery. |
| P.11 | Automated test coverage | 🟡 In progress / partially completed | Automated coverage includes live status parsing, deterministic row matching, mocked page extraction, and browser-thread dispatch. | Extend coverage for authentication, recovery, persistence, migration completion, and packaging behavior. |
| P.17 | Remove the manual browser selector | ✅ Completed | Manual browser selection has been removed. | None. |
| P.18 | Use the Windows default browser automatically | ✅ Completed | The Windows default browser is selected automatically. | None. |
| P.19 | Select Qt GUI framework | ✅ Completed | PySide6 was selected. | None. |
| P.20 | PySide6 migration | 🟡 In progress / partially completed | The PySide6 foundation is present. | Complete integration and UI state management in P.20.2. |
| P.20.1 | PySide6 GUI foundation | ✅ Completed | The base PySide6 GUI and application structure exist. | None. |
| P.20.2 | Complete PySide6 integration and UI state management | ⬜ Planned | Foundation is available from P.20.1. | Complete lifecycle integration, state transitions, and Qt-safe UI updates. |
| P.22 | Validate the packaged executable on a clean Windows environment | 🟡 In progress | A second physical PC exposed an intermittent packaged-browser runtime crash. Clean-Windows validation has not passed. | Reproduce with P.22.1 diagnostics and complete all physical-PC checks. |
| P.22.1 | Add persistent packaged-browser runtime diagnostics | ✅ Completed | Persistent startup and generation-scoped browser lifecycle logging was added for evidence collection; root cause is not yet determined. | Collect and analyze logs from the affected physical PC. |
| P.23 | Live PRISMA auction monitoring | ✅ Completed | P.23.1-P.23.3 provide live retrieval, public-session classification, bounded lookups, typed DOM/unavailable failures, and generation-safe manual-closure recovery. | None for this stage. |
| P.23.1 | Implement live PRISMA page adapter | ✅ Completed | Real-session validation confirmed navigation, delayed table loading, active date filtering, `Marketed >= 1000`, rendered `Auction ID`/`Status` headers, deterministic row matching, `Finished` to `Completed` normalization, typed filtered-row failures, diagnostics, and managed-browser cleanup. Live DOM corrections support the current collapsed filter panel and PRISMA's rendered header row. | None for this increment. |
| P.23.2 | Add authentication/session handling if required | ✅ Completed | The current PRISMA auctions workflow is public. Generation-scoped validation accepts delayed public readiness and the harmless consent banner, detects login redirects/DOM signals, sanitizes diagnostics, and returns typed authentication-required or invalid-session failures. Credential persistence and login automation were intentionally not added. | None for this increment. |
| P.23.3 | Handle timeout, unavailable page, changed DOM, and manual browser closure | ✅ Completed | Bounded live lookups, typed timeout/unavailable/DOM results, lifecycle-driven monitoring termination, idempotent cleanup, stable English UI messages, and stale-generation protection are covered by deterministic tests. | Manual real-session closure/disconnect timing validation remains recommended; no additional implementation is required for this increment. |
| P.24 | Persist monitoring results and status changes | ✅ Completed | Actual live checks, transactional status transitions, and the latest successful per-auction baseline are stored in the runtime SQLite database; restart recovery, error/skip semantics, ordered reads, and persistence-before-UI emission are covered by tests. | No notification UI is included; P.25 remains separate. |
| P.25 | Add user-visible status-change notifications | ✅ Completed | Current-cycle persisted `Changed` transitions produce exact, ordered, non-modal status-change entries in Recent activity; typed eligibility, exclusions, Qt signal delivery, single-cycle summaries, accessible distinction, and the shared 50-item bound are covered by tests. | Complete a manual Windows visual/accessibility smoke check with live transitions. |
| P.26 | Move writable runtime data to the user data directory | ✅ Completed | SQLite, generated Excel, import state, and rotating logs use one `%LOCALAPPDATA%\PrismaFunction` boundary; confirmed source/package/temp legacy artifacts migrate with locking, verification, atomic publication, and deterministic conflict retention. | Complete the documented manual installed-package migration smoke check on Windows. |
| P.27 | Package the application with PyInstaller | ✅ Completed | The authoritative windowed `PrismaFunction.spec` produces a validated `onedir` package with PySide6, the Qt Windows platform plugin, Playwright and its Node driver, application dependencies, and version metadata. Deterministic validation rejects missing runtime components, developer-only files, and writable runtime artifacts in the distribution. | Same-machine interactive launch checks remain manual; clean-machine validation is P.28. |
| P.28 | Validate the executable on a clean Windows environment | 🟡 In progress | The 2026-07-18 physical Windows package test passed the exercised startup, Chrome, monitoring, header-only import, runtime-path, cleanup, and relaunch checks, but its recorded outcome is Partial / Blocked. | Repeat on a standard non-administrator computer without developer tools; test a data-bearing export, Edge, unsupported-default-browser handling, and restart baseline persistence. See `P28_VALIDATION_2026-07-18.md`. |
| P.29 | Add project-wide Windows CI | ✅ Completed | Windows CI runs the full pytest suite, Python compilation, and PyInstaller packaging validation on pushes and pull requests for `main`, with manual dispatch support. | None. |
| P.30 | Final release readiness and versioned release archive | ✅ Completed (repository-side) | Version 1.0.0 metadata, deterministic versioned ZIP and SHA-256 workflow, tests, build instructions, release notes, and a final checklist are complete. | Run and record manual packaged-app, archive, checksum, and second-PC validation; tag and publish only after merge. |
| P.31 | Modern PySide6 monitoring dashboard | ✅ Completed | Responsive light workspace and graphite sidebar, truthful summary cards, model-backed searchable/filterable auction table, browser and monitoring state badges, activity feed, accessible controls, and focused offscreen UI coverage are implemented without changing managed-browser ownership. | Complete manual Windows scaling checks at 125%, 150%, 175%, and 200%. |
| P.32 | Windows installer and uninstaller using Inno Setup | ✅ Completed (repository-side) | A version-controlled, per-user, signed-ready Inno Setup definition installs the validated PyInstaller onedir package, creates Start Menu and optional desktop shortcuts, and preserves runtime data during upgrade and uninstall. Deterministic contract tests and build/validation documentation are included. | Build and manually validate the installer and uninstaller on a standard non-administrator Windows computer; sign release candidates before publication. |
| P.33 | Unified PRISMA CSV import foundation | ✅ Completed | P.33.1-P.33.8 provide separate contracts, audited import, recoverable cumulative persistence, atomic deterministic output, explicit transactional historical Market / Storage backfill, and an expanded evidence-backed reference catalog. | Expand the reference catalog only from authoritative evidence. |
| P.33.1 | Separate and detect both CSV contracts | ✅ Completed | Exact headers, encodings, delimiters, typed detection outcomes, duplicate rejection, and regression-safe routing are implemented and validated. | None for this increment. |
| P.33.2 | Import complete original PRISMA exports | ✅ Completed | Typed imported/filtered/rejected results account for every source row; supported capacity and EUR tariff conversions, direction/network selection, strict dates, and product-duration rules are validated. | None. |
| P.33.3 | Add market and storage reference enrichment | ✅ Completed | Direction-authoritative enrichment exposes side-specific canonical names and market/storage classifications in detailed records; required-side mismatches are typed rejections, irrelevant sides are preserved but ignored, and the 18-field normalized/process_csv contract remains unchanged. | Expand the catalog only when additional authoritative mappings are confirmed. |
| P.33.4 | Add controlled daily source updates | ✅ Completed | Immutable typed state/results, exact-byte SHA-256 identity, authoritative import validation, stable apply/unchanged/reject decisions, and a pure timezone-aware daily due policy are implemented for caller-supplied local files. | None. |
| P.33.5 | Integrate the completed import workflow | ✅ Completed | SQLite-led recovery, atomic Excel publication, exact-retry repair, truthful stored summaries, deferred shutdown, and source-date guidance are implemented and verified by the 299-test suite. | Manual Windows UI and file-lock smoke testing remains recommended. |
| P.33.6 | Manual validation fixes | ✅ Completed | The Monitoring CSV action has unambiguous user-facing text; deterministic `Auctions` worksheet widths are applied and validated without Excel; exact retry repairs legacy default-width output without changing stored rows; historical backfill safety was investigated and documented. | Do not backfill automatically. A future explicit, transactional, idempotent, row-audited maintenance operation remains deferred, with its execution surface and durable audit format still to be decided. |
| P.33.7 | Explicit historical Market / Storage backfill | ✅ Completed | `AuctionStorage.backfill_historical_market_storage()` fills only missing safely resolvable single-side values under `BEGIN IMMEDIATE`, preserves canonical equivalents/conflicts, and appends a durable run plus deterministic per-row audit with exact typed counters. | No automatic or force mode; bundle rows remain unresolvable because both source-side identities were not retained. |
| P.33.8 | Expanded authoritative Market / Storage mapping | ✅ Completed | All 37 Exit and 37 Entry network-point aliases explicitly classified as `RESERVOIR` in the checked-in authoritative export resolve as side-specific Storage references; the five explicit Market mappings remain unchanged. | Add aliases only from checked-in authoritative evidence; do not infer cross-side equivalence. |
| P.34.1 | Safe auction deduplication | ✅ Completed | Selected network-point IDs are mandatory and audited during import; storage rejects blank IDs and conflicting same-identity batches before auction mutation while preserving identical-duplicate accounting. | No schema migration; network-point names are never identity fallbacks. |
| P.34.2 | Maximize the managed browser window | ✅ Completed | Chromium launches with `--start-maximized`, Playwright uses the native window size without a fixed viewport, regression coverage verifies both settings, and the maximized Windows behavior passed manual validation. | None. |
| P.35 | Authoritative PRISMA reference catalog expansion | ✅ Completed | Every exact nonblank network-point name explicitly classified as `RESERVOIR` in the updated checked-in `Auction_overview.csv` resolves as a side-specific Storage alias: exactly 50 Exit and 51 Entry aliases. The five `mapping.csv` Market mappings and `VGS Storage Hub` canonical compatibility remain unchanged. | Add aliases only from exact checked-in side-specific evidence; do not infer relationships or mappings. |
| P.35.1 | Expand authoritative Market mapping catalog (Batch 1) | ✅ Completed | Exactly two customer-approved side-specific aliases resolve to PSV and THE from Auction-ID-linked CSV/PDF evidence with normalized booked capacity of at least 1000 kWh/h, recorded in `evidence/p35-1/EVIDENCE_MANIFEST.md`. Existing Market mappings and the complete Storage catalog remain unchanged. | Twelve aliases from the preliminary 14-row candidate set were rejected below the capacity threshold. Other shared-ID rows were not reviewed or accepted, remain outside this batch, and provide no mappings. No completeness claim is made. |
| P.35.2 | Deterministic user-supplied official CSV/PDF paired import | ❌ Cancelled (2026-07-28) | Was an in-progress uncommitted working-tree implementation adding automated CSV/PDF pair staging, geometry-based PDF parsing, and a paired-operation ledger. | Superseded by `Prisma Function.odt`, the sole authoritative specification, which requires a manual official-CSV download and processing flow, not automated/paired source acquisition. Cancelled without ever being committed; the diff was backed up to `Prisma-function-backups/p35.2-cancelled-2026-07-28/` before removal. See P.36 below. |
| P.35.3 | Managed-browser automatic CSV/PDF acquisition | ❌ Cancelled (2026-07-28) | Was planned only; no code existed. | Superseded by the authoritative manual-download requirement. Automated acquisition is out of scope unless a future authoritative specification explicitly requests it. |
| P.35.4 | Paired-source lifecycle and diagnostics hardening | ❌ Cancelled (2026-07-28) | Was planned only; no code existed. | Depended on P.35.2/P.35.3, both cancelled. |
| P.35.5 | Installed-app paired acquisition validation | ❌ Cancelled (2026-07-28) | Was planned only; no code existed. | Depended on P.35.2/P.35.3, both cancelled. |

## Authoritative specification pivot (2026-07-28)

`Prisma Function.odt` (`C:\Users\portm\Desktop\Pisma mini\Prisma Function.odt`) is adopted as the
**sole authoritative business specification** going forward. It describes a materially simpler,
manual workflow than the automated/paired acquisition line P.35.2-P.35.5 pursued:

- The user manually opens the official PRISMA site in a new browser tab (an "open Prisma" control)
  and manually selects dates and downloads the official CSV export from that site themselves.
- The download folder is either created under the user's Documents folder or explicitly chosen by
  the user; there is no hidden internal staging directory.
- All file processing happens only inside the Prisma Function program, after the user supplies the
  downloaded file to it.
- The user manually closes PRISMA (a "closed Prisma" control) when finished.
- Output is a `;`-delimited UTF-8 CSV with a fixed 12-field contract (auction date; exit market or
  storage; entry market or storage; capacity type entry/exit/bundle; point name; product type;
  flow start/end timestamps; booked capacity; computed flow-duration hours; tariff price; premium
  price), filtered to auctions with booked capacity ≥ 1 MWh, all prices normalized to EUR/MWh/h, all
  timestamps in CET/CEST, decimal separator `.`.
- The program must also display the market/storage mapping referenced by the specification's
  attached screenshot (not located alongside the `.odt` file — see unresolved questions below).
- PDF input is mentioned only as "CSV (PDF if needed)"; the condition that would require PDF is not
  specified, so PDF support stays out of scope until authoritatively clarified.

P.35.2's automated CSV/PDF pairing, staging, and fingerprinting design conflicts with this manual
model and was cancelled rather than adapted, per the sequence below (P.36).

### Unresolved specification questions (require authoritative clarification, not inferred)

1. **Scope boundary against the existing monitoring product.** `Prisma Function.odt` does not state
   whether it replaces/deprecates the existing live PRISMA auction-monitoring dashboard, scheduler,
   and Playwright-driven live-status automation (P.7-P.25, P.31), or whether the manual CSV workflow
   is a separate, additional feature that coexists with monitoring. This determines whether P.36.10
   (removal of obsolete browser automation) applies to the whole monitoring subsystem or only to
   automated *source-acquisition* code such as the cancelled P.35.2-P.35.5 line.
2. **Mapping-display screenshot.** The specification says the program must display market mapping
   "according to the attached screenshot" ("згідно доданого скріншоту"), but no screenshot file was
   found alongside `Prisma Function.odt` (or as a separate attachment). The exact mapping UI layout
   cannot be implemented (P.36.8) without this artifact.
3. **PDF trigger condition.** "CSV файл (за потреби pdf)" states a PDF may be needed "if required,"
   without stating when. Until clarified, PDF import (P.36.5) remains unimplemented/out of scope.
4. **Official auction-resource link.** The specification refers to "the provided link" for the
   official auction resource without including the URL in the extracted text. The existing codebase
   already targets a specific PRISMA URL for monitoring; whether the "open Prisma" control must use
   that same URL, or a different authoritative one, needs confirmation.
5. **Exit/Entry market-or-storage output shape.** The specification's output contract lists a single
   "Ринок виходу або Хранилище" (exit market-or-storage) and a single "Ринок входу або Хранилище"
   (entry market-or-storage) field per row, rather than separate always-present exit/entry columns.
   Whether this reuses the existing Market/Storage reference-catalog duality as-is, or requires a
   restructured output shape, needs confirmation before P.36.6/P.36.7 are implemented.

## P.36 roadmap — manual PRISMA workflow (per `Prisma Function.odt`)

Each increment below is small and independently testable. **P.36.1 is completed and introduced
only documentation and contracts — no application behavior changes.** Later increments are not
started until their applicable open questions are resolved.

| ID | Stage | Status | Scope |
|---|---|---|---|
| P.36.1 | Adopt the authoritative specification: documentation and contracts only | ✅ Completed | Recorded the manual workflow, the 12-field output CSV contract (names, order, formats, units), and the open questions above. No application behavior changed. |
| P.36.2 | Manual "open Prisma" / "closed Prisma" lifecycle | ⬜ Planned (blocked on question 1 and 4) | A user-triggered control opens the official site in a new browser tab; a second user-triggered control closes it. No automated navigation, login, date-setting, or download. |
| P.36.3 | Documents-based or user-selected download directory | ⬜ Planned | Default the expected download location to the user's Documents folder; let the user choose a different folder explicitly. No hidden internal staging path. |
| P.36.4 | Manual CSV selection and validation | ⬜ Planned | User selects the manually downloaded official CSV from disk; validate its exact header/encoding contract; typed accept/reject, no silent coercion. |
| P.36.5 | Optional PDF support | ⬜ Blocked on question 3 | Add PDF input only once the authoritative trigger condition is confirmed; otherwise stays explicitly out of scope. |
| P.36.6 | Filtering, calculation, conversion, and mapping | ⬜ Planned (blocked on question 5) | Implement the ≥ 1 MWh filter, EUR/MWh/h normalization, CET/CEST timestamps, flow-duration-hours calculation, and market/storage mapping resolution for the 12-field contract. |
| P.36.7 | Output CSV writer | ⬜ Planned | Emit the `;`-delimited, UTF-8, dot-decimal output file matching P.36.1's contract exactly. |
| P.36.8 | Mapping display in the UI | ⬜ Blocked on question 2 | Show the resolved market/storage mapping to the user as specified by the (currently missing) attached screenshot. |
| P.36.9 | Accumulation, deduplication, atomic publication, and recovery | ⬜ Planned | Reuse/adapt the existing atomic-publish, dedup, and SQLite-recovery patterns (P.33-P.34 series) for the single-CSV manual workflow; no PDF pairing or fingerprinting. |
| P.36.10 | Remove obsolete browser automation and dependencies | ⬜ Blocked on question 1 | Remove automated source-acquisition code/dependencies confirmed obsolete by the authoritative spec (at minimum, the cancelled P.35.2 `pdfplumber`/`pdfminer` packaging changes never re-added); scope against the monitoring subsystem depends on question 1. |
| P.36.11 | Windows packaging and installer validation | ⬜ Planned | Update `PrismaFunction.spec`, `validate_package.py`, and the Inno Setup installer for the final dependency set; validate the packaged build. |
| P.36.12 | Regression and clean-Windows acceptance tests | ⬜ Planned | Full pytest regression plus a manual clean-Windows acceptance checklist matching the specification's expected result (relevant-only auctions, correct output format, mapping display). |

## Current key limitation

The live adapter is implemented, is the default monitoring source, and has passed
a real public PRISMA session in system-default Chrome. Public-session validation
and safe authentication-required detection are complete. Live-page recovery is
implemented with bounded lookups, typed failures, and generation-safe cleanup.
Manual real-session validation remains recommended for browser closure,
disconnect, and live DOM timing behavior. Whether this monitoring adapter remains
in scope alongside the new manual CSV workflow is unresolved question 1 above.

## Next recommended increment

**P.24, P.25, P.33 through P.33.8, P.35, and P.35.1 are complete. P.35.2-P.35.5 are cancelled.**
**P.36.1 is complete.** The next recommended increment is **P.36.2**, which remains blocked until
authoritative answers are provided for unresolved specification questions 1 and 4.

## Release target

- **Minimum usable version:** real PRISMA status retrieval, safe monitoring, and result persistence.
- **Stable Windows v1.0:** completed PySide6 migration, PyInstaller `onedir` build, clean-machine validation, documentation, version metadata, and a release archive.

## Maintenance note

Statuses must be updated after each merged increment.
