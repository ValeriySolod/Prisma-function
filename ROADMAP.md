# Prisma-function Roadmap

`ROADMAP.md` records implementation history and the current dependency-ordered product plan.
`AGENTS.md` defines detailed engineering rules, validation requirements, and the Definition of Done.
The newest explicitly approved customer requirements supersede older roadmap text when a conflict is recorded below.

## Status legend

- ✅ Completed
- 🟡 In progress / partially completed
- 🟨 Documentation/contracts in progress
- ⬜ Planned
- 🚫 Suspended / superseded; must not be implemented
- ❌ Cancelled

## Product direction

`Prisma Function.odt` is the authoritative business specification.

**Current workflow (P.38, 2026-08-16 customer-approved revision — supersedes the P.36 managed-download workflow below):**

1. The user downloads the official PRISMA Export CSV independently, outside Prisma Function. Prisma Function never opens, controls, or downloads anything from the PRISMA website.
2. The user selects that local CSV inside Prisma Function (Select CSV, the completed P.36.4 path — now the sole and primary acquisition path, not a fallback).
3. Prisma Function validates and processes the selected CSV inside the application.
4. Prisma Function transforms accepted rows into the exact 12-column output CSV contract defined below.
5. Prisma Function publishes the processed result into the approved Documents-directory default (P.36.3), cumulatively and deduplicated, updating the displayed Mapping table.

**Historical workflow (P.36.2–P.36.22, customer clarifications recorded 2026-08-02 — removed by P.38):**

1. ~~The user opens PRISMA from Prisma Function.~~
2. ~~The user selects a start date and an end date inside Prisma Function. There is no first-day-of-month restriction.~~
3. ~~The user initiates the official PRISMA CSV download through Prisma Function.~~
4. ~~Prisma Function uses a download directory created under the user's Documents directory or another existing directory explicitly selected by the user.~~
5. Prisma Function validates and processes the downloaded CSV inside the application. *(retained, now applied to a manually selected CSV — see current workflow above)*
6. ~~As a fallback only, the user may explicitly select a previously downloaded CSV through the completed P.36.4 path.~~ *(P.36.4 is now the primary and only path, not a fallback)*
7. Prisma Function transforms accepted rows into the exact 12-column output CSV contract defined below. *(retained, unchanged)*
8. Prisma Function publishes the processed result using a publication mechanism that must be explicitly approved before P.36.16 implementation. *(retained; P.36.16's approved cumulative-publication mechanism is unchanged)*
9. ~~The user closes the application-owned PRISMA session with the Close Prisma control when finished. Manual browser closure must also be detected safely.~~

This historical numbered list is preserved verbatim (struck through where removed) as the record of what P.36.2–P.36.22 implemented; see the "P.38" section below for the full removal scope and disposition of every superseded sub-increment.

The P.36 workflow itself replaced the live-monitoring dashboard, scheduler, and automated monitoring product flow. Their completed records remain historical evidence; their removal is recorded under P.36.10.

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
| P.34.2 | Maximize managed browser window | ✅ Completed; superseded by P.36.20 | Real-Windows behavior validated at the time. The `--start-maximized` launch requirement itself is superseded by the 2026-08-13 customer-approved P.36.20 minimized-launch requirement; this row's historical implementation and validation record is preserved, not erased. |
| P.35–P.35.1 | Authoritative mapping catalog expansion | ✅ Completed | Preserve exact side-specific evidence and regression rules. |
| P.35.2–P.35.5 | Paired CSV/PDF acquisition line | ❌ Cancelled | Do not restore the cancelled paired-source or PDF-processing design. |

Detailed historical records and test counts remain in Git history (see `workflow_p.md` as it existed before its removal and consolidation into `AGENTS.md`/`CLAUDE.md`). This summary must not be used to claim that an unrun current test suite has passed.

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
its dated entry in CHANGELOG.md). P.36.10 is implemented, automated-tested, packaging-validated, and merged to
`main` via PR #65 (merge commit `d6dd456`; see its dated entry in CHANGELOG.md). P.36.11 is substantially complete
(2026-08-05, see its own dated section in CHANGELOG.md); P.36.12 remains planned. They must be scheduled only when
their dependencies below are satisfied and must use the 12-column contract.

> **Note (P.37.4, 2026-08-14):** the detailed per-increment implementation
> narratives, dated defect-fix write-ups, and decision-gate records for
> P.36.13 through P.36.21 that used to appear here have been relocated
> verbatim to `CHANGELOG.md`. This section resumes with current status,
> current blockers/risks, and the next recommended increment.

### Remaining support and finalization stages

