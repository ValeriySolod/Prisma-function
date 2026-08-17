from __future__ import annotations

import csv
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import pytest

from csv_contracts import MONITORING_CSV_COLUMNS, PRISMA_EXPORT_COLUMNS, CsvFormatError
from processor import (
    PrismaImportError,
    PrismaImportStatus,
    import_prisma_export,
    process_csv,
)
from prisma_references import (
    PrismaReference,
    PrismaReferenceCatalog,
    ReferenceAlias,
    ReferenceClassification,
    ReferenceSide,
)

BASE = {
    "Auction ID": "000123456789012345", "Start of Auction": "01.01.2025 09:00",
    "Marketed Capacity": "1000", "Unit Marketed Capacity": "kWh/h",
    "Product Runtime Start": "02.01.2025 00:00", "Product Runtime End": "03.01.2025 00:00",
    "Direction": "Entry", "Network Point Name Entry": "VGS Storage Hub (4290)",
    "Network Point ID Entry": "ENTRY-ID", "Network Point Name Exit": "",
    "Network Point ID Exit": "EXIT-ID", "Network Point Name Exit/Entry": "Bundle point",
    "Network Point ID Exit/Entry": "BUNDLE-ID", "Regulated Tariff Exit TSO": "1,25",
    "Unit Regulated Exit Capacity Tariff": "cent/kWh/h/Runtime",
    "Regulated Tariff Entry TSO": "0.75",
    "Unit Regulated Entry Capacity Tariff": "cent/kWh/h/Runtime", "Surcharge": "0,5",
    "Unit Surcharge": "cent/kWh/h/Runtime",
}


def write_csv(tmp_path: Path, rows: list[dict]) -> Path:
    path = tmp_path / "Auction_overview.csv"
    pd.DataFrame(rows).reindex(columns=PRISMA_EXPORT_COLUMNS).fillna("").to_csv(
        path, sep=";", encoding="cp1252", index=False
    )
    return path


def test_detailed_result_classifies_every_row_and_preserves_id(tmp_path: Path) -> None:
    rows = [BASE, {**BASE, "Marketed Capacity": "999"}, {**BASE, "Direction": "sideways"}]
    result = import_prisma_export(write_csv(tmp_path, rows))
    assert (result.total_source_rows, result.imported_count, result.filtered_count, result.rejected_count) == (3, 1, 1, 1)
    assert result.total_source_rows == result.imported_count + result.filtered_count + result.rejected_count
    assert result.rows[0]["auction_id"] == "000123456789012345"
    assert [
        (issue.source_row_number, issue.status, issue.reason_code)
        for issue in result.issues
    ] == [
        (3, PrismaImportStatus.FILTERED, "capacity_below_threshold"),
        (4, PrismaImportStatus.REJECTED, "unsupported_direction"),
    ]
    for issue in result.issues:
        assert issue.message
        assert "000123456789012345" not in issue.message


def test_import_prisma_export_reads_past_5000_rows_until_end_of_file(tmp_path: Path) -> None:
    rows = [
        {
            **BASE,
            "Auction ID": f"A-{index:05d}",
            "Network Point ID Entry": f"ENTRY-{index:05d}",
            "Marketed Capacity": str(1000 + index),
        }
        for index in range(5001)
    ]

    result = import_prisma_export(write_csv(tmp_path, rows))

    assert result.total_source_rows == 5001
    assert result.imported_count == 5001
    assert result.filtered_count == 0
    assert result.rejected_count == 0
    assert len(result.rows) == 5001
    assert result.rows[-1]["auction_id"] == "A-05000"


@pytest.mark.parametrize(("direction", "normalized", "point", "point_id"), [
    ("Entry", "entry", "VGS Storage Hub (4290)", "ENTRY-ID"),
    ("Exit", "exit", "VGS Storage Hub (4290)", "EXIT-ID"),
    ("Exit/Entry", "bundle", "Bundle point", "BUNDLE-ID"),
])
def test_all_directions_select_their_own_network_point(tmp_path: Path, direction: str, normalized: str, point: str, point_id: str) -> None:
    source = {**BASE, "Direction": direction}
    if direction == "Entry":
        source["Network Point Name Exit"] = ""
    elif direction == "Exit":
        source["Network Point Name Exit"] = "VGS Storage Hub (4290)"
        source["Network Point Name Entry"] = ""
    else:
        source["Network Point Name Exit"] = "VGS Storage Hub (4290)"
        source["Network Point Name Entry"] = "VGS Storage Hub (4290)"
    row = process_csv(write_csv(tmp_path, [source]))[0]
    assert (row["direction"], row["network_point"], row["network_point_id"]) == (normalized, point, point_id)


