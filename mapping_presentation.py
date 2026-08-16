"""Qt-independent Mapping presentation for the authoritative output CSV."""
from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Mapping

from prisma_output import OUTPUT_CSV_COLUMNS

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


def _flow_start_sort_key(row: Mapping[str, str]) -> datetime:
    return datetime.fromisoformat(row["Flow Start"])


def build_mapping_rows_from_output_records(
    records: list[Mapping[str, str]],
) -> tuple[MappingDisplayRow, ...]:
    """Build Mapping rows from already-published authoritative output records."""
    ordered_rows = sorted(records, key=_flow_start_sort_key, reverse=True)
    return tuple(
        MappingDisplayRow(
            auction_date=row["Auction Date"],
            exit_market=row["Exit Market"],
            entry_market=row["Entry Market"],
            capacity_type=row["Capacity Type"],
            network_point_name=row["Network Point Name"],
            product_type=row["Product Type"],
            flow_start=row["Flow Start"],
            flow_end=row["Flow End"],
            booked_capacity=row["Booked Capacity"],
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