| ID | Stage | Status | Dependencies and scope |
|---|---|---|---|
| P.36.20 | Minimize the managed browser window | ✅ Implemented, automated-tested, real-Windows manually validated (2026-08-13), and merged to `main` via PR #71 (merge commit `60603aa`) | Supersedes P.34.2's maximized launch. Single-argument change in `prisma_lifecycle.py` (`--start-minimized` replacing `--start-maximized`); no change to navigation, date-range configuration, download orchestration, or closure detection. See its own dated section in CHANGELOG.md. |
| P.36.8 | Mapping display in the UI | 🟡 Implemented, automated-tested, merged to `main` (PR #64); manually validated on real Windows (manual-selection path only) | Requires P.36.15 (met). See its own dated section in CHANGELOG.md for the full implemented result and evidence. |
| P.36.10 | Remove superseded monitoring and obsolete dependencies | ✅ Implemented, automated-tested, packaging-validated, and merged to `main` via PR #65 (merge commit `d6dd456`) | See its own dated section in CHANGELOG.md for the full implemented result and evidence. |
| P.36.11 | Windows packaging and installer validation | 🟡 Substantially complete (2026-08-05) | Requires the final dependency set after P.36.8, P.36.10, P.36.15, and P.36.16 (all merged, met). See its own dated section in CHANGELOG.md for the full implemented result, defects fixed, and real-Windows validation evidence, including the one recorded signing deviation. |
| P.36.17 | Remove Recent activity panel and expand the Mapping workspace | 🟡 Implemented, automated-tested, and merged to `main` via PR #67 (merge commit `fd8abb6`) | UI-only removal, no change to the 12-column contract or any P.36 processing/publication behavior. See its own dated section in CHANGELOG.md. Real-Windows validation of the released vertical space and Mapping resize behavior remains outstanding. |
| P.36.18 | Order Mapping rows by Flow Start descending | 🟡 Implemented, automated-tested, packaging-validated, and merged to `main` via PR #68 (merge commit `3e9a4dd`) | Presentation-only ordering in `mapping_presentation.py`; no change to `import_result.rows`, the 12-column output CSV, or publication order. See its own dated section in CHANGELOG.md. Real-Windows validation remains outstanding. |
| P.36.19 | Historical ECB exchange rate to EUR in Mapping | 🟡 Implemented, automated-tested, real-Windows Mapping display validated (2026-08-13), and merged to `main` via PR #70 (merge commit `04509d3`) | Mapping-display-only addition; no change to the 35-column input or 12-column output contract. See its own dated section in CHANGELOG.md. The live auction-detail endpoint is discovered and implemented (2026-08-13); the same-day page-wiring and EXIT/ENTRY currency-leak defect fixes are implemented and automated-tested; the Mapping contract is corrected to its authoritative 10 columns (`Auction Date`/`Booked Capacity` restored, same day) and its real-Windows visual validation (run from source, not the packaged executable) is complete; outstanding: a future evidenced batch adding further approved market/storage currency metadata beyond the one evidenced `VGS Storage Hub` EXIT-side entry. |
| P.36.21 | Strict EUR normalization of Tariff Price and Premium Price | 🟡 Implemented, automated-tested, and merged to `main` via PR #73 (merge commit `3aec0f0`) | Fail-closed EUR gate in `price_normalization.py`. **Corrected 2026-08-13 (same day):** the gate is now wired into `app.py`'s real, active "Import PRISMA Export" call graph itself (`prisma_import_workflow.run_prisma_import_workflow`), which publishes the confirmed-EUR 12-column CSV (`Prisma_Output_Published_EUR.csv`, via `prisma_publication.publish_cumulative_output`) and no longer calls the legacy Excel pipeline at all (kept only as dormant, independently tested compatibility code); renamed `processor.py`'s misleading pre-EUR price fields. **Corrected again 2026-08-13 (third pass, same day):** the published CSV now lands in the approved download directory (`self._download_directory.current`, `P.36.3`) instead of `%LOCALAPPDATA%` (`RuntimePaths.published_directory` removed); Open Result now opens the real `PrismaWorkflowResult.output_path` from the last success (`self._last_output_path`), never clobbered by a later failure; `publish_cumulative_output()` reuses one precomputed `PriceNormalizationResult` per processing operation instead of normalizing the batch twice. **Corrected again 2026-08-14 (fourth pass):** `precomputed_normalization` is now validated against an immutable `price_normalization.compute_batch_binding()` fingerprint (Auction ID, state, exit/entry market, source Tariff/Premium Price, row order), not just a same-length index set, so a result computed for a different or reordered same-length batch is rejected; source and converted EUR prices are now validated finite, non-negative, and safely serializable, so a NaN/Infinite/negative/unserializably-large price is blocked as `invalid_conversion_data` instead of silently passing through or raising an uncontrolled `decimal.DecimalException`. See its own dated sections in CHANGELOG.md for the full corrected call graph, atomicity guarantee, and evidence. Outstanding: manual real-Windows/real-PRISMA/real-ECB validation. |
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
- Resolved 2026-08-03 (customer decision): the blocker described in CHANGELOG.md no longer needs to be root-caused before
  P.36.14 can proceed. An approved bounded-filesystem-observation production fallback is implemented,
  tested, and documented (see P.36.14's dated 2026-08-03 entry above). The one remaining acceptance item is
  a full real-installed-Chrome production-mode pass, which this sandboxed development environment cannot
  perform (no `chrome.exe`/`msedge.exe` installed) — it requires a normal interactive Windows desktop
  session with Chrome or Edge installed.
- Resolved 2026-08-03 (real-Windows defect fix): the confirmed real-Windows defect where selected start/end
  dates were not actually applied to the official PRISMA reporting page is fixed (missing time-of-day
  verification plus a new framework-committed-state check, see P.36.14's matching dated entry in CHANGELOG.md) and
  live-verified end-to-end against the real site via headless Chromium. Manual real-Windows validation of
  this specific fix (distinguishable dates, confirm both appear in the PRISMA controls, confirm the
  resulting request/download uses that range) remains outstanding, in addition to the still-outstanding
  full real-installed-Chrome production acceptance pass described in CHANGELOG.md.
- P.36.15 is implemented, automated-tested, reviewed, and merged to `main` via PR #62 (merge commit
  `c84344f`; see its dated 2026-08-04 entry above); final review found no remaining actionable code
  defects. It is not gated on the P.36.14 real-Windows validation item described in CHANGELOG.md, since it consumes only an
  already-validated on-disk CSV and touches no browser/PRISMA session itself; manual real-Windows/real-PRISMA
  validation of P.36.15 itself remains outstanding.
- P.36.16's decision gate is resolved (2026-08-04, customer-approved "option 2": cumulative file, exact
  full-12-field deduplication, atomic replace — see its dated entry in CHANGELOG.md); it is implemented,
  automated-tested, and merged to `main` via PR #63 (merge commit `daf4760`, confirmed in Git history), and
  not yet manually validated on real Windows/real PRISMA data.
- P.36.8 (mapping display) is implemented, automated-tested, and manually validated on real Windows via the
  manual-selection (P.36.4) trigger path (2026-08-04, see its dated entry in CHANGELOG.md); branched from `main` at
  merge commit `daf4760` and merged to `main` via PR #64 (merge commit `5e3f309`). Real-Windows validation
  of the managed-download (P.36.14) trigger path remains outstanding.
- `ROADMAP.md` and `CLAUDE.md` must remain synchronized on the active 12-column contract and P.36 dependency order.
- Completed P.36.4 remains useful as fallback, but treating it as the primary flow would contradict the current specification.
- P.36.10 (superseded monitoring/scheduler removal) is implemented, automated-tested,
  packaging-validated, and merged to `main` via PR #65 (merge commit `d6dd456`, 2026-08-05; see its
  dated entry in CHANGELOG.md).
