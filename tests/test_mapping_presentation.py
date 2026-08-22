from __future__ import annotations

from pathlib import Path

from prisma_function.mapping_presentation import (
    MAPPING_DISPLAY_FIELDS,
    MappingDisplayRow,
    build_mapping_rows_from_output_records,
    load_mapping_rows_from_output_csv,
)
from prisma_function.prisma_output import OUTPUT_CSV_COLUMNS


def _record(**overrides: str) -> dict[str, str]:
    record = {
        "Auction Date": "01-01-2025",
        "Exit Market": "THE",
        "Entry Market": "PSV",
        "Capacity Type": "exit/entry",
        "Network Point Name": "Point A",
        "Product Type": "Day",
        "Flow Start": "02-01-2025 00:00",
        "Flow End": "03-01-2025 00:00",
        "Booked Capacity": "1000.0",
        "Flow Duration Hours": "24.0",
        "Tariff Price": "0.020000",
        "Premium Price": "0.005000",
    }
    record.update(overrides)
    return record


def test_mapping_display_fields_match_authoritative_output_contract() -> None:
    assert MAPPING_DISPLAY_FIELDS == OUTPUT_CSV_COLUMNS
    assert MAPPING_DISPLAY_FIELDS == (
        "Auction Date",
        "Exit Market",
        "Entry Market",
        "Capacity Type",
        "Network Point Name",
        "Product Type",
        "Flow Start",
        "Flow End",
        "Booked Capacity",
        "Flow Duration Hours",
        "Tariff Price",
        "Premium Price",
    )


def test_build_mapping_rows_formats_booked_capacity_to_one_decimal_place() -> None:
    rows = build_mapping_rows_from_output_records(
        [_record(**{"Booked Capacity": "1089601.0416666665"})]
    )
    assert rows[0].booked_capacity == "1089601.0"


def test_build_mapping_rows_leaves_unparseable_booked_capacity_unchanged() -> None:
    rows = build_mapping_rows_from_output_records([_record(**{"Booked Capacity": ""})])
    assert rows[0].booked_capacity == ""


def test_build_mapping_rows_maps_all_twelve_output_fields() -> None:
    rows = build_mapping_rows_from_output_records([_record()])
    assert rows == (
        MappingDisplayRow(
            "01-01-2025",
            "THE",
            "PSV",
            "exit/entry",
            "Point A",
            "Day",
            "02-01-2025 00:00",
            "03-01-2025 00:00",
            "1000.0",
            "24.0",
            "0.020000",
            "0.005000",
        ),
    )


def test_build_mapping_rows_orders_by_flow_start_descending_without_mutating_input() -> None:
    records = [
        _record(**{"Exit Market": "Jan", "Flow Start": "01-01-2025 00:00"}),
        _record(**{"Exit Market": "Mar", "Flow Start": "01-03-2025 00:00"}),
        _record(**{"Exit Market": "Feb", "Flow Start": "01-02-2025 00:00"}),
    ]
    rows = build_mapping_rows_from_output_records(records)
    assert [row.exit_market for row in rows] == ["Mar", "Feb", "Jan"]
    assert [row["Exit Market"] for row in records] == ["Jan", "Mar", "Feb"]


# --- backward-compatible legacy/new date-format handling ---------------------

def test_build_mapping_rows_sorts_mixed_legacy_and_new_flow_start_formats() -> None:
    # Cumulative published data may contain rows written under either
    # contract: the legacy `YYYY-MM-DD HH:mm` (pre-format-correction) and the
    # new `DD-MM-YYYY HH:mm` (this increment onward). Both must sort into one
    # correct chronological (descending) order without raising.
    records = [
        _record(**{"Exit Market": "Jan-legacy", "Flow Start": "2025-01-01 00:00"}),
        _record(**{"Exit Market": "Mar-new", "Flow Start": "01-03-2025 00:00"}),
        _record(**{"Exit Market": "Feb-legacy", "Flow Start": "2025-02-01 00:00"}),
    ]
    rows = build_mapping_rows_from_output_records(records)
    assert [row.exit_market for row in rows] == ["Mar-new", "Feb-legacy", "Jan-legacy"]
    # Sorting is by the actual parsed timestamp regardless of source
    # contract, but every displayed value is converted to the current
    # `DD-MM-YYYY HH:mm` display format -- including legacy rows, whose
    # underlying stored/published record is never rewritten by this
    # in-memory conversion.
    assert [row.flow_start for row in rows] == [
        "01-03-2025 00:00", "01-02-2025 00:00", "01-01-2025 00:00",
    ]


def test_build_mapping_rows_keeps_blank_or_malformed_flow_start_displayable() -> None:
    # A blank or unparseable Flow Start must not raise out of sorting (which
    # would make the whole Mapping output undisplayable over one bad row);
    # it is placed after every row with a valid Flow Start, and every row
    # (including the bad one) is still present with its own field values.
    records = [
        _record(**{"Exit Market": "Valid", "Flow Start": "01-01-2025 00:00"}),
        _record(**{"Exit Market": "Blank", "Flow Start": ""}),
        _record(**{"Exit Market": "Malformed", "Flow Start": "not a date"}),
    ]
    rows = build_mapping_rows_from_output_records(records)
    assert len(rows) == 3
    assert rows[0].exit_market == "Valid"
    # Stable sort: the two unparseable rows keep their original relative
    # order (Blank before Malformed) among themselves.
    assert [row.exit_market for row in rows[1:]] == ["Blank", "Malformed"]
    assert {row.flow_start for row in rows} == {"01-01-2025 00:00", "", "not a date"}


