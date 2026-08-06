from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from csv_contracts import PRISMA_EXPORT_COLUMNS
from mapping_presentation import (
    MAPPING_DISPLAY_FIELDS,
    MappingDisplayRow,
    build_mapping_rows,
)
from processor import PrismaImportIssue, PrismaImportResult, PrismaImportStatus, import_prisma_export

BASE = {
    "Auction ID": "1", "Start of Auction": "01.01.2025 09:00",
    "Marketed Capacity": "1000", "Unit Marketed Capacity": "kWh/h",
    "Product Runtime Start": "02.01.2025 00:00", "Product Runtime End": "03.01.2025 00:00",
    "Regulated Tariff Exit TSO": "1,25", "Unit Regulated Exit Capacity Tariff": "cent/kWh/h/Runtime",
    "Regulated Tariff Entry TSO": "0.75", "Unit Regulated Entry Capacity Tariff": "cent/kWh/h/Runtime",
    "Surcharge": "0,5", "Unit Surcharge": "cent/kWh/h/Runtime",
}


def write_csv(tmp_path: Path, rows: list[dict], name: str = "Auction_overview.csv") -> Path:
    path = tmp_path / name
    pd.DataFrame(rows).reindex(columns=PRISMA_EXPORT_COLUMNS).fillna("").to_csv(
        path, sep=";", encoding="cp1252", index=False
    )
    return path


# --- MAPPING_DISPLAY_FIELDS contract -----------------------------------------

def test_mapping_display_fields_exact_order_and_spelling() -> None:
    assert MAPPING_DISPLAY_FIELDS == (
        "Exit Market", "Entry Market", "Network Point Name",
        "TSO Name Exit", "TSO Name Entry",
    )


# --- pure field mapping and ordering (no processor/catalog involved) --------

def _row(**overrides) -> dict:
    row = {
        "exit_market": "", "entry_market": "", "network_point": "",
        "tso_exit": "", "tso_entry": "", "flow_start": "2025-01-01T00:00:00",
    }
    row.update(overrides)
    return row


def _result(rows: list[dict]) -> PrismaImportResult:
    return PrismaImportResult(
        imported_rows=rows, total_source_rows=len(rows), imported_count=len(rows),
        filtered_count=0, rejected_count=0, issues=[],
    )


def test_build_mapping_rows_maps_fields_in_exact_order() -> None:
    result = _result([
        _row(
            exit_market="CEGH", entry_market="PSV", network_point="Point A",
            tso_exit="TSO-A", tso_entry="TSO-B",
        ),
    ])
    rows = build_mapping_rows(result)
    assert rows == (
        MappingDisplayRow("CEGH", "PSV", "Point A", "TSO-A", "TSO-B"),
    )


def test_build_mapping_rows_preserves_row_order_across_multiple_rows() -> None:
    result = _result([
        _row(exit_market="A"), _row(exit_market="B"), _row(exit_market="C"),
    ])
    rows = build_mapping_rows(result)
    assert [row.exit_market for row in rows] == ["A", "B", "C"]


def test_build_mapping_rows_empty_accepted_result_returns_empty_tuple() -> None:
    result = PrismaImportResult(
        imported_rows=[], total_source_rows=0, imported_count=0,
        filtered_count=0, rejected_count=0, issues=[],
    )
    assert build_mapping_rows(result) == ()


def test_build_mapping_rows_filtered_and_rejected_only_result_is_empty() -> None:
    result = PrismaImportResult(
        imported_rows=[], total_source_rows=2, imported_count=0,
        filtered_count=1, rejected_count=1,
        issues=[
            PrismaImportIssue(2, PrismaImportStatus.FILTERED, "capacity_below_threshold", "x"),
            PrismaImportIssue(3, PrismaImportStatus.REJECTED, "unknown_entry_reference", "y"),
        ],
    )
    assert build_mapping_rows(result) == ()


def test_build_mapping_rows_does_not_swap_or_infer_across_sides() -> None:
    # An entry-only row has no exit-side evidence at all: the exit fields must
    # stay exactly empty, never inferred/copied from the entry side.
    result = _result([
        _row(exit_market="", entry_market="VGS Storage Hub", tso_exit="", tso_entry="GUD"),
    ])
    row = build_mapping_rows(result)[0]
    assert row.exit_market == ""
    assert row.tso_name_exit == ""
    assert row.entry_market == "VGS Storage Hub"
    assert row.tso_name_entry == "GUD"


# --- P.36.18: Flow Start descending ordering ---------------------------------