- P.36.17 (remove Recent activity panel, expand Mapping) is implemented, automated-tested, and
  packaging-validated (2026-08-06; see its dated entry in CHANGELOG.md) on branch
  `feature/p36-17-remove-recent-activity`; merged to `main` via PR #67 (merge commit `fd8abb6`), and
  real-Windows validation of the released vertical space and Mapping resize behavior remains outstanding.
- P.36.18 (order Mapping rows by Flow Start descending) is implemented, automated-tested, and
  packaging-validated (2026-08-06; see its dated entry in CHANGELOG.md) on branch
  `feature/mapping-flow-start-descending`; merged to `main` via PR #68 (merge commit `3e9a4dd`), and
  real-Windows validation of the displayed order remains outstanding.
- P.36.19 (historical ECB exchange rate to EUR in Mapping) is implemented and automated-tested
  (2026-08-12, corrected 2026-08-13, same-day defect fixes 2026-08-13; see its dated entry in CHANGELOG.md)
  on branch `feature/auction-end-date-ecb-rate`; merged to `main` via PR #70 (merge commit `04509d3`).
  The former real-environment
  blocker is resolved: live Windows/PRISMA DevTools inspection (2026-08-13) discovered the official
  auction-detail endpoint (`GET https://platform.prisma-capacity.eu/rest/auctions/{auction_id}`),
  and `PlaywrightAuctionDetailFetcher` now implements it for real. Two blocking integration defects
  found in a final review of that correction are both fixed on the same day: (1) `app.py` now
  passes the existing managed Playwright page into rate resolution via
  `PrismaLifecycleController.run_on_page()` and a new `ManagedPrismaAuctionDetailFetcher` adapter
  (marshalled onto the controller's own owner thread, since Playwright's sync API is not safe to
  call from any other thread), so an uncached Finished auction resolved while Prisma is open now
  reaches the real endpoint; (2) `VGS Storage Hub`'s EUR currency evidence (proven EXIT-only) no
  longer leaks onto its ENTRY side, now that `PrismaReferenceCatalog.currency_for()` takes an
  explicit `ReferenceSide`. Still outstanding: market/storage currency evidence remains approved
  for exactly one catalog entry (`VGS Storage Hub`, EUR, EXIT side only), so
  `PrismaReferenceCatalog.currency_for()` still returns `None` for every other current catalog
  entry (and for `VGS Storage Hub`'s own ENTRY side) until a future evidenced batch adds further
  decisions — the correct, safe behavior for unevidenced data, not a defect. The ECB integration
  itself required no such blocker and was additionally confirmed against the real public ECB SDW
  endpoint (see its dated entry in CHANGELOG.md). Real-Windows visual validation of the Mapping display
  (run from source, not the packaged executable) is complete for the current 10-column contract
  (2026-08-13; see the dated "Real-Windows Mapping validation" note in CHANGELOG.md) — the remaining gap is
  the further evidenced currency batch above, not the display itself.
- P.36.21 (strict EUR normalization of Tariff Price and Premium Price) is implemented and
  automated-tested (2026-08-13; corrected same day, see its own dated section in CHANGELOG.md) on branch
  `feature/p36-21-eur-price-normalization`; merged to `main` via PR #73 (merge commit `3aec0f0`).
  `price_normalization.py` gates
  fail-closed on a confirmed EUR/MWh/h conversion; `processor.py`'s misleading pre-EUR price field
  names are corrected; the cumulative publication target is renamed to a new, clearly distinguished
  filename (`Prisma_Output_Published_EUR.csv`) so a pre-P.36.21 file is never read, mutated, or
  mixed with strict-EUR output. A same-day review found the gate was originally wired only into
  `prisma_output.write_prisma_output`/`prisma_publication.publish_cumulative_output`, neither of
  which `app.py` called — so the real "Import PRISMA Export" button could still present a completed
  result with an unconfirmed price. This is fixed: `prisma_import_workflow.run_prisma_import_workflow`
  (the function `app.py` actually calls) now runs the strict gate itself, before any source-operation
  state change, and publishes the confirmed-EUR CSV directly; the legacy Excel pipeline
  (`storage.py`'s `export_excel`/`auctions` table) is no longer called by the active workflow at all
  (kept only as dormant, independently tested compatibility code, per the correction's option (a)).
  A further same-day (third-pass) review found the published CSV still landed under
  `%LOCALAPPDATA%` (`RuntimePaths.published_directory`) rather than the approved download directory,
  and that `publish_cumulative_output()` independently re-normalized the same batch
  `run_prisma_import_workflow()` had already normalized. Both are fixed: `app.py` now snapshots
  `self._download_directory.current` and passes it as `publication_directory`;
  `RuntimePaths.published_directory` is removed; Open Result now opens the real
  `PrismaWorkflowResult.output_path` from `self._last_output_path`, set only on success and never
  clobbered by a later failure; and `publish_cumulative_output()` accepts an optional, validated
  `precomputed_normalization` so the workflow's one `PriceNormalizationResult` is reused instead of
  recomputed. See the "Blocking correction: publication location and single normalization result
  (2026-08-13, third pass, same day)" entry in its own dated section in CHANGELOG.md for the full detail and
  evidence. A fourth-pass review (2026-08-14) found `_validate_precomputed_normalization` accepted a
  same-length precomputed result computed for a *different* or reordered batch, and found
  `normalize_prices_for_output` did not validate a source/converted Decimal finite, non-negative, or
  safely serializable — both are fixed: an immutable `price_normalization.compute_batch_binding()`
  fingerprint now binds a result to its exact ordered rows, and every source/converted price is now
  validated before acceptance, blocking (never raising) on a NaN/Infinite/negative/unserializable value.
  See the "Blocking correction: exact-batch binding for `precomputed_normalization` and Decimal input
  validation (2026-08-14, fourth pass)" entry in its own dated section in CHANGELOG.md for the full detail and
  evidence. Outstanding: manual real-Windows/real-PRISMA/real-ECB validation through
  the real UI button, including that the published file lands in the approved directory and Open
  Result opens it. The separate PRISMA 5000-row large-export defect (P.36.14) was not touched.

## Current blockers and risks — note on P.38/P.39/P.37

P.38 (2026-08-16) removed the entire managed PRISMA browser/download workflow (see its own section above). Every outstanding real-Windows/real-PRISMA validation item recorded above against P.36.2, P.36.3's managed-download support, P.36.8's managed-download trigger path, P.36.13, P.36.14 (including the 5,000-row large-export defect and its P.36.22 fix), and P.36.20 is now moot: that code no longer exists and cannot be validated or shipped. Their historical implementation and validation records remain below and in CHANGELOG.md as evidence of what was built and tested at the time, per the Maintenance note's preservation rule — they are not instructions for further work. P.36.4 (manual CSV selection), P.36.8's mapping-display UI itself, P.36.15, and P.36.16 are unaffected in scope by P.38/P.39 and their own outstanding real-Windows validation items (real-PRISMA CSV) remain live and current. P.36.19 (Mapping-display Currency/Rate columns) is likewise unaffected in scope and its own real-ECB validation item remains live and current, unchanged by P.37. P.36.21's strict-EUR-gate *contract* (fail closed, never guess, never publish source-currency as EUR) is unaffected, but its Tariff/Premium *resolution mechanism* is superseded by P.37 (2026-08-17 real-Windows validation finding, fixed same day — see P.37's own section below for the current mechanism and its own outstanding real-ECB validation item). P.39 (same day as P.38) further removed the "Import PRISMA Export"/"Open Result" buttons and the export-date picker; see its own section below. Any earlier text below still describing the two-step Select-CSV-then-Import-PRISMA-Export flow, the export-date control, or Open Result reflects pre-P.39 history, not current behavior.

## P.39 — Select CSV as the single processing action

**Status:** ✅ Implemented and automated-tested (2026-08-16) on branch `feature/remove-managed-prisma-download`, same day as and following P.38.

**Correction:** P.38 removed managed PRISMA acquisition but left a two-step local flow: Select CSV only previewed the Mapping table, and a separate "Import PRISMA Export" button (with its own file dialog and an "PRISMA EXPORT DATE" picker) actually processed and published. This is withdrawn: Select CSV is now the single user action. `app.py`'s `_select_manual_csv()` validates the chosen file, refreshes the Mapping preview, and — only if that preview succeeded — immediately calls `_process_selected_csv()` on a background thread, which merges the file into cumulative persistent storage (deduplicated, exact-retry-safe, unchanged rules) and publishes the confirmed-EUR 12-column output, then refreshes the Mapping table again as part of that same flow. The "Import PRISMA Export" button, the "Open Result" button, `PrismaMonitorApp._last_output_path`, and the export-date `QDateEdit`/label are removed; `source_date` is now always today's date (the same fallback the pre-P.39 code already used when no UI date was supplied), so no CSV transformation, filtering, market-mapping, currency-conversion, datetime-normalization, or deduplication rule changed. Select CSV is disabled while a selection's processing is still in flight. See its own dated section in CHANGELOG.md for the full removal scope and evidence.

## Next recommended increment

1. Obtain real-Windows manual validation of P.38/P.39/P.37 together: launch the packaged or source application, confirm no PRISMA-website access of any kind occurs, select a local PRISMA Export CSV with real non-EUR prices, confirm it is processed and published automatically with a confirmed EUR/MWh/h Tariff Price/Premium Price resolved against the real public ECB endpoint, and confirm the Mapping table reflects it.
2. Complete and review the documentation correction across `ROADMAP.md`, `AGENTS.md`, and the auto-loaded `CLAUDE.md` so all active instructions agree on the 12-column contract and dependency order.
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
   (merge commit `d6dd456`; see its dated entry in CHANGELOG.md).
9. P.36.11 (Windows packaging and installer validation) is substantially complete (2026-08-05, see its own
   dated section in CHANGELOG.md): fresh PyInstaller build, `validate_package.py`, executable identity, isolated
   startup/shutdown, Inno Setup installer build from a space-containing path, and the full real-Windows
   per-user install/upgrade/uninstall/relaunch/data-preservation lifecycle all passed. Merged to `main`
   via PR #66 (merge commit `94a6de9`). Before this can be marked ✅ Completed, either obtain a real
   release code-signing tool to produce a genuinely signed (not local-self-signed-test) installer, or
   record an explicit customer decision that the local self-signed-test build satisfies the "unsigned local
   installer build" acceptance item permanently.
10. P.36.12 (regression and clean-Windows acceptance) remains planned; do not begin it until P.36.11 is
    merged and any remaining signing decision from item 9 is resolved.
11. P.36.17 (remove Recent activity panel, expand Mapping) is implemented, automated-tested,
    packaging-validated (2026-08-06, see its own dated section in CHANGELOG.md), and merged to `main`
    via PR #67 (merge commit `fd8abb6`); obtain real-Windows validation of the removed panel/released
    Mapping space before P.36.12.
12. P.36.18 (order Mapping rows by Flow Start descending) is implemented, automated-tested,
    packaging-validated (2026-08-06, see its own dated section in CHANGELOG.md), and merged to `main`
    via PR #68 (merge commit `3e9a4dd`); obtain real-Windows validation of the displayed order before
    P.36.12.
13. P.36.19 (historical ECB exchange rate to EUR in Mapping) is implemented and automated-tested
    (2026-08-12, corrected 2026-08-13, same-day defect fixes 2026-08-13, see its own dated section
    above). The live auction-detail endpoint is discovered and `PlaywrightAuctionDetailFetcher`
    implements it for real; `app.py` now wires the existing managed Playwright page into rate
    resolution via `PrismaLifecycleController.run_on_page()`/`ManagedPrismaAuctionDetailFetcher`;
    `VGS Storage Hub` has evidenced EUR currency metadata correctly scoped to its EXIT side only;
    the Mapping contract is corrected to its authoritative 10 columns (`Auction Date`/`Booked
    Capacity` restored). Real-Windows visual validation of the Mapping display (run from source,
    not the packaged executable), including the now-live page wiring and the current 10-column
    contract, is complete (2026-08-13; see the dated "Real-Windows Mapping validation" note
    above). Merged to `main` via PR #70 (merge commit `04509d3`). Before it can be marked
    ✅ Completed: obtain or record further approved, evidenced market/storage currency decisions
    (mirroring the P.35.1 process) for catalog entries — and sides — beyond `VGS Storage Hub`'s
    EXIT side.
14. P.36.21 (strict EUR normalization of Tariff Price and Premium Price) is implemented,
    automated-tested, and corrected same-day so the real "Import PRISMA Export" button itself is
    strict-EUR-gated, then corrected again same-day (third pass) so the published CSV lands in the
    approved download directory instead of `%LOCALAPPDATA%`, Open Result opens the real successful
    output path, and normalization runs exactly once per processing operation (2026-08-13, see its own
    dated sections in CHANGELOG.md); corrected again (fourth pass, 2026-08-14) so a precomputed normalization
    result is bound to its exact ordered row batch (not just a same-length index set) and every
    source/converted Decimal price is validated finite, non-negative, and safely serializable before
    acceptance; merged to `main` via PR #73 (merge commit `3aec0f0`). Obtain
    real-Windows/real-PRISMA/real-ECB validation through the real UI before P.36.12.

The obsolete 14-column P.36.6 prompt must not be executed.

## P.38 — Remove managed PRISMA browser/download workflow

**Status:** ✅ Implemented and automated-tested (2026-08-16) on branch `feature/remove-managed-prisma-download`. Merged to `main`: pending. Real-Windows manual validation: outstanding.

**Customer decision (2026-08-16):** the managed PRISMA browser/download workflow is withdrawn. PrismaFunction must never open, control, or download anything from the PRISMA website; the user downloads the official CSV export independently and Prisma Function's workflow starts from selecting that local CSV. This supersedes the P.36.2/P.36.3/P.36.8/P.36.13/P.36.14/P.36.20/P.36.22 managed-acquisition design recorded above; those entries' historical implementation and validation records are preserved, not erased, but must not guide further implementation. `browser.py`, `prisma_lifecycle.py`, `prisma_download.py`, `prisma_page.py`, and `date_range_selection.py` (and their dedicated tests) are deleted; `app.py`'s Open Prisma/Close Prisma/Date Range/Download Folder UI and controller wiring are removed; `download_directory.py` is trimmed to only the Documents-directory default; `prisma_auction_lookup.PrismaAuctionLookup` fails closed with no live transport instead of defaulting to a Playwright fetcher; `playwright` is removed from dependencies and packaging. Local CSV validation, the 12-column transformation, EUR normalization, CET/CEST handling, cumulative persistence/deduplication, and the Mapping table are all unaffected. See its own dated section in CHANGELOG.md for the full removal scope, the known fail-closed consequence for never-before-resolved Finished auctions (an inherent result of removing all PRISMA-website access, not a defect), and exact validation evidence (606 passed, 1 skipped; compileall, `git diff --check`, PyInstaller build, and `validate_package.py` all passed).

## P.40 — Composite-key cumulative row deduplication

**Status:** ✅ Implemented and automated-tested (2026-08-17) on branch `feature/p38-composite-row-deduplication` (the branch name predates this numbering correction — see the note below; it is not a re-implementation of the already-completed P.38 removal above).

**Numbering note:** this increment was requested under the label "P.38", but P.38 and P.39 above already record different, completed, unrelated work (removing the managed PRISMA browser/download workflow, and collapsing Select CSV into the single processing action). Reusing "P.38" for this unrelated deduplication change would corrupt that historical record, so it is recorded here as **P.40**, the next free slot, following the same correction pattern already used between P.36.21/P.37 and P.38/P.39 in this document.

**Customer decision (2026-08-17):** cumulative deduplication for the published 12-column output (`Prisma_Output_Published_EUR.csv`, P.36.16/P.36.21) is redefined from P.36.16's original exact-full-12-field-row equality rule to an exact composite key: **Auction ID + Network Point Name + Capacity Type**. A row is a duplicate of an already-published row only when all three components match; every other field (`Booked Capacity`, `Flow Start`/`Flow End`, the confirmed EUR prices, etc.) is never part of the identity. PRISMA data is immutable by customer decision: when an incoming row's composite key already has a recorded counterpart, the stored row is kept unchanged and the incoming row is skipped outright — never updated, merged, or reported as a conflict — even if its non-key values differ. Different rows sharing the same source file, source date, product period, filename, or file hash remain independently acceptable; none of that metadata is part of the identity.

**Implementation.** `storage.AuctionStorage` gains a new, purely additive table, `published_output_row_keys` (`auction_id`, `network_point_name`, `capacity_type`, `PRIMARY KEY(auction_id, network_point_name, capacity_type)`), created via the same idempotent `CREATE TABLE IF NOT EXISTS` pattern already used for `auction_rate_resolutions` (P.36.19) — so an existing database file created before this increment opens safely, with no destructive rewrite of any existing table (`auctions`, `prisma_source_operations`, `auction_rate_resolutions`, and the historical Market/Storage audit tables are all untouched). Two new methods, `published_output_row_keys()` (durable, cross-session read) and `record_published_output_row_keys()` (atomic insert, `BEGIN IMMEDIATE`, raises `AuctionStorageError` on an unexpected pre-existing key), back the actual dedup decision. `prisma_publication.publish_cumulative_output` (P.36.16) now checks each incoming row's composite key against this durable store plus the keys already seen earlier in the very same import batch (covering partial-overlap imports within one file) before ever formatting or appending it; a match skips the row outright. New composite keys are recorded in `AuctionStorage` only *after* the CSV write itself has already succeeded, so a mid-write failure never marks a key as published when its row is not actually in the file (the file is always the leading write; the key index trails it). If the cumulative CSV file itself is missing (deleted or never created, as opposed to present-but-malformed, which remains the existing typed `INVALID_EXISTING_FILE` failure), previously recorded keys are not treated as blocking for that call — the file is rebuilt from the current import exactly like the pre-P.40 recovery contract, so a deleted output file still self-heals on the next import instead of silently staying empty because its rows' keys are still "known" in storage.

**Backward compatibility / migration.** Deduplication is now composite-key-only — never content-based — so two rows with different Auction IDs are never conflated merely because their formatted output happens to coincide, matching "different rows ... must remain independently acceptable" literally. This means a cumulative CSV file already populated under the pre-P.40 exact-full-row-equality rule keeps its existing rows exactly as published (nothing in the file is rewritten, reinterpreted, or deleted), but those specific rows have no recorded composite key, since Auction ID was never one of the 12 output columns and cannot be recovered from the CSV alone. This is a deliberate, documented, one-time transitional limit, the same "never reconcile old data against a new identity contract, just stop conflating them" choice this codebase already made for the unrelated pre-P.36.21 legacy-currency file (`LEGACY_PUBLISHED_OUTPUT_FILENAME`): if a source file whose rows were already published *before* this increment shipped is re-selected again afterward, those specific rows are evaluated fresh on that one occasion and may be appended once more; from that first post-upgrade pass onward, their key is recorded and every further import of the same composite key — in this or any later session — is correctly recognized and skipped.

**Scope discipline.** No UI file (`app.py`, `ui_components.py`, `mapping_presentation.py`) changed; the composite-key contract and its storage live entirely in `storage.py`/`prisma_publication.py`, matching "keep storage and deduplication logic outside the UI." The managed PRISMA acquisition removal (P.38) and the single-action Select CSV flow (P.39) are unaffected and not restored/reintroduced. `_MIXED_OUTCOME_ROWS`/`Marketed-Capacity`-only test variants that used to prove "distinct row" under the old exact-content rule were updated to use a distinct Auction ID where they need a genuinely new composite key, and to assert the new immutable-skip outcome where the old assumption (differing non-key values remain distinct) no longer holds; three new parametrized cases prove each of the three key components independently preserves distinctness. See the added/updated tests in `tests/test_storage.py` and `tests/test_prisma_publication.py`.

**Validation:** full automated suite passed (619 passed, 1 skipped — the one platform-dependent symlink test, unchanged from before this increment); `python -m compileall`; `git diff --check`. Outstanding: manual real-Windows validation (reselecting an already-published local CSV, confirming exact-retry idempotence and the Mapping table) has not been performed in this sandboxed environment.

### P.40 correction — remove the remaining source-date uniqueness invariant (2026-08-17)

**Status:** ✅ Implemented and automated-tested (2026-08-17), same branch.

**Regression found during real-Windows validation.** Selecting a second, distinct PRISMA Export CSV for a source date that already had an accepted source failed with "PRISMA import failed: Accepted sources must have unique source dates in ascending order." The composite-key change above only redefined *cumulative-output row* deduplication; it left a second, independent invariant untouched — `prisma_source_operations`' one-operation-per-date identity, enforced by `prisma_source_updates.py`'s `evaluate_prisma_source_update`/`PrismaSourceState` (which this active path called) and by a `UNIQUE(source_date)` constraint on the table itself. That invariant, not the composite key, produced the rejection.

**Customer decision (2026-08-17):** multiple distinct CSV imports sharing a source date or product period must be accepted. Source provenance (source date, filename, or whole-file sha256) must never deduplicate or reject an import; exact-retry and partial-overlap idempotence are preserved exclusively through the P.40 composite row key above.

**Implementation.** `prisma_source_updates.py` (`evaluate_prisma_source_update`, `PrismaSourceState`, `AcceptedPrismaSource`, `SourceUpdateReason`) is deleted along with its dedicated test module: it existed solely to enforce the invariant being removed and had no other caller. `prisma_import_workflow.py` now defines its own minimal `SourceUpdateStatus` (`APPLIED`/`UNCHANGED` only — `REJECTED` was never actually returned to a caller even before this correction, since a rejection always raised `PrismaWorkflowError` first) and computes/verifies the source file's sha256 directly, with a lightweight TOCTOU re-hash after import, matching the old fail-closed behavior for a source that changes mid-validation. `storage.AuctionStorage.begin_operation` now looks up and creates ledger rows by `sha256` alone (`operation_for_digest`, replacing `operation_for_date`); a different file for an already-used source date is always its own independent operation — never a conflict — and the "another operation is unresolved for a different date" guard that previously blocked a new import in `run_prisma_import_workflow` is removed, so a previous attempt's failure never blocks the next Select CSV attempt regardless of file or date. Resuming an in-flight or already-accepted operation by matching digest is retained as an internal bookkeeping optimization only (it still lets an interrupted retry of the exact same bytes continue instead of duplicating a ledger row); it provides no row-level dedup guarantee of its own, which remains the composite key's job exclusively. The pre-SQLite legacy JSON migration (`state.json`) is preserved but no longer builds a `PrismaSourceState`, so a legacy ledger with entries sharing a date migrates without error.

**Backward compatibility / migration.** A database file created before this correction still has `UNIQUE(source_date)` physically baked into `prisma_source_operations`; `CREATE TABLE IF NOT EXISTS` cannot lift a constraint on an already-existing table, so `AuctionStorage._ensure_source_operations_schema` detects the old constraint (via the table's recorded `sqlite_master` SQL) and losslessly rebuilds the table under the corrected `UNIQUE(sha256)` identity, within the same transaction `_create_schema` already holds — this either fully applies or leaves the database completely unchanged. `auctions`, `auction_rate_resolutions`, and `published_output_row_keys` are untouched by this migration.

**Scope discipline.** No UI file changed. `storage.py`/`prisma_import_workflow.py` are the only production files touched, plus the deletion of `prisma_source_updates.py`; `BUILDING.md` and `.github/workflows/windows-ci.yml`'s `compileall` file lists were updated to drop the deleted module. See the updated/added tests in `tests/test_prisma_import_workflow.py` (a same-date, different-content import while a prior operation is unresolved is now proven *accepted*, replacing the old "...is_blocked..." test) and `tests/test_app.py`'s import path update.

**Validation:** full automated suite; `python -m compileall`; `git diff --check`. Outstanding: real-Windows manual validation of this specific correction (reselecting a distinct CSV for a source date with an already-accepted or unresolved operation) has not been performed in this sandboxed environment.

### P.40 correction — recover a stale runtime-data migration lock on restart (2026-08-17)

**Status:** ✅ Implemented and automated-tested (2026-08-17), same branch.

**Regression found during real-Windows validation.** PrismaFunction was closed (Windows `tasklist` confirmed no python/PrismaFunction process remained), then immediately relaunched. Startup failed with "Runtime-data migration is busy in another PrismaFunction process. Retry shortly." even though no competing process existed.

**Root cause.** `runtime_paths._inspect_stale_lock` checked the lock directory's filesystem-modification age against `LOCK_STALE_SECONDS` (300s) *before* checking whether the lock's recorded owner process was still alive. A lock less than five minutes old was therefore always treated as "not stale," regardless of whether its owner PID had already exited — exactly the immediate-restart case.

**Implementation.** `_inspect_stale_lock` now reads the lock's recorded owner and, whenever a PID can be parsed from it (`_parse_lock_owner_pid`, factored out of `_lock_owner_is_running`), decides staleness solely from `_process_is_running(pid)` — a confirmed-dead owner is reclaimable immediately, with no age wait, and a confirmed-live owner is never reclaimed regardless of age. The `age < LOCK_STALE_SECONDS` check is now used only as a conservative fallback for the case no positive PID can be identified (owner file missing or unreadable, e.g. a lock caught mid-acquisition between `mkdir()` and the owner file being written), preserving the existing "never treat a partially-initialized lock as stale" behavior. Lock acquisition/release (`lock.mkdir()`, the atomic owner-file write via `os.replace`, and the `try/finally`-guarded release in `migrate_legacy_runtime_data`) were already atomic and already covered every success/handled-failure path; this correction changes only the staleness decision, not the acquire/release mechanics.

**Scope discipline.** Only `runtime_paths.py` (`_inspect_stale_lock`, plus the new `_parse_lock_owner_pid` helper reused by `_lock_owner_is_running`) changed. No other module calls into the migration-lock path. See `tests/test_runtime_paths.py`'s new `test_lock_from_terminated_process_is_recovered_immediately_on_restart` (confirms immediate reclamation of a fresh-but-dead-owner lock) and `test_lock_from_live_process_is_never_recovered_regardless_of_age` (confirms an aged-but-live-owner lock still correctly reports "busy"); all prior stale-lock tests (`test_stale_interrupted_migration_lock_is_recovered`, `test_replacement_between_stale_inspection_and_quarantine_is_preserved`, `test_partially_initialized_lock_is_never_treated_as_stale`) pass unchanged.

**Validation:** full automated suite (623 passed, 1 skipped). Outstanding: real-Windows manual validation of this specific correction (close-then-immediately-relaunch) has not been performed in this sandboxed environment.

## P.37 — ECB currency normalization keyed by Start of Auction

**Status:** ✅ Implemented and automated-tested (2026-08-17), same branch as P.40, fixing a real-Windows validation finding against the P.36.21 output path.

**Numbering note:** "P.37" is reused here for the Tariff/Premium currency-mechanism correction that `CLAUDE.md` already documents under that label. The unrelated documentation-reorganization work recorded as `P.37.1`–`P.37.6` (splitting the historical narrative into `CHANGELOG.md`, 2026-08-14) is a separate, already-completed increment and is not affected by, or related to, this entry; only the top-level "P.37" label is shared between the two, and no dependency exists in either direction.

**Problem addressed (real-Windows validation finding).** Selecting a real PRISMA Export CSV failed with "42 auction(s) could not be confirmed in EUR/MWh/h." P.36.19/P.36.21's Tariff/Premium EUR-normalization mechanism resolved currency from a market/storage catalog (`prisma_references.py`, evidenced for exactly one entry, EUR only) and the auction's END date via a *live* PRISMA auction-detail lookup (`prisma_auction_lookup.PrismaAuctionLookup`). Since P.38 removed all browser/PRISMA-website access, that lookup always fails closed in the running application — the exact "known fail-closed consequence for never-before-resolved Finished auctions" P.38's own dated section documents as an inherent, accepted result of removing PRISMA-website access. In practice this meant the Tariff/Premium output path was blocked for essentially all new data, since almost no catalog entry carries approved currency evidence either.

**P.37 resolves this for the Tariff/Premium output path** (not the Mapping display; see "Superseded" below) by resolving the ECB rate a different, fully self-sufficient way:

- Currency is parsed directly from each price field's own CSV unit string in `processor.py` (`cent` → EUR, `pence` → GBP, `halér` → CZK, `CHF/100` → CHF; all four divide by 100, matching the exact real unit strings evidenced in `Auction_overview.csv`), independently for the exit-side tariff, entry-side tariff, and Premium/Surcharge — never inferred from a market/storage catalog.
- The ECB rate is resolved by `(auction_date, currency)`, where `auction_date` is the calendar date parsed from each row's own `Start of Auction` (already `row["auction_date"]`, unchanged from its existing role as the output `Auction Date` column) — never an auction-end date requiring a live PRISMA lookup.
- A bundle row (`Direction == "Exit/Entry"`) whose exit and entry sides are denominated in different currencies has each side resolved and converted to EUR independently; only the two already-EUR values are summed, never a shared/blended rate or a pre-conversion mixed-currency sum. The same independence applies to Premium/Surcharge, which carries its own separately resolved currency.
- Each unique `(auction_date, currency)` pair is resolved at most once per import and durably persisted in a new `storage.AuctionStorage` table (`ecb_auction_date_rates`, keyed by `(auction_date, currency)`), reused across later imports without another ECB request — the same idempotent-reuse/conflict-detection persistence pattern P.36.19's `auction_rate_resolutions` table already established, applied to the new key.
- Fails closed exactly as P.36.21 already required: a row whose currency/date pair has no confirmed ECB rate blocks the entire batch, with no partial output; a missing/unsupported currency or unparseable auction date can never reach `price_normalization.py` in the first place, since `processor.py` already rejects such a row at import time. The user-facing block message no longer references "auction-end" evidence (obsolete under this mechanism) and instead names the missing auction date/currency ECB evidence directly.

**Reused unchanged:** `ecb_rates.py` in full — its quotation-direction inversion (ECB's published "currency per EUR" figure inverted into "EUR per currency unit") and its weekend/ECB-holiday fallback (`endPeriod`-bounded query to the latest prior publication) required no changes at all, since both were already generically keyed by `(currency, date)`. `price_normalization.py`'s `format_price`/`PRICE_DECIMAL_PLACES`/`ROUND_HALF_UP` serialization, `PriceNormalizationOutcome`/`NormalizedPrice`/`PriceConversionFailure`/`PriceNormalizationResult` dataclasses, Decimal-arithmetic/input-validation conventions, and the overall fail-closed BLOCKED-carries-nothing batch contract are all unchanged in spirit, adapted only to the new per-side resolution/conversion path. `prisma_output.transform_row`/`OUTPUT_CSV_COLUMNS` and `prisma_publication.py`'s merge/dedup/atomic-publish contract (including P.40's composite-key deduplication) are untouched; the 12-column output contract itself is unchanged.

**Superseded (for Tariff/Premium normalization only — not Mapping):** `rate_resolution.resolve_rates_for_rows`/`resolve_auction_rate` and `prisma_auction_lookup.PrismaAuctionLookup` are no longer in the Tariff/Premium EUR call graph (`price_normalization.normalize_prices_for_output` no longer accepts `reference_catalog`/`auction_lookup`/`page`, and neither does `prisma_output.write_prisma_output`/`prisma_publication.publish_cumulative_output`/`prisma_import_workflow.run_prisma_import_workflow`, all of which forwarded them only for that purpose). Both modules remain fully implemented, unmodified, and in active use for the Mapping UI's own `Currency`/`Rate to EUR`/`Rate Date` display columns (`mapping_presentation.py`, `app.py`'s separate `_refresh_mapping_display()` call graph) — including that path's documented "Unavailable" behavior for a never-cached Finished auction, which P.37 does not change and was not asked to change.

**Changed files:** `processor.py` (per-side currency-tagged price parsing, new `_PRICE_UNITS` table), `storage.py` (new `EcbAuctionDateRateRecord`/`ecb_auction_date_rates` table/methods; `_translate_legacy_price_fields` extended to drop the new P.37-only row keys before the dormant `auctions`-table upsert), `price_normalization.py` (new `(auction_date, currency)` resolution/conversion path, replacing the Auction-ID-keyed one for this module only), `prisma_output.py`/`prisma_publication.py`/`prisma_import_workflow.py` (dropped the now-unused `auction_lookup`/`page` parameters and the obsolete "auction-end" wording from their user-facing failure messages; `prisma_publication.py` additionally dropped `reference_catalog`, which it only ever forwarded to normalization). `app.py` required no changes: its only call to `run_prisma_import_workflow` never passed any of the dropped parameters, and its separate Mapping-preview call to `rate_resolution.resolve_rates_for_rows` is untouched. P.40's composite-key deduplication (`published_output_row_keys`) is preserved unmodified.

**Outstanding:** real-Windows/real-PRISMA/real-ECB validation through the real UI with the actual CSV that produced the original "42 auction(s)" failure (same posture as the existing outstanding P.36.19/P.36.21 items).

## Release target

- **Minimum usable version:** user selects a locally downloaded PRISMA Export CSV, which is immediately processed and merged into a correct published 12-column cumulative result — with no PRISMA-website access of any kind and no separate import step.
- **Stable Windows release:** completed mapping display, obsolete-code removal, final dependency packaging, installer validation, full regression suite, and real clean-Windows acceptance evidence.

## Maintenance note

Update statuses only after the increment is implemented, reviewed, merged, and its required tests/validation have actually passed. Preserve historical completion records while marking superseded requirements unambiguously.
