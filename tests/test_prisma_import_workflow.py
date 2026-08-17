from __future__ import annotations

import csv
from datetime import date, datetime, timezone
from pathlib import Path

import hashlib
import json
import pandas as pd
import pytest
import sqlite3

import prisma_import_workflow as workflow
import prisma_output
import prisma_publication
from csv_contracts import MONITORING_CSV_COLUMNS, PRISMA_EXPORT_COLUMNS, CsvDetectionResult, CsvFormat
from ecb_rates import EcbRateNotFoundError
from prisma_import_workflow import PrismaWorkflowError, run_prisma_import_workflow
from prisma_references import (
    PrismaReference,
    PrismaReferenceCatalog,
    ReferenceAlias,
    ReferenceClassification,
    ReferenceSide,
)
from processor import import_prisma_export
from storage import AuctionStorage, AuctionStorageError


BASE = {
    "Auction ID": "A-1", "Start of Auction": "01.01.2025 09:00",
    "Marketed Capacity": "1000", "Unit Marketed Capacity": "kWh/h",
    "Product Runtime Start": "02.01.2025 00:00", "Product Runtime End": "03.01.2025 00:00",
    "Direction": "Entry", "Network Point Name Entry": "VGS Storage Hub (4290)",
    "Network Point ID Entry": "ENTRY-ID", "Regulated Tariff Entry TSO": "0.75",
    "Unit Regulated Entry Capacity Tariff": "cent/kWh/h/Runtime",
    "Surcharge": "0.5", "Unit Surcharge": "cent/kWh/h/Runtime", "State": "Finished",
}

# P.37: every default row above uses `cent/kWh/h/Runtime` units, which
# `processor.py` resolves to currency EUR -- `ecb_rates.resolve_rate_to_eur`
# short-circuits EUR to the identity rate with zero ECB access, so these
# tests never perform real ECB network access. `eur_catalog()` grants market/
# storage name resolution for "VGS Storage Hub (4290)" (a test-only catalog,
# distinct from the real `DEFAULT_PRISMA_REFERENCES`); its currency-evidence
# fields are no longer read by P.37's pricing path. See
# `tests/test_price_normalization.py` for EUR-conversion-specific coverage
# (non-EUR rates, blocking, Decimal precision) and `tests/test_app.py` for
# the real, unmocked `app.py` → `run_prisma_import_workflow` call-graph proof.
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


def write_export(path: Path, rows: list[dict]) -> Path:
    pd.DataFrame(rows).reindex(columns=PRISMA_EXPORT_COLUMNS).fillna("").to_csv(
        path, sep=";", encoding="cp1252", index=False
    )
    return path


def run(source: Path, root: Path, day: date, **overrides):
    kwargs = dict(
        database_path=root / "auctions.db", state_path=root / "state.json",
        publication_directory=root / "published",
        reference_catalog=eur_catalog(),
    )
    kwargs.update(overrides)
    # `run_prisma_import_workflow()` no longer creates `publication_directory`
    # itself (P.36.21 publication-location correction: it must already be an
    # approved, existing directory — `app.py` guarantees this via
    # `download_directory.validate_download_directory()` before this
    # function is ever called). Tests own that same precondition here.
    Path(kwargs["publication_directory"]).mkdir(parents=True, exist_ok=True)
    return run_prisma_import_workflow(
        source, source_date=day, evaluated_at=datetime(2025, 1, 10, tzinfo=timezone.utc), **kwargs,
    )


def read_published(root: Path) -> tuple[list[str], list[dict[str, str]]]:
    path = root / "published" / prisma_publication.PUBLISHED_OUTPUT_FILENAME
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle, delimiter=";")
        rows = list(reader)
    header = rows[0]
    records = [dict(zip(header, row)) for row in rows[1:]]
    return header, records


