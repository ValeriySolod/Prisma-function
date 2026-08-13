"""Qt-independent P.36.8 boundary: present already-resolved mapping evidence
from one completed P.36.15 import/transformation result.

Per the authoritative Mapping contract, the presentation uses exactly this
hierarchy and order: `Auction Date`, `Exit Market`, `Entry Market`, `Network
Point Name`, `TSO Name Exit`, `TSO Name Entry`, `Booked Capacity` (extended by
the P.36.19 `Currency`/`Rate to EUR`/`Rate Date` columns below). It is a UI
view only: it never adds, removes, renames, or reorders the 12-column output
CSV contract, and it never introduces a separate `Exit Storage`/`Entry
Storage` field.

This module performs no parsing, filtering, normalization, or side-specific
Market/Storage resolution of its own: `processor.import_prisma_export`
(P.33/P.36.4, reused unchanged by P.36.15) already implements and tests every
one of those authoritative rules, including exact side-specific evidence
resolution with no fuzzy, substring, geographic, identifier-only, TSO-name,
or cross-side matching. This module only selects and orders already-resolved
fields from one already-completed `processor.PrismaImportResult` into the
presentation; it introduces no matching or inference of its own.

Per P.36.18, the presentation orders rows by `Flow Start` descending (latest
first), parsed from each row's already-formatted `flow_start` value (a
`YYYY-MM-DD HH:mm` Europe/Berlin local string produced by
`processor._import_row`/`_parse_date` via `prisma_datetime.py` from the
authoritative `DD.MM.YYYY HH:MM` PRISMA export contract), never by lexical
comparison of a formatted string. `datetime.fromisoformat` accepts this exact
format (space-separated date/time, no seconds) as well as the previous
`T`-separated ISO representation, so both remain sortable. This affects only
the order rows are displayed in; `import_result.rows` itself, the 12-column
output CSV, and publication order are untouched.

Per P.36.19, the presentation is additionally extended with three
Mapping-only columns — `Currency`, `Rate to EUR`, `Rate Date` — built from
`rate_resolution.resolve_rates_for_rows`'s already-computed, already-cached
per-Auction-ID `RateResolutionResult` values (keyed by each row's own
`auction_id`). This module performs no PRISMA lookup, currency inference, or
ECB resolution of its own; a row whose Auction ID has no resolution supplied
(not yet processed) or whose resolution did not reach
`RateResolutionOutcome.RESOLVED` (cancelled, unfinished, or any other
unresolved/failed reason) shows a short, technical-detail-free English
placeholder in all three columns instead of a fabricated or misleading rate.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping

from processor import PrismaImportResult
from rate_resolution import RateResolutionOutcome, RateResolutionResult

__all__ = ["MAPPING_DISPLAY_FIELDS", "MappingDisplayRow", "build_mapping_rows"]

# Authoritative Mapping presentation hierarchy, extended by the P.36.19
# Currency/Rate to EUR/Rate Date columns. Exactly these 10 columns, in this
# order; never add, remove, rename, or reorder them, and never add a separate
# Exit Storage/Entry Storage field.
MAPPING_DISPLAY_FIELDS = (
    "Auction Date",
    "Exit Market",
    "Entry Market",
    "Network Point Name",
    "TSO Name Exit",
    "TSO Name Entry",
    "Booked Capacity",
    "Currency",
    "Rate to EUR",
    "Rate Date",
)

# Short, technical-detail-free English placeholders for a row whose rate
# resolution did not reach RateResolutionOutcome.RESOLVED. Full diagnostic
# context (the resolution's own `message`) stays in logs, per the smallest
# existing status/error presentation mechanism: plain text in the existing
# cell, no new dialog or status widget.
_NOT_PROCESSED_TEXT = "Unresolved"
_OUTCOME_DISPLAY_TEXT: Mapping[RateResolutionOutcome, str] = {
    RateResolutionOutcome.NOT_FINISHED: "Not finished",
    RateResolutionOutcome.AUCTION_END_UNAVAILABLE: "Unavailable",
    RateResolutionOutcome.CURRENCY_UNKNOWN: "Unknown",
    RateResolutionOutcome.ECB_RATE_UNAVAILABLE: "Unavailable",
    RateResolutionOutcome.CONFLICT: "Unresolved",
}


@dataclass(frozen=True)
class MappingDisplayRow:
    """One immutable, already-resolved mapping presentation row."""

    auction_date: str
    exit_market: str
    entry_market: str
    network_point_name: str
    tso_name_exit: str
    tso_name_entry: str
    booked_capacity: str
    currency: str
    rate_to_eur: str
    rate_date: str


def _flow_start_sort_key(row: dict[str, Any]) -> datetime:
    return datetime.fromisoformat(row["flow_start"])


def _rate_fields(resolution: RateResolutionResult | None) -> tuple[str, str, str]:
    if resolution is None:
        return (_NOT_PROCESSED_TEXT, _NOT_PROCESSED_TEXT, _NOT_PROCESSED_TEXT)
    if resolution.outcome is not RateResolutionOutcome.RESOLVED:
        text = _OUTCOME_DISPLAY_TEXT.get(resolution.outcome, _NOT_PROCESSED_TEXT)
        return (text, text, text)
    return (
        resolution.currency or _NOT_PROCESSED_TEXT,
        str(resolution.rate_to_eur) if resolution.rate_to_eur is not None else _NOT_PROCESSED_TEXT,
        resolution.rate_date.isoformat() if resolution.rate_date is not None else _NOT_PROCESSED_TEXT,
    )


def build_mapping_rows(
    import_result: PrismaImportResult,
    rate_resolutions: Mapping[str, RateResolutionResult] | None = None,
) -> tuple[MappingDisplayRow, ...]:
    """Build the ordered P.36.18/P.36.19 presentation rows from one completed
    import and its already-computed per-Auction-ID rate resolutions.

    Only ``import_result.rows`` (the already-accepted, already-enriched rows)
    are considered, each mapped straight through in its own existing field
    values with no cross-side substitution. Rows are ordered by ``flow_start``
    descending (the latest Flow Start first), parsed chronologically rather
    than compared as formatted strings; equal ``flow_start`` values retain
    their original import order, since ``sorted()`` is stable and reversing
    it does not disturb tie order. ``import_result.rows`` itself is read, not
    mutated, so this presentation ordering never affects the accepted rows,
    the 12-column output CSV, or publication order. A filtered/rejected-only
    import result (or any import with zero accepted rows) yields an empty
    tuple, never an error.

    ``rate_resolutions`` maps each row's own ``auction_id`` to its already-
    computed ``rate_resolution.RateResolutionResult`` (typically produced
    once per unique Auction ID by ``rate_resolution.resolve_rates_for_rows``
    before this function is called); omitting it (or a row whose Auction ID
    is absent from it) displays the unresolved placeholder rather than
    performing any resolution here.
    """
    resolutions = rate_resolutions or {}
    ordered_rows = sorted(import_result.rows, key=_flow_start_sort_key, reverse=True)
    return tuple(
        MappingDisplayRow(
            auction_date=row["auction_date"],
            exit_market=row["exit_market"],
            entry_market=row["entry_market"],
            network_point_name=row["network_point"],
            tso_name_exit=row["tso_exit"],
            tso_name_entry=row["tso_entry"],
            booked_capacity=str(row["booked_capacity_kwh_h"]),
            currency=currency,
            rate_to_eur=rate_to_eur,
            rate_date=rate_date,
        )
        for row in ordered_rows
        for currency, rate_to_eur, rate_date in (
            _rate_fields(resolutions.get(row.get("auction_id"))),
        )
    )
