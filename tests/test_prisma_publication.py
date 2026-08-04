from __future__ import annotations

import csv
import os
from pathlib import Path

import pandas as pd
import pytest

from csv_contracts import PRISMA_EXPORT_COLUMNS
from download_directory import DownloadDirectoryError
from processor import PrismaImportResult, import_prisma_export
from prisma_output import OUTPUT_CSV_COLUMNS
from prisma_publication import (
    PUBLISHED_OUTPUT_FILENAME,
    PrismaPublicationOutcome,
    describe_publication_failure,
    publish_cumulative_output,
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


def import_result_for(tmp_path: Path, rows: list[dict], name: str = "Auction_overview.csv") -> PrismaImportResult:
    source = write_csv(tmp_path, rows, name=name)
    return import_prisma_export(source)


def _read_published(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle, delimiter=";")
        rows = list(reader)
    header = rows[0]
    records = [dict(zip(header, row)) for row in rows[1:]]
    return header, records


def _import_row(**overrides) -> dict:
    """A minimal already-enriched row shape (see `prisma_output.transform_row`),
    used to exercise `publish_cumulative_output` directly without routing
    through the full CSV-import pipeline, for tests that only care about the
    cumulative-file read/merge/write behavior itself."""
    base = {
        "auction_date": "2025-01-01T09:00:00",
        "exit_market": "",
        "entry_market": "Entry Market",
        "direction": "entry",
        "network_point": "Network Point",
        "product_type": "Day Ahead",
        "flow_start": "2025-01-02T00:00:00",
        "flow_end": "2025-01-03T00:00:00",
        "booked_capacity_kwh_h": 1000.0,
        "runtime_hours": 24.0,
        "tariff_eur_mwh_h": 20.0,
        "premium_eur_mwh_h": 5.0,
    }
    base.update(overrides)
    return base


def make_import_result(rows: list[dict]) -> PrismaImportResult:
    return PrismaImportResult(
        imported_rows=rows,
        total_source_rows=len(rows),
        imported_count=len(rows),
        filtered_count=0,
        rejected_count=0,
        issues=[],
    )


_SAMPLE_DATA_LINE = ";".join([
    "2025-01-01T09:00:00", "", "Entry Market", "entry", "Network Point",
    "Day Ahead", "2025-01-02T00:00:00", "2025-01-03T00:00:00",
    "1000.0", "24.0", "20.0", "5.0",
])


# --- first publication / basic append ----------------------------------------

def test_first_publication_creates_file_from_current_import(tmp_path: Path) -> None:
    out_dir = tmp_path / "pub"
    out_dir.mkdir()
    result = publish_cumulative_output(import_result_for(tmp_path, [BASE]), out_dir)
    assert result.succeeded
    assert result.output_path == out_dir / PUBLISHED_OUTPUT_FILENAME
    header, records = _read_published(result.output_path)
    assert tuple(header) == OUTPUT_CSV_COLUMNS
    assert len(records) == 1
    assert result.appended_row_count == 1
    assert result.total_row_count == 1


def test_appending_new_unique_rows_to_existing_valid_file(tmp_path: Path) -> None:
    out_dir = tmp_path / "pub"
    out_dir.mkdir()
    first = publish_cumulative_output(import_result_for(tmp_path, [BASE]), out_dir)
    assert first.succeeded

    other = {**BASE, "Marketed Capacity": "2000"}
    second = publish_cumulative_output(
        import_result_for(tmp_path, [other], name="Auction_overview_2.csv"), out_dir
    )
    assert second.succeeded
    assert second.appended_row_count == 1
    assert second.total_row_count == 2
    _, records = _read_published(second.output_path)
    assert len(records) == 2
    assert records[0]["Booked Capacity"] == "1000.0"
    assert records[1]["Booked Capacity"] == "2000.0"


# --- deduplication -------------------------------------------------------

def test_duplicate_against_existing_rows_is_not_appended(tmp_path: Path) -> None:
    out_dir = tmp_path / "pub"
    out_dir.mkdir()
    first = publish_cumulative_output(import_result_for(tmp_path, [BASE]), out_dir)
    assert first.succeeded

    second = publish_cumulative_output(
        import_result_for(tmp_path, [BASE], name="Auction_overview_repeat.csv"), out_dir
    )
    assert second.succeeded
    assert second.appended_row_count == 0
    assert second.total_row_count == 1
    _, records = _read_published(second.output_path)
    assert len(records) == 1


def test_duplicates_within_one_import_are_written_once(tmp_path: Path) -> None:
    out_dir = tmp_path / "pub"
    out_dir.mkdir()
    result = publish_cumulative_output(import_result_for(tmp_path, [BASE, BASE]), out_dir)
    assert result.succeeded
    assert result.appended_row_count == 1
    assert result.total_row_count == 1
    _, records = _read_published(result.output_path)
    assert len(records) == 1


def test_row_differing_in_any_single_field_remains_distinct(tmp_path: Path) -> None:
    out_dir = tmp_path / "pub"
    out_dir.mkdir()
    first = publish_cumulative_output(import_result_for(tmp_path, [BASE]), out_dir)
    assert first.succeeded

    almost_identical = {**BASE, "Marketed Capacity": "1000.5"}
    second = publish_cumulative_output(
        import_result_for(tmp_path, [almost_identical], name="Auction_overview_variant.csv"),
        out_dir,
    )
    assert second.succeeded
    assert second.appended_row_count == 1
    assert second.total_row_count == 2


# --- ordering --------------------------------------------------------------

def test_existing_and_new_row_order_is_preserved(tmp_path: Path) -> None:
    out_dir = tmp_path / "pub"
    out_dir.mkdir()
    row_a = {**BASE, "Marketed Capacity": "1000"}
    row_b = {**BASE, "Marketed Capacity": "1100"}
    row_c = {**BASE, "Marketed Capacity": "1200"}
    row_d = {**BASE, "Marketed Capacity": "1300"}

    first = publish_cumulative_output(import_result_for(tmp_path, [row_a, row_b]), out_dir)
    assert first.succeeded
    second = publish_cumulative_output(
        import_result_for(tmp_path, [row_c, row_d], name="second.csv"), out_dir
    )
    assert second.succeeded
    _, records = _read_published(second.output_path)
    assert [record["Booked Capacity"] for record in records] == [
        "1000.0", "1100.0", "1200.0", "1300.0",
    ]


# --- single header on repeated runs -----------------------------------------

def test_only_one_header_present_after_repeated_runs(tmp_path: Path) -> None:
    out_dir = tmp_path / "pub"
    out_dir.mkdir()
    for index in range(3):
        row = {**BASE, "Marketed Capacity": str(1000 + index)}
        result = publish_cumulative_output(
            import_result_for(tmp_path, [row], name=f"run_{index}.csv"), out_dir
        )
        assert result.succeeded
    lines = result.output_path.read_text(encoding="utf-8").splitlines()
    header_lines = [line for line in lines if line == ";".join(OUTPUT_CSV_COLUMNS)]
    assert len(header_lines) == 1
    assert lines[0] == ";".join(OUTPUT_CSV_COLUMNS)


# --- empty accepted input ----------------------------------------------------

def test_empty_accepted_input_preserves_valid_existing_file(tmp_path: Path) -> None:
    out_dir = tmp_path / "pub"
    out_dir.mkdir()
    first = publish_cumulative_output(import_result_for(tmp_path, [BASE]), out_dir)
    assert first.succeeded
    before_mtime = first.output_path.stat().st_mtime_ns
    before_content = first.output_path.read_bytes()

    empty_import = import_result_for(tmp_path, [{**BASE, "Marketed Capacity": "1"}], name="empty.csv")
    assert empty_import.imported_count == 0
    result = publish_cumulative_output(empty_import, out_dir)
    assert result.succeeded
    assert result.appended_row_count == 0
    assert result.total_row_count == 1
    assert result.output_path.stat().st_mtime_ns == before_mtime
    assert result.output_path.read_bytes() == before_content


# --- malformed existing file --------------------------------------------

def test_empty_existing_file_fails_without_modification(tmp_path: Path) -> None:
    out_dir = tmp_path / "pub"
    out_dir.mkdir()
    target = out_dir / PUBLISHED_OUTPUT_FILENAME
    target.write_bytes(b"")

    result = publish_cumulative_output(import_result_for(tmp_path, [BASE]), out_dir)
    assert result.outcome is PrismaPublicationOutcome.INVALID_EXISTING_FILE
    assert target.read_bytes() == b""
    assert result.import_result is not None
    assert result.import_result.imported_count == 1


def test_wrong_delimiter_existing_file_fails_without_modification(tmp_path: Path) -> None:
    out_dir = tmp_path / "pub"
    out_dir.mkdir()
    target = out_dir / PUBLISHED_OUTPUT_FILENAME
    original = ",".join(OUTPUT_CSV_COLUMNS) + "\n"
    target.write_text(original, encoding="utf-8")

    result = publish_cumulative_output(import_result_for(tmp_path, [BASE]), out_dir)
    assert result.outcome is PrismaPublicationOutcome.INVALID_EXISTING_FILE
    assert target.read_text(encoding="utf-8") == original


def test_undecodable_existing_file_fails_without_modification(tmp_path: Path) -> None:
    out_dir = tmp_path / "pub"
    out_dir.mkdir()
    target = out_dir / PUBLISHED_OUTPUT_FILENAME
    original = b"\xff\xfe\x00\x01not-utf8"
    target.write_bytes(original)

    result = publish_cumulative_output(import_result_for(tmp_path, [BASE]), out_dir)
    assert result.outcome is PrismaPublicationOutcome.INVALID_EXISTING_FILE
    assert target.read_bytes() == original


def test_wrong_header_existing_file_fails_without_modification(tmp_path: Path) -> None:
    out_dir = tmp_path / "pub"
    out_dir.mkdir()
    target = out_dir / PUBLISHED_OUTPUT_FILENAME
    original = "Auction Date;Exit Market;Wrong Column\n2025-01-01;;X\n"
    target.write_text(original, encoding="utf-8")

    result = publish_cumulative_output(import_result_for(tmp_path, [BASE]), out_dir)
    assert result.outcome is PrismaPublicationOutcome.INVALID_EXISTING_FILE
    assert target.read_text(encoding="utf-8") == original


# --- strict CSV parsing (quoting, blank rows, repeated headers) -------------

def test_embedded_newline_in_quoted_field_round_trips_without_corruption(tmp_path: Path) -> None:
    out_dir = tmp_path / "pub"
    out_dir.mkdir()
    multiline_row = _import_row(network_point="Line1\nLine2")

    first = publish_cumulative_output(make_import_result([multiline_row]), out_dir)
    assert first.succeeded
    assert first.appended_row_count == 1
    _, records = _read_published(first.output_path)
    assert records[0]["Network Point Name"] == "Line1\nLine2"

    # Republishing the exact same row must be recognized as an exact
    # duplicate: if the embedded newline had been mis-split on read, this
    # row would either fail to match (falsely appended again) or corrupt
    # the comparison in some other way.
    second = publish_cumulative_output(make_import_result([multiline_row]), out_dir)
    assert second.succeeded
    assert second.appended_row_count == 0
    assert second.total_row_count == 1

    # A field that merely starts the same but is genuinely different must
    # still be recognized as distinct, proving the comparison is not
    # accidentally truncated at the embedded newline either.
    distinct_row = _import_row(network_point="Line1\nLine2-different")
    third = publish_cumulative_output(make_import_result([distinct_row]), out_dir)
    assert third.succeeded
    assert third.appended_row_count == 1
    assert third.total_row_count == 2
    _, final_records = _read_published(third.output_path)
    assert final_records[0]["Network Point Name"] == "Line1\nLine2"
    assert final_records[1]["Network Point Name"] == "Line1\nLine2-different"


def test_malformed_quoting_in_existing_file_fails_without_modification(tmp_path: Path) -> None:
    out_dir = tmp_path / "pub"
    out_dir.mkdir()
    target = out_dir / PUBLISHED_OUTPUT_FILENAME
    original = ";".join(OUTPUT_CSV_COLUMNS) + "\n" + '"2025-01-01"bad;x;y\n'
    target.write_text(original, encoding="utf-8")

    result = publish_cumulative_output(make_import_result([_import_row()]), out_dir)
    assert result.outcome is PrismaPublicationOutcome.INVALID_EXISTING_FILE
    assert target.read_text(encoding="utf-8") == original


def test_repeated_header_among_data_rows_fails_without_modification(tmp_path: Path) -> None:
    out_dir = tmp_path / "pub"
    out_dir.mkdir()
    target = out_dir / PUBLISHED_OUTPUT_FILENAME
    header_line = ";".join(OUTPUT_CSV_COLUMNS)
    original = f"{header_line}\n{_SAMPLE_DATA_LINE}\n{header_line}\n"
    target.write_text(original, encoding="utf-8")

    result = publish_cumulative_output(make_import_result([_import_row()]), out_dir)
    assert result.outcome is PrismaPublicationOutcome.INVALID_EXISTING_FILE
    assert target.read_text(encoding="utf-8") == original


def test_blank_data_row_in_existing_file_fails_without_modification(tmp_path: Path) -> None:
    out_dir = tmp_path / "pub"
    out_dir.mkdir()
    target = out_dir / PUBLISHED_OUTPUT_FILENAME
    header_line = ";".join(OUTPUT_CSV_COLUMNS)
    original = f"{header_line}\n{_SAMPLE_DATA_LINE}\n\n"
    target.write_text(original, encoding="utf-8")

    result = publish_cumulative_output(make_import_result([_import_row()]), out_dir)
    assert result.outcome is PrismaPublicationOutcome.INVALID_EXISTING_FILE
    assert target.read_text(encoding="utf-8") == original


# --- symlink containment ------------------------------------------------

def test_target_symlink_outside_publication_directory_is_rejected(tmp_path: Path) -> None:
    out_dir = tmp_path / "pub"
    out_dir.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    external_target = outside / "external.csv"
    external_content = b"not a publication file, must stay untouched"
    external_target.write_bytes(external_content)

    link = out_dir / PUBLISHED_OUTPUT_FILENAME
    try:
        link.symlink_to(external_target)
    except (OSError, NotImplementedError):
        pytest.skip("Symlink creation is not available on this platform/user.")

    result = publish_cumulative_output(make_import_result([_import_row()]), out_dir)
    assert result.outcome is PrismaPublicationOutcome.INVALID_EXISTING_FILE
    assert external_target.read_bytes() == external_content
    assert link.is_symlink()


# --- write failure / atomicity -----------------------------------------------

# A source with one accepted, one filtered (below-threshold), and one
# rejected (unknown alias) row, mirroring `test_prisma_output.py`'s own
# `_MIXED_OUTCOME_ROWS`. Used below to prove that a failure preserves the
# *complete* `PrismaImportResult` — accepted, filtered, and rejected
# evidence alike — not just the accepted rows. The accepted row uses a
# distinct "Marketed Capacity" (not plain `BASE`) so its transformed output
# is never an exact duplicate of another test's already-published row,
# which would otherwise short-circuit `publish_cumulative_output` into its
# "nothing new to write" success path before the write itself is ever
# attempted.
_MIXED_OUTCOME_ROWS = [
    {**BASE, "Marketed Capacity": "5000"},
    {**BASE, "Marketed Capacity": "999"},
    {**BASE, "Network Point Name Entry": "Totally Unknown Point"},
]


def test_reservation_or_staging_failure_preserves_prior_file_and_import_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out_dir = tmp_path / "pub"
    out_dir.mkdir()
    first = publish_cumulative_output(import_result_for(tmp_path, [BASE]), out_dir)
    assert first.succeeded
    before_content = first.output_path.read_bytes()

    def failing_mkstemp(*_args, **_kwargs):
        raise OSError("simulated reservation failure")

    monkeypatch.setattr("prisma_publication.tempfile.mkstemp", failing_mkstemp)
    mixed_import = import_result_for(tmp_path, _MIXED_OUTCOME_ROWS, name="other.csv")
    result = publish_cumulative_output(mixed_import, out_dir)

    assert result.outcome is PrismaPublicationOutcome.WRITE_FAILED
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
    assert first.output_path.read_bytes() == before_content
    remaining = [entry.name for entry in out_dir.iterdir()]
    assert remaining == [PUBLISHED_OUTPUT_FILENAME]


def test_replace_failure_preserves_prior_file_and_cleans_staging_artifact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out_dir = tmp_path / "pub"
    out_dir.mkdir()
    first = publish_cumulative_output(import_result_for(tmp_path, [BASE]), out_dir)
    assert first.succeeded
    before_content = first.output_path.read_bytes()

    def failing_replace(*_args, **_kwargs):
        raise OSError("simulated disk failure")

    monkeypatch.setattr("prisma_publication.os.replace", failing_replace)
    other = {**BASE, "Marketed Capacity": "5000"}
    result = publish_cumulative_output(
        import_result_for(tmp_path, [other], name="other.csv"), out_dir
    )

    assert result.outcome is PrismaPublicationOutcome.WRITE_FAILED
    assert result.import_result is not None
    assert result.import_result.imported_count == 1
    assert first.output_path.read_bytes() == before_content
    remaining = [entry.name for entry in out_dir.iterdir()]
    assert remaining == [PUBLISHED_OUTPUT_FILENAME]


def test_write_failure_mid_stream_cleans_staged_file_and_preserves_prior_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out_dir = tmp_path / "pub"
    out_dir.mkdir()
    first = publish_cumulative_output(import_result_for(tmp_path, [BASE]), out_dir)
    assert first.succeeded
    before_content = first.output_path.read_bytes()

    # Build the second import (which uses pandas' own CSV writer internally)
    # before patching `csv.writer`, so only `prisma_publication._write_rows`'s
    # own writer is affected.
    other = {**BASE, "Marketed Capacity": "5000"}
    other_import = import_result_for(tmp_path, [other], name="other.csv")

    original_writer = csv.writer

    class _FailingWriter:
        def __init__(self, real) -> None:
            self._real = real

        def writerow(self, row):
            return self._real.writerow(row)

        def writerows(self, _rows):
            raise OSError("simulated write failure mid-stream")

    def failing_writer_factory(*args, **kwargs):
        return _FailingWriter(original_writer(*args, **kwargs))

    monkeypatch.setattr("prisma_publication.csv.writer", failing_writer_factory)
    result = publish_cumulative_output(other_import, out_dir)

    assert result.outcome is PrismaPublicationOutcome.WRITE_FAILED
    assert first.output_path.read_bytes() == before_content
    remaining = [entry.name for entry in out_dir.iterdir()]
    assert remaining == [PUBLISHED_OUTPUT_FILENAME]


def test_first_publication_write_failure_leaves_no_file_at_all(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out_dir = tmp_path / "pub"
    out_dir.mkdir()

    def failing_replace(*_args, **_kwargs):
        raise OSError("simulated disk failure")

    monkeypatch.setattr("prisma_publication.os.replace", failing_replace)
    result = publish_cumulative_output(import_result_for(tmp_path, [BASE]), out_dir)

    assert result.outcome is PrismaPublicationOutcome.WRITE_FAILED
    assert list(out_dir.iterdir()) == []


# --- atomic visibility -------------------------------------------------------

def test_target_never_shows_partial_content_during_publication(tmp_path: Path) -> None:
    out_dir = tmp_path / "pub"
    out_dir.mkdir()
    first = publish_cumulative_output(import_result_for(tmp_path, [BASE]), out_dir)
    assert first.succeeded
    _, initial_records = _read_published(first.output_path)
    assert len(initial_records) == 1

    other = {**BASE, "Marketed Capacity": "9000"}
    second = publish_cumulative_output(
        import_result_for(tmp_path, [other], name="other.csv"), out_dir
    )
    assert second.succeeded
    header, records = _read_published(second.output_path)
    assert tuple(header) == OUTPUT_CSV_COLUMNS
    assert len(records) == 2
    names = [entry.name for entry in out_dir.iterdir()]
    assert names == [PUBLISHED_OUTPUT_FILENAME]
    assert not any(name.endswith(".staging") for name in names)


# --- directory containment ---------------------------------------------------

def test_no_reads_or_writes_escape_the_publication_directory(tmp_path: Path) -> None:
    out_dir = tmp_path / "pub"
    out_dir.mkdir()
    sibling = tmp_path / "sibling"
    sibling.mkdir()
    decoy = sibling / PUBLISHED_OUTPUT_FILENAME
    decoy.write_bytes(b"untouched")

    result = publish_cumulative_output(import_result_for(tmp_path, [BASE]), out_dir)
    assert result.succeeded
    assert decoy.read_bytes() == b"untouched"
    assert [entry.name for entry in sibling.iterdir()] == [PUBLISHED_OUTPUT_FILENAME]
    assert [entry.name for entry in out_dir.iterdir()] == [PUBLISHED_OUTPUT_FILENAME]


# --- destination validation ---------------------------------------------

def test_nonexistent_publication_directory_is_rejected_without_writing(tmp_path: Path) -> None:
    missing_dir = tmp_path / "does_not_exist"
    result = publish_cumulative_output(import_result_for(tmp_path, [BASE]), missing_dir)
    assert result.outcome is PrismaPublicationOutcome.INVALID_PUBLICATION_DIRECTORY
    assert not missing_dir.exists()


def test_invalid_publication_directory_preserves_the_exact_completed_import_result(
    tmp_path: Path,
) -> None:
    """An invalid publication *directory* is rejected before any read of the
    cumulative file, but the completed `PrismaImportResult` — accepted,
    filtered, and rejected evidence alike — must still be returned unchanged,
    matching the documented contract that this evidence is retained on every
    publication outcome, not only on `WRITE_FAILED`/`INVALID_EXISTING_FILE`.
    """
    missing_dir = tmp_path / "does_not_exist"
    mixed_import = import_result_for(tmp_path, _MIXED_OUTCOME_ROWS)

    result = publish_cumulative_output(mixed_import, missing_dir)

    assert result.outcome is PrismaPublicationOutcome.INVALID_PUBLICATION_DIRECTORY
    assert result.import_result is mixed_import
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
    assert not missing_dir.exists()


def test_file_as_publication_directory_is_rejected(tmp_path: Path) -> None:
    not_a_dir = tmp_path / "file.txt"
    not_a_dir.write_text("x", encoding="utf-8")
    result = publish_cumulative_output(import_result_for(tmp_path, [BASE]), not_a_dir)
    assert result.outcome is PrismaPublicationOutcome.INVALID_PUBLICATION_DIRECTORY


def test_non_writable_publication_directory_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out_dir = tmp_path / "pub"
    out_dir.mkdir()
    real_access = os.access

    def fake_access(path, mode):
        if Path(path) == out_dir.resolve() and mode == os.W_OK:
            return False
        return real_access(path, mode)

    monkeypatch.setattr("prisma_publication.os.access", fake_access)
    result = publish_cumulative_output(import_result_for(tmp_path, [BASE]), out_dir)
    assert result.outcome is PrismaPublicationOutcome.INVALID_PUBLICATION_DIRECTORY
    assert list(out_dir.iterdir()) == []


# --- messages ----------------------------------------------------------------

def test_describe_publication_failure_returns_stable_messages() -> None:
    for outcome in PrismaPublicationOutcome:
        message = describe_publication_failure(outcome)
        assert isinstance(message, str) and message