def test_new_repeat_and_next_daily_export_are_cumulative_and_enriched(tmp_path):
    first = write_export(tmp_path / "first.csv", [BASE])
    initial = run(first, tmp_path, date(2025, 1, 1))
    assert (initial.processed, initial.inserted, initial.updated, initial.unchanged) == (1, 1, 0, 0)
    repeated = run(first, tmp_path, date(2025, 1, 1))
    assert repeated.source_status.value == "unchanged"
    assert repeated.deduplicated == 1
    assert (repeated.inserted, repeated.updated, repeated.unchanged) == (0, 0, 1)
    _, records_after_retry = read_published(tmp_path)
    assert len(records_after_retry) == 1  # retry republishes, never duplicates

    next_rows = [
        # Same identity as A-1, but a changed non-output field (TSO Entry)
        # so the `auctions` row is counted "updated"; the 12-column output
        # (which excludes TSO fields) stays identical, so it still
        # deduplicates against the already-published A-1 row.
        {**BASE, "TSO Entry": "GUD"},
        {**BASE, "Auction ID": "A-2", "Network Point ID Entry": "ENTRY-2", "Marketed Capacity": "2000"},
        {**BASE, "Auction ID": "A-3", "Network Point ID Entry": "ENTRY-3", "Marketed Capacity": "3000"},
    ]
    second = write_export(tmp_path / "second.csv", next_rows)
    daily = run(second, tmp_path, date(2025, 1, 1))
    assert (daily.processed, daily.inserted, daily.updated, daily.unchanged) == (3, 2, 1, 0)
    assert daily.deduplicated == 1
    header, records = read_published(tmp_path)
    assert tuple(header) == prisma_output.OUTPUT_CSV_COLUMNS
    # A-1 deduplicates against its own already-published row (exact 12-field
    # match); A-2/A-3 are genuinely distinct (different Booked Capacity) and
    # are appended.
    assert len(records) == 3
    assert {record["Entry Market"] for record in records} == {"VGS Storage Hub"}
    assert sorted(record["Booked Capacity"] for record in records) == ["1000.0", "2000.0", "3000.0"]


def test_same_date_partially_overlapping_csv_adds_only_new_distinct_rows(tmp_path):
    run(write_export(tmp_path / "first.csv", [BASE]), tmp_path, date(2025, 1, 1))
    second_rows = [
        BASE,
        {**BASE, "Auction ID": "A-2", "Network Point ID Entry": "ENTRY-2", "Marketed Capacity": "2000"},
    ]

    result = run(write_export(tmp_path / "second.csv", second_rows), tmp_path, date(2025, 1, 1))
    _, records = read_published(tmp_path)

    assert result.source_status.value == "applied"
    assert result.total_source_rows == 2
    assert result.accepted == 2
    assert result.deduplicated == 1
    assert result.inserted == 1
    assert len(records) == 2
    assert sorted(record["Booked Capacity"] for record in records) == ["1000.0", "2000.0"]


def test_manual_csv_workflow_processes_and_publishes_more_than_5000_rows(tmp_path):
    rows = [
        {
            **BASE,
            "Auction ID": f"A-{index:05d}",
            "Network Point ID Entry": f"ENTRY-{index:05d}",
            "Marketed Capacity": str(1000 + index),
        }
        for index in range(5001)
    ]

    result = run(write_export(tmp_path / "large.csv", rows), tmp_path, date(2025, 1, 1))
    header, records = read_published(tmp_path)

    assert tuple(header) == prisma_output.OUTPUT_CSV_COLUMNS
    assert len(records) == 5001
    assert result.total_source_rows == 5001
    assert result.accepted == 5001
    assert result.filtered == 0
    assert result.rejected == 0
    assert result.deduplicated == 0
    assert "Source rows: 5001" in result.summary()
    assert "accepted: 5001" in result.summary()
    assert "deduplicated: 0" in result.summary()