@pytest.mark.parametrize(("direction", "field", "side"), [
    ("Entry", "Network Point ID Entry", "entry"),
    ("Exit", "Network Point ID Exit", "exit"),
    ("Exit/Entry", "Network Point ID Exit/Entry", None),
])
@pytest.mark.parametrize("source_value", ["", " \t "])
def test_blank_selected_network_point_id_is_audited(
    tmp_path: Path, direction: str, field: str, side: str | None, source_value: str
) -> None:
    source = {**BASE, "Direction": direction, field: source_value}
    if direction == "Exit":
        source["Network Point Name Exit"] = "VGS Storage Hub (4290)"
    result = import_prisma_export(write_csv(tmp_path, [source]))
    issue = result.issues[0]
    assert (result.imported_count, result.rejected_count) == (0, 1)
    assert (issue.reason_code, issue.message) == (
        "missing_network_point_id",
        "The selected network-point ID is empty.",
    )
    assert (issue.field_name, issue.side, issue.source_value) == (
        field,
        side,
        source_value,
    )


@pytest.mark.parametrize(("direction", "name_field", "id_field", "code"), [
    (
        "Entry",
        "Network Point Name Entry",
        "Network Point ID Entry",
        "missing_required_entry_reference",
    ),
    (
        "Exit",
        "Network Point Name Exit",
        "Network Point ID Exit",
        "missing_required_exit_reference",
    ),
    (
        "Exit/Entry",
        "Network Point Name Exit/Entry",
        "Network Point ID Exit/Entry",
        "missing_network_point",
    ),
])
def test_blank_selected_name_takes_precedence_over_blank_selected_id(
    tmp_path: Path, direction: str, name_field: str, id_field: str, code: str
) -> None:
    result = import_prisma_export(write_csv(tmp_path, [{
        **BASE,
        "Direction": direction,
        name_field: "",
        id_field: "",
    }]))

    issue = result.issues[0]
    assert issue.reason_code == code
    assert issue.field_name == name_field


def test_selected_network_point_id_preserves_valid_text(tmp_path: Path) -> None:
    row = process_csv(write_csv(tmp_path, [{
        **BASE, "Network Point ID Entry": "  000123-A  "
    }]))[0]
    assert row["network_point_id"] == "000123-A"


@pytest.mark.parametrize(("capacity", "unit", "expected"), [
    ("1000", "kWh/h", 1000.0), ("1", "MWh/h", 1000.0), ("24000", "kWh/d", 1000.0),
])
def test_capacity_conversions_and_exact_threshold(tmp_path: Path, capacity: str, unit: str, expected: float) -> None:
    row = process_csv(write_csv(tmp_path, [{**BASE, "Marketed Capacity": capacity, "Unit Marketed Capacity": unit}]))[0]
    assert row["booked_capacity_kwh_h"] == expected


@pytest.mark.parametrize(("capacity", "unit", "status"), [
    ("999", "kWh/h", PrismaImportStatus.FILTERED),
    ("", "kWh/h", PrismaImportStatus.REJECTED), ("bad", "kWh/h", PrismaImportStatus.REJECTED),
    ("-1", "kWh/h", PrismaImportStatus.REJECTED), ("NaN", "kWh/h", PrismaImportStatus.REJECTED),
    ("Infinity", "kWh/h", PrismaImportStatus.REJECTED), ("1000", "therms", PrismaImportStatus.REJECTED),
])
def test_invalid_capacity_is_explicit(tmp_path: Path, capacity: str, unit: str, status: PrismaImportStatus) -> None:
    result = import_prisma_export(write_csv(tmp_path, [{**BASE, "Marketed Capacity": capacity, "Unit Marketed Capacity": unit}]))
    assert result.rows == [] and result.issues[0].status is status