def test_build_mapping_rows_keeps_blank_or_malformed_auction_date_displayable() -> None:
    # Same never-raise guarantee as Flow Start, applied to Auction Date: a
    # blank or unparseable value is displayed unchanged instead of failing
    # the whole Mapping build.
    records = [
        _record(**{"Exit Market": "Legacy", "Auction Date": "2025-01-10"}),
        _record(**{"Exit Market": "Blank", "Auction Date": ""}),
        _record(**{"Exit Market": "Malformed", "Auction Date": "not a date"}),
    ]
    rows = build_mapping_rows_from_output_records(records)
    assert len(rows) == 3
    by_market = {row.exit_market: row.auction_date for row in rows}
    assert by_market == {
        "Legacy": "10-01-2025",
        "Blank": "",
        "Malformed": "not a date",
    }


def test_load_mapping_rows_from_output_csv_reads_every_published_row(tmp_path: Path) -> None:
    path = tmp_path / "Prisma_Output_Published_EUR.csv"
    data_rows = [
        _record(
            **{
                "Exit Market": f"M{index:05d}",
                "Flow Start": f"{(index % 28) + 1:02d}-01-2025 00:00",
                "Booked Capacity": str(1000 + index),
            }
        )
        for index in range(5001)
    ]
    path.write_text(
        ";".join(OUTPUT_CSV_COLUMNS)
        + "\n"
        + "\n".join(";".join(row.values()) for row in data_rows)
        + "\n",
        encoding="utf-8",
    )

    rows = load_mapping_rows_from_output_csv(path)

    assert len(rows) == 5001
    assert {row.exit_market for row in rows} == {f"M{index:05d}" for index in range(5001)}


def test_load_mapping_rows_from_output_csv_reads_mixed_legacy_and_new_published_rows(
    tmp_path: Path,
) -> None:
    # Regression: a cumulative file containing rows published before this
    # increment (legacy `YYYY-MM-DD`/`YYYY-MM-DD HH:mm`) alongside rows
    # published after it (new `DD-MM-YYYY`/`DD-MM-YYYY HH:mm`) must remain
    # fully readable and displayable, not raise and clear the whole Mapping.
    path = tmp_path / "Prisma_Output_Published_EUR.csv"
    data_rows = [
        _record(**{
            "Exit Market": "Legacy",
            "Auction Date": "2025-01-01",
            "Flow Start": "2025-01-02 00:00",
            "Flow End": "2025-01-03 00:00",
        }),
        _record(**{
            "Exit Market": "New",
            "Auction Date": "05-01-2025",
            "Flow Start": "06-01-2025 00:00",
            "Flow End": "07-01-2025 00:00",
        }),
    ]
    original_text = (
        ";".join(OUTPUT_CSV_COLUMNS)
        + "\n"
        + "\n".join(";".join(row.values()) for row in data_rows)
        + "\n"
    )
    path.write_text(original_text, encoding="utf-8")

    rows = load_mapping_rows_from_output_csv(path)

    assert len(rows) == 2
    # Newer Flow Start (New, 06-01-2025) sorts first.
    assert [row.exit_market for row in rows] == ["New", "Legacy"]
    # Both rows display in the current `DD-MM-YYYY`/`DD-MM-YYYY HH:mm`
    # format, including the legacy row -- but the file on disk is untouched.
    assert rows[0].auction_date == "05-01-2025"
    assert rows[0].flow_start == "06-01-2025 00:00"
    assert rows[0].flow_end == "07-01-2025 00:00"
    assert rows[1].auction_date == "01-01-2025"
    assert rows[1].flow_start == "02-01-2025 00:00"
    assert rows[1].flow_end == "03-01-2025 00:00"
    assert path.read_text(encoding="utf-8") == original_text


def test_load_mapping_rows_from_output_csv_converts_legacy_rows_without_modifying_source(
    tmp_path: Path,
) -> None:
    # Regression: a legacy stored/published row (all three date/time fields
    # in the pre-format-correction `YYYY-MM-DD`/`YYYY-MM-DD HH:mm` contract)
    # must appear in the Mapping display using the new `DD-MM-YYYY`/
    # `DD-MM-YYYY HH:mm` format, while the underlying published CSV file is
    # never rewritten, migrated, or otherwise modified by loading it.
    path = tmp_path / "Prisma_Output_Published_EUR.csv"
    legacy_row = _record(**{
        "Auction Date": "2025-06-15",
        "Flow Start": "2025-06-16 06:00",
        "Flow End": "2025-06-17 06:00",
    })
    original_text = (
        ";".join(OUTPUT_CSV_COLUMNS) + "\n" + ";".join(legacy_row.values()) + "\n"
    )
    path.write_text(original_text, encoding="utf-8")

    rows = load_mapping_rows_from_output_csv(path)

    assert len(rows) == 1
    assert rows[0].auction_date == "15-06-2025"
    assert rows[0].flow_start == "16-06-2025 06:00"
    assert rows[0].flow_end == "17-06-2025 06:00"
    # The source file itself is byte-for-byte unchanged -- only the in-memory
    # Mapping rows are converted for display.
    assert path.read_text(encoding="utf-8") == original_text