def test_normal_import_never_runs_historical_backfill(tmp_path, monkeypatch):
    monkeypatch.setattr(
        AuctionStorage,
        "backfill_historical_market_storage",
        lambda *_: pytest.fail("historical backfill must remain explicit"),
    )
    result = run(
        write_export(tmp_path / "source.csv", [BASE]),
        tmp_path,
        date(2025, 1, 1),
    )
    assert result.inserted == 1


def test_daily_export_reports_inserted_updated_and_unchanged(tmp_path):
    first_rows = [BASE, {**BASE, "Auction ID": "A-2", "Network Point ID Entry": "E-2", "Marketed Capacity": "2000"}]
    run(write_export(tmp_path / "one.csv", first_rows), tmp_path, date(2025, 1, 1))
    next_rows = [
        {**BASE, "TSO Entry": "GUD"},  # same identity as A-1, changed non-output field: "updated"
        first_rows[1],  # exact repeat of A-2: "unchanged"
        {**BASE, "Auction ID": "A-3", "Network Point ID Entry": "E-3", "Marketed Capacity": "3000"},
    ]
    result = run(write_export(tmp_path / "two.csv", next_rows), tmp_path, date(2025, 1, 2))
    assert (result.inserted, result.updated, result.unchanged) == (1, 1, 1)


def test_malformed_rows_are_audited_without_losing_valid_rows(tmp_path):
    source = write_export(tmp_path / "mixed.csv", [BASE, {**BASE, "Direction": "sideways"}])
    result = run(source, tmp_path, date(2025, 1, 1))
    assert (result.processed, result.rejected, len(result.issues)) == (1, 1, 1)
    assert result.issues[0].source_row_number == 3


def test_monitoring_and_unsupported_inputs_are_rejected(tmp_path):
    monitoring = tmp_path / "monitor.csv"
    monitoring.write_text(",".join(MONITORING_CSV_COLUMNS) + "\n", encoding="utf-8")
    with pytest.raises(PrismaWorkflowError) as caught:
        run(monitoring, tmp_path, date(2025, 1, 1))
    assert str(caught.value) == (
        "Monitoring CSV cannot be imported as detailed PRISMA results."
    )
    unknown = tmp_path / "unknown.csv"
    unknown.write_text("name,value\n", encoding="utf-8")
    with pytest.raises(PrismaWorkflowError, match="Unsupported CSV format"):
        run(unknown, tmp_path, date(2025, 1, 1))


def test_ambiguous_input_is_rejected_explicitly(tmp_path, monkeypatch):
    source = tmp_path / "ambiguous.csv"
    source.write_text("anything\n", encoding="utf-8")
    monkeypatch.setattr(workflow, "detect_csv_format", lambda path: CsvDetectionResult(CsvFormat.AMBIGUOUS))
    with pytest.raises(PrismaWorkflowError, match="ambiguous"):
        run(source, tmp_path, date(2025, 1, 1))


def test_output_is_deterministic_for_reversed_input(tmp_path):
    rows = [BASE, {**BASE, "Auction ID": "A-2", "Network Point ID Entry": "E-2", "Marketed Capacity": "2000"}]
    first_root, second_root = tmp_path / "a", tmp_path / "b"
    first_root.mkdir(); second_root.mkdir()
    run(write_export(first_root / "x.csv", rows), first_root, date(2025, 1, 1))
    run(write_export(second_root / "x.csv", list(reversed(rows))), second_root, date(2025, 1, 1))
    _, left = read_published(first_root)
    _, right = read_published(second_root)
    # The cumulative file's row *order* reflects append order (not a query
    # ORDER BY, unlike the pre-P.36.21 Excel export), so forward vs reversed
    # input can legitimately append in a different order; the *content* must
    # still be identical as a set.
    key = lambda record: record["Booked Capacity"]
    assert sorted(left, key=key) == sorted(right, key=key)


