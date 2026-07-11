from __future__ import annotations

import math
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

MIN_MARKETED_CAPACITY_KWH_H = 1000.0
DATE_FORMAT = "%d.%m.%Y %H:%M"
REQUIRED_COLUMNS = (
    "Auction ID", "Start of Auction", "Marketed Capacity",
    "Unit Marketed Capacity", "Product Runtime Start",
    "Product Runtime End", "Direction",
)


def _text(value: Any) -> str:
    return "" if pd.isna(value) else str(value).strip()


def _number(value: Any) -> float:
    if pd.isna(value) or value == "":
        return 0.0
    if isinstance(value, str):
        value = value.replace(" ", "").replace(",", ".")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("Numeric value must be finite")
    return number


def _parse_date(value: Any) -> datetime:
    return datetime.strptime(_text(value), DATE_FORMAT)


def _network_value(row: pd.Series, field: str) -> str:
    direction = _text(row.get("Direction")).lower()
    if direction == "entry":
        return _text(row.get(f"Network Point {field} Entry"))
    if direction == "exit":
        return _text(row.get(f"Network Point {field} Exit"))
    return (_text(row.get(f"Network Point {field} Exit/Entry"))
            or _text(row.get(f"Network Point {field} Exit"))
            or _text(row.get(f"Network Point {field} Entry")))


def _product_type(start: datetime, end: datetime) -> str:
    hours = (end - start).total_seconds() / 3600
    if hours <= 24:
        return "WD / Day Ahead"
    if hours <= 31 * 24:
        return "Month"
    if hours <= 93 * 24:
        return "Quarter"
    return "Year"


def _tariff_eur_mwh_h(row: pd.Series) -> float:
    return (_number(row.get("Regulated Tariff Exit TSO"))
            + _number(row.get("Regulated Tariff Entry TSO"))) * 10


def process_csv(path: Path) -> list[dict[str, Any]]:
    frame = pd.read_csv(path, sep=";", encoding="cp1252", keep_default_na=False)
    missing = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError(f"CSV is missing required columns: {', '.join(missing)}")

    rows: list[dict[str, Any]] = []
    for _, source in frame.iterrows():
        try:
            marketed = _number(source.get("Marketed Capacity"))
            unit = _text(source.get("Unit Marketed Capacity"))
            if unit == "MWh/h":
                marketed *= 1000
            elif unit != "kWh/h":
                continue
            if marketed < MIN_MARKETED_CAPACITY_KWH_H:
                continue

            flow_start = _parse_date(source.get("Product Runtime Start"))
            flow_end = _parse_date(source.get("Product Runtime End"))
            runtime_hours = (flow_end - flow_start).total_seconds() / 3600
            if runtime_hours <= 0:
                continue
            auction_date = _parse_date(source.get("Start of Auction"))
            tariff = _tariff_eur_mwh_h(source)
            premium = _number(source.get("Surcharge")) * 10
        except (ValueError, TypeError, OverflowError):
            continue

        rows.append({
            "auction_id": str(source["Auction ID"]),
            "auction_date": auction_date.isoformat(),
            "exit_market": "", "entry_market": "",
            "direction": _text(source.get("Direction")).lower(),
            "network_point": _network_value(source, "Name"),
            "network_point_id": _network_value(source, "ID"),
            "tso_exit": _text(source.get("TSO Exit")),
            "tso_entry": _text(source.get("TSO Entry")),
            "product_type": _product_type(flow_start, flow_end),
            "flow_start": flow_start.isoformat(),
            "flow_end": flow_end.isoformat(),
            "booked_capacity_kwh_h": marketed,
            "runtime_hours": runtime_hours,
            "tariff_eur_mwh_h": tariff,
            "premium_eur_mwh_h": premium,
            "state": _text(source.get("State")),
        })
    return rows
