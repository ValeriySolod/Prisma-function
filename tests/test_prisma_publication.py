from __future__ import annotations

import csv
import os
from pathlib import Path

import pandas as pd
import pytest

from csv_contracts import PRISMA_EXPORT_COLUMNS
from download_directory import DownloadDirectoryError
from prisma_references import (
    PrismaReference,
    PrismaReferenceCatalog,
    ReferenceAlias,
    ReferenceClassification,
    ReferenceSide,
)
from price_normalization import normalize_prices_for_output
from processor import PrismaImportResult, import_prisma_export
from prisma_output import OUTPUT_CSV_COLUMNS
from prisma_publication import (
    LEGACY_PUBLISHED_OUTPUT_FILENAME,
    PUBLISHED_OUTPUT_FILENAME,
    PrismaPublicationOutcome,
    describe_publication_failure,
    publish_cumulative_output,
)
from storage import AuctionStorage

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
    "Unit Surcharge": "cent/kWh/h/Runtime", "State": "Finished",
}

def eur_catalog() -> PrismaReferenceCatalog:
    return PrismaReferenceCatalog((
        PrismaReference(
            "VGS Storage Hub", ReferenceClassification.STORAGE,
            (
                ReferenceAlias("VGS Storage Hub (4290)", ReferenceSide.EXIT),
                ReferenceAlias("VGS Storage Hub (4290)", ReferenceSide.ENTRY),
            ),
            exit_currency="EUR", entry_currency="EUR",
        ),
    ))


def write_csv(tmp_path: Path, rows: list[dict], name: str = "Auction_overview.csv") -> Path:
    path = tmp_path / name
    pd.DataFrame(rows).reindex(columns=PRISMA_EXPORT_COLUMNS).fillna("").to_csv(
        path, sep=";", encoding="cp1252", index=False
    )
    return path


def import_result_for(tmp_path: Path, rows: list[dict], name: str = "Auction_overview.csv") -> PrismaImportResult:
    source = write_csv(tmp_path, rows, name=name)
    return import_prisma_export(source, reference_catalog=eur_catalog())


