"""Recoverable orchestration for user-supplied PRISMA Export CSV files.

SQLite is authoritative for source lifecycle. Legacy JSON is read only when the
ledger is empty. A pending ledger row precedes auction mutation; auction changes
and summary metadata share one transaction with the data_committed transition.

P.36.21 correction. This is `app.py`'s only active completed-processing path
(the "Import PRISMA Export" button), so it is also where P.36.21's strict
EUR/MWh/h invariant must be enforced for the application to ever present a
result as completed. `price_normalization.normalize_prices_for_output`
(reusing P.36.19's `rate_resolution.resolve_rates_for_rows` and its durable
per-Auction-ID cache) is resolved exactly once per processing operation,
strictly before any operation-state transition or output write; a blocked
normalization raises `PrismaPriceNormalizationError` (a `PrismaWorkflowError`)
with no state change and no output written, so a retry is always safe once
resolution becomes available. That one `PriceNormalizationResult` is then
reused as-is (`precomputed_normalization=`) when publishing, so
`price_normalization.normalize_prices_for_output` never runs a second time
for the same batch. The active published result is the strict, EUR-confirmed
12-column CSV written by `prisma_publication.publish_cumulative_output`
(P.36.16) — never the pre-P.36 `storage.export_excel()` Excel workbook, which
labels its price columns "EUR" without ever confirming a currency conversion.
`storage.export_excel`/`AuctionStorage.EXCEL_COLUMNS`/`validate_excel` remain
defined, unchanged, and independently tested (`tests/test_storage.py`) as
dormant compatibility code; this module simply no longer calls them. The
`auctions` SQLite table is still populated via `storage.apply_operation()`
(dormant bookkeeping — historical-backfill/audit infrastructure — never the
presented output) so that unrelated functionality keeps working.

Publication location correction (2026-08-13, second review pass).
``publication_directory`` must already be an existing, approved, user-facing
directory — the Documents-directory contract (`P.36.3`) `app.py` already
validates via `download_directory.validate_download_directory()` before this
function is ever called — never `%LOCALAPPDATA%`. This function does not
create, mkdir, or otherwise silently materialize ``publication_directory``
itself; `prisma_publication.
publish_cumulative_output`'s own existing-directory validation is the single
place that check happens, so a directory that has since become unavailable
(deleted, unmounted, permissions revoked) fails closed with a typed
`PrismaWorkflowError` instead of being silently recreated.
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from csv_contracts import CsvFormat, detect_csv_format
from ecb_rates import EcbRateSource
from price_normalization import (
    PriceNormalizationResult,
    describe_price_normalization_failure,
    normalize_prices_for_output,
)
from prisma_auction_lookup import PrismaAuctionLookup
from prisma_publication import describe_publication_failure, publish_cumulative_output
from prisma_references import DEFAULT_PRISMA_REFERENCES, PrismaReferenceCatalog
from prisma_source_updates import AcceptedPrismaSource, PrismaSourceState, SourceUpdateStatus, evaluate_prisma_source_update
from processor import PrismaImportIssue, PrismaImportResult, import_prisma_export
from storage import AuctionStorage, AuctionStorageError

__all__ = [
    "PrismaWorkflowError",
    "PrismaPriceNormalizationError",
    "PrismaWorkflowResult",
    "run_prisma_import_workflow",
]


class PrismaWorkflowError(RuntimeError):
    pass


class PrismaPriceNormalizationError(PrismaWorkflowError):
    """At least one otherwise-publishable row lacks a confirmed EUR/MWh/h
    conversion (P.36.21). No source operation was begun/applied/finalized and
    no output was created or replaced; retry once the missing currency,
    auction-end, or ECB rate evidence becomes available. `normalization`
    carries the full typed detail (affected Auction IDs and stable reason
    codes) for callers/logs; `str(self)` is the same stable,
    technical-detail-free summary shown to the user."""

    def __init__(self, normalization: PriceNormalizationResult) -> None:
        self.normalization = normalization
        super().__init__(describe_price_normalization_failure(normalization))


@dataclass(frozen=True)
class PrismaWorkflowResult:
    processed: int | None
    inserted: int | None
    updated: int | None
    unchanged: int | None
    filtered: int | None
    rejected: int | None
    issues: tuple[PrismaImportIssue, ...]
    output_path: Path
    source_status: SourceUpdateStatus
    message: str
    audit_issue_count: int | None = None

    def summary(self) -> str:
        value = lambda item: "unavailable" if item is None else str(item)
        audit = self.audit_issue_count if self.audit_issue_count is not None else len(self.issues)
        return (
            f"{self.message} Processed: {value(self.processed)}; inserted: {value(self.inserted)}; "
            f"updated: {value(self.updated)}; unchanged: {value(self.unchanged)}; "
            f"filtered: {value(self.filtered)}; rejected: {value(self.rejected)}; "
            f"audit issues: {value(audit)}. Output: {self.output_path}"
        )


def _legacy_state(path: Path) -> PrismaSourceState:
    if not path.exists():
        return PrismaSourceState()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return PrismaSourceState(tuple(AcceptedPrismaSource(
            date.fromisoformat(item["source_date"]), item["source_name"], item["sha256"]
        ) for item in payload["accepted_sources"]))
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        raise PrismaWorkflowError("The legacy PRISMA import state could not be read safely.") from exc


def _state(storage: AuctionStorage, legacy_path: Path) -> PrismaSourceState:
    rows = storage.operations()
    if not rows:
        legacy = _legacy_state(legacy_path)
        for accepted in legacy.accepted_sources:
            storage.import_legacy_operation(
                f"legacy-{accepted.source_date.isoformat()}-{accepted.sha256[:12]}",
                accepted.source_date.isoformat(), accepted.source_name, accepted.sha256,
            )
        rows = storage.operations()
    accepted = tuple(AcceptedPrismaSource(
        date.fromisoformat(row["source_date"]), row["source_name"], row["sha256"]
    ) for row in rows if row["status"] == "accepted")
    return PrismaSourceState(accepted)


def _result_from_operation(row, output_path: Path, status: SourceUpdateStatus, message: str,
                            issues: tuple[PrismaImportIssue, ...] = ()) -> PrismaWorkflowResult:
    summary = json.loads(row["summary_json"] or "{}")
    get = lambda key: int(summary[key]) if key in summary else None
    return PrismaWorkflowResult(get("processed"), get("inserted"), get("updated"), get("unchanged"),
        get("filtered"), get("rejected"), issues, output_path, status, message, get("audit_issues"))


def run_prisma_import_workflow(
    source_path: str | Path, *, source_date: date, evaluated_at: datetime,
    database_path: Path, state_path: Path, publication_directory: Path,
    reference_catalog: PrismaReferenceCatalog = DEFAULT_PRISMA_REFERENCES,
    auction_lookup: PrismaAuctionLookup | None = None,
    page: object = None,
    ecb_source: EcbRateSource | None = None,
) -> PrismaWorkflowResult:
    """Validate, EUR-normalize (P.36.21), and publish (P.36.16) one PRISMA
    Export CSV as the exact 12-column cumulative EUR/MWh/h output.

    ``auction_lookup``/``page`` are forwarded unchanged to
    `rate_resolution.resolve_rates_for_rows` for any uncached Finished
    auction. Per the revised specification, PrismaFunction never opens,
    controls, or downloads anything from the PRISMA website, so no caller
    supplies either argument today: an uncached Finished auction's rate
    resolution fails closed (`RateResolutionOutcome.AUCTION_END_UNAVAILABLE`)
    instead of blocking on live PRISMA access, and a previously resolved
    auction is served from `storage.AuctionStorage`'s durable cache. Both
    parameters remain so a fake/test `PrismaAuctionLookup` can still exercise
    this function's full call graph. This function never touches a browser
    itself.
    """
    detection = detect_csv_format(source_path)
    if detection.format is CsvFormat.MONITORING:
        raise PrismaWorkflowError(
            "Monitoring CSV cannot be imported as detailed PRISMA results."
        )
    if detection.format is CsvFormat.AMBIGUOUS:
        raise PrismaWorkflowError("The CSV contract is ambiguous and cannot be imported safely.")
    if detection.format is not CsvFormat.PRISMA_EXPORT:
        raise PrismaWorkflowError(detection.message)

    storage = AuctionStorage(database_path)
    unresolved = storage.unresolved_operations()
    if any(row["source_date"] != source_date.isoformat() for row in unresolved):
        raise PrismaWorkflowError(
            "Another PRISMA source operation is unresolved. Retry that source before importing a new date."
        )
    captured: list[PrismaImportResult] = []
    def importer(path):
        result = import_prisma_export(path, reference_catalog=reference_catalog)
        captured.append(result)
        return result
    update = evaluate_prisma_source_update(source_path, source_date=source_date, evaluated_at=evaluated_at,
        prior_state=_state(storage, state_path), importer=importer)
    if update.status is SourceUpdateStatus.REJECTED:
        raise PrismaWorkflowError(update.message)

    imported = captured[0] if captured else import_prisma_export(source_path, reference_catalog=reference_catalog)

    # P.36.21 strict EUR gate: resolved once, before any operation-state
    # transition or output write. A blocked normalization never begins,
    # applies, or finalizes a source operation, and never creates, replaces,
    # or appends any output.
    normalization = normalize_prices_for_output(
        imported.rows, storage=storage, reference_catalog=reference_catalog,
        auction_lookup=auction_lookup, page=page, ecb_source=ecb_source,
    )
    if not normalization.succeeded:
        raise PrismaPriceNormalizationError(normalization)

    try:
        operation = storage.begin_operation(source_date.isoformat(), update.source_name, update.sha256)
        already_accepted = operation["status"] == "accepted"
        if operation["status"] == "pending":
            summary = {"total_source_rows": imported.total_source_rows,
                       "filtered": imported.filtered_count, "rejected": imported.rejected_count,
                       "audit_issues": len(imported.issues)}
            storage.apply_operation(operation["operation_id"], imported.rows, summary)
            operation = storage.operation_for_date(source_date.isoformat())

        publication = publish_cumulative_output(
            imported, publication_directory, storage=storage,
            reference_catalog=reference_catalog, auction_lookup=auction_lookup,
            page=page, ecb_source=ecb_source,
            precomputed_normalization=normalization,
        )
        if not publication.succeeded:
            # The normalization gate above already guarantees every row's
            # price is confirmed EUR; a failure here is a destination/
            # existing-file problem, never an unconfirmed-price problem.
            # Never finalize as accepted on this failure.
            raise PrismaWorkflowError(describe_publication_failure(publication.outcome))

        if not already_accepted:
            storage.finalize_operation(operation["operation_id"])
        final = storage.operation_for_date(source_date.isoformat())
        message = (
            "Exact retry: the accepted PRISMA source and confirmed EUR output are valid."
            if already_accepted else
            "The PRISMA source was validated, confirmed in EUR, published, and accepted."
        )
        return _result_from_operation(
            final, publication.output_path, update.status, message, tuple(imported.issues)
        )
    except (AuctionStorageError, sqlite3.Error, OSError) as exc:
        raise PrismaWorkflowError(str(exc)) from exc
