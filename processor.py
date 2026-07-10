from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

MIN_MARKETED_CAPACITY_KWH_H = 1000.0
DATE_FORMAT = "%d.%m.%Y %H:%M"


def _text(value: Any) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def _number(value: Any) -> float:
    if pd.isna(value) or value == "":
        return 0.0
    if isinstance(value, str):
        value = value.replace(" ", "").replace(",", ".")
    return float(value)


def _parse_date(value: Any) -> datetime:
    return datetime.strptime(_text(value), DATE_FORMAT)


def _network_point(row: pd.Series) -> str:
    direction = _text(row.get("Direction")).lower()
    if direction == "entry":
        return _text(row.get("Network Point Name Entry"))
    if direction == "exit":
        return _text(row.get("Network Point Name Exit"))
    return (
        _text(row.get("Network Point Name Exit/Entry"))
        or _text(row.get("Network Point Name Exit"))
        or _text(row.get("Network Point Name Entry"))
    )


def _network_point_id(row: pd.Series) -> str:
    direction = _text(row.get("Direction")).lower()
    if direction == "entry":
        return _text(row.get("Network Point ID Entry"))
    if direction == "exit":
        return _text(row.get("Network Point ID Exit"))
    return (
        _text(row.get("Network Point ID Exit/Entry"))
        or _text(row.get("Network Point ID Exit"))
        or _text(row.get("Network Point ID Entry"))
    )


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
    exit_tariff = _number(row.get("Regulated Tariff Exit TSO"))
    entry_tariff = _number(row.get("Regulated Tariff Entry TSO"))
    # Source unit: cent/kWh/h/Runtime. Numerically 1 cent/kWh = 10 EUR/MWh.
    return (exit_tariff + entry_tariff) * 10


def process_csv(path: Path) -> list[dict[str, Any]]:
    frame = pd.read_csv(path, sep=";", encoding="cp1252")

    required = {
        "Auction ID",
        "Start of Auction",
        "Marketed Capacity",
        "Unit Marketed Capacity",
        "Product Runtime Start",
        "Product Runtime End",
        "Direction",
    }
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise ValueError(f"У CSV відсутні колонки: {', '.join(missing)}")

    rows: list[dict[str, Any]] = []

    for _, source in frame.iterrows():
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

        direction = _text(source.get("Direction")).lower()

        rows.append(
            {
                "auction_id": str(source["Auction ID"]),
                "auction_date": _parse_date(source["Start of Auction"]).isoformat(),
                "exit_market": "",
                "entry_market": "",
                "direction": direction,
                "network_point": _network_point(source),
                "network_point_id": _network_point_id(source),
                "tso_exit": _text(source.get("TSO Exit")),
                "tso_entry": _text(source.get("TSO Entry")),
                "product_type": _product_type(flow_start, flow_end),
                "flow_start": flow_start.isoformat(),
                "flow_end": flow_end.isoformat(),
                "booked_capacity_kwh_h": marketed,
                "runtime_hours": runtime_hours,
                "tariff_eur_mwh_h": _tariff_eur_mwh_h(source),
                "premium_eur_mwh_h": _number(source.get("Surcharge")) * 10,
                "state": _text(source.get("State")),
            }
        )

    return rows