@pytest.mark.parametrize(("start", "duration", "expected"), [
    (datetime(2025, 1, 1, 10), timedelta(hours=24), "WD"),
    (datetime(2025, 1, 2), timedelta(hours=24), "Day Ahead"),
    (datetime(2025, 1, 2), timedelta(days=31), "Month"),
    (datetime(2025, 1, 2), timedelta(days=31, minutes=1), "Quarter"),
    # These two boundary cases start in January and their 93-day span crosses
    # the 2025-03-30 Europe/Berlin spring DST transition on purpose: Product
    # Type classification is defined in LOCAL WALL-CLOCK hours (see
    # `processor._product_type`/`prisma_datetime.local_wall_clock_hours`),
    # deliberately independent of `runtime_hours`/`Flow Duration Hours`'s real
    # DST-aware elapsed time, so these boundary cases must classify exactly as
    # they did before the DST-aware duration correction, unaffected by the
    # transition they happen to cross.
    (datetime(2025, 1, 2), timedelta(days=93), "Quarter"),
    (datetime(2025, 1, 2), timedelta(days=93, minutes=1), "Year"),
])
def test_product_type_boundaries(tmp_path: Path, start: datetime, duration: timedelta, expected: str) -> None:
    row = {**BASE, "Product Runtime Start": start.strftime("%d.%m.%Y %H:%M"), "Product Runtime End": (start + duration).strftime("%d.%m.%Y %H:%M")}
    assert process_csv(write_csv(tmp_path, [row]))[0]["product_type"] == expected


def test_product_type_boundary_crossing_spring_dst_uses_wall_clock_not_real_elapsed_hours(
    tmp_path: Path,
) -> None:
    # Same exact interval as the restored "Year" boundary case above
    # (2025-01-02 + 93 days + 1 minute), asserted together with its Flow
    # Duration Hours to make the wall-clock-vs-real-elapsed distinction
    # explicit in one place: Product Type still reflects the 93*24h+1min
    # local wall-clock duration ("Year"), while Flow Duration Hours reflects
    # the real elapsed time, which is exactly one hour less because the
    # interval crosses the 2025-03-30 spring-forward transition.
    start = datetime(2025, 1, 2)
    end = start + timedelta(days=93, minutes=1)
    row = {
        **BASE,
        "Product Runtime Start": start.strftime("%d.%m.%Y %H:%M"),
        "Product Runtime End": end.strftime("%d.%m.%Y %H:%M"),
    }
    result = process_csv(write_csv(tmp_path, [row]))[0]
    wall_clock_hours = 93 * 24 + 1 / 60
    assert result["product_type"] == "Year"
    assert result["runtime_hours"] == pytest.approx(wall_clock_hours - 1)


def test_product_type_boundary_at_exactly_93_days_crossing_spring_dst_remains_quarter(
    tmp_path: Path,
) -> None:
    # Same exact interval as the restored "Quarter" boundary case above
    # (2025-01-02 + exactly 93 days).
    start = datetime(2025, 1, 2)
    end = start + timedelta(days=93)
    row = {
        **BASE,
        "Product Runtime Start": start.strftime("%d.%m.%Y %H:%M"),
        "Product Runtime End": end.strftime("%d.%m.%Y %H:%M"),
    }
    result = process_csv(write_csv(tmp_path, [row]))[0]
    assert result["product_type"] == "Quarter"
    assert result["runtime_hours"] == pytest.approx(93 * 24 - 1)


@pytest.mark.parametrize(("field", "value"), [
    ("Product Runtime Start", "1.01.2025 00:00"), ("Product Runtime End", "invalid"),
    ("Product Runtime End", "02.01.2025 00:00"), ("Product Runtime End", "01.01.2025 23:59"),
])
def test_strict_dates_and_positive_runtime(tmp_path: Path, field: str, value: str) -> None:
    result = import_prisma_export(write_csv(tmp_path, [{**BASE, field: value}]))
    assert result.rejected_count == 1


def test_flow_before_auction_calendar_date_is_rejected(tmp_path: Path) -> None:
    row = {
        **BASE,
        "Product Runtime Start": "31.12.2024 23:00",
        "Product Runtime End": "01.01.2025 01:00",
    }
    result = import_prisma_export(write_csv(tmp_path, [row]))
    assert result.issues[0].reason_code == "flow_before_auction_date"
    assert result.issues[0].message == (
        "Product flow starts on a calendar date before the auction date."
    )


