# ENTSOG network-point market reference

Local, versioned reference data used to resolve the Exit Market/Entry Market
pair for `BORDER_TRANSITION_POINT` and `RESERVOIR` PRISMA network points,
sourced from the ENTSOG Transparency Platform. This supplements — it never
replaces — the exact, evidence-based string-alias catalog in
`prisma_references.py`, which is always consulted first and always wins when
it has a match.

See `entsog_reference_data.py` (resource loader), `entsog_market_resolution.py`
(resolution rules), and `processor.py`'s `_enrich_row`/`_entsog_pair_for_required_side`
(integration) for the implementation.

## Source and snapshot

All resource files under `src/prisma_function/resources/entsog/` were fetched
from the public ENTSOG Transparency Platform REST API on **2026-08-19** and
are re-fetched only by the manual refresh procedure below — the application
itself never makes a network call to ENTSOG.

| Resource file | Source endpoint |
| --- | --- |
| `operator_point_directions.json` | `https://transparency.entsog.eu/api/v1/operatorpointdirections.json` |
| `operators.json` | `https://transparency.entsog.eu/api/v1/operators.json` |
| `balancing_zones.json` | `https://transparency.entsog.eu/api/v1/balancingzones.json` |
| `interconnections.json` | `https://transparency.entsog.eu/api/v1/interconnections.json` |
| `aggregate_interconnections.json` | `https://transparency.entsog.eu/api/v1/aggregateinterconnections.json` |

Only fields this application actually consumes are kept (see below); the
original XLSX/JSON exports are not bundled. `interconnections.json` and
`aggregate_interconnections.json` are bundled for completeness, per the
approved specification's five resource categories, and for future use; the
current resolver (`entsog_market_resolution.py`) resolves everything it needs
directly from `operator_point_directions.json` plus `operators.json`, since
each ENTSOG operator-point-direction record already carries both a point's
own balancing zone and its adjacent zone.

## Field meanings

### `operator_point_directions.json`

One entry per ENTSOG `(point, operator, direction)` triple, filtered to
records that carry both a point EIC and a TSO EIC (a record with either
blank cannot be joined against a PRISMA CSV row and is dropped).

| Field | ENTSOG source field | Meaning |
| --- | --- | --- |
| `point_eic` | `tsoItemIdentifier` | The network point's own EIC, matching PRISMA's `Network Point EIC Exit/Entry`. |
| `operator_key` | `operatorKey` | ENTSOG's stable operator identity, e.g. `DE-TSO-0005`. |
| `tso_eic` | `tsoEicCode` | The operator's EIC, matching PRISMA's `TSO EIC Exit/Entry` when PRISMA populates it. |
| `direction` | `directionKey` | `"entry"` or `"exit"`, matching PRISMA's `Direction`. |
| `own_zone` | `tSOBalancingZone` | The operator's own balancing zone at this point/direction (e.g. `"DE THE BZ"`). |
| `adjacent_zone` | `adjacentZones` | The balancing zone on the other side of this point, when ENTSOG has one on file. |
| `adjacent_country` | `adjacentCountry` | ISO country code of the adjacent side; informational only, not used for matching. |
| `point_type` | `pointType` | ENTSOG's own point classification; informational only — resolution keys off PRISMA's own `Network Point Type Exit/Entry` instead. |
| `point_label` | `pointLabel` | Human-readable point name, for audit/debugging only. |

### `operators.json`

Filtered to operators that carry a non-blank `tsoEicCode`.

| Field | ENTSOG source field |
| --- | --- |
| `operator_key` | `operatorKey` |
| `tso_eic` | `tsoEicCode` |
| `short_name` | `tsoShortName` (falls back to `operatorLabel`) |
| `long_name` | `tsoLongName` (falls back to `operatorLabelLong`) |
| `country` | `operatorCountryKey` |

### `balancing_zones.json`, `interconnections.json`, `aggregate_interconnections.json`

Compact projections of the corresponding ENTSOG endpoints (zone key/label/
country; and interconnection point/country/zone/operator on each side).
Bundled per the approved specification; not currently read by
`entsog_market_resolution.py`.

## Resolution rules implemented

See `entsog_market_resolution.py:resolve_entsog_market_pair` for the exact
logic. Summary:

1. Only `BORDER_TRANSITION_POINT` and `RESERVOIR` (PRISMA's own `Network
   Point Type Exit/Entry` value) are considered; only for a unidirectional
   row (`Direction` = `Exit` or `Entry`) — a two-sided `Exit/Entry` bundle row
   keeps its existing direct per-side string-catalog resolution and never
   reaches this module.
2. The operator is identified exactly: first by the row's own `TSO EIC
   Exit/Entry` against the local ENTSOG operator table; if that is blank or
   unrecognized, by the row's `TSO Exit/Entry` display name against the
   versioned `prisma_tso_aliases.json` alias table. Never fuzzy, substring,
   country, or geographic matching.
3. The **curated fallback table** (`curated_fallback_routes.json`) is
   checked first, by the exact `(point_eic, operator_key, direction)` key —
   a full override for both `Exit Market` and `Entry Market` for the 16
   customer-approved routes documented in that file, each with its own
   source URL.
4. Otherwise, the live `operator_point_directions.json` join
   `(point_eic, tso_eic, direction)` is used:
   - `BORDER_TRANSITION_POINT`: the row's own side gets `own_zone`; the
     opposite side gets `adjacent_zone`. Either may stay blank when ENTSOG's
     own record is itself incomplete.
   - `RESERVOIR`: only the row's own side gets `own_zone` (the "applicable
     Market"); the opposite side always stays blank, per the approved rule.
     The connected storage facility itself is already carried by the
     existing `Network Point Name` output column and needs no resolution
     here.
5. Any failure to resolve exactly (missing point EIC, unrecognized operator,
   no matching ENTSOG record, a record with both zones blank) returns a
   blank market for the affected side. A row is never rejected because this
   resolution fails — it only leaves that side's Market blank, exactly like
   every other reference resolution in this application.

### Curated fallback routes

`curated_fallback_routes.json` documents, with an individual source URL
each, the 16 customer-approved routes for points where the live ENTSOG
export is missing a record entirely, leaves the adjacent zone blank (mostly
Norway-connected German/Dutch entry points, which ENTSOG does not model as
an EU balancing zone), or — for Melendugno specifically — carries
inconsistent `adjacentCountry` data across its two ENTSOG operator records.
Each entry is a full override for its exact key, never merged with a partial
ENTSOG value.

### Explicit exceptions (no code path resolves these)

- **Bacton Exit** — the aggregated point can lead to either Belgium or the
  Netherlands; left unresolved.
- **North Sea Entry (NOSEE)** — represents production, not another
  balancing market; only its own side (via Energinet's direct ENTSOG
  record) is ever populated, never a second Market.
- **CONVERSION B VERS H** — an internal TRF gas-quality conversion point;
  its PRISMA `Network Point Type` is `OTHER_NETWORK_POINT`, which this
  module never considers, so it is already out of scope by construction.

## The PRISMA-TSO-name alias table

`prisma_tso_aliases.json` maps the exact PRISMA `TSO Entry` display name to
its ENTSOG `operator_key`/`tso_eic`, for rows where PRISMA leaves `TSO EIC
Entry` blank (routine for many Entry rows) or supplies an EIC ENTSOG does not
recognize (e.g. National Gas Transmission PLC's legacy `55XNATIONALGASTC`).

The table has **29** entries, covering every PRISMA Entry TSO name confirmed
observed across the two full 5,000-row checked-in samples
(`Auction_overview.csv`, `evidence/p35-1/Auction_overview.csv`). The 29th,
**TAG GmbH**, maps to ENTSOG operator `AT-TSO-0003` / TSO EIC
`21X-AT-C-A0A0A-B` (confirmed 2026-08-19; already present in the bundled
`operators.json`, so no re-fetch was needed). An alias for a TSO name PRISMA
has not yet been observed with still simply leaves that row's Market blank
(fail-closed) rather than being guessed. When a new name is confirmed, add it
to `prisma_tso_aliases.json`, bump its `version`, and record the evidence in
this file.

## Refresh procedure

1. Fetch each endpoint above in full, paginating with `limit`/`offset` until
   the returned count matches `meta.count`/`meta.total` (`operators.json` and
   `operatorpointdirections.json` use different pagination-result key
   casing — check the actual JSON response keys, do not assume).
2. Recompute the compact resource files: keep only the fields listed above;
   for `operator_point_directions.json`, drop any record missing either the
   point EIC or the TSO EIC; for `operators.json`, drop any operator with a
   blank `tsoEicCode`.
3. Re-derive `prisma_tso_aliases.json` from the checked-in PRISMA CSV
   samples' `TSO Entry`/`TSO EIC Entry` columns, matching each blank-EIC name
   to an ENTSOG operator by exact, case-insensitive legal-entity-name
   identity only (`tsoShortName`/`tsoLongName`/`tsoDisplayName`/
   `operatorLabel`/`operatorLabelLong`). Never fuzzy, substring, country, or
   geographic matching.
4. Re-verify every entry in `curated_fallback_routes.json` still reflects the
   live ENTSOG data (a route may become fully resolvable by the live join
   again, at which point it may be removed) and update its `source_url`s.
5. Bump each changed resource file's `version` and `snapshot_date`, and
   update this document's snapshot date and the table above if any endpoint
   URL changed.
6. Run the focused suites (`tests/test_entsog_reference_data.py`,
   `tests/test_entsog_market_resolution.py`, `tests/test_processor.py`),
   the complete test suite, `python -m compileall`, and `git diff --check`.
