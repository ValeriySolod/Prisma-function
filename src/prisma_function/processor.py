from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

from prisma_function.csv_contracts import CsvFormat, PRISMA_EXPORT_COLUMNS, require_csv_format
from prisma_function.entsog_market_resolution import resolve_entsog_market_pair
from prisma_function.prisma_datetime import (
    PrismaLocalTimestampAmbiguousError,
    PrismaLocalTimestampFormatError,
    PrismaLocalTimestampNonexistentError,
    elapsed_hours,
    format_auction_date,
    format_flow_timestamp,
    local_wall_clock_hours,
    parse_prisma_local_timestamp,
)
from prisma_function.prisma_references import (
    DEFAULT_PRISMA_REFERENCES,
    PrismaReferenceCatalog,
    ReferenceClassification,
    ReferenceSide,
)

MIN_MARKETED_CAPACITY_KWH_H = 1000.0

# P.37: unit string -> (ISO 4217 currency, physical-unit factor to MWh/h).
# Currency conversion itself never happens here (see price_normalization.py);
# this only unit-normalizes the source-currency amount, exactly as the
# pre-P.37 cent-only table already did. cent/pence/halér are minor units
# (÷100 implicit); CHF/100 states its own ÷100 explicitly in the unit
# string itself -- all four therefore share the same numeric factors.
# Only the exact "/Runtime"-suffixed strings evidenced in
# Auction_overview.csv are supported; ".../d/d" and ".../h/d" (no
# "/Runtime") stay unsupported, same as before P.37.
_PRICE_UNITS: dict[str, tuple[str, float]] = {
    "cent/kWh/h/Runtime": ("EUR", 10.0),
    "cent/kWh/d/Runtime": ("EUR", 10.0 / 24),
    "pence/kWh/h/Runtime": ("GBP", 10.0),
    "pence/kWh/d/Runtime": ("GBP", 10.0 / 24),
    "halér/kWh/h/Runtime": ("CZK", 10.0),
    "halér/kWh/d/Runtime": ("CZK", 10.0 / 24),
    "CHF/100/kWh/h/Runtime": ("CHF", 10.0),
    "CHF/100/kWh/d/Runtime": ("CHF", 10.0 / 24),
}


class PrismaImportStatus(str, Enum):
    IMPORTED = "imported"
    FILTERED = "filtered"
    REJECTED = "rejected"


class PrismaEnrichmentReasonCode(str, Enum):
    MISSING_REQUIRED_EXIT_REFERENCE = "missing_required_exit_reference"
    MISSING_REQUIRED_ENTRY_REFERENCE = "missing_required_entry_reference"
    UNKNOWN_EXIT_REFERENCE = "unknown_exit_reference"
    UNKNOWN_ENTRY_REFERENCE = "unknown_entry_reference"


class PrismaImportError(RuntimeError):
    """Raised when an export cannot be parsed safely as a complete import."""


@dataclass(frozen=True)
class PrismaImportIssue:
    source_row_number: int
    status: PrismaImportStatus
    reason_code: str | PrismaEnrichmentReasonCode
    message: str
    field_name: str | None = None
    side: str | None = None
    source_value: str | None = None


@dataclass(frozen=True)
class PrismaImportedRecord:
    """An enriched row paired with its unchanged source row and physical line."""

    source_row_number: int
    row: dict[str, Any]
    raw_row: Mapping[str, str]
    exit_reference: PrismaResolvedReference | None
    entry_reference: PrismaResolvedReference | None


@dataclass(frozen=True)
class PrismaResolvedReference:
    """A canonical, classified reference resolved for one capacity side."""

    canonical_name: str
    classification: ReferenceClassification
    side: ReferenceSide


@dataclass(frozen=True)
class PrismaImportResult:
    imported_rows: list[dict[str, Any]]
    total_source_rows: int
    imported_count: int
    filtered_count: int
    rejected_count: int
    issues: list[PrismaImportIssue]
    enriched_records: tuple[PrismaImportedRecord, ...] = ()

    @property
    def rows(self) -> list[dict[str, Any]]:
        """Compatibility-friendly shorthand for the imported rows."""
        return self.imported_rows


