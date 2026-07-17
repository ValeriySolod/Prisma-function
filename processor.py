from __future__ import annotations

import csv
import math
import re
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from csv_contracts import CsvFormat, PRISMA_EXPORT_COLUMNS, require_csv_format

MIN_MARKETED_CAPACITY_KWH_H = 1000.0
DATE_FORMAT = "%d.%m.%Y %H:%M"
_DATE_PATTERN = re.compile(r"\d{2}\.\d{2}\.\d{4} \d{2}:\d{2}\Z")


class PrismaImportStatus(str, Enum):
    IMPORTED = "imported"
    FILTERED = "filtered"
    REJECTED = "rejected"


class PrismaImportError(RuntimeError):
    """Raised when an export cannot be parsed safely as a complete import."""


@dataclass(frozen=True)
class PrismaImportIssue:
    source_row_number: int
    status: PrismaImportStatus
    reason_code: str
    message: str


@dataclass(frozen=True)
class PrismaImportResult:
    imported_rows: list[dict[str, Any]]
    total_source_rows: int
    imported_count: int
    filtered_count: int
    rejected_count: int
    issues: list[PrismaImportIssue]

    @property
    def rows(self) -> list[dict[str, Any]]:
        """Compatibility-friendly shorthand for the imported rows."""
        return self.imported_rows