def _publish(import_result, out_dir, tmp_path: Path, **overrides):
    kwargs = dict(
        storage=AuctionStorage(tmp_path / "auctions.db"),
    )
    kwargs.update(overrides)
    return publish_cumulative_output(import_result, out_dir, **kwargs)


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
    cumulative-file read/merge/write behavior itself. Defaults to EUR (rate
    identity, no ECB access) so P.36.21/P.37's strict EUR gate does not block
    these otherwise-unrelated P.36.16 merge/dedup tests; see
    `tests/test_price_normalization.py` for EUR-conversion-specific coverage.

    `tariff_source_mwh_h`/`premium_source_mwh_h` are accepted as legacy
    convenience kwarg names (mapping onto the exit-side tariff field and the
    premium field respectively) so most existing call sites in this file
    need no change under P.37's exit/entry-split row shape.
    """
    base = {
        "auction_id": BASE["Auction ID"],
        "state": "Finished",
        "auction_date": "2025-01-01",
        "exit_market": "",
        "entry_market": "VGS Storage Hub",
        "direction": "entry",
        "network_point": "Network Point",
        "product_type": "Day Ahead",
        "flow_start": "2025-01-02T00:00:00",
        "flow_end": "2025-01-03T00:00:00",
        "booked_capacity_kwh_h": 1000.0,
        "runtime_hours": 24.0,
        "tariff_exit_source_mwh_h": 20.0,
        "tariff_exit_currency": "EUR",
        "tariff_entry_source_mwh_h": 0.0,
        "tariff_entry_currency": "",
        "premium_source_mwh_h": 5.0,
        "premium_currency": "EUR",
    }
    if "tariff_source_mwh_h" in overrides:
        base["tariff_exit_source_mwh_h"] = overrides.pop("tariff_source_mwh_h")
    if "premium_source_mwh_h" in overrides:
        base["premium_source_mwh_h"] = overrides.pop("premium_source_mwh_h")
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
    "1000.0", "24.0", "20.000000", "5.000000",
])


# --- first publication / basic append ----------------------------------------

def test_first_publication_creates_file_from_current_import(tmp_path: Path) -> None:
    out_dir = tmp_path / "pub"
    out_dir.mkdir()
    result = _publish(import_result_for(tmp_path, [BASE]), out_dir, tmp_path)
    assert result.succeeded
    assert result.output_path == out_dir / PUBLISHED_OUTPUT_FILENAME
    header, records = _read_published(result.output_path)
    assert tuple(header) == OUTPUT_CSV_COLUMNS
    assert len(records) == 1
    assert result.appended_row_count == 1
    assert result.total_row_count == 1


def test_published_output_uses_corrected_datetime_representation(tmp_path: Path) -> None:
    out_dir = tmp_path / "pub"
    out_dir.mkdir()
    result = _publish(import_result_for(tmp_path, [BASE]), out_dir, tmp_path)
    assert result.succeeded
    _, records = _read_published(result.output_path)
    row = records[0]
    assert row["Auction Date"] == "2025-01-01"
    assert row["Flow Start"] == "2025-01-02 00:00"
    assert row["Flow End"] == "2025-01-03 00:00"
    for column in ("Auction Date", "Flow Start", "Flow End"):
        assert "T" not in row[column]
        assert "+" not in row[column]
        assert row[column].count(":") <= 1


def test_appending_new_unique_rows_to_existing_valid_file(tmp_path: Path) -> None:
    out_dir = tmp_path / "pub"
    out_dir.mkdir()
    storage = AuctionStorage(tmp_path / "auctions.db")
    first = _publish(import_result_for(tmp_path, [BASE]), out_dir, tmp_path, storage=storage)
    assert first.succeeded

    # A different Auction ID is a different P.40 composite key even though
    # every other field, including Booked Capacity, could coincide; here it
    # also differs so this row is unambiguously new either way.
    other = {**BASE, "Auction ID": "000123456789099999", "Marketed Capacity": "2000"}
    second = _publish(
        import_result_for(tmp_path, [other], name="Auction_overview_2.csv"), out_dir, tmp_path,
        storage=storage,
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
    storage = AuctionStorage(tmp_path / "auctions.db")
    first = _publish(import_result_for(tmp_path, [BASE]), out_dir, tmp_path, storage=storage)
    assert first.succeeded

    second = _publish(
        import_result_for(tmp_path, [BASE], name="Auction_overview_repeat.csv"), out_dir, tmp_path,
        storage=storage,
    )
    assert second.succeeded
    assert second.appended_row_count == 0
    assert second.total_row_count == 1
    _, records = _read_published(second.output_path)
    assert len(records) == 1


def test_duplicates_within_one_import_are_written_once(tmp_path: Path) -> None:
    out_dir = tmp_path / "pub"
    out_dir.mkdir()
    result = _publish(import_result_for(tmp_path, [BASE, BASE]), out_dir, tmp_path)
    assert result.succeeded
    assert result.appended_row_count == 1
    assert result.total_row_count == 1
    _, records = _read_published(result.output_path)
    assert len(records) == 1


def test_row_differing_only_in_a_non_key_field_is_skipped_as_a_duplicate(tmp_path: Path) -> None:
    """P.40: the composite key is Auction ID + Network Point Name + Capacity
    Type only. PRISMA data is immutable by customer decision, so once a key
    is recorded, a later row sharing that exact key is always skipped — even
    though its `Booked Capacity` (not part of the key) differs. The
    already-stored row's values are kept unchanged; this is not a conflict
    error and not a merge, just a skip."""
    out_dir = tmp_path / "pub"
    out_dir.mkdir()
    storage = AuctionStorage(tmp_path / "auctions.db")
    first = _publish(import_result_for(tmp_path, [BASE]), out_dir, tmp_path, storage=storage)
    assert first.succeeded

    almost_identical = {**BASE, "Marketed Capacity": "1000.5"}
    second = _publish(
        import_result_for(tmp_path, [almost_identical], name="Auction_overview_variant.csv"),
        out_dir, tmp_path, storage=storage,
    )
    assert second.succeeded
    assert second.appended_row_count == 0
    assert second.total_row_count == 1
    _, records = _read_published(second.output_path)
    assert len(records) == 1
    assert records[0]["Booked Capacity"] == "1000.0"


@pytest.mark.parametrize(
    "override",
    [
        {"auction_id": "ZZZ999999999999999"},
        {"network_point": "A Different Network Point"},
        {"direction": "exit"},
    ],
    ids=["auction_id", "network_point_name", "capacity_type"],
)
def test_row_differing_in_any_composite_key_field_remains_distinct(
    tmp_path: Path, override: dict
) -> None:
    """Each of the three key components — Auction ID, Network Point Name,
    Capacity Type — independently makes a row a distinct P.40 identity, even
    when every other field (including Booked Capacity) is unchanged. Uses the
    already-enriched row shape directly (see `_import_row`) so this exercises
    only the composite-key contract itself, not catalog alias resolution."""
    out_dir = tmp_path / "pub"
    out_dir.mkdir()
    storage = AuctionStorage(tmp_path / "auctions.db")
    row_a = _import_row()
    row_b = _import_row(**override)
    result = _publish(make_import_result([row_a, row_b]), out_dir, tmp_path, storage=storage)
    assert result.succeeded
    assert result.appended_row_count == 2
    assert result.total_row_count == 2


def test_partial_overlap_within_one_import_keeps_only_the_first_occurrence(
    tmp_path: Path,
) -> None:
    """Two rows sharing one composite key inside the *same* import batch
    (a partial-overlap import) must resolve exactly like two separate
    publish calls would: the first occurrence is kept, the later one is
    skipped, never merged or reported as a conflict."""
    out_dir = tmp_path / "pub"
    out_dir.mkdir()
    row_first = _import_row(booked_capacity_kwh_h=1000.0)
    row_later = _import_row(booked_capacity_kwh_h=9999.0)
    result = _publish(make_import_result([row_first, row_later]), out_dir, tmp_path)
    assert result.succeeded
    assert result.appended_row_count == 1
    assert result.total_row_count == 1
    _, records = _read_published(result.output_path)
    assert len(records) == 1
    assert records[0]["Booked Capacity"] == "1000.0"


def test_composite_key_dedup_persists_across_separate_storage_instances(
    tmp_path: Path,
) -> None:
    """The composite-key index is durable, cross-session storage: a brand
    new `AuctionStorage` opened against the same database file must still
    recognize a key recorded by an earlier, now-closed instance."""
    out_dir = tmp_path / "pub"
    out_dir.mkdir()
    db_path = tmp_path / "auctions.db"
    first = _publish(
        import_result_for(tmp_path, [BASE]), out_dir, tmp_path, storage=AuctionStorage(db_path)
    )
    assert first.succeeded

    reopened_storage = AuctionStorage(db_path)
    assert (BASE["Auction ID"], "VGS Storage Hub (4290)", "entry") in (
        reopened_storage.published_output_row_keys()
    )

    conflicting = {**BASE, "Marketed Capacity": "2000"}
    second = _publish(
        import_result_for(tmp_path, [conflicting], name="Auction_overview_2.csv"),
        out_dir, tmp_path, storage=reopened_storage,
    )
    assert second.succeeded
    assert second.appended_row_count == 0
    assert second.total_row_count == 1


def test_legacy_file_row_is_key_tracked_from_its_first_post_upgrade_publish(
    tmp_path: Path,
) -> None:
    """Backward compatibility / migration: a cumulative file already
    populated before this composite-key table existed has no recorded keys
    for its rows (Auction ID cannot be recovered from the CSV alone). This
    is a deliberate, documented, one-time transitional limit — see the
    module docstring — so the very first post-upgrade publish that touches
    such a row (here, against a *fresh* storage simulating an older
    database) still appends it once more; but from that point on its key is
    recorded, so any further row sharing that key — even with different
    non-key values — is correctly skipped as a duplicate, never appended
    again."""
    out_dir = tmp_path / "pub"
    out_dir.mkdir()
    legacy_import = import_result_for(tmp_path, [BASE])
    legacy_storage = AuctionStorage(tmp_path / "legacy_auctions.db")
    seed = _publish(legacy_import, out_dir, tmp_path, storage=legacy_storage)
    assert seed.succeeded
    # Simulate a pre-P.40 database: this storage's composite-key table has
    # never recorded this row's key.
    fresh_storage = AuctionStorage(tmp_path / "fresh_auctions.db")
    assert fresh_storage.published_output_row_keys() == set()

    republished = _publish(
        import_result_for(tmp_path, [BASE], name="Auction_overview_repeat.csv"),
        out_dir, tmp_path, storage=fresh_storage,
    )
    assert republished.succeeded
    assert republished.appended_row_count == 1
    assert republished.total_row_count == 2
    assert (BASE["Auction ID"], "VGS Storage Hub (4290)", "entry") in (
        fresh_storage.published_output_row_keys()
    )

    changed_capacity = {**BASE, "Marketed Capacity": "7000"}
    now_skipped = _publish(
        import_result_for(tmp_path, [changed_capacity], name="Auction_overview_changed.csv"),
        out_dir, tmp_path, storage=fresh_storage,
    )
    assert now_skipped.succeeded
    assert now_skipped.appended_row_count == 0
    assert now_skipped.total_row_count == 2


def test_cumulative_deduplication_operates_on_final_normalized_price_values(tmp_path: Path) -> None:
    """Deduplication compares the complete, exact 12-field *normalized* EUR
    row, not the pre-conversion source price."""
    out_dir = tmp_path / "pub"
    out_dir.mkdir()
    storage = AuctionStorage(tmp_path / "auctions.db")
    row_a = _import_row(tariff_source_mwh_h=20.0)
    row_b = _import_row(tariff_source_mwh_h=20.0)
    result = _publish(make_import_result([row_a, row_b]), out_dir, tmp_path, storage=storage)
    assert result.succeeded
    assert result.appended_row_count == 1
    _, records = _read_published(result.output_path)
    assert records[0]["Tariff Price"] == "20.000000"


# --- ordering --------------------------------------------------------------

def test_existing_and_new_row_order_is_preserved(tmp_path: Path) -> None:
    out_dir = tmp_path / "pub"
    out_dir.mkdir()
    storage = AuctionStorage(tmp_path / "auctions.db")
    # Distinct Auction IDs so all four rows are genuinely distinct P.40
    # composite keys, not just distinct by Booked Capacity.
    row_a = {**BASE, "Auction ID": "000000000000000001", "Marketed Capacity": "1000"}
    row_b = {**BASE, "Auction ID": "000000000000000002", "Marketed Capacity": "1100"}
    row_c = {**BASE, "Auction ID": "000000000000000003", "Marketed Capacity": "1200"}
    row_d = {**BASE, "Auction ID": "000000000000000004", "Marketed Capacity": "1300"}

    first = _publish(import_result_for(tmp_path, [row_a, row_b]), out_dir, tmp_path, storage=storage)
    assert first.succeeded
    second = _publish(
        import_result_for(tmp_path, [row_c, row_d], name="second.csv"), out_dir, tmp_path,
        storage=storage,
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
    storage = AuctionStorage(tmp_path / "auctions.db")
    for index in range(3):
        row = {**BASE, "Marketed Capacity": str(1000 + index)}
        result = _publish(
            import_result_for(tmp_path, [row], name=f"run_{index}.csv"), out_dir, tmp_path,
            storage=storage,
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
    storage = AuctionStorage(tmp_path / "auctions.db")
    first = _publish(import_result_for(tmp_path, [BASE]), out_dir, tmp_path, storage=storage)
    assert first.succeeded
    before_mtime = first.output_path.stat().st_mtime_ns
    before_content = first.output_path.read_bytes()

    empty_import = import_result_for(tmp_path, [{**BASE, "Marketed Capacity": "1"}], name="empty.csv")
    assert empty_import.imported_count == 0
    result = _publish(empty_import, out_dir, tmp_path, storage=storage)
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

    result = _publish(import_result_for(tmp_path, [BASE]), out_dir, tmp_path)
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

    result = _publish(import_result_for(tmp_path, [BASE]), out_dir, tmp_path)
    assert result.outcome is PrismaPublicationOutcome.INVALID_EXISTING_FILE
    assert target.read_text(encoding="utf-8") == original


def test_undecodable_existing_file_fails_without_modification(tmp_path: Path) -> None:
    out_dir = tmp_path / "pub"
    out_dir.mkdir()
    target = out_dir / PUBLISHED_OUTPUT_FILENAME
    original = b"\xff\xfe\x00\x01not-utf8"
    target.write_bytes(original)

    result = _publish(import_result_for(tmp_path, [BASE]), out_dir, tmp_path)
    assert result.outcome is PrismaPublicationOutcome.INVALID_EXISTING_FILE
    assert target.read_bytes() == original


def test_wrong_header_existing_file_fails_without_modification(tmp_path: Path) -> None:
    out_dir = tmp_path / "pub"
    out_dir.mkdir()
    target = out_dir / PUBLISHED_OUTPUT_FILENAME
    original = "Auction Date;Exit Market;Wrong Column\n2025-01-01;;X\n"
    target.write_text(original, encoding="utf-8")

    result = _publish(import_result_for(tmp_path, [BASE]), out_dir, tmp_path)
    assert result.outcome is PrismaPublicationOutcome.INVALID_EXISTING_FILE
    assert target.read_text(encoding="utf-8") == original


# --- strict CSV parsing (quoting, blank rows, repeated headers) -------------

def test_embedded_newline_in_quoted_field_round_trips_without_corruption(tmp_path: Path) -> None:
    out_dir = tmp_path / "pub"
    out_dir.mkdir()
    storage = AuctionStorage(tmp_path / "auctions.db")
    multiline_row = _import_row(network_point="Line1\nLine2")

    first = _publish(make_import_result([multiline_row]), out_dir, tmp_path, storage=storage)
    assert first.succeeded
    assert first.appended_row_count == 1
    _, records = _read_published(first.output_path)
    assert records[0]["Network Point Name"] == "Line1\nLine2"

    # Republishing the exact same row must be recognized as an exact
    # duplicate: if the embedded newline had been mis-split on read, this
    # row would either fail to match (falsely appended again) or corrupt
    # the comparison in some other way.
    second = _publish(make_import_result([multiline_row]), out_dir, tmp_path, storage=storage)
    assert second.succeeded
    assert second.appended_row_count == 0
    assert second.total_row_count == 1

    # A field that merely starts the same but is genuinely different must
    # still be recognized as distinct, proving the comparison is not
    # accidentally truncated at the embedded newline either.
    distinct_row = _import_row(network_point="Line1\nLine2-different")
    third = _publish(make_import_result([distinct_row]), out_dir, tmp_path, storage=storage)
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

    result = _publish(make_import_result([_import_row()]), out_dir, tmp_path)
    assert result.outcome is PrismaPublicationOutcome.INVALID_EXISTING_FILE
    assert target.read_text(encoding="utf-8") == original


def test_repeated_header_among_data_rows_fails_without_modification(tmp_path: Path) -> None:
    out_dir = tmp_path / "pub"
    out_dir.mkdir()
    target = out_dir / PUBLISHED_OUTPUT_FILENAME
    header_line = ";".join(OUTPUT_CSV_COLUMNS)
    original = f"{header_line}\n{_SAMPLE_DATA_LINE}\n{header_line}\n"
    target.write_text(original, encoding="utf-8")

    result = _publish(make_import_result([_import_row()]), out_dir, tmp_path)
    assert result.outcome is PrismaPublicationOutcome.INVALID_EXISTING_FILE
    assert target.read_text(encoding="utf-8") == original


def test_blank_data_row_in_existing_file_fails_without_modification(tmp_path: Path) -> None:
    out_dir = tmp_path / "pub"
    out_dir.mkdir()
    target = out_dir / PUBLISHED_OUTPUT_FILENAME
    header_line = ";".join(OUTPUT_CSV_COLUMNS)
    original = f"{header_line}\n{_SAMPLE_DATA_LINE}\n\n"
    target.write_text(original, encoding="utf-8")

    result = _publish(make_import_result([_import_row()]), out_dir, tmp_path)
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

    result = _publish(make_import_result([_import_row()]), out_dir, tmp_path)
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
    storage = AuctionStorage(tmp_path / "auctions.db")
    # A distinct Auction ID from `_MIXED_OUTCOME_ROWS`'s accepted row below,
    # so that row's P.40 composite key is genuinely new and a write is
    # actually attempted (not short-circuited as an already-known key).
    seed = {**BASE, "Auction ID": "000000000000000000"}
    first = _publish(import_result_for(tmp_path, [seed]), out_dir, tmp_path, storage=storage)
    assert first.succeeded
    before_content = first.output_path.read_bytes()

    def failing_mkstemp(*_args, **_kwargs):
        raise OSError("simulated reservation failure")

    monkeypatch.setattr("prisma_publication.tempfile.mkstemp", failing_mkstemp)
    mixed_import = import_result_for(tmp_path, _MIXED_OUTCOME_ROWS, name="other.csv")
    result = _publish(mixed_import, out_dir, tmp_path, storage=storage)

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
    storage = AuctionStorage(tmp_path / "auctions.db")
    # Distinct Auction ID so `other` below is a genuinely new P.40 key.
    seed = {**BASE, "Auction ID": "000000000000000000"}
    first = _publish(import_result_for(tmp_path, [seed]), out_dir, tmp_path, storage=storage)
    assert first.succeeded
    before_content = first.output_path.read_bytes()

    def failing_replace(*_args, **_kwargs):
        raise OSError("simulated disk failure")

    monkeypatch.setattr("prisma_publication.os.replace", failing_replace)
    other = {**BASE, "Marketed Capacity": "5000"}
    result = _publish(
        import_result_for(tmp_path, [other], name="other.csv"), out_dir, tmp_path, storage=storage,
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
    storage = AuctionStorage(tmp_path / "auctions.db")
    # Distinct Auction ID so `other` below is a genuinely new P.40 key.
    seed = {**BASE, "Auction ID": "000000000000000000"}
    first = _publish(import_result_for(tmp_path, [seed]), out_dir, tmp_path, storage=storage)
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
    result = _publish(other_import, out_dir, tmp_path, storage=storage)

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
    result = _publish(import_result_for(tmp_path, [BASE]), out_dir, tmp_path)

    assert result.outcome is PrismaPublicationOutcome.WRITE_FAILED
    assert list(out_dir.iterdir()) == []


# --- atomic visibility -------------------------------------------------------

def test_target_never_shows_partial_content_during_publication(tmp_path: Path) -> None:
    out_dir = tmp_path / "pub"
    out_dir.mkdir()
    storage = AuctionStorage(tmp_path / "auctions.db")
    # Distinct Auction ID so `other` below is a genuinely new P.40 key.
    seed = {**BASE, "Auction ID": "000000000000000000"}
    first = _publish(import_result_for(tmp_path, [seed]), out_dir, tmp_path, storage=storage)
    assert first.succeeded
    _, initial_records = _read_published(first.output_path)
    assert len(initial_records) == 1

    other = {**BASE, "Marketed Capacity": "9000"}
    second = _publish(
        import_result_for(tmp_path, [other], name="other.csv"), out_dir, tmp_path, storage=storage,
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

    result = _publish(import_result_for(tmp_path, [BASE]), out_dir, tmp_path)
    assert result.succeeded
    assert decoy.read_bytes() == b"untouched"
    assert [entry.name for entry in sibling.iterdir()] == [PUBLISHED_OUTPUT_FILENAME]
    assert [entry.name for entry in out_dir.iterdir()] == [PUBLISHED_OUTPUT_FILENAME]


# --- destination validation ---------------------------------------------

def test_nonexistent_publication_directory_is_rejected_without_writing(tmp_path: Path) -> None:
    missing_dir = tmp_path / "does_not_exist"
    result = _publish(import_result_for(tmp_path, [BASE]), missing_dir, tmp_path)
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

    result = _publish(mixed_import, missing_dir, tmp_path)

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
    result = _publish(import_result_for(tmp_path, [BASE]), not_a_dir, tmp_path)
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
    result = _publish(import_result_for(tmp_path, [BASE]), out_dir, tmp_path)
    assert result.outcome is PrismaPublicationOutcome.INVALID_PUBLICATION_DIRECTORY
    assert list(out_dir.iterdir()) == []


# --- messages ----------------------------------------------------------------

def test_describe_publication_failure_returns_stable_messages() -> None:
    for outcome in PrismaPublicationOutcome:
        message = describe_publication_failure(outcome)
        assert isinstance(message, str) and message


# --- P.36.21/P.37 strict EUR gate and legacy-file compatibility ---------------

def test_unresolved_ecb_rate_blocks_publication_and_leaves_existing_file_untouched(
    tmp_path: Path,
) -> None:
    from ecb_rates import EcbRateNotFoundError

    class UnavailableEcbSource:
        def fetch(self, currency, *, on_or_before, timeout_seconds):
            raise EcbRateNotFoundError(f"no rate for {currency}")

    out_dir = tmp_path / "pub"
    out_dir.mkdir()
    storage = AuctionStorage(tmp_path / "auctions.db")
    first = _publish(import_result_for(tmp_path, [BASE]), out_dir, tmp_path, storage=storage)
    assert first.succeeded
    before_content = first.output_path.read_bytes()

    other = {
        **BASE, "Marketed Capacity": "9000",
        "Regulated Tariff Entry TSO": "1",
        "Unit Regulated Entry Capacity Tariff": "pence/kWh/h/Runtime",
    }
    blocked_import_result = import_result_for(tmp_path, [other], name="unresolved.csv")
    result = _publish(
        blocked_import_result, out_dir, tmp_path,
        storage=AuctionStorage(tmp_path / "other_auctions.db"),
        ecb_source=UnavailableEcbSource(),
    )
    assert result.outcome is PrismaPublicationOutcome.PRICE_NORMALIZATION_FAILED
    assert result.price_normalization is not None
    assert not result.price_normalization.succeeded
    assert first.output_path.read_bytes() == before_content
    remaining = [entry.name for entry in out_dir.iterdir()]
    assert remaining == [PUBLISHED_OUTPUT_FILENAME]


def test_legacy_filename_is_never_read_written_or_touched(tmp_path: Path) -> None:
    out_dir = tmp_path / "pub"
    out_dir.mkdir()
    legacy_path = out_dir / LEGACY_PUBLISHED_OUTPUT_FILENAME
    legacy_content = b"pre-P.36.21 rows;not proven EUR\n"
    legacy_path.write_bytes(legacy_content)

    result = _publish(import_result_for(tmp_path, [BASE]), out_dir, tmp_path)
    assert result.succeeded
    assert result.output_path == out_dir / PUBLISHED_OUTPUT_FILENAME
    assert result.output_path != legacy_path
    assert legacy_path.read_bytes() == legacy_content
    names = sorted(entry.name for entry in out_dir.iterdir())
    assert names == sorted([LEGACY_PUBLISHED_OUTPUT_FILENAME, PUBLISHED_OUTPUT_FILENAME])


def test_published_output_filename_differs_from_legacy_filename() -> None:
    assert PUBLISHED_OUTPUT_FILENAME != LEGACY_PUBLISHED_OUTPUT_FILENAME
    assert LEGACY_PUBLISHED_OUTPUT_FILENAME == "Prisma_Output_Published.csv"


# --- P.36.21 correction: precomputed_normalization boundary -----------------

def test_precomputed_normalization_is_reused_without_a_second_normalization_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    out_dir = tmp_path / "pub"
    out_dir.mkdir()
    storage = AuctionStorage(tmp_path / "auctions.db")
    import_result = import_result_for(tmp_path, [BASE])
    normalization = normalize_prices_for_output(
        import_result.rows, storage=storage,    )
    assert normalization.succeeded

    def fail_if_called(*_a, **_k):
        pytest.fail(
            "normalize_prices_for_output must not run again when a valid "
            "precomputed result is supplied."
        )

    monkeypatch.setattr("prisma_publication.normalize_prices_for_output", fail_if_called)
    result = publish_cumulative_output(
        import_result, out_dir, storage=storage,        precomputed_normalization=normalization,
    )
    assert result.succeeded
    _, records = _read_published(result.output_path)
    assert len(records) == 1


def test_mismatched_precomputed_normalization_is_rejected(tmp_path: Path) -> None:
    out_dir = tmp_path / "pub"
    out_dir.mkdir()
    storage = AuctionStorage(tmp_path / "auctions.db")
    import_result = import_result_for(
        tmp_path, [BASE, {**BASE, "Marketed Capacity": "2000"}]
    )
    # Computed for a different (single-row) batch, not the two-row
    # `import_result` above — must never be silently accepted as if it
    # covered the actual batch being published.
    mismatched = normalize_prices_for_output(
        import_result.rows[:1], storage=storage,    )
    assert mismatched.succeeded

    with pytest.raises(ValueError):
        publish_cumulative_output(
            import_result, out_dir, storage=storage,            precomputed_normalization=mismatched,
        )
    assert list(out_dir.iterdir()) == []


def test_blocked_precomputed_normalization_is_honored_without_a_second_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from ecb_rates import EcbRateNotFoundError

    class UnavailableEcbSource:
        def fetch(self, currency, *, on_or_before, timeout_seconds):
            raise EcbRateNotFoundError(f"no rate for {currency}")

    out_dir = tmp_path / "pub"
    out_dir.mkdir()
    storage = AuctionStorage(tmp_path / "auctions.db")
    unresolved = {
        **BASE, "Regulated Tariff Entry TSO": "1",
        "Unit Regulated Entry Capacity Tariff": "pence/kWh/h/Runtime",
    }
    blocked_import_result = import_result_for(tmp_path, [unresolved], name="unresolved.csv")
    blocked = normalize_prices_for_output(
        blocked_import_result.rows, storage=storage, ecb_source=UnavailableEcbSource(),
    )
    assert not blocked.succeeded

    def fail_if_called(*_a, **_k):
        pytest.fail("normalize_prices_for_output must not run again for a precomputed BLOCKED result.")

    monkeypatch.setattr("prisma_publication.normalize_prices_for_output", fail_if_called)
    result = publish_cumulative_output(
        blocked_import_result, out_dir, storage=storage,
        ecb_source=UnavailableEcbSource(), precomputed_normalization=blocked,
    )
    assert result.outcome is PrismaPublicationOutcome.PRICE_NORMALIZATION_FAILED
    assert list(out_dir.iterdir()) == []


# --- P.36.21 review correction: exact-batch binding, not just row count -----

def test_precomputed_normalization_for_a_different_batch_of_the_same_length_is_rejected(
    tmp_path: Path,
) -> None:
    """The original defect: a successful `PriceNormalizationResult` computed
    for a *different* single-row batch has the same `prices_by_row_index`
    index set (`{0}`) as the real one-row `import_result` below, so an
    index-set-only check would wrongly accept it and misattribute its price."""
    out_dir = tmp_path / "pub"
    out_dir.mkdir()
    storage = AuctionStorage(tmp_path / "auctions.db")
    import_result = make_import_result([_import_row(auction_id="AAA000000000000001")])

    other_batch_result = make_import_result([
        _import_row(
            auction_id="ZZZ999999999999999", tariff_source_mwh_h=99.0, premium_source_mwh_h=42.0,
        )
    ])
    foreign_normalization = normalize_prices_for_output(
        other_batch_result.rows, storage=storage,    )
    assert foreign_normalization.succeeded
    assert set(foreign_normalization.prices_by_row_index) == set(range(len(import_result.rows)))

    with pytest.raises(ValueError):
        publish_cumulative_output(
            import_result, out_dir, storage=storage,            precomputed_normalization=foreign_normalization,
        )
    assert list(out_dir.iterdir()) == []


def test_precomputed_normalization_for_reordered_rows_is_rejected(tmp_path: Path) -> None:
    out_dir = tmp_path / "pub"
    out_dir.mkdir()
    storage = AuctionStorage(tmp_path / "auctions.db")
    row_a = _import_row(auction_id="AAA000000000000001", tariff_source_mwh_h=20.0)
    row_b = _import_row(auction_id="BBB000000000000002", tariff_source_mwh_h=40.0)

    forward = make_import_result([row_a, row_b])
    reversed_order = make_import_result([row_b, row_a])
    normalization_for_reversed = normalize_prices_for_output(
        reversed_order.rows, storage=storage,    )
    assert normalization_for_reversed.succeeded

    with pytest.raises(ValueError):
        publish_cumulative_output(
            forward, out_dir, storage=storage,            precomputed_normalization=normalization_for_reversed,
        )
    assert list(out_dir.iterdir()) == []


def test_precomputed_normalization_with_only_auction_id_changed_is_rejected(
    tmp_path: Path,
) -> None:
    out_dir = tmp_path / "pub"
    out_dir.mkdir()
    storage = AuctionStorage(tmp_path / "auctions.db")
    original = make_import_result([_import_row(auction_id="AAA000000000000001")])
    normalization = normalize_prices_for_output(
        original.rows, storage=storage,    )
    assert normalization.succeeded

    # Only the Auction ID differs; every other binding field (state, exit/entry
    # market, source tariff/premium) is identical.
    renamed_auction = make_import_result([_import_row(auction_id="ZZZ999999999999999")])

    with pytest.raises(ValueError):
        publish_cumulative_output(
            renamed_auction, out_dir, storage=storage,            precomputed_normalization=normalization,
        )
    assert list(out_dir.iterdir()) == []


def test_precomputed_normalization_with_only_source_tariff_price_changed_is_rejected(
    tmp_path: Path,
) -> None:
    out_dir = tmp_path / "pub"
    out_dir.mkdir()
    storage = AuctionStorage(tmp_path / "auctions.db")
    original = make_import_result([_import_row(tariff_source_mwh_h=20.0)])
    normalization = normalize_prices_for_output(
        original.rows, storage=storage,    )
    assert normalization.succeeded

    repriced = make_import_result([_import_row(tariff_source_mwh_h=999.0)])

    with pytest.raises(ValueError):
        publish_cumulative_output(
            repriced, out_dir, storage=storage,            precomputed_normalization=normalization,
        )
    assert list(out_dir.iterdir()) == []


def test_precomputed_normalization_with_only_source_premium_price_changed_is_rejected(
    tmp_path: Path,
) -> None:
    out_dir = tmp_path / "pub"
    out_dir.mkdir()
    storage = AuctionStorage(tmp_path / "auctions.db")
    original = make_import_result([_import_row(premium_source_mwh_h=5.0)])
    normalization = normalize_prices_for_output(
        original.rows, storage=storage,    )
    assert normalization.succeeded

    repriced = make_import_result([_import_row(premium_source_mwh_h=999.0)])

    with pytest.raises(ValueError):
        publish_cumulative_output(
            repriced, out_dir, storage=storage,            precomputed_normalization=normalization,
        )
    assert list(out_dir.iterdir()) == []


def test_precomputed_normalization_for_the_exact_original_batch_is_still_reused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The exact-batch binding check must not reject the legitimate reuse
    case: the identical batch it was computed for still passes and still
    triggers no second `normalize_prices_for_output()` call."""
    out_dir = tmp_path / "pub"
    out_dir.mkdir()
    storage = AuctionStorage(tmp_path / "auctions.db")
    import_result = make_import_result([
        _import_row(auction_id="AAA000000000000001", tariff_source_mwh_h=20.0),
        _import_row(auction_id="BBB000000000000002", tariff_source_mwh_h=40.0),
    ])
    normalization = normalize_prices_for_output(
        import_result.rows, storage=storage,    )
    assert normalization.succeeded

    def fail_if_called(*_a, **_k):
        pytest.fail(
            "normalize_prices_for_output must not run again for the exact "
            "original batch."
        )

    monkeypatch.setattr("prisma_publication.normalize_prices_for_output", fail_if_called)
    result = publish_cumulative_output(
        import_result, out_dir, storage=storage,        precomputed_normalization=normalization,
    )
    assert result.succeeded
    _, records = _read_published(result.output_path)
    assert len(records) == 2