@pytest.mark.parametrize(("unit", "currency", "factor"), [
    ("cent/kWh/h/Runtime", "EUR", 10), ("cent/kWh/d/Runtime", "EUR", 10 / 24),
    ("pence/kWh/h/Runtime", "GBP", 10), ("pence/kWh/d/Runtime", "GBP", 10 / 24),
    ("halér/kWh/h/Runtime", "CZK", 10), ("halér/kWh/d/Runtime", "CZK", 10 / 24),
    ("CHF/100/kWh/h/Runtime", "CHF", 10), ("CHF/100/kWh/d/Runtime", "CHF", 10 / 24),
])
def test_tariff_and_surcharge_conversions(
    tmp_path: Path, unit: str, currency: str, factor: float
) -> None:
    row = {**BASE, "Regulated Tariff Exit TSO": "1", "Unit Regulated Exit Capacity Tariff": unit,
           "Regulated Tariff Entry TSO": "2", "Unit Regulated Entry Capacity Tariff": unit,
           "Surcharge": "3", "Unit Surcharge": unit}
    result = process_csv(write_csv(tmp_path, [row]))[0]
    assert result["tariff_exit_source_mwh_h"] == pytest.approx(1 * factor)
    assert result["tariff_exit_currency"] == currency
    assert result["tariff_entry_source_mwh_h"] == pytest.approx(2 * factor)
    assert result["tariff_entry_currency"] == currency
    assert result["premium_source_mwh_h"] == pytest.approx(3 * factor)
    assert result["premium_currency"] == currency
    # LEGACY (pre-P.37, dormant `auctions`-table path): the currency-blind
    # sum of both tariff sides, unchanged in value from before P.37.
    assert result["tariff_source_mwh_h"] == pytest.approx(3 * factor)


def test_bundle_exit_and_entry_tariff_and_currency_stay_independent_when_currencies_differ(
    tmp_path: Path,
) -> None:
    row = {
        **BASE,
        "Regulated Tariff Exit TSO": "1", "Unit Regulated Exit Capacity Tariff": "pence/kWh/h/Runtime",
        "Regulated Tariff Entry TSO": "2", "Unit Regulated Entry Capacity Tariff": "cent/kWh/h/Runtime",
    }
    result = process_csv(write_csv(tmp_path, [row]))[0]
    assert (result["tariff_exit_source_mwh_h"], result["tariff_exit_currency"]) == (10.0, "GBP")
    assert (result["tariff_entry_source_mwh_h"], result["tariff_entry_currency"]) == (20.0, "EUR")
    # LEGACY sum is still the currency-blind addition of both sides, exactly
    # as before P.37 -- only `price_normalization.py` may treat these two
    # currencies independently.
    assert result["tariff_source_mwh_h"] == pytest.approx(30.0)


def test_empty_price_unit_pairs_are_zero(tmp_path: Path) -> None:
    row = {**BASE, "Regulated Tariff Exit TSO": "", "Unit Regulated Exit Capacity Tariff": "",
           "Regulated Tariff Entry TSO": "", "Unit Regulated Entry Capacity Tariff": "",
           "Surcharge": "", "Unit Surcharge": ""}
    result = process_csv(write_csv(tmp_path, [row]))[0]
    assert (result["tariff_source_mwh_h"], result["premium_source_mwh_h"]) == (0, 0)
    assert (result["tariff_exit_currency"], result["tariff_entry_currency"], result["premium_currency"]) == (
        "", "", "",
    )


def test_present_zero_price_has_nonblank_currency(tmp_path: Path) -> None:
    row = {**BASE, "Surcharge": "0", "Unit Surcharge": "cent/kWh/h/Runtime"}
    result = process_csv(write_csv(tmp_path, [row]))[0]
    assert (result["premium_source_mwh_h"], result["premium_currency"]) == (0.0, "EUR")


def test_empty_price_with_present_unit_has_auditable_rejection(tmp_path: Path) -> None:
    row = {**BASE, "Surcharge": "", "Unit Surcharge": "cent/kWh/h/Runtime"}
    result = import_prisma_export(write_csv(tmp_path, [row]))
    issue = result.issues[0]
    assert (issue.source_row_number, issue.status, issue.reason_code) == (
        2,
        PrismaImportStatus.REJECTED,
        "empty_surcharge",
    )
    assert issue.message == "Surcharge is empty while its unit is present."