class _RowRejected(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _number(value: Any, *, label: str) -> float:
    text = _text(value)
    if not text:
        raise _RowRejected(
            f"empty_{label}",
            f"{label.replace('_', ' ').title()} is empty.",
        )
    try:
        number = float(text.replace(" ", "").replace(",", "."))
    except (TypeError, ValueError, OverflowError) as exc:
        raise _RowRejected(
            f"malformed_{label}",
            f"{label.replace('_', ' ').title()} is malformed.",
        ) from exc
    if not math.isfinite(number):
        raise _RowRejected(
            f"non_finite_{label}",
            f"{label.replace('_', ' ').title()} must be finite.",
        )
    if number < 0:
        raise _RowRejected(
            f"negative_{label}",
            f"{label.replace('_', ' ').title()} must not be negative.",
        )
    return number


def _parse_date(value: Any, *, label: str) -> datetime:
    text = _text(value)
    if not _DATE_PATTERN.fullmatch(text):
        raise _RowRejected(
            f"invalid_{label}",
            f"{label.replace('_', ' ').title()} is not in DD.MM.YYYY HH:MM format.",
        )
    try:
        return datetime.strptime(text, DATE_FORMAT)
    except ValueError as exc:
        raise _RowRejected(
            f"invalid_{label}",
            f"{label.replace('_', ' ').title()} is not a valid date.",
        ) from exc


def _capacity(row: dict[str, Any]) -> float:
    value = _number(row.get("Marketed Capacity"), label="marketed_capacity")
    unit = _text(row.get("Unit Marketed Capacity"))
    factors = {"kWh/h": 1.0, "MWh/h": 1000.0, "kWh/d": 1 / 24}
    if unit not in factors:
        raise _RowRejected(
            "unsupported_capacity_unit",
            f"Unsupported marketed capacity unit: {unit or '(blank)' }.",
        )
    return value * factors[unit]


def _direction_and_network(row: dict[str, Any]) -> tuple[str, str, str]:
    source_direction = _text(row.get("Direction"))
    directions = {
        "Entry": ("entry", "Entry"),
        "Exit": ("exit", "Exit"),
        "Exit/Entry": ("bundle", "Exit/Entry"),
    }
    if source_direction not in directions:
        raise _RowRejected("unsupported_direction", f"Unsupported direction: {source_direction or '(blank)'}.")
    direction, suffix = directions[source_direction]
    name = _text(row.get(f"Network Point Name {suffix}"))
    point_id = _text(row.get(f"Network Point ID {suffix}"))
    if not name:
        raise _RowRejected("missing_network_point", "The selected network-point name is empty.")
    return direction, name, point_id


def _product_type(auction_date: datetime, start: datetime, runtime_hours: float) -> str:
    if runtime_hours <= 24:
        return "WD" if start.date() == auction_date.date() else "Day Ahead"
    if runtime_hours <= 31 * 24:
        return "Month"
    if runtime_hours <= 93 * 24:
        return "Quarter"
    return "Year"


def _price(row: dict[str, Any], value_field: str, unit_field: str, *, label: str) -> float:
    value_text = _text(row.get(value_field))
    unit = _text(row.get(unit_field))
    if not value_text and not unit:
        return 0.0
    if not value_text:
        raise _RowRejected(
            f"empty_{label}",
            f"{label.replace('_', ' ').title()} is empty while its unit is present.",
        )
    if not unit:
        raise _RowRejected(
            f"missing_{label}_unit",
            f"{label.replace('_', ' ').title()} has no unit.",
        )
    factors = {"cent/kWh/h/Runtime": 10.0, "cent/kWh/d/Runtime": 10.0 / 24}
    if unit not in factors:
        raise _RowRejected(
            f"unsupported_{label}_unit",
            f"Unsupported {label.replace('_', ' ')} unit: {unit}.",
        )
    return _number(value_text, label=label) * factors[unit]


def _import_row(source: dict[str, Any]) -> dict[str, Any]:
    raw_auction_id = source.get("Auction ID")
    auction_id = "" if raw_auction_id is None else str(raw_auction_id)
    if not auction_id.strip():
        raise _RowRejected("missing_auction_id", "Auction ID is empty.")
    marketed = _capacity(source)
    if marketed < MIN_MARKETED_CAPACITY_KWH_H:
        raise _RowRejected(
            "capacity_below_threshold",
            "Normalized marketed capacity is below 1000 kWh/h.",
        )
    direction, network_point, network_point_id = _direction_and_network(source)
    auction_date = _parse_date(source.get("Start of Auction"), label="auction_date")
    flow_start = _parse_date(source.get("Product Runtime Start"), label="flow_start")
    flow_end = _parse_date(source.get("Product Runtime End"), label="flow_end")
    if flow_start.date() < auction_date.date():
        raise _RowRejected(
            "flow_before_auction_date",
            "Product flow starts on a calendar date before the auction date.",
        )
    runtime_hours = (flow_end - flow_start).total_seconds() / 3600
    if not math.isfinite(runtime_hours) or runtime_hours <= 0:
        raise _RowRejected("non_positive_runtime", "Product runtime must be positive and finite.")
    tariff = _price(
        source,
        "Regulated Tariff Exit TSO",
        "Unit Regulated Exit Capacity Tariff",
        label="exit_tariff",
    )
    tariff += _price(
        source,
        "Regulated Tariff Entry TSO",
        "Unit Regulated Entry Capacity Tariff",
        label="entry_tariff",
    )
    premium = _price(source, "Surcharge", "Unit Surcharge", label="surcharge")
    return {
        "auction_id": auction_id,
        "auction_date": auction_date.isoformat(),
        "exit_market": "",
        "entry_market": "",
        "direction": direction,
        "network_point": network_point,
        "network_point_id": network_point_id,
        "tso_exit": _text(source.get("TSO Exit")),
        "tso_entry": _text(source.get("TSO Entry")),
        "product_type": _product_type(auction_date, flow_start, runtime_hours),
        "flow_start": flow_start.isoformat(),
        "flow_end": flow_end.isoformat(),
        "booked_capacity_kwh_h": marketed,
        "runtime_hours": runtime_hours,
        "tariff_eur_mwh_h": tariff,
        "premium_eur_mwh_h": premium,
        "state": _text(source.get("State")),
    }


def import_prisma_export(path: str | Path) -> PrismaImportResult:
    require_csv_format(path, CsvFormat.PRISMA_EXPORT)
    rows: list[dict[str, Any]] = []
    issues: list[PrismaImportIssue] = []
    filtered = rejected = total = 0
    with Path(path).open("r", encoding="cp1252", newline="") as csv_file:
        reader = csv.reader(csv_file, delimiter=";", strict=True)
        try:
            header = next(reader)
        except (StopIteration, csv.Error) as exc:
            raise PrismaImportError("The PRISMA export header could not be parsed.") from exc
        if tuple(header) != PRISMA_EXPORT_COLUMNS:
            raise PrismaImportError(
                "The parsed PRISMA export header does not match the required contract."
            )

        while True:
            # line_num is the last physical line consumed. For quoted records with
            # embedded newlines, the issue points to the record's starting line.
            source_row_number = reader.line_num + 1
            try:
                fields = next(reader)
            except StopIteration:
                break
            except csv.Error as exc:
                raise PrismaImportError(
                    "The PRISMA export could not be parsed safely at physical "
                    f"line {source_row_number}: {exc}. No partial result was returned."
                ) from exc

            total += 1
            if len(fields) != len(PRISMA_EXPORT_COLUMNS):
                rejected += 1
                issues.append(
                    PrismaImportIssue(
                        source_row_number,
                        PrismaImportStatus.REJECTED,
                        "invalid_column_count",
                        "PRISMA export record has "
                        f"{len(fields)} fields; expected {len(PRISMA_EXPORT_COLUMNS)}.",
                    )
                )
                continue

            source = dict(zip(PRISMA_EXPORT_COLUMNS, fields, strict=True))
            try:
                rows.append(_import_row(source))
            except _RowRejected as exc:
                if exc.code == "capacity_below_threshold":
                    status = PrismaImportStatus.FILTERED
                    filtered += 1
                else:
                    status = PrismaImportStatus.REJECTED
                    rejected += 1
                issues.append(
                    PrismaImportIssue(
                        source_row_number,
                        status,
                        exc.code,
                        str(exc),
                    )
                )
    return PrismaImportResult(rows, total, len(rows), filtered, rejected, issues)


def process_csv(path: str | Path) -> list[dict[str, Any]]:
    return import_prisma_export(path).rows