def test_invalid_source_price_in_a_precomputed_batch_leaves_existing_output_byte_for_byte_unchanged(
    tmp_path: Path,
) -> None:
    """A blocked batch (here, one row with a NaN source Tariff Price) must
    never touch an already-published cumulative file, whether the block
    happens inside `publish_cumulative_output`'s own normalization pass or
    via a precomputed `BLOCKED` result."""
    out_dir = tmp_path / "pub"
    out_dir.mkdir()
    storage = AuctionStorage(tmp_path / "auctions.db")
    first = _publish(import_result_for(tmp_path, [BASE]), out_dir, tmp_path, storage=storage)
    assert first.succeeded
    existing_bytes = first.output_path.read_bytes()

    bad_row = _import_row(auction_id="ZZZ999999999999999", tariff_source_mwh_h=float("nan"))
    blocked_import_result = make_import_result([bad_row])
    blocked = normalize_prices_for_output(
        blocked_import_result.rows, storage=storage,    )
    assert not blocked.succeeded
    assert blocked.prices_by_row_index == {}

    result = publish_cumulative_output(
        blocked_import_result, out_dir, storage=storage,        precomputed_normalization=blocked,
    )
    assert result.outcome is PrismaPublicationOutcome.PRICE_NORMALIZATION_FAILED
    assert first.output_path.read_bytes() == existing_bytes
