from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import pytest

from processor import process_csv

BASE = {
    "Auction ID": "A-1", "Start of Auction": "01.01.2025 09:00",
    "Marketed Capacity": "1000", "Unit Marketed Capacity": "kWh/h",
    "Product Runtime Start": "02.01.2025 00:00", "Product Runtime End": "03.01.2025 00:00",
    "Direction": " Entry ", "Network Point Name Entry": "Entry point",
    "Network Point ID Entry": "ENTRY-ID", "Network Point Name Exit": "Exit point",
    "Network Point ID Exit": "EXIT-ID", "Regulated Tariff Exit TSO": "1,25",
    "Regulated Tariff Entry TSO": "0.75", "Surcharge": "0,5",
}


def write_csv(tmp_path: Path, rows: list[dict]) -> Path:
    path = tmp_path / "Auction_overview.csv"
    pd.DataFrame(rows).to_csv(path, sep=";", encoding="cp1252", index=False)
    return path


@pytest.mark.parametrize(("capacity", "unit", "expected"), [
    ("1000", "kWh/h", 1000.0), ("1", "MWh/h", 1000.0),
    ("1,5", "MWh/h", 1500.0), ("1 000.5", "kWh/h", 1000.5),
])
def test_capacity_normalization(tmp_path: Path, capacity: str, unit: str, expected: float) -> None:
    result = process_csv(write_csv(tmp_path, [{**BASE, "Marketed Capacity": capacity, "Unit Marketed Capacity": unit}]))
    assert result[0]["booked_capacity_kwh_h"] == expected


@pytest.mark.parametrize(("capacity", "unit"), [("999.99", "kWh/h"), ("1000", "therms")])
def test_invalid_or_small_capacity_is_skipped(tmp_path: Path, capacity: str, unit: str) -> None:
    assert process_csv(write_csv(tmp_path, [{**BASE, "Marketed Capacity": capacity, "Unit Marketed Capacity": unit}])) == []


def test_missing_required_column_has_english_error(tmp_path: Path) -> None:
    row = {key: value for key, value in BASE.items() if key != "Direction"}
    with pytest.raises(ValueError, match="CSV is missing required columns: Direction"):
        process_csv(write_csv(tmp_path, [row]))


@pytest.mark.parametrize(("direction", "point", "point_id"), [
    (" Entry ", "Entry point", "ENTRY-ID"), ("Exit", "Exit point", "EXIT-ID"),
])
def test_direction_selects_network_point(tmp_path: Path, direction: str, point: str, point_id: str) -> None:
    result = process_csv(write_csv(tmp_path, [{**BASE, "Direction": direction}]))[0]
    assert (result["direction"], result["network_point"], result["network_point_id"]) == (direction.strip().lower(), point, point_id)


@pytest.mark.parametrize(("duration", "expected"), [
    (timedelta(hours=24), "WD / Day Ahead"), (timedelta(days=31), "Month"),
    (timedelta(days=93), "Quarter"), (timedelta(days=93, minutes=1), "Year"),
])
def test_product_type_boundaries(tmp_path: Path, duration: timedelta, expected: str) -> None:
    start = datetime(2025, 1, 2)
    row = {**BASE, "Product Runtime Start": start.strftime("%d.%m.%Y %H:%M"), "Product Runtime End": (start + duration).strftime("%d.%m.%Y %H:%M")}
    assert process_csv(write_csv(tmp_path, [row]))[0]["product_type"] == expected


@pytest.mark.parametrize("end", ["02.01.2025 00:00", "01.01.2025 23:59"])
def test_non_positive_runtime_is_skipped(tmp_path: Path, end: str) -> None:
    assert process_csv(write_csv(tmp_path, [{**BASE, "Product Runtime End": end}])) == []


def test_bad_row_does_not_block_valid_row(tmp_path: Path) -> None:
    bad = {**BASE, "Auction ID": "bad", "Product Runtime Start": "not a date"}
    assert [row["auction_id"] for row in process_csv(write_csv(tmp_path, [bad, BASE]))] == ["A-1"]


@pytest.mark.parametrize("capacity", ["NaN", "nan", "Infinity", "-Infinity", "inf", "-inf"])
def test_non_finite_capacity_isolated_from_valid_row(tmp_path: Path, capacity: str) -> None:
    bad = {**BASE, "Auction ID": "bad-numeric", "Marketed Capacity": capacity}
    rows = process_csv(write_csv(tmp_path, [bad, BASE]))
    assert [row["auction_id"] for row in rows] == ["A-1"]


@pytest.mark.parametrize("field", [
    "Regulated Tariff Exit TSO", "Regulated Tariff Entry TSO", "Surcharge",
])
@pytest.mark.parametrize("value", ["NaN", "Infinity"])
def test_non_finite_price_isolated_from_valid_row(tmp_path: Path, field: str, value: str) -> None:
    bad = {**BASE, "Auction ID": "bad-price", field: value}
    rows = process_csv(write_csv(tmp_path, [bad, BASE]))
    assert [row["auction_id"] for row in rows] == ["A-1"]


def test_empty_capacity_is_zero_and_below_threshold(tmp_path: Path) -> None:
    assert process_csv(write_csv(tmp_path, [{**BASE, "Marketed Capacity": ""}])) == []


def test_empty_tariffs_and_surcharge_are_zero(tmp_path: Path) -> None:
    row = {
        **BASE,
        "Regulated Tariff Exit TSO": "",
        "Regulated Tariff Entry TSO": "",
        "Surcharge": "",
    }
    result = process_csv(write_csv(tmp_path, [row]))[0]
    assert result["tariff_eur_mwh_h"] == 0.0
    assert result["premium_eur_mwh_h"] == 0.0


def test_realistic_csv_keeps_only_valid_row(tmp_path: Path) -> None:
    bad_date = {**BASE, "Auction ID": "bad-date", "Product Runtime End": "invalid"}
    bad_number = {**BASE, "Auction ID": "bad-number", "Marketed Capacity": "Infinity"}
    rows = process_csv(write_csv(tmp_path, [BASE, bad_date, bad_number]))
    assert [row["auction_id"] for row in rows] == ["A-1"]


def test_output_shape_dates_and_prices(tmp_path: Path) -> None:
    result = process_csv(write_csv(tmp_path, [BASE]))[0]
    assert set(result) == {"auction_id", "auction_date", "exit_market", "entry_market", "direction", "network_point", "network_point_id", "tso_exit", "tso_entry", "product_type", "flow_start", "flow_end", "booked_capacity_kwh_h", "runtime_hours", "tariff_eur_mwh_h", "premium_eur_mwh_h", "state"}
    assert (result["auction_date"], result["flow_start"], result["flow_end"]) == ("2025-01-01T09:00:00", "2025-01-02T00:00:00", "2025-01-03T00:00:00")
    assert (result["tariff_eur_mwh_h"], result["premium_eur_mwh_h"]) == (20.0, 5.0)