@pytest.mark.parametrize(("value", "unit"), [
    ("1", ""), ("1", "USD/kWh/h/Runtime"),
    # CHF without the literal "/100" segment stays unsupported -- the unit
    # string itself, not just the currency name, must match exactly.
    ("1", "CHF/kWh/h/Runtime"),
    # "/d/d" and "/h/d" (no "/Runtime" suffix) stay unsupported, unchanged
    # from before P.37.
    ("1", "cent/kWh/d/d"), ("1", "cent/kWh/h/d"),
    ("1", "pence/kWh/d/d"), ("1", "halér/kWh/h/d"),
    ("bad", "cent/kWh/h/Runtime"), ("-1", "cent/kWh/h/Runtime"),
    ("NaN", "cent/kWh/h/Runtime"), ("Infinity", "cent/kWh/h/Runtime"),
])
def test_invalid_or_unsupported_price_is_rejected(tmp_path: Path, value: str, unit: str) -> None:
    row = {**BASE, "Surcharge": value, "Unit Surcharge": unit}
    assert import_prisma_export(write_csv(tmp_path, [row])).rejected_count == 1


def test_bad_rows_are_isolated_without_loss(tmp_path: Path) -> None:
    bad = {**BASE, "Auction ID": "bad", "Product Runtime Start": "not a date"}
    result = import_prisma_export(write_csv(tmp_path, [bad, BASE, BASE]))
    assert result.total_source_rows == 3 and result.imported_count == 2 and result.rejected_count == 1


def test_missing_auction_id_has_stable_audit_issue(tmp_path: Path) -> None:
    result = import_prisma_export(write_csv(tmp_path, [{**BASE, "Auction ID": ""}]))
    issue = result.issues[0]
    assert (issue.source_row_number, issue.reason_code, issue.message) == (
        2,
        "missing_auction_id",
        "Auction ID is empty.",
    )


def test_blank_unknown_direction_and_missing_selected_name_are_rejected(tmp_path: Path) -> None:
    rows = [{**BASE, "Direction": ""}, {**BASE, "Direction": "Other"}, {**BASE, "Network Point Name Entry": ""}]
    assert import_prisma_export(write_csv(tmp_path, rows)).rejected_count == 3


def test_header_only_export(tmp_path: Path) -> None:
    result = import_prisma_export(write_csv(tmp_path, []))
    assert (result.rows, result.total_source_rows, result.imported_count, result.filtered_count, result.rejected_count, result.issues) == ([], 0, 0, 0, 0, [])


@pytest.mark.parametrize("field_delta", [-1, 1])
def test_invalid_column_count_is_rejected_and_counted(
    tmp_path: Path, field_delta: int
) -> None:
    path = write_csv(tmp_path, [BASE])
    lines = path.read_text(encoding="cp1252").splitlines()
    fields = next(csv.reader([lines[1]], delimiter=";"))
    if field_delta < 0:
        fields.pop()
    else:
        fields.append("unexpected")
    with path.open("a", encoding="cp1252", newline="") as csv_file:
        csv.writer(csv_file, delimiter=";", lineterminator="\n").writerow(fields)

    result = import_prisma_export(path)
    issue = result.issues[0]
    assert (result.total_source_rows, result.imported_count, result.rejected_count) == (
        2,
        1,
        1,
    )
    assert result.total_source_rows == (
        result.imported_count + result.filtered_count + result.rejected_count
    )
    assert (issue.source_row_number, issue.reason_code) == (3, "invalid_column_count")
    assert f"{len(PRISMA_EXPORT_COLUMNS) + field_delta} fields" in issue.message
    assert f"expected {len(PRISMA_EXPORT_COLUMNS)}" in issue.message