class _RowRejected(ValueError):
    def __init__(
        self,
        code: str | PrismaEnrichmentReasonCode,
        message: str,
        *,
        field_name: str | None = None,
        side: str | None = None,
        source_value: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.field_name = field_name
        self.side = side
        self.source_value = source_value


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
    title = label.replace("_", " ").title()
    try:
        return parse_prisma_local_timestamp(text)
    except PrismaLocalTimestampNonexistentError as exc:
        raise _RowRejected(f"nonexistent_{label}", f"{title} {exc}") from exc
    except PrismaLocalTimestampAmbiguousError as exc:
        raise _RowRejected(f"ambiguous_{label}", f"{title} {exc}") from exc
    except PrismaLocalTimestampFormatError as exc:
        raise _RowRejected(f"invalid_{label}", f"{title} {exc}") from exc


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
    id_field = f"Network Point ID {suffix}"
    original_point_id = "" if row.get(id_field) is None else str(row[id_field])
    point_id = _text(original_point_id)
    if not name:
        side = direction if direction in ("entry", "exit") else None
        code: str | PrismaEnrichmentReasonCode = "missing_network_point"
        if side == "entry":
            code = PrismaEnrichmentReasonCode.MISSING_REQUIRED_ENTRY_REFERENCE
        elif side == "exit":
            code = PrismaEnrichmentReasonCode.MISSING_REQUIRED_EXIT_REFERENCE
        raise _RowRejected(
            code,
            "The selected network-point name is empty.",
            field_name=f"Network Point Name {suffix}",
            side=side,
            source_value="",
        )
    if not point_id:
        raise _RowRejected(
            "missing_network_point_id",
            "The selected network-point ID is empty.",
            field_name=id_field,
            side=direction if direction in ("entry", "exit") else None,
            source_value=original_point_id,
        )
    return direction, name, point_id


def _product_type(auction_date: datetime, start: datetime, wall_clock_hours: float) -> str:
    # Classification thresholds are, and always have been, defined in local
    # Europe/Berlin wall-clock hours (see `prisma_datetime.local_wall_clock_hours`),
    # deliberately independent of `runtime_hours`/`Flow Duration Hours`'s real
    # DST-aware elapsed time, so a boundary case does not silently shift
    # buckets merely because its interval happens to cross a DST transition.
    if wall_clock_hours <= 24:
        return "WD" if start.date() == auction_date.date() else "Day Ahead"
    if wall_clock_hours <= 31 * 24:
        return "Month"
    if wall_clock_hours <= 93 * 24:
        return "Quarter"
    return "Year"


@dataclass(frozen=True)
class _ParsedPrice:
    """One already-unit-normalized (cent/pence/halér/CHF-100 -> main
    currency unit, kWh -> MWh) source-currency price field, plus the ISO
    4217 currency it was denominated in. ``currency == ""`` means the field
    was entirely absent (both value and unit blank); a present field always
    carries one of `_PRICE_UNITS`'s currencies, never a guessed or unknown
    one, since `_price()` rejects the row for any other unit string.
    """

    value_mwh_h: float
    currency: str


def _price(row: dict[str, Any], value_field: str, unit_field: str, *, label: str) -> _ParsedPrice:
    value_text = _text(row.get(value_field))
    unit = _text(row.get(unit_field))
    if not value_text and not unit:
        return _ParsedPrice(0.0, "")
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
    parsed = _PRICE_UNITS.get(unit)
    if parsed is None:
        raise _RowRejected(
            f"unsupported_{label}_unit",
            f"Unsupported {label.replace('_', ' ')} unit: {unit}.",
        )
    currency, factor = parsed
    return _ParsedPrice(_number(value_text, label=label) * factor, currency)


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
    runtime_hours = elapsed_hours(flow_start, flow_end)
    if not math.isfinite(runtime_hours) or runtime_hours <= 0:
        raise _RowRejected("non_positive_runtime", "Product runtime must be positive and finite.")
    wall_clock_hours = local_wall_clock_hours(flow_start, flow_end)
    # P.37: exit and entry tariff are parsed and kept independently -- never
    # summed here -- because a bundle (`Direction == "Exit/Entry"`) row's two
    # sides may be denominated in different currencies. Only
    # `price_normalization.py` may sum them, and only after each side has
    # already been independently converted to EUR.
    tariff_exit = _price(
        source,
        "Regulated Tariff Exit TSO",
        "Unit Regulated Exit Capacity Tariff",
        label="exit_tariff",
    )
    tariff_entry = _price(
        source,
        "Regulated Tariff Entry TSO",
        "Unit Regulated Entry Capacity Tariff",
        label="entry_tariff",
    )
    premium = _price(source, "Surcharge", "Unit Surcharge", label="surcharge")
    return {
        "auction_id": auction_id,
        "auction_date": format_auction_date(auction_date),
        "exit_market": "",
        "entry_market": "",
        "direction": direction,
        "network_point": network_point,
        "network_point_id": network_point_id,
        "tso_exit": _text(source.get("TSO Exit")),
        "tso_entry": _text(source.get("TSO Entry")),
        "product_type": _product_type(auction_date, flow_start, wall_clock_hours),
        "flow_start": format_flow_timestamp(flow_start),
        "flow_end": format_flow_timestamp(flow_end),
        "booked_capacity_kwh_h": marketed,
        "runtime_hours": runtime_hours,
        # Physical-unit-normalized (cent/pence/halér/CHF-100 per kWh/h[/d] ->
        # main-currency-unit per MWh/h) source-currency prices, kept
        # side-independent for tariff (exit/entry may differ in currency on
        # a bundle row) and with their own resolved ISO 4217 currency. Not
        # EUR: no currency conversion has happened yet. See
        # `price_normalization.py` (P.37/P.36.21) for the single place that
        # converts these to EUR/MWh/h, using the ECB rate resolved for this
        # row's own `auction_date` and each price's own currency.
        "tariff_exit_source_mwh_h": tariff_exit.value_mwh_h,
        "tariff_exit_currency": tariff_exit.currency,
        "tariff_entry_source_mwh_h": tariff_entry.value_mwh_h,
        "tariff_entry_currency": tariff_entry.currency,
        "premium_source_mwh_h": premium.value_mwh_h,
        "premium_currency": premium.currency,
        # LEGACY (pre-P.37): the currency-blind sum of both tariff sides,
        # kept only for `storage.py`'s dormant `auctions`/Excel export path,
        # which never claimed EUR correctness even before P.37 (see
        # `storage.py`'s `_LEGACY_PRICE_FIELD_ALIASES` docstring). Never used
        # by the active EUR-normalized output.
        "tariff_source_mwh_h": tariff_exit.value_mwh_h + tariff_entry.value_mwh_h,
        "state": _text(source.get("State")),
    }


def _entsog_pair_for_required_side(
    row: dict[str, Any], source: dict[str, Any]
):
    """Resolve the ENTSOG-based market pair from the row's own required side
    (the only side a unidirectional row populates), or `None` when the row
    is a two-sided Exit/Entry bundle -- which keeps its existing direct
    per-side resolution and never reaches ENTSOG resolution -- or when
    nothing can be resolved. See `entsog_market_resolution.py`.
    """
    if row["direction"] not in ("exit", "entry"):
        return None
    suffix = "Exit" if row["direction"] == "exit" else "Entry"
    return resolve_entsog_market_pair(
        point_eic=_text(source.get(f"Network Point EIC {suffix}")),
        tso_eic=_text(source.get(f"TSO EIC {suffix}")),
        tso_name=_text(source.get(f"TSO {suffix}")),
        direction=row["direction"],
        point_type=_text(source.get(f"Network Point Type {suffix}")),
    )


def _enrich_row(
    row: dict[str, Any],
    source: dict[str, Any],
    catalog: PrismaReferenceCatalog,
) -> tuple[
    dict[str, Any],
    PrismaResolvedReference | None,
    PrismaResolvedReference | None,
]:
    required_sides = {
        "exit": (ReferenceSide.EXIT,),
        "entry": (ReferenceSide.ENTRY,),
        "bundle": (ReferenceSide.EXIT, ReferenceSide.ENTRY),
    }[row["direction"]]
    entsog_pair = _entsog_pair_for_required_side(row, source)

    def _entsog_value(side: ReferenceSide) -> str | None:
        if entsog_pair is None:
            return None
        value = entsog_pair.exit_market if side is ReferenceSide.EXIT else entsog_pair.entry_market
        return value or None

    # `resolved` is the audit trail returned as exit_reference/entry_reference:
    # "what did we identify this side as" -- a STORAGE-classified entry means
    # the point is a known storage facility (already fully represented by the
    # unchanged `Network Point Name` output column), a MARKET-classified entry
    # means a real balancing-zone/trading-hub name. `market_values` is the
    # separate, narrower set of strings actually written into Exit Market/
    # Entry Market: only ever populated from a MARKET-classified source.
    # Storage evidence -- whether from the legacy evidence-based string
    # catalog or (implicitly, since it never produces one) ENTSOG -- must
    # never populate a Market column; the approved RESERVOIR mapping requires
    # the transmission operator's own balancing zone there instead, supplied
    # exclusively by the ENTSOG resolver.
    resolved: dict[ReferenceSide, PrismaResolvedReference] = {}
    market_values: dict[ReferenceSide, str] = {}
    # Exit Market/Entry Market are each populated from their own exact,
    # side-specific field (`Network Point Name Exit`/`Network Point Name
    # Entry`) regardless of Direction: a side not required by Direction is
    # still attempted here, but never blocks the row when its own field is
    # blank or its value has no approved catalog match -- that side's market
    # is simply left blank. Only a side Direction actually requires still
    # rejects the row on the same blank/unknown conditions, exactly as
    # before. Neither side is ever inferred/cross-filled from the other via
    # the string-alias catalog; the ENTSOG-based fallback below is the one
    # explicitly approved exception, deriving the opposite side only from
    # the required side's own EIC/TSO/Direction evidence, never from a
    # guess.
    for side in (ReferenceSide.EXIT, ReferenceSide.ENTRY):
        required = side in required_sides
        field_name = f"Network Point Name {side.value.title()}"
        original_value = "" if source.get(field_name) is None else str(source[field_name])
        if not original_value.strip():
            if not required:
                continue
            code = (
                PrismaEnrichmentReasonCode.MISSING_REQUIRED_EXIT_REFERENCE
                if side is ReferenceSide.EXIT
                else PrismaEnrichmentReasonCode.MISSING_REQUIRED_ENTRY_REFERENCE
            )
            raise _RowRejected(
                code,
                f"Direction {row['direction']} requires a populated {side.value}-side "
                f"reference in {field_name}.",
                field_name=field_name,
                side=side.value,
                source_value=original_value,
            )
        reference = catalog.lookup(original_value, side)
        entsog_value = _entsog_value(side) if required else None
        if reference is None:
            if entsog_value is not None:
                resolved[side] = PrismaResolvedReference(
                    entsog_value, ReferenceClassification.MARKET, side
                )
                market_values[side] = entsog_value
                continue
            if not required:
                continue
            code = (
                PrismaEnrichmentReasonCode.UNKNOWN_EXIT_REFERENCE
                if side is ReferenceSide.EXIT
                else PrismaEnrichmentReasonCode.UNKNOWN_ENTRY_REFERENCE
            )
            raise _RowRejected(
                code,
                f"Unknown {side.value}-side market/storage reference in {field_name}: "
                f"{original_value}.",
                field_name=field_name,
                side=side.value,
                source_value=original_value,
            )
        resolved[side] = PrismaResolvedReference(
            reference.canonical_name, reference.classification, side
        )
        if reference.classification is ReferenceClassification.STORAGE:
            # Storage identity confirmed by the legacy catalog; the Market
            # column must still come exclusively from the ENTSOG resolver's
            # transmission-operator balancing zone (never the storage
            # facility's own label). Blank when ENTSOG cannot resolve it --
            # the row stays accepted (the point itself is known), only its
            # Market is fail-closed blank.
            if entsog_value is not None:
                market_values[side] = entsog_value
        else:
            market_values[side] = reference.canonical_name

    # BORDER_TRANSITION_POINT/RESERVOIR only: fill the opposite (non-
    # required) side from the same ENTSOG evidence the required side was
    # just resolved from -- e.g. the adjacent balancing zone for a border
    # point, or nothing at all for a RESERVOIR point, whose opposite side
    # stays blank by rule (`resolve_entsog_market_pair` itself never returns
    # a RESERVOIR opposite-side value). Only applies when that side is not
    # already resolved (a populated opposite-side field with its own
    # catalog/ENTSOG match above always wins) and never overwrites it.
    if row["direction"] in ("exit", "entry"):
        required_side = ReferenceSide.EXIT if row["direction"] == "exit" else ReferenceSide.ENTRY
        opposite_side = (
            ReferenceSide.ENTRY if required_side is ReferenceSide.EXIT else ReferenceSide.EXIT
        )
        if opposite_side not in resolved:
            opposite_value = _entsog_value(opposite_side)
            if opposite_value is not None:
                resolved[opposite_side] = PrismaResolvedReference(
                    opposite_value, ReferenceClassification.MARKET, opposite_side
                )
                market_values[opposite_side] = opposite_value

    enriched = dict(row)
    exit_reference = resolved.get(ReferenceSide.EXIT)
    entry_reference = resolved.get(ReferenceSide.ENTRY)
    enriched["exit_market"] = market_values.get(ReferenceSide.EXIT, "")
    enriched["entry_market"] = market_values.get(ReferenceSide.ENTRY, "")
    return enriched, exit_reference, entry_reference


def import_prisma_export(
    path: str | Path,
    *,
    reference_catalog: PrismaReferenceCatalog = DEFAULT_PRISMA_REFERENCES,
) -> PrismaImportResult:
    require_csv_format(path, CsvFormat.PRISMA_EXPORT)
    rows: list[dict[str, Any]] = []
    records: list[PrismaImportedRecord] = []
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
                imported = _import_row(source)
                enriched, exit_reference, entry_reference = _enrich_row(
                    imported, source, reference_catalog
                )
                rows.append(enriched)
                records.append(
                    PrismaImportedRecord(
                        source_row_number,
                        enriched,
                        MappingProxyType(dict(source)),
                        exit_reference,
                        entry_reference,
                    )
                )
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
                        exc.field_name,
                        exc.side,
                        exc.source_value,
                    )
                )
    return PrismaImportResult(
        rows, total, len(rows), filtered, rejected, issues, tuple(records)
    )


def process_csv(path: str | Path) -> list[dict[str, Any]]:
    return import_prisma_export(path).rows
