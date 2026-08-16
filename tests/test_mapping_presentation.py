from __future__ import annotations

from pathlib import Path

from mapping_presentation import (
    MAPPING_DISPLAY_FIELDS,
    MappingDisplayRow,
    build_mapping_rows_from_output_records,
    load_mapping_rows_from_output_csv,
)
from prisma_output import OUTPUT_CSV_COLUMNS


def _record(**overrides: str) -> dict[str, str]:
    record = {
        "Auction Date": "2025-01-01",
        "Exit Market": "THE",
        "Entry Market": "PSV",
        "Capacity Type": "exit/entry",
        "Network Point Name": "Point A",
        "Product Type": "Day",
        "Flow Start": "2025-01-02 00:00",
        "Flow End": "2025-01-03 00:00",
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


def test_build_mapping_rows_maps_all_twelve_output_fields() -> None:
    rows = build_mapping_rows_from_output_records([_record()])
    assert rows == (
        MappingDisplayRow(
            "2025-01-01",
            "THE",
            "PSV",
            "exit/entry",
            "Point A",
            "Day",
            "2025-01-02 00:00",
            "2025-01-03 00:00",
            "1000.0",
            "24.0",
            "0.020000",
            "0.005000",
        ),
    )


def test_build_mapping_rows_orders_by_flow_start_descending_without_mutating_input() -> None:
    records = [
        _record(**{"Exit Market": "Jan", "Flow Start": "2025-01-01 00:00"}),
        _record(**{"Exit Market": "Mar", "Flow Start": "2025-03-01 00:00"}),
        _record(**{"Exit Market": "Feb", "Flow Start": "2025-02-01 00:00"}),
    ]
    rows = build_mapping_rows_from_output_records(records)
    assert [row.exit_market for row in rows] == ["Mar", "Feb", "Jan"]
    assert [row["Exit Market"] for row in records] == ["Jan", "Mar", "Feb"]


def test_load_mapping_rows_from_output_csv_reads_every_published_row(tmp_path: Path) -> None:
    path = tmp_path / "Prisma_Output_Published_EUR.csv"
    data_rows = [
        _record(
            **{
                "Exit Market": f"M{index:05d}",
                "Flow Start": f"2025-01-{(index % 28) + 1:02d} 00:00",
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
