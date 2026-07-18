# Prisma-function Roadmap

`ROADMAP.md` tracks implementation progress and remaining work. `workflow_p.md` remains the detailed source for the development workflow, requirements, validation rules, and Definition of Done.

## Status legend

- ✅ Completed
- 🟡 In progress / partially completed
- ⬜ Planned

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
| P.25 | Add user-visible status-change notifications | ⬜ Planned | Notifications are not implemented. | Surface meaningful status changes to the user. |
| P.26 | Move writable runtime data to the user data directory | ✅ Completed | SQLite, generated Excel, import state, and rotating logs use one `%LOCALAPPDATA%\PrismaFunction` boundary; confirmed source/package/temp legacy artifacts migrate with locking, verification, atomic publication, and deterministic conflict retention. | Complete the documented manual installed-package migration smoke check on Windows. |
| P.27 | Package the application with PyInstaller | ⬜ Planned | No completed application package is claimed. | Create and verify a PyInstaller `onedir` build. |
| P.28 | Validate the executable on a clean Windows environment | ⬜ Planned | Clean-machine validation has not been completed. | Validate launch and core workflows without a development environment. |
| P.29 | Add project-wide Windows CI | ✅ Completed | Windows CI runs the full pytest suite, Python compilation, and PyInstaller packaging validation on pushes and pull requests for `main`, with manual dispatch support. | None. |
| P.30 | Final release readiness and versioned release archive | ✅ Completed (repository-side) | Version 1.0.0 metadata, deterministic versioned ZIP and SHA-256 workflow, tests, build instructions, release notes, and a final checklist are complete. | Run and record manual packaged-app, archive, checksum, and second-PC validation; tag and publish only after merge. |
| P.31 | Modern PySide6 monitoring dashboard | ✅ Completed | Responsive light workspace and graphite sidebar, truthful summary cards, model-backed searchable/filterable auction table, browser and monitoring state badges, activity feed, accessible controls, and focused offscreen UI coverage are implemented without changing managed-browser ownership. | Complete manual Windows scaling checks at 125%, 150%, 175%, and 200%. |
| P.32 | Windows installer and uninstaller using Inno Setup | ⬜ Planned | Installer work is intentionally outside P.31. | Add and validate a signed-ready Inno Setup installer and uninstaller workflow. |
| P.33 | Unified PRISMA CSV import foundation | ✅ Completed | P.33.1-P.33.7 provide separate contracts, audited import, recoverable cumulative persistence, atomic deterministic output, and an explicit transactional historical Market / Storage backfill API. | Expand the reference catalog only from authoritative evidence. |
| P.33.1 | Separate and detect both CSV contracts | ✅ Completed | Exact headers, encodings, delimiters, typed detection outcomes, duplicate rejection, and regression-safe routing are implemented and validated. | None for this increment. |
| P.33.2 | Import complete original PRISMA exports | ✅ Completed | Typed imported/filtered/rejected results account for every source row; supported capacity and EUR tariff conversions, direction/network selection, strict dates, and product-duration rules are validated. | None. |
| P.33.3 | Add market and storage reference enrichment | ✅ Completed | Direction-authoritative enrichment exposes side-specific canonical names and market/storage classifications in detailed records; required-side mismatches are typed rejections, irrelevant sides are preserved but ignored, and the 18-field normalized/process_csv contract remains unchanged. | Expand the catalog only when additional authoritative mappings are confirmed. |
| P.33.4 | Add controlled daily source updates | ✅ Completed | Immutable typed state/results, exact-byte SHA-256 identity, authoritative import validation, stable apply/unchanged/reject decisions, and a pure timezone-aware daily due policy are implemented for caller-supplied local files. | None. |
| P.33.5 | Integrate the completed import workflow | ✅ Completed | SQLite-led recovery, atomic Excel publication, exact-retry repair, truthful stored summaries, deferred shutdown, and source-date guidance are implemented and verified by the 299-test suite. | Manual Windows UI and file-lock smoke testing remains recommended. |
| P.33.6 | Manual validation fixes | ✅ Completed | The Monitoring CSV action has unambiguous user-facing text; deterministic `Auctions` worksheet widths are applied and validated without Excel; exact retry repairs legacy default-width output without changing stored rows; historical backfill safety was investigated and documented. | Do not backfill automatically. A future explicit, transactional, idempotent, row-audited maintenance operation remains deferred, with its execution surface and durable audit format still to be decided. |
| P.33.7 | Explicit historical Market / Storage backfill | ✅ Completed | `AuctionStorage.backfill_historical_market_storage()` fills only missing safely resolvable single-side values under `BEGIN IMMEDIATE`, preserves canonical equivalents/conflicts, and appends a durable run plus deterministic per-row audit with exact typed counters. | No automatic or force mode; bundle rows remain unresolvable because both source-side identities were not retained. |
| P.34.1 | Safe auction deduplication | ✅ Completed | Selected network-point IDs are mandatory and audited during import; storage rejects blank IDs and conflicting same-identity batches before auction mutation while preserving identical-duplicate accounting. | No schema migration; network-point names are never identity fallbacks. |

## Current key limitation

The live adapter is implemented, is the default monitoring source, and has passed
a real public PRISMA session in system-default Chrome. Public-session validation
and safe authentication-required detection are complete. Live-page recovery is
implemented with bounded lookups, typed failures, and generation-safe cleanup.
Manual real-session validation remains recommended for browser closure,
disconnect, and live DOM timing behavior.

## Next recommended increment

**P.24 and P.33 through P.33.7 are complete.** Monitoring now has durable check
and transition history plus restart-safe successful-status baselines. Full
original PRISMA Export CSV files have a
separate, audited, enriched, cumulative local-file import path through the PySide6
UI, while Monitoring CSV loading remains a distinct action. Generated workbooks
have validated deterministic widths. Historical Market / Storage maintenance
is available only through an explicit transactional storage API for the safely
identifiable subset; it is never invoked by startup, import, or update. P.25
remains the next monitoring increment for user-visible change notifications,
while P.32 remains a separate planned installer stage.

## Release target

- **Minimum usable version:** real PRISMA status retrieval, safe monitoring, and result persistence.
- **Stable Windows v1.0:** completed PySide6 migration, PyInstaller `onedir` build, clean-machine validation, documentation, version metadata, and a release archive.

## Maintenance note

Statuses must be updated after each merged increment.
