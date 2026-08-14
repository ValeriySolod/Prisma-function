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

## Next recommended increment

1. Complete and review the documentation correction across `ROADMAP.md`, `AGENTS.md`, and the auto-loaded `CLAUDE.md` so all active instructions agree on the 12-column contract and dependency order.
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

## Release target

- **Minimum usable P.36 version:** user selects dates, initiates a managed official CSV download, receives a correct published 12-column result, and can close/reopen the owned PRISMA session safely.
- **Stable Windows release:** completed mapping display, obsolete-code removal, final dependency packaging, installer validation, full regression suite, and real clean-Windows acceptance evidence.

## Maintenance note

Update statuses only after the increment is implemented, reviewed, merged, and its required tests/validation have actually passed. Preserve historical completion records while marking superseded requirements unambiguously.