def test_embedded_newline_uses_record_starting_physical_line(tmp_path: Path) -> None:
    path = write_csv(tmp_path, [{**BASE, "Network Point Name Entry": "München\nSouth"}])
    with path.open("a", encoding="cp1252", newline="") as csv_file:
        csv.writer(csv_file, delimiter=";", lineterminator="\n").writerow(["too", "few"])
    catalog = PrismaReferenceCatalog((PrismaReference(
        "München South", ReferenceClassification.MARKET,
        (ReferenceAlias("München\nSouth", ReferenceSide.ENTRY),),
    ),))
    result = import_prisma_export(path, reference_catalog=catalog)
    assert result.rows[0]["network_point"] == "München\nSouth"
    assert result.issues[0].source_row_number == 4


def test_unrecoverable_csv_error_raises_clear_import_error(tmp_path: Path) -> None:
    path = write_csv(tmp_path, [])
    with path.open("a", encoding="cp1252", newline="") as csv_file:
        csv_file.write('"unterminated')
    with pytest.raises(
        PrismaImportError,
        match=r"could not be parsed safely at physical line 2:.*No partial result",
    ):
        import_prisma_export(path)


def test_incomplete_header_is_rejected_at_processor_boundary(tmp_path: Path) -> None:
    path = tmp_path / "incomplete.csv"
    columns = [column for column in PRISMA_EXPORT_COLUMNS if column != "Direction"]
    pd.DataFrame([BASE]).reindex(columns=columns).to_csv(
        path, sep=";", encoding="cp1252", index=False
    )
    with pytest.raises(
        CsvFormatError,
        match="PRISMA Export CSV header is incomplete; missing columns: Direction",
    ):
        import_prisma_export(path)


def test_wrong_csv_contract_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "monitoring.csv"
    path.write_text(",".join(MONITORING_CSV_COLUMNS) + "\n", encoding="utf-8")
    with pytest.raises(CsvFormatError, match="detected monitoring"):
        import_prisma_export(path)


def test_process_csv_compatibility_and_output_keys(tmp_path: Path) -> None:
    result = process_csv(write_csv(tmp_path, [BASE]))
    assert isinstance(result, list) and isinstance(result[0], dict)
    assert set(result[0]) == {
        "auction_id", "auction_date", "exit_market", "entry_market", "direction",
        "network_point", "network_point_id", "tso_exit", "tso_entry", "product_type",
        "flow_start", "flow_end", "booked_capacity_kwh_h", "runtime_hours",
        "tariff_exit_source_mwh_h", "tariff_exit_currency",
        "tariff_entry_source_mwh_h", "tariff_entry_currency",
        "premium_source_mwh_h", "premium_currency",
        "tariff_source_mwh_h", "state",
    }


def test_cp1252_text_and_numeric_prices_are_preserved(tmp_path: Path) -> None:
    catalog = PrismaReferenceCatalog((PrismaReference(
        "München", ReferenceClassification.MARKET,
        (ReferenceAlias("München", ReferenceSide.ENTRY),),
    ),))
    row = import_prisma_export(
        write_csv(tmp_path, [{**BASE, "Network Point Name Entry": "München"}]),
        reference_catalog=catalog,
    ).rows[0]
    assert row["network_point"] == "München"
    assert (row["auction_date"], row["flow_start"], row["flow_end"]) == (
        "2025-01-01",
        "2025-01-02 00:00",
        "2025-01-03 00:00",
    )
    assert row["tariff_source_mwh_h"] == 20.0
    assert row["premium_source_mwh_h"] == 5.0
    assert isinstance(row["tariff_source_mwh_h"], float)
    assert isinstance(row["premium_source_mwh_h"], float)


# --- P.36 output date/time contract (Europe/Berlin, YYYY-MM-DD / YYYY-MM-DD HH:mm) ---


def test_auction_date_is_exactly_yyyy_mm_dd(tmp_path: Path) -> None:
    row = process_csv(write_csv(tmp_path, [BASE]))[0]
    assert row["auction_date"] == "2025-01-01"


def test_flow_start_and_end_are_exactly_yyyy_mm_dd_hh_mm(tmp_path: Path) -> None:
    row = process_csv(write_csv(tmp_path, [BASE]))[0]
    assert row["flow_start"] == "2025-01-02 00:00"
    assert row["flow_end"] == "2025-01-03 00:00"


@pytest.mark.parametrize("field", ["auction_date", "flow_start", "flow_end"])
def test_output_datetime_fields_never_contain_t_seconds_or_offset(tmp_path: Path, field: str) -> None:
    row = process_csv(write_csv(tmp_path, [BASE]))[0]
    value = row[field]
    assert "T" not in value
    assert "+" not in value
    assert value.count(":") <= 1