def test_csv_publication_failure_preserves_previous_bytes_and_retry_recovers(tmp_path, monkeypatch):
    source = write_export(tmp_path / "source.csv", [BASE])
    first = run(source, tmp_path, date(2025, 1, 1))
    published_path = tmp_path / "published" / prisma_publication.PUBLISHED_OUTPUT_FILENAME
    previous = published_path.read_bytes()

    real_replace = workflow.publish_cumulative_output.__globals__["os"].replace
    monkeypatch.setattr(
        workflow.publish_cumulative_output.__globals__["os"], "replace",
        lambda *_: (_ for _ in ()).throw(OSError("simulated disk failure")),
    )
    other = write_export(
        tmp_path / "other.csv",
        [{**BASE, "Auction ID": "A-2", "Network Point ID Entry": "E-2", "Marketed Capacity": "2000"}],
    )
    other_digest = hashlib.sha256(other.read_bytes()).hexdigest()
    with pytest.raises(PrismaWorkflowError):
        run(other, tmp_path, date(2025, 1, 2))
    assert published_path.read_bytes() == previous
    with sqlite3.connect(tmp_path / "auctions.db") as connection:
        assert connection.execute(
            "SELECT status FROM prisma_source_operations WHERE sha256=?", (other_digest,)
        ).fetchone()[0] == "data_committed"

    monkeypatch.setattr(workflow.publish_cumulative_output.__globals__["os"], "replace", real_replace)
    retried = run(other, tmp_path, date(2025, 1, 2))
    assert retried.inserted == 1
    _, records = read_published(tmp_path)
    assert len(records) == 2
    with sqlite3.connect(tmp_path / "auctions.db") as connection:
        assert connection.execute(
            "SELECT status FROM prisma_source_operations WHERE sha256=?", (other_digest,)
        ).fetchone()[0] == "accepted"


def test_different_same_date_source_is_accepted_while_another_operation_is_unresolved(tmp_path, monkeypatch):
    """P.40 correction regression test: a real-Windows validation failure
    showed a second, distinct CSV import for a source date that already had
    an operation in flight was incorrectly rejected ("Accepted sources must
    have unique source dates in ascending order."). Source-date uniqueness
    is no longer any part of the ledger's identity (see
    `prisma_import_workflow`'s module docstring), so a different file for
    the same date must always be accepted independently, even while an
    earlier, unrelated operation for that same date is still unresolved."""
    first = write_export(tmp_path / "first.csv", [BASE])
    original_publish = workflow.publish_cumulative_output
    monkeypatch.setattr(
        workflow, "publish_cumulative_output",
        lambda *_a, **_k: (_ for _ in ()).throw(AuctionStorageError("stage failed")),
    )
    with pytest.raises(PrismaWorkflowError, match="stage failed"):
        run(first, tmp_path, date(2025, 1, 1))
    with sqlite3.connect(tmp_path / "auctions.db") as connection:
        assert connection.execute(
            "SELECT status FROM prisma_source_operations"
        ).fetchone()[0] == "data_committed"

    monkeypatch.setattr(workflow, "publish_cumulative_output", original_publish)
    changed = write_export(
        tmp_path / "changed.csv",
        [{**BASE, "Auction ID": "A-9", "Network Point ID Entry": "ENTRY-9", "Marketed Capacity": "5000"}],
    )
    result = run(changed, tmp_path, date(2025, 1, 1))
    assert result.inserted == 1
    _, records = read_published(tmp_path)
    assert len(records) == 1