def test_build_mapping_rows_orders_by_flow_start_descending() -> None:
    result = _result([
        _row(exit_market="Jan", flow_start="2025-01-01T00:00:00"),
        _row(exit_market="Mar", flow_start="2025-03-01T00:00:00"),
        _row(exit_market="Feb", flow_start="2025-02-01T00:00:00"),
    ])
    rows = build_mapping_rows(result)
    assert [row.exit_market for row in rows] == ["Mar", "Feb", "Jan"]


def test_build_mapping_rows_equal_flow_start_preserves_original_order() -> None:
    result = _result([
        _row(exit_market="A", flow_start="2025-06-01T00:00:00"),
        _row(exit_market="B", flow_start="2025-06-01T00:00:00"),
        _row(exit_market="C", flow_start="2025-06-01T00:00:00"),
    ])
    rows = build_mapping_rows(result)
    assert [row.exit_market for row in rows] == ["A", "B", "C"]


def test_build_mapping_rows_sorting_keeps_complete_row_data_together() -> None:
    result = _result([
        _row(
            exit_market="Early", entry_market="Early-Entry", network_point="Early-Point",
            tso_exit="Early-TSO-X", tso_entry="Early-TSO-Y", flow_start="2025-01-01T00:00:00",
        ),
        _row(
            exit_market="Late", entry_market="Late-Entry", network_point="Late-Point",
            tso_exit="Late-TSO-X", tso_entry="Late-TSO-Y", flow_start="2025-12-01T00:00:00",
        ),
    ])
    rows = build_mapping_rows(result)
    assert rows == (
        MappingDisplayRow("Late", "Late-Entry", "Late-Point", "Late-TSO-X", "Late-TSO-Y"),
        MappingDisplayRow("Early", "Early-Entry", "Early-Point", "Early-TSO-X", "Early-TSO-Y"),
    )


def test_build_mapping_rows_single_row_input_is_valid() -> None:
    result = _result([_row(exit_market="Only", flow_start="2025-05-01T00:00:00")])
    rows = build_mapping_rows(result)
    assert [row.exit_market for row in rows] == ["Only"]


def test_build_mapping_rows_does_not_mutate_import_result_rows_order() -> None:
    imported_rows = [
        _row(exit_market="Jan", flow_start="2025-01-01T00:00:00"),
        _row(exit_market="Mar", flow_start="2025-03-01T00:00:00"),
    ]
    result = _result(imported_rows)
    build_mapping_rows(result)
    assert [row["exit_market"] for row in result.imported_rows] == ["Jan", "Mar"]


# --- integration through the real P.36.15 import/enrichment boundary --------

def test_exit_only_row_resolves_market_through_exit_market_field(tmp_path: Path) -> None:
    row = {
        **BASE, "Auction ID": "111", "Direction": "Exit",
        "Network Point Name Exit": "VIP DK-THE (H646) (H646)", "Network Point ID Exit": "EXIT-1",
        "TSO Exit": "GTE", "TSO Entry": "",
    }
    source = write_csv(tmp_path, [row])
    imported = import_prisma_export(source)
    assert imported.rejected_count == 0 and imported.filtered_count == 0
    display = build_mapping_rows(imported)
    assert display == (
        MappingDisplayRow("THE", "", "VIP DK-THE (H646) (H646)", "GTE", ""),
    )


def test_entry_only_row_resolves_storage_through_entry_market_field(tmp_path: Path) -> None:
    row = {
        **BASE, "Auction ID": "222", "Direction": "Entry",
        "Network Point Name Entry": "VGS Storage Hub (4290)", "Network Point ID Entry": "ENTRY-1",
        "TSO Exit": "", "TSO Entry": "GUD",
    }
    source = write_csv(tmp_path, [row])
    imported = import_prisma_export(source)
    assert imported.rejected_count == 0 and imported.filtered_count == 0
    display = build_mapping_rows(imported)
    assert display == (
        MappingDisplayRow("", "VGS Storage Hub", "VGS Storage Hub (4290)", "", "GUD"),
    )


