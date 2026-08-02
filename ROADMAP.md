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
| P.36.3 | Documents-based or user-selected download directory | ✅ Completed | Existing accessible directory selection is implemented and session-scoped. Directory creation and managed-download integration remain P.36.14 concerns. |
| P.36.4 | Manual CSV selection and validation | ✅ Completed as fallback | Exact official-export validation exists. Manual selection is a fallback path, not the primary product workflow. |
| P.36.5 | PDF-scope decision | ✅ Completed in part; output-shape decision superseded | Runtime PDF input remains excluded. The former 14-column output decision is withdrawn and must not guide implementation. |

### Suspended obsolete increments

| ID | Former stage | Status | Disposition |
|---|---|---|---|
| P.36.6 | Filtering/calculation/mapping for a 14-column output | 🚫 Suspended / superseded | The old P.36.6 prompt must not be executed. Replaced by P.36.15. |
| P.36.7 | 14-column output CSV writer | 🚫 Suspended / superseded | Replaced by P.36.15. |
| P.36.9 | Accumulation/deduplication/atomic publication under the withdrawn design | 🚫 Suspended / superseded | Publication is redefined by P.36.16 after its decision gate. |

P.36.8, P.36.10, P.36.11, and P.36.12 remain planned support/finalization stages. They must be scheduled only when their dependencies below are satisfied and must use the 12-column contract.

### P.36.13 — Date-range selection inside Prisma Function

**Status:** ⬜ Planned — next implementation increment
**Dependencies required before implementation:** P.36.2 completed.

**Objective:** Let the user select and validate a start date and an end date inside Prisma Function.

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

### P.36.14 — User-initiated, application-managed PRISMA CSV download

**Status:** ⬜ Planned; blocked by decision gate
**Dependencies required before implementation:** P.36.2, P.36.3, and P.36.13 completed.

**Decision gate before implementation:** Approve the exact supported browser/download mechanism and verified PRISMA interaction required to apply the selected dates and initiate the official CSV export. Also decide file naming, completion detection, collision behavior, and whether the Documents subdirectory is created automatically or selected when absent. Do not infer these details and do not restore P.35.2–P.35.5.

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

### P.36.15 — Transform into the exact 12-column output CSV contract

**Status:** ⬜ Planned
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

### P.36.16 — Publish the processed result

**Status:** ⬜ Planned; blocked by decision gate
**Dependency required before implementation:** P.36.15 completed.

**Decision gate before implementation:** The customer must define “publication”: destination, filename, overwrite/versioning behavior, whether results accumulate across runs, duplicate identity and conflict behavior, recovery expectations, and the user-visible success artifact. No implementation begins until these are explicit.

**Objective:** Publish a successfully transformed 12-column result atomically using the approved publication contract.

**Included scope after approval:**

- atomic write/replace behavior appropriate to the approved destination;
- deterministic naming and collision behavior;
- truthful success/failure UI and recoverable retry;
- reuse of compatible P.33/P.34 transaction, audit, deduplication, and recovery patterns only where the approved contract requires them.

**Excluded scope:**

- inventing a destination or accumulation policy;
- publishing partial or failed transformations;
- changing the 12-column contract;
- unrelated export formats or cloud services.

**Acceptance criteria and focused tests:**

- publication exactly matches the approved decision-gate contract;
- interrupted or failed publication never exposes a partial final artifact;
- overwrite, collision, duplicate, retry, and recovery behavior is deterministic and tested where applicable;
- UI reports the real final state and artifact without leaking sensitive data;
- focused tests, full regression tests, compilation, and whitespace validation pass;
- documentation records the approved publication contract and exact executed validation results.

### Remaining support and finalization stages

| ID | Stage | Status | Dependencies and scope |
|---|---|---|---|
| P.36.8 | Mapping display in the UI | ⬜ Planned | Requires P.36.15. Display exactly `Exit Market`, `Entry Market`, `Network Point Name`, `TSO Name Exit`, `TSO Name Entry`; it must not change output CSV fields. |
| P.36.10 | Remove superseded monitoring and obsolete dependencies | ⬜ Planned | Begin only after the final P.36 runtime flow is integrated and covered. Remove only code proven unreachable/obsolete; preserve required browser, mapping, import, audit, and packaging boundaries. |
| P.36.11 | Windows packaging and installer validation | ⬜ Planned | Requires the final dependency set after P.36.8, P.36.10, P.36.15, and P.36.16. Update and validate PyInstaller and Inno Setup artifacts. |
| P.36.12 | Regression and clean-Windows acceptance | ⬜ Planned | Final gate after all required P.36 implementation and packaging stages. Run the full suite and the approved real-Windows end-to-end checklist. |

## Current blockers and risks

- P.36.14 cannot start until the application-managed browser/download mechanism and file-completion rules are explicitly approved and validated against the real PRISMA site.
- P.36.16 cannot start until “publication” is explicitly defined.
- `ROADMAP.md`, `workflow_p.md`, and `CLAUDE.md` must remain synchronized on the active 12-column contract and P.36 dependency order.
- Completed P.36.4 remains useful as fallback, but treating it as the primary flow would contradict the current specification.
- The superseded monitoring subsystem remains present until P.36.10; new work must not accidentally reconnect it as the product workflow.

## Next recommended increment

1. Complete and review the documentation correction across `ROADMAP.md`, `workflow_p.md`, and the auto-loaded `CLAUDE.md` so all active instructions agree on the 12-column contract and dependency order.
2. Implement P.36.13 as one bounded, independently tested increment.
3. Resolve the P.36.14 decision gate before preparing its implementation task.

The obsolete 14-column P.36.6 prompt must not be executed.

## Release target

- **Minimum usable P.36 version:** user selects dates, initiates a managed official CSV download, receives a correct published 12-column result, and can close/reopen the owned PRISMA session safely.
- **Stable Windows release:** completed mapping display, obsolete-code removal, final dependency packaging, installer validation, full regression suite, and real clean-Windows acceptance evidence.

## Maintenance note

Update statuses only after the increment is implemented, reviewed, merged, and its required tests/validation have actually passed. Preserve historical completion records while marking superseded requirements unambiguously.
