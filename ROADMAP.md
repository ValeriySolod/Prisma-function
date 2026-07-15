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
| P.24 | Persist monitoring results and status changes | ⬜ Planned | Persistence is not complete. | Store checks and detected status transitions safely. |
| P.25 | Add user-visible status-change notifications | ⬜ Planned | Notifications are not implemented. | Surface meaningful status changes to the user. |
| P.26 | Move writable runtime data to the user data directory | ⬜ Planned | Runtime path migration is not complete. | Use an appropriate writable Windows user-data location. |
| P.27 | Package the application with PyInstaller | ⬜ Planned | No completed application package is claimed. | Create and verify a PyInstaller `onedir` build. |
| P.28 | Validate the executable on a clean Windows environment | ⬜ Planned | Clean-machine validation has not been completed. | Validate launch and core workflows without a development environment. |
| P.29 | Add project-wide Windows CI | ✅ Completed | Windows CI runs the full pytest suite, Python compilation, and PyInstaller packaging validation on pushes and pull requests for `main`, with manual dispatch support. | None. |
| P.30 | Final release readiness and versioned release archive | ✅ Completed (repository-side) | Version 1.0.0 metadata, deterministic versioned ZIP and SHA-256 workflow, tests, build instructions, release notes, and a final checklist are complete. | Run and record manual packaged-app, archive, checksum, and second-PC validation; tag and publish only after merge. |
| P.31 | Modern PySide6 monitoring dashboard | ✅ Completed | Responsive light workspace and graphite sidebar, truthful summary cards, model-backed searchable/filterable auction table, browser and monitoring state badges, activity feed, accessible controls, and focused offscreen UI coverage are implemented without changing managed-browser ownership. | Complete manual Windows scaling checks at 125%, 150%, 175%, and 200%. |
| P.32 | Windows installer and uninstaller using Inno Setup | ⬜ Planned | Installer work is intentionally outside P.31. | Add and validate a signed-ready Inno Setup installer and uninstaller workflow. |

## Current key limitation

The live adapter is implemented, is the default monitoring source, and has passed
a real public PRISMA session in system-default Chrome. Public-session validation
and safe authentication-required detection are complete. Live-page recovery is
implemented with bounded lookups, typed failures, and generation-safe cleanup.
Manual real-session validation remains recommended for browser closure,
disconnect, and live DOM timing behavior.

## Next recommended increment

**P.31 is complete.** The modern desktop monitoring interface is implemented
and covered by automated tests. P.32 (Windows installer and uninstaller using
Inno Setup) is the next planned increment; it is not part of this change.

## Release target

- **Minimum usable version:** real PRISMA status retrieval, safe monitoring, and result persistence.
- **Stable Windows v1.0:** completed PySide6 migration, PyInstaller `onedir` build, clean-machine validation, documentation, version metadata, and a release archive.

## Maintenance note

Statuses must be updated after each merged increment.