def test_bundle_row_resolves_each_side_independently_with_no_cross_side_leakage(
    tmp_path: Path,
) -> None:
    # "Arnoldstein Exit" is a real evidenced alias on BOTH sides in the
    # authoritative catalog, but resolves to a DIFFERENT canonical name on
    # each side (CEGH on exit, PSV on entry). A bundle row using the exact
    # same source string on both sides must resolve them independently.
    row = {
        **BASE, "Auction ID": "333", "Direction": "Exit/Entry",
        "Network Point Name Exit": "Arnoldstein Exit", "Network Point ID Exit": "EXIT-2",
        "Network Point Name Entry": "Arnoldstein Exit", "Network Point ID Entry": "ENTRY-2",
        "Network Point Name Exit/Entry": "Arnoldstein Bundle Point",
        "Network Point ID Exit/Entry": "BUNDLE-2",
        "TSO Exit": "TSO-A", "TSO Entry": "TSO-B",
    }
    source = write_csv(tmp_path, [row])
    imported = import_prisma_export(source)
    assert imported.rejected_count == 0 and imported.filtered_count == 0
    display = build_mapping_rows(imported)
    assert display == (
        MappingDisplayRow(
            "CEGH", "PSV", "Arnoldstein Bundle Point", "TSO-A", "TSO-B",
        ),
    )


def test_multiple_accepted_rows_preserve_import_order(tmp_path: Path) -> None:
    rows = [
        {
            **BASE, "Auction ID": "441", "Direction": "Exit",
            "Network Point Name Exit": "VIP DK-THE (H646) (H646)", "Network Point ID Exit": "EXIT-1",
        },
        {
            **BASE, "Auction ID": "442", "Direction": "Entry",
            "Network Point Name Entry": "VGS Storage Hub (4290)", "Network Point ID Entry": "ENTRY-1",
        },
    ]
    source = write_csv(tmp_path, rows)
    imported = import_prisma_export(source)
    display = build_mapping_rows(imported)
    assert [row.network_point_name for row in display] == [
        "VIP DK-THE (H646) (H646)", "VGS Storage Hub (4290)",
    ]


def test_build_mapping_rows_orders_chronologically_not_lexically_through_real_pipeline(
    tmp_path: Path,
) -> None:
    # "01.12.2025" (1 Dec 2025) sorts lexically BEFORE "12.01.2025" (12 Jan
    # 2025) as raw DD.MM.YYYY strings, since '0' < '1' in the first
    # character. Chronologically 12 Jan 2025 is earlier than 1 Dec 2025, so a
    # correct descending-by-date sort must put 1 Dec 2025 first even though a
    # naive lexical sort of the formatted strings would disagree.
    # Both are real evidenced exit aliases in the authoritative catalog
    # (resolving to distinct canonical markets, THE and CEGH), so this
    # exercises the real side-specific resolution boundary, not invented data.
    december_row = {
        **BASE, "Auction ID": "601", "Direction": "Exit",
        "Start of Auction": "01.12.2025 09:00",
        "Product Runtime Start": "01.12.2025 10:00", "Product Runtime End": "01.12.2025 11:00",
        "Network Point Name Exit": "VIP DK-THE (H646) (H646)", "Network Point ID Exit": "EXIT-1",
    }
    january_row = {
        **BASE, "Auction ID": "602", "Direction": "Exit",
        "Start of Auction": "12.01.2025 09:00",
        "Product Runtime Start": "12.01.2025 10:00", "Product Runtime End": "12.01.2025 11:00",
        "Network Point Name Exit": "Baumgarten WAG AT->SK", "Network Point ID Exit": "EXIT-2",
    }
    # Source order is January-then-December, the opposite of both the
    # expected chronological-descending display order and the wrong lexical
    # order, so this cannot pass by accident.
    source = write_csv(tmp_path, [january_row, december_row])
    imported = import_prisma_export(source)
    assert imported.rejected_count == 0 and imported.filtered_count == 0
    display = build_mapping_rows(imported)
    assert [row.exit_market for row in display] == ["THE", "CEGH"]
    # The underlying accepted rows keep the original source/import order.
    assert [row["exit_market"] for row in imported.rows] == ["CEGH", "THE"]


def test_filtered_and_rejected_rows_are_excluded_from_the_real_pipeline(
    tmp_path: Path,
) -> None:
    filtered = {
        **BASE, "Auction ID": "551", "Direction": "Entry", "Marketed Capacity": "10",
        "Network Point Name Entry": "VGS Storage Hub (4290)", "Network Point ID Entry": "ENTRY-1",
    }
    rejected = {
        **BASE, "Auction ID": "552", "Direction": "Entry",
        "Network Point Name Entry": "Unknown Point XYZ", "Network Point ID Entry": "ENTRY-2",
    }
    source = write_csv(tmp_path, [filtered, rejected])
    imported = import_prisma_export(source)
    assert imported.filtered_count == 1
    assert imported.rejected_count == 1
    assert build_mapping_rows(imported) == ()