@pytest.mark.parametrize("damage", ["missing", "corrupt"])
def test_exact_retry_republishes_missing_output_but_detects_corruption(tmp_path, damage):
    source = write_export(tmp_path / "source.csv", [BASE])
    initial = run(source, tmp_path, date(2025, 1, 1))
    output = tmp_path / "published" / prisma_publication.PUBLISHED_OUTPUT_FILENAME
    if damage == "missing":
        output.unlink()
    else:
        output.write_bytes(b"not a valid published csv")

    if damage == "corrupt":
        # A malformed existing cumulative file is a typed publication
        # failure (`PrismaPublicationOutcome.INVALID_EXISTING_FILE`), never
        # silently overwritten or bypassed.
        with pytest.raises(PrismaWorkflowError):
            run(source, tmp_path, date(2025, 1, 1))
        assert output.read_bytes() == b"not a valid published csv"
        return

    retried = run(source, tmp_path, date(2025, 1, 1))
    assert retried.source_status is workflow.SourceUpdateStatus.UNCHANGED
    assert initial.inserted == 1
    assert (retried.inserted, retried.unchanged) == (0, 1)
    _, records = read_published(tmp_path)
    assert len(records) == 1
    with sqlite3.connect(tmp_path / "auctions.db") as connection:
        assert connection.execute("SELECT count(*) FROM auctions").fetchone()[0] == 1


def test_header_only_export_is_accepted_as_distinct_empty_import(tmp_path):
    result = run(write_export(tmp_path / "empty.csv", []), tmp_path, date(2025, 1, 1))
    assert (result.processed, result.filtered, result.rejected, result.inserted) == (0, 0, 0, 0)
    assert result.source_status is workflow.SourceUpdateStatus.APPLIED
    header, records = read_published(tmp_path)
    assert tuple(header) == prisma_output.OUTPUT_CSV_COLUMNS
    assert records == []


@pytest.mark.parametrize(
    ("row", "filtered", "rejected"),
    [({**BASE, "Marketed Capacity": "999"}, 1, 0),
     ({**BASE, "Direction": "sideways"}, 0, 1)],
)
def test_fully_nonimportable_exports_keep_exact_audit_counts(
    tmp_path, row, filtered, rejected
):
    result = run(write_export(tmp_path / "source.csv", [row]), tmp_path, date(2025, 1, 1))
    assert (result.processed, result.filtered, result.rejected) == (0, filtered, rejected)
    assert result.audit_issue_count == 1
    retried = run(tmp_path / "source.csv", tmp_path, date(2025, 1, 1))
    assert (retried.filtered, retried.rejected, retried.audit_issue_count) == (
        filtered, rejected, 1
    )


def test_sqlite_failure_before_pending_record_leaves_everything_untouched(tmp_path, monkeypatch):
    source = write_export(tmp_path / "source.csv", [BASE])
    monkeypatch.setattr(
        workflow.AuctionStorage, "begin_operation",
        lambda *_: (_ for _ in ()).throw(AuctionStorageError("begin failed")),
    )
    with pytest.raises(PrismaWorkflowError, match="begin failed"):
        run(source, tmp_path, date(2025, 1, 1))
    with sqlite3.connect(tmp_path / "auctions.db") as connection:
        assert connection.execute("SELECT count(*) FROM auctions").fetchone()[0] == 0
        assert connection.execute("SELECT count(*) FROM prisma_source_operations").fetchone()[0] == 0
    assert not (tmp_path / "published" / prisma_publication.PUBLISHED_OUTPUT_FILENAME).exists()


def test_sqlite_mid_transaction_failure_rolls_back_and_retry_resumes(tmp_path, monkeypatch):
    source = write_export(tmp_path / "source.csv", [BASE])
    original = AuctionStorage._upsert_rows

    def fail_after_mutation(connection, rows):
        original(connection, rows)
        raise sqlite3.OperationalError("injected transaction failure")

    monkeypatch.setattr(AuctionStorage, "_upsert_rows", staticmethod(fail_after_mutation))
    with pytest.raises(PrismaWorkflowError, match="injected"):
        run(source, tmp_path, date(2025, 1, 1))
    with sqlite3.connect(tmp_path / "auctions.db") as connection:
        assert connection.execute("SELECT count(*) FROM auctions").fetchone()[0] == 0
        assert connection.execute("SELECT status FROM prisma_source_operations").fetchone()[0] == "pending"
    assert not (tmp_path / "published" / prisma_publication.PUBLISHED_OUTPUT_FILENAME).exists()
    monkeypatch.setattr(AuctionStorage, "_upsert_rows", staticmethod(original))
    assert run(source, tmp_path, date(2025, 1, 1)).inserted == 1