def test_normal_cet_period_input_is_interpreted_correctly(tmp_path: Path) -> None:
    # 10 January 2026 is standard time (CET, UTC+1) in Europe/Berlin.
    row = {
        **BASE,
        "Start of Auction": "10.01.2026 09:00",
        "Product Runtime Start": "10.01.2026 10:00",
        "Product Runtime End": "10.01.2026 16:00",
    }
    result = process_csv(write_csv(tmp_path, [row]))[0]
    assert (result["auction_date"], result["flow_start"], result["flow_end"]) == (
        "2026-01-10", "2026-01-10 10:00", "2026-01-10 16:00",
    )
    assert result["runtime_hours"] == 6.0


def test_normal_cest_period_input_is_interpreted_correctly(tmp_path: Path) -> None:
    # 10 July 2026 is daylight-saving time (CEST, UTC+2) in Europe/Berlin.
    row = {
        **BASE,
        "Start of Auction": "10.07.2026 09:00",
        "Product Runtime Start": "10.07.2026 10:00",
        "Product Runtime End": "10.07.2026 16:00",
    }
    result = process_csv(write_csv(tmp_path, [row]))[0]
    assert (result["auction_date"], result["flow_start"], result["flow_end"]) == (
        "2026-07-10", "2026-07-10 10:00", "2026-07-10 16:00",
    )
    assert result["runtime_hours"] == 6.0


def test_flow_duration_hours_correct_across_spring_dst_transition(tmp_path: Path) -> None:
    # Europe/Berlin spring-forward in 2026 is 2026-03-29 (clocks jump
    # 02:00 CET -> 03:00 CEST); the wall-clock difference (3 hours) is one
    # hour more than the true elapsed time (2 hours) because of the jump.
    row = {
        **BASE,
        "Start of Auction": "28.03.2026 09:00",
        "Product Runtime Start": "29.03.2026 01:00",
        "Product Runtime End": "29.03.2026 04:00",
    }
    result = process_csv(write_csv(tmp_path, [row]))[0]
    assert result["runtime_hours"] == 2.0


def test_flow_duration_hours_correct_across_autumn_dst_transition(tmp_path: Path) -> None:
    # Europe/Berlin autumn-back in 2026 is 2026-10-25 (clocks fall back
    # 03:00 CEST -> 02:00 CET); both endpoints below are unambiguous
    # (before and after the overlap), and the true elapsed time (4 hours)
    # is one hour more than the wall-clock difference (3 hours).
    row = {
        **BASE,
        "Start of Auction": "24.10.2026 09:00",
        "Product Runtime Start": "25.10.2026 01:00",
        "Product Runtime End": "25.10.2026 04:00",
    }
    result = process_csv(write_csv(tmp_path, [row]))[0]
    assert result["runtime_hours"] == 4.0


def test_nonexistent_local_time_is_rejected(tmp_path: Path) -> None:
    # 2026-03-29 02:30 does not exist in Europe/Berlin (spring-forward gap).
    row = {**BASE, "Product Runtime Start": "29.03.2026 02:30"}
    result = import_prisma_export(write_csv(tmp_path, [row]))
    assert result.rows == []
    issue = result.issues[0]
    assert issue.reason_code == "nonexistent_flow_start"
    assert "does not exist" in issue.message


def test_ambiguous_local_time_is_rejected(tmp_path: Path) -> None:
    # 2026-10-25 02:30 occurs twice in Europe/Berlin (autumn-back overlap),
    # and no authoritative rule resolves which of the two instants applies.
    row = {**BASE, "Product Runtime Start": "25.10.2026 02:30"}
    result = import_prisma_export(write_csv(tmp_path, [row]))
    assert result.rows == []
    issue = result.issues[0]
    assert issue.reason_code == "ambiguous_flow_start"
    assert "ambiguous" in issue.message


def test_invalid_datetime_input_remains_a_typed_row_rejection(tmp_path: Path) -> None:
    row = {**BASE, "Product Runtime Start": "not a date"}
    result = import_prisma_export(write_csv(tmp_path, [row]))
    assert result.rows == []
    assert result.issues[0].reason_code == "invalid_flow_start"
