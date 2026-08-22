"""Qt-independent Mapping presentation for the authoritative output CSV."""
from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Mapping

from prisma_function.prisma_datetime import (
    AUCTION_DATE_OUTPUT_FORMAT,
    FLOW_TIMESTAMP_OUTPUT_FORMAT,
    MAPPING_AUCTION_DATE_OUTPUT_FORMAT,
    MAPPING_FLOW_TIMESTAMP_OUTPUT_FORMAT,
)
from prisma_function.prisma_output import OUTPUT_CSV_COLUMNS

__all__ = [
    "MAPPING_DISPLAY_FIELDS",
    "MappingDisplayRow",
    "build_mapping_rows_from_output_records",
    "load_mapping_rows_from_output_csv",
]


MAPPING_DISPLAY_FIELDS = OUTPUT_CSV_COLUMNS


@dataclass(frozen=True)
class MappingDisplayRow:
    """One immutable row from the already-published 12-column output."""

    auction_date: str
    exit_market: str
    entry_market: str
    capacity_type: str
    network_point_name: str
    product_type: str
    flow_start: str
    flow_end: str
    booked_capacity: str
    flow_duration_hours: str
    tariff_price: str
    premium_price: str


# Cumulative published data may mix rows written under either Auction
# Date/Flow Start/End contract: the new `MAPPING_AUCTION_DATE_OUTPUT_FORMAT`/
# `MAPPING_FLOW_TIMESTAMP_OUTPUT_FORMAT` (`DD-MM-YYYY`/`DD-MM-YYYY HH:mm`,
# this increment onward) and the legacy `AUCTION_DATE_OUTPUT_FORMAT`/
# `FLOW_TIMESTAMP_OUTPUT_FORMAT` (`YYYY-MM-DD`/`YYYY-MM-DD HH:mm`, written
# before it). Previously accepted rows are never rewritten in storage, so
# both must remain readable indefinitely; only the in-memory rows built here
# for Mapping display are converted to the new format.
_AUCTION_DATE_FORMATS = (MAPPING_AUCTION_DATE_OUTPUT_FORMAT, AUCTION_DATE_OUTPUT_FORMAT)
_FLOW_START_FORMATS = (MAPPING_FLOW_TIMESTAMP_OUTPUT_FORMAT, FLOW_TIMESTAMP_OUTPUT_FORMAT)


def _parse_with_formats(value: object, formats: tuple[str, ...]) -> datetime | None:
    """Parse ``value`` under the first matching format in ``formats``, or
    return `None` for a blank or unrecognized value -- never raises."""
    text = "" if value is None else str(value).strip()
    if not text:
        return None
    for fmt in formats:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def _parse_flow_start(value: object) -> datetime | None:
    """Parse ``value`` under either supported Flow Start format, or return
    `None` for a blank or unrecognized value -- never raises."""
    return _parse_with_formats(value, _FLOW_START_FORMATS)


def _display_auction_date(value: object) -> str:
    """Convert a stored Auction Date to the new `DD-MM-YYYY` display format.

    Accepts either the legacy `YYYY-MM-DD` or the already-new `DD-MM-YYYY`
    contract; a blank or unrecognized value is returned unchanged rather than
    raising, so one bad row never makes the whole Mapping table undisplayable.
    """
    original = "" if value is None else str(value)
    parsed = _parse_with_formats(original, _AUCTION_DATE_FORMATS)
    return original if parsed is None else parsed.strftime(MAPPING_AUCTION_DATE_OUTPUT_FORMAT)


def _display_flow_timestamp(value: object) -> str:
    """Convert a stored Flow Start/End to the new `DD-MM-YYYY HH:mm` display
    format.

    Accepts either the legacy `YYYY-MM-DD HH:mm` or the already-new
    `DD-MM-YYYY HH:mm` contract; a blank or unrecognized value is returned
    unchanged rather than raising, so one bad row never makes the whole
    Mapping table undisplayable.
    """
    original = "" if value is None else str(value)
    parsed = _parse_with_formats(original, _FLOW_START_FORMATS)
    return original if parsed is None else parsed.strftime(MAPPING_FLOW_TIMESTAMP_OUTPUT_FORMAT)


def _display_booked_capacity(value: object) -> str:
    """Format a stored Booked Capacity value to exactly one decimal place for
    display (e.g. `1089601.0416666665` -> `1089601.0`).

    A blank or unparseable value is returned unchanged rather than raising,
    so one bad row never makes the whole Mapping table undisplayable. This
    is purely a display conversion: the underlying stored/published value is
    never rewritten.
    """
    original = "" if value is None else str(value)
    try:
        number = float(original)
    except ValueError:
        return original
    return f"{number:.1f}"


def _flow_start_sort_key(row: Mapping[str, str]) -> tuple[int, datetime]:
    """Deterministic descending-by-Flow-Start sort key.

    A row whose Flow Start is blank or unparseable under either supported
    format is never allowed to raise out of `sorted()` (which would make the
    entire Mapping output undisplayable over one bad row); it instead sorts
    after every row with a valid Flow Start, ordered by group first
    (``1`` for valid > ``0`` for unparseable, so `reverse=True` keeps every
    unparseable row last) and only compares by parsed timestamp within the
    valid group. `sorted()`'s stability keeps unparseable rows in their
    original relative order, since `reverse=True` reverses key comparison,
    not tie order.
    """
    parsed = _parse_flow_start(row.get("Flow Start"))
    if parsed is None:
        return (0, datetime.min)
    return (1, parsed)


def build_mapping_rows_from_output_records(
    records: list[Mapping[str, str]],
) -> tuple[MappingDisplayRow, ...]:
    """Build Mapping rows from already-published authoritative output records.

    Auction Date/Flow Start/Flow End are converted to the current
    `DD-MM-YYYY`/`DD-MM-YYYY HH:mm` display format regardless of which
    contract the underlying stored/published record was written under, and
    Booked Capacity is formatted to exactly one decimal place; the stored
    record itself is a plain input `Mapping` here and is never mutated,
    rewritten, or migrated by this function.
    """
    ordered_rows = sorted(records, key=_flow_start_sort_key, reverse=True)
    return tuple(
        MappingDisplayRow(
            auction_date=_display_auction_date(row["Auction Date"]),
            exit_market=row["Exit Market"],
            entry_market=row["Entry Market"],
            capacity_type=row["Capacity Type"],
            network_point_name=row["Network Point Name"],
            product_type=row["Product Type"],
            flow_start=_display_flow_timestamp(row["Flow Start"]),
            flow_end=_display_flow_timestamp(row["Flow End"]),
            booked_capacity=_display_booked_capacity(row["Booked Capacity"]),
            flow_duration_hours=row["Flow Duration Hours"],
            tariff_price=row["Tariff Price"],
            premium_price=row["Premium Price"],
        )
        for row in ordered_rows
    )


def load_mapping_rows_from_output_csv(path: Path) -> tuple[MappingDisplayRow, ...]:
    """Load all cumulative, deduplicated Mapping rows from the published CSV."""
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter=";")
        if tuple(reader.fieldnames or ()) != OUTPUT_CSV_COLUMNS:
            raise ValueError("The published output CSV does not match the 12-column contract.")
        return build_mapping_rows_from_output_records(list(reader))