def test_finalization_failure_remains_recoverable_and_never_reports_success(tmp_path, monkeypatch):
    source = write_export(tmp_path / "source.csv", [BASE])
    original = AuctionStorage.finalize_operation
    monkeypatch.setattr(
        AuctionStorage, "finalize_operation",
        lambda *_: (_ for _ in ()).throw(AuctionStorageError("finalize failed")),
    )
    with pytest.raises(PrismaWorkflowError, match="finalize failed"):
        run(source, tmp_path, date(2025, 1, 1))
    # The output is already fully, atomically published (P.36.21 normalized
    # the price and P.36.16 wrote the file) before finalize is even
    # attempted; only the operation's own "accepted" bookkeeping lags.
    _, records = read_published(tmp_path)
    assert len(records) == 1
    with sqlite3.connect(tmp_path / "auctions.db") as connection:
        assert connection.execute("SELECT status FROM prisma_source_operations").fetchone()[0] == "data_committed"
    monkeypatch.setattr(AuctionStorage, "finalize_operation", original)
    recovered = run(source, tmp_path, date(2025, 1, 1))
    assert recovered.inserted == 1
    with sqlite3.connect(tmp_path / "auctions.db") as connection:
        assert connection.execute("SELECT status FROM prisma_source_operations").fetchone()[0] == "accepted"


def test_legacy_json_migrates_with_unavailable_metadata_and_repairs_output(tmp_path):
    source = write_export(tmp_path / "source.csv", [BASE])
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    AuctionStorage(tmp_path / "auctions.db").upsert(
        import_prisma_export(source, reference_catalog=eur_catalog()).rows
    )
    (tmp_path / "state.json").write_text(json.dumps({"accepted_sources": [{
        "source_date": "2025-01-01", "source_name": source.name, "sha256": digest,
    }]}), encoding="utf-8")
    result = run(source, tmp_path, date(2025, 1, 1))
    assert result.source_status is workflow.SourceUpdateStatus.UNCHANGED
    assert result.total_source_rows == result.accepted == 1
    assert (result.filtered, result.rejected) == (0, 0)
    assert result.deduplicated == 0
    assert result.inserted == 0
    _, records = read_published(tmp_path)
    assert len(records) == 1


# --- P.36.21/P.37 strict EUR gate: the active workflow itself --------------

class UnavailableEcbSource:
    def fetch(self, currency, *, on_or_before, timeout_seconds):
        raise EcbRateNotFoundError(f"no rate for {currency}")


def _unresolved_entry_tariff_row(**overrides) -> dict:
    """`BASE` with its entry tariff denominated in GBP (`pence/...`) instead
    of EUR (`cent/...`), so it requires an ECB lookup -- combined with
    `UnavailableEcbSource`, this reproduces P.37's fail-closed path without
    real network access."""
    return {
        **BASE,
        "Regulated Tariff Entry TSO": "1",
        "Unit Regulated Entry Capacity Tariff": "pence/kWh/h/Runtime",
        **overrides,
    }


def test_unresolved_ecb_rate_blocks_the_active_workflow_before_any_state_change(tmp_path):
    source = write_export(tmp_path / "source.csv", [_unresolved_entry_tariff_row()])
    with pytest.raises(workflow.PrismaPriceNormalizationError) as caught:
        run(source, tmp_path, date(2025, 1, 1), ecb_source=UnavailableEcbSource())
    assert not caught.value.normalization.succeeded
    # `AuctionStorage(database_path)` always creates its schema on
    # construction, but no operation may have been begun and no auction row
    # may have been persisted: the EUR gate runs strictly before either.
    with sqlite3.connect(tmp_path / "auctions.db") as connection:
        assert connection.execute("SELECT count(*) FROM prisma_source_operations").fetchone()[0] == 0
        assert connection.execute("SELECT count(*) FROM auctions").fetchone()[0] == 0
    # `run()` pre-creates the (now-required-to-already-exist) publication
    # directory itself, matching `app.py`'s real precondition; the gate
    # blocks before `publish_cumulative_output` ever runs, so no output file
    # is written into it.
    assert not (tmp_path / "published" / prisma_publication.PUBLISHED_OUTPUT_FILENAME).exists()


