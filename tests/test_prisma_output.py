from __future__ import annotations

import csv
import os
from pathlib import Path

import pandas as pd
import pytest

from csv_contracts import PRISMA_EXPORT_COLUMNS
from download_directory import DownloadDirectoryError
from prisma_output import (
    OUTPUT_CSV_COLUMNS,
    PrismaOutputOutcome,
    build_output_filename,
    describe_output_failure,
    transform_row,
    write_prisma_output,
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


def write_csv(tmp_path: Path, rows: list[dict], name: str = "Auction_overview.csv") -> Path:
    path = tmp_path / name
    pd.DataFrame(rows).reindex(columns=PRISMA_EXPORT_COLUMNS).fillna("").to_csv(
        path, sep=";", encoding="cp1252", index=False
    )
    return path


def _read_output(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle, delimiter=";")
        rows = list(reader)
    header = rows[0]
    records = [dict(zip(header, row)) for row in rows[1:]]
    return header, records


# --- header / contract shape -------------------------------------------------

def test_output_columns_constant_is_exact_order() -> None:
    assert OUTPUT_CSV_COLUMNS == (
        "Auction Date", "Exit Market", "Entry Market", "Capacity Type",
        "Network Point Name", "Product Type", "Flow Start", "Flow End",
        "Booked Capacity", "Flow Duration Hours", "Tariff Price", "Premium Price",
    )


def test_written_header_matches_exact_contract_and_row_field_count(tmp_path: Path) -> None:
    source = write_csv(tmp_path, [BASE])
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    result = write_prisma_output(source, out_dir)
    assert result.succeeded
    header, records = _read_output(result.output_path)
    assert tuple(header) == OUTPUT_CSV_COLUMNS
    assert len(records) == 1
    assert len(records[0]) == 12


def test_output_is_utf8_and_semicolon_delimited(tmp_path: Path) -> None:
    source = write_csv(tmp_path, [BASE])
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    result = write_prisma_output(source, out_dir)
    raw = result.output_path.read_bytes()
    raw.decode("utf-8")  # must not raise
    text = raw.decode("utf-8")
    assert ";" in text.splitlines()[0]
    assert "," not in text.splitlines()[0]


# --- successful transformation -----------------------------------------------

def test_successful_transformation_maps_fields_correctly(tmp_path: Path) -> None:
    source = write_csv(tmp_path, [BASE])
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    result = write_prisma_output(source, out_dir)
    assert result.succeeded
    _, records = _read_output(result.output_path)
    row = records[0]
    assert row["Auction Date"] == "2025-01-01T09:00:00"
    assert row["Exit Market"] == ""
    assert row["Entry Market"] == "VGS Storage Hub"
    assert row["Capacity Type"] == "entry"
    assert row["Network Point Name"] == "VGS Storage Hub (4290)"
    assert row["Product Type"] == "Day Ahead"
    assert row["Flow Start"] == "2025-01-02T00:00:00"
    assert row["Flow End"] == "2025-01-03T00:00:00"
    assert row["Booked Capacity"] == "1000.0"
    assert row["Flow Duration Hours"] == "24.0"
    assert float(row["Tariff Price"]) == pytest.approx(20.0)
    assert float(row["Premium Price"]) == pytest.approx(5.0)


def test_transform_row_is_pure_field_mapping() -> None:
    row = {
        "auction_date": "2025-01-01T09:00:00", "exit_market": "BG", "entry_market": "",
        "direction": "exit", "network_point": "Point", "product_type": "Month",
        "flow_start": "2025-02-01T00:00:00", "flow_end": "2025-03-01T00:00:00",
        "booked_capacity_kwh_h": 2500.0, "runtime_hours": 672.0,
        "tariff_eur_mwh_h": 10.0, "premium_eur_mwh_h": 0.0,
    }
    assert transform_row(row) == {
        "Auction Date": "2025-01-01T09:00:00", "Exit Market": "BG", "Entry Market": "",
        "Capacity Type": "exit", "Network Point Name": "Point", "Product Type": "Month",
        "Flow Start": "2025-02-01T00:00:00", "Flow End": "2025-03-01T00:00:00",
        "Booked Capacity": "2500.0", "Flow Duration Hours": "672.0",
        "Tariff Price": "10.0", "Premium Price": "0.0",
    }


# --- market/storage placement by side ----------------------------------------

def test_entry_direction_populates_only_entry_market_with_storage_classification(tmp_path: Path) -> None:
    source = write_csv(tmp_path, [{**BASE, "Direction": "Entry"}])
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    result = write_prisma_output(source, out_dir)
    _, records = _read_output(result.output_path)
    assert records[0]["Exit Market"] == ""
    assert records[0]["Entry Market"] == "VGS Storage Hub"


def test_exit_direction_populates_only_exit_market_with_market_classification(tmp_path: Path) -> None:
    source = write_csv(tmp_path, [{
        **BASE, "Direction": "Exit",
        "Network Point Name Exit": "Kulata (BG)/Sidirokastron (GR)",
        "Network Point Name Entry": "",
    }])
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    result = write_prisma_output(source, out_dir)
    _, records = _read_output(result.output_path)
    assert records[0]["Exit Market"] == "BG"
    assert records[0]["Entry Market"] == ""
    assert records[0]["Capacity Type"] == "exit"


def test_bundle_direction_populates_both_sides_from_side_specific_evidence(tmp_path: Path) -> None:
    source = write_csv(tmp_path, [{
        **BASE, "Direction": "Exit/Entry",
        "Network Point Name Exit/Entry": "VGS Storage Hub (4290)",
        "Network Point Name Entry": "VGS Storage Hub (4290)",
        "Network Point Name Exit": "VGS Storage Hub (4290)",
    }])
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    result = write_prisma_output(source, out_dir)
    _, records = _read_output(result.output_path)
    assert records[0]["Exit Market"] == "VGS Storage Hub"
    assert records[0]["Entry Market"] == "VGS Storage Hub"
    assert records[0]["Capacity Type"] == "bundle"


# --- rejection behavior --------------------------------------------------

def test_unresolved_alias_row_is_excluded_from_output_but_recorded_as_rejected(tmp_path: Path) -> None:
    source = write_csv(tmp_path, [{
        **BASE, "Direction": "Entry", "Network Point Name Entry": "Totally Unknown Point",
    }])
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    result = write_prisma_output(source, out_dir)
    assert result.succeeded
    _, records = _read_output(result.output_path)
    assert records == []
    assert result.import_result.rejected_count == 1
    assert result.import_result.issues[0].reason_code == "unknown_entry_reference"


def test_missing_required_side_row_is_excluded_and_recorded(tmp_path: Path) -> None:
    source = write_csv(tmp_path, [{
        **BASE, "Direction": "Entry", "Network Point Name Entry": "",
    }])
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    result = write_prisma_output(source, out_dir)
    assert result.succeeded
    _, records = _read_output(result.output_path)
    assert records == []
    assert result.import_result.issues[0].reason_code == "missing_required_entry_reference"


def test_capacity_below_threshold_is_filtered_and_excluded(tmp_path: Path) -> None:
    source = write_csv(tmp_path, [{**BASE, "Marketed Capacity": "999"}])
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    result = write_prisma_output(source, out_dir)
    assert result.succeeded
    _, records = _read_output(result.output_path)
    assert records == []
    assert result.import_result.filtered_count == 1


def test_mixed_accepted_and_rejected_rows_only_writes_accepted(tmp_path: Path) -> None:
    good = BASE
    bad = {**BASE, "Network Point Name Entry": "Unknown Point"}
    source = write_csv(tmp_path, [good, bad])
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    result = write_prisma_output(source, out_dir)
    _, records = _read_output(result.output_path)
    assert len(records) == 1
    assert result.import_result.rejected_count == 1


def test_zero_accepted_rows_still_produces_header_only_output(tmp_path: Path) -> None:
    source = write_csv(tmp_path, [{**BASE, "Marketed Capacity": "1"}])
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    result = write_prisma_output(source, out_dir)
    assert result.succeeded
    header, records = _read_output(result.output_path)
    assert tuple(header) == OUTPUT_CSV_COLUMNS
    assert records == []


# --- source import failure ----------------------------------------------

def test_malformed_source_csv_fails_transformation_and_writes_nothing(tmp_path: Path) -> None:
    bad_source = tmp_path / "not_prisma.csv"
    bad_source.write_text("just,a,random,csv\n1,2,3,4\n", encoding="utf-8")
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    result = write_prisma_output(bad_source, out_dir)
    assert result.outcome is PrismaOutputOutcome.SOURCE_IMPORT_FAILED
    assert result.output_path is None
    assert list(out_dir.iterdir()) == []


def test_describe_output_failure_returns_stable_messages() -> None:
    for outcome in PrismaOutputOutcome:
        message = describe_output_failure(outcome)
        assert isinstance(message, str) and message


# --- destination validation ------------------------------------------------

def test_nonexistent_output_directory_is_rejected_without_writing(tmp_path: Path) -> None:
    source = write_csv(tmp_path, [BASE])
    missing_dir = tmp_path / "does_not_exist"
    result = write_prisma_output(source, missing_dir)
    assert result.outcome is PrismaOutputOutcome.INVALID_OUTPUT_DIRECTORY
    assert result.output_path is None
    assert not missing_dir.exists()


def test_file_as_output_directory_is_rejected(tmp_path: Path) -> None:
    source = write_csv(tmp_path, [BASE])
    not_a_dir = tmp_path / "file.txt"
    not_a_dir.write_text("x", encoding="utf-8")
    result = write_prisma_output(source, not_a_dir)
    assert result.outcome is PrismaOutputOutcome.INVALID_OUTPUT_DIRECTORY


def test_non_writable_output_directory_is_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = write_csv(tmp_path, [BASE])
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    real_access = os.access

    def fake_access(path, mode):
        if Path(path) == out_dir.resolve() and mode == os.W_OK:
            return False
        return real_access(path, mode)

    monkeypatch.setattr("prisma_output.os.access", fake_access)
    result = write_prisma_output(source, out_dir)
    assert result.outcome is PrismaOutputOutcome.INVALID_OUTPUT_DIRECTORY
    assert list(out_dir.iterdir()) == []


# --- naming / collision -----------------------------------------------------

def test_build_output_filename_uses_source_stem_with_transformed_suffix() -> None:
    assert build_output_filename("Auction_overview.csv") == "Auction_overview_transformed.csv"
    assert build_output_filename(Path("/x/y/Report.csv")) == "Report_transformed.csv"


def test_collision_never_overwrites_and_uses_incrementing_suffix(tmp_path: Path) -> None:
    source = write_csv(tmp_path, [BASE])
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    existing = out_dir / "Auction_overview_transformed.csv"
    existing.write_bytes(b"pre-existing content")

    result = write_prisma_output(source, out_dir)
    assert result.succeeded
    assert result.output_path.name == "Auction_overview_transformed_2.csv"
    assert existing.read_bytes() == b"pre-existing content"


def test_two_independent_calls_never_merge_or_deduplicate_across_operations(tmp_path: Path) -> None:
    """P.36.16 accumulation/deduplication must not be introduced by P.36.15."""
    source = write_csv(tmp_path, [BASE])
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    first = write_prisma_output(source, out_dir)
    second = write_prisma_output(source, out_dir)

    assert first.output_path != second.output_path
    _, first_records = _read_output(first.output_path)
    _, second_records = _read_output(second.output_path)
    assert len(first_records) == 1
    assert len(second_records) == 1
    # Each file independently contains exactly this operation's own row, not
    # an accumulated/merged total across both calls.
    assert first_records == second_records


# --- write failure / atomicity ----------------------------------------------

# A source with one accepted, one filtered (below-threshold), and one
# rejected (unknown alias) row, used by the write-failure tests below to
# prove the *complete* already-computed PrismaImportResult (not just a
# non-None placeholder) survives a failure that happens after
# import_prisma_export() already succeeded.
_MIXED_OUTCOME_ROWS = [
    BASE,
    {**BASE, "Marketed Capacity": "999"},
    {**BASE, "Network Point Name Entry": "Totally Unknown Point"},
]


def test_reservation_failure_returns_write_failed_with_the_completed_import_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = write_csv(tmp_path, _MIXED_OUTCOME_ROWS)
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    def failing_reserve(*_args, **_kwargs):
        raise OSError("simulated reservation failure")

    monkeypatch.setattr("prisma_output.reserve_unique_download_path", failing_reserve)
    result = write_prisma_output(source, out_dir)

    assert result.outcome is PrismaOutputOutcome.WRITE_FAILED
    assert result.output_path is None
    assert list(out_dir.iterdir()) == []
    assert result.import_result is not None
    assert (
        result.import_result.imported_count,
        result.import_result.filtered_count,
        result.import_result.rejected_count,
    ) == (1, 1, 1)
    assert result.import_result.rows[0]["auction_id"] == BASE["Auction ID"]
    assert {issue.reason_code for issue in result.import_result.issues} == {
        "capacity_below_threshold",
        "unknown_entry_reference",
    }


def test_write_failure_leaves_no_partial_final_output_and_cleans_temp_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = write_csv(tmp_path, _MIXED_OUTCOME_ROWS)
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    def failing_replace(*_args, **_kwargs):
        raise OSError("simulated disk failure")

    monkeypatch.setattr("prisma_output.os.replace", failing_replace)
    result = write_prisma_output(source, out_dir)

    assert result.outcome is PrismaOutputOutcome.WRITE_FAILED
    remaining = list(out_dir.iterdir())
    # The exclusively-reserved placeholder is removed on failure, and no
    # staged ".staging" temp file survives either.
    assert remaining == []
    # The already-completed PrismaImportResult (accepted, filtered, and
    # rejected outcomes alike) is preserved, not discarded, on this failure.
    assert result.import_result is not None
    assert (
        result.import_result.imported_count,
        result.import_result.filtered_count,
        result.import_result.rejected_count,
    ) == (1, 1, 1)
    assert result.import_result.rows[0]["auction_id"] == BASE["Auction ID"]
    assert {issue.reason_code for issue in result.import_result.issues} == {
        "capacity_below_threshold",
        "unknown_entry_reference",
    }


def test_write_failure_during_staging_cleans_up_staged_temp_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = write_csv(tmp_path, _MIXED_OUTCOME_ROWS)
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    real_writerows = csv.DictWriter.writerows

    def failing_writerows(self, rows):
        raise OSError("simulated write failure mid-stream")

    monkeypatch.setattr(csv.DictWriter, "writerows", failing_writerows)
    try:
        result = write_prisma_output(source, out_dir)
    finally:
        monkeypatch.setattr(csv.DictWriter, "writerows", real_writerows)

    assert result.outcome is PrismaOutputOutcome.WRITE_FAILED
    assert list(out_dir.iterdir()) == []
    assert result.import_result is not None
    assert (
        result.import_result.imported_count,
        result.import_result.filtered_count,
        result.import_result.rejected_count,
    ) == (1, 1, 1)


def test_successful_write_leaves_no_staging_artifacts(tmp_path: Path) -> None:
    source = write_csv(tmp_path, [BASE])
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    result = write_prisma_output(source, out_dir)
    names = [entry.name for entry in out_dir.iterdir()]
    assert names == [result.output_path.name]
    assert not any(name.endswith(".staging") for name in names)


# --- reference catalog injection --------------------------------------------

def test_custom_reference_catalog_is_honored(tmp_path: Path) -> None:
    catalog = PrismaReferenceCatalog((
        PrismaReference(
            "Custom Market",
            ReferenceClassification.MARKET,
            (ReferenceAlias("VGS Storage Hub (4290)", ReferenceSide.ENTRY),),
        ),
    ))
    source = write_csv(tmp_path, [BASE])
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    result = write_prisma_output(source, out_dir, reference_catalog=catalog)
    _, records = _read_output(result.output_path)
    assert records[0]["Entry Market"] == "Custom Market"