def test_mixed_resolved_and_unresolved_batch_publishes_nothing(tmp_path):
    resolved_row = {
        **BASE, "Direction": "Exit", "Network Point Name Exit": "VGS Storage Hub (4290)",
        "Network Point Name Entry": "", "Network Point ID Exit": "EXIT-ID",
    }
    unresolved_row = _unresolved_entry_tariff_row(
        **{"Auction ID": "A-2", "Network Point ID Entry": "E-2"}
    )
    source = write_export(tmp_path / "mixed.csv", [resolved_row, unresolved_row])

    with pytest.raises(workflow.PrismaPriceNormalizationError):
        run(source, tmp_path, date(2025, 1, 1), ecb_source=UnavailableEcbSource())
    assert not (tmp_path / "published" / prisma_publication.PUBLISHED_OUTPUT_FILENAME).exists()
    with sqlite3.connect(tmp_path / "auctions.db") as connection:
        assert connection.execute("SELECT count(*) FROM auctions").fetchone()[0] == 0


def test_retry_succeeds_once_the_ecb_rate_becomes_available(tmp_path):
    from decimal import Decimal

    from ecb_rates import EcbRateObservation

    source = write_export(tmp_path / "source.csv", [_unresolved_entry_tariff_row()])
    with pytest.raises(workflow.PrismaPriceNormalizationError):
        run(source, tmp_path, date(2025, 1, 1), ecb_source=UnavailableEcbSource())

    class WorkingEcbSource:
        def fetch(self, currency, *, on_or_before, timeout_seconds):
            return EcbRateObservation(on_or_before, Decimal("2"))

    retried = run(source, tmp_path, date(2025, 1, 1), ecb_source=WorkingEcbSource())
    assert retried.inserted == 1
    _, records = read_published(tmp_path)
    assert len(records) == 1


# --- P.36.21 correction: one normalization result per processing operation --

def test_price_normalization_runs_exactly_once_per_processing_operation(tmp_path, monkeypatch):
    """`run_prisma_import_workflow()` must resolve/normalize prices once and
    reuse that exact `PriceNormalizationResult` when publishing
    (`publish_cumulative_output(..., precomputed_normalization=...)`), never
    call `price_normalization.normalize_prices_for_output` a second time for
    the same batch."""
    import price_normalization

    calls: list[int] = []
    original = price_normalization.normalize_prices_for_output

    def counting(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)

    monkeypatch.setattr(workflow, "normalize_prices_for_output", counting)
    monkeypatch.setattr(prisma_publication, "normalize_prices_for_output", counting)

    source = write_export(tmp_path / "source.csv", [BASE])
    result = run(source, tmp_path, date(2025, 1, 1))
    assert result.inserted == 1
    assert len(calls) == 1


def test_publication_directory_must_already_exist_and_is_never_silently_created(tmp_path):
    """The publication directory is the approved, user-facing directory
    `app.py` resolves via `download_directory.default_download_directory()`,
    never something this function conjures into existence itself; a missing
    directory fails closed instead of being silently created."""
    source = write_export(tmp_path / "source.csv", [BASE])
    missing = tmp_path / "does_not_exist"
    with pytest.raises(PrismaWorkflowError):
        run_prisma_import_workflow(
            source, source_date=date(2025, 1, 1),
            evaluated_at=datetime(2025, 1, 10, tzinfo=timezone.utc),
            database_path=tmp_path / "auctions.db", state_path=tmp_path / "state.json",
            publication_directory=missing,
            reference_catalog=eur_catalog(),
        )
    assert not missing.exists()
