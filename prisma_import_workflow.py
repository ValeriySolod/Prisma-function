"""Recoverable orchestration for user-supplied PRISMA Export CSV files.

SQLite is authoritative for source lifecycle. Legacy JSON is read only when the
ledger is empty. A pending ledger row precedes auction mutation; auction changes
and summary metadata share one transaction with the data_committed transition.

P.40 correction (2026-08-17, real-Windows validation finding). The prior
source-operation lifecycle rejected a second distinct CSV import for a
source date that already had an accepted source ("Accepted sources must have
unique source dates in ascending order."), which blocked legitimate
same-day/same-period re-imports. That whole source-date uniqueness invariant
— along with `prisma_source_updates.py`'s `evaluate_prisma_source_update`/
`PrismaSourceState`, which enforced it — is removed from this active path.
Source provenance (source date, filename, or whole-file sha256) is never used
to deduplicate or reject an import here; `storage.AuctionStorage.
begin_operation` now keys the ledger by sha256 alone (see its docstring), so
distinct files sharing a source date are always independently accepted. The
only content-level idempotence guarantee in this workflow is
`prisma_publication.publish_cumulative_output`'s P.40 composite row key
("Auction ID + Network Point Name + Capacity Type"); exact-retry and
partial-overlap imports rely on that, and on `apply_operation`'s own
identity-keyed upsert, exclusively — never on a source-provenance comparison
performed before processing. A digest match against an already in-flight or
already-accepted ledger row still short-circuits re-processing the exact same
bytes, but this is an internal resume/bookkeeping optimization, not a
rejection path: it never blocks a distinct file, and every processing
attempt — new content or a resumed retry — leaves the ledger in a resolved
terminal state (`accepted`) on success, or an inert, non-blocking row on
failure, so the next Select CSV attempt (any file, any date) is never blocked
by a previous attempt's outcome.

P.36.21/P.37 correction. This is `app.py`'s only active completed-processing
path (the "Select CSV" action), so it is also where the strict EUR/MWh/h
invariant must be enforced for the application to ever present a result as
completed. `price_normalization.normalize_prices_for_output` (resolving the
ECB rate per P.37 by `(auction_date, currency)` parsed directly from each
row's own `Start of Auction` and CSV unit strings, with its own durable
cache — no PRISMA lookup, no market-catalog currency) is resolved exactly
once per processing operation, strictly before any operation-state
transition or output write; a blocked normalization raises
`PrismaPriceNormalizationError` (a `PrismaWorkflowError`) with no state
change and no output written, so a retry is always safe once resolution
becomes available. That one `PriceNormalizationResult` is then reused as-is
(`precomputed_normalization=`) when publishing, so
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

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from pathlib import Path

from csv_contracts import CsvFormat, detect_csv_format
from ecb_rates import EcbRateSource
from price_normalization import (
    PriceNormalizationResult,
    describe_price_normalization_failure,
    normalize_prices_for_output,
)
from prisma_publication import describe_publication_failure, publish_cumulative_output
from prisma_references import DEFAULT_PRISMA_REFERENCES, PrismaReferenceCatalog
from processor import PrismaImportIssue, import_prisma_export
from storage import AuctionStorage, AuctionStorageError

__all__ = [
    "PrismaWorkflowError",
    "PrismaPriceNormalizationError",
    "PrismaWorkflowResult",
    "SourceUpdateStatus",
    "run_prisma_import_workflow",
]


class SourceUpdateStatus(str, Enum):
    """Whether one processing operation's source content was new (`APPLIED`)
    or an exact-content retry of a previously accepted operation
    (`UNCHANGED`), keyed by sha256 alone (P.40 correction — never source
    date, filename, or any cross-operation date comparison). Row-level
    idempotence is provided exclusively by `prisma_publication`'s composite
    key, independent of this status."""

    APPLIED = "applied"
    UNCHANGED = "unchanged"


class PrismaWorkflowError(RuntimeError):
    pass


class PrismaPriceNormalizationError(PrismaWorkflowError):
    """At least one otherwise-publishable row lacks a confirmed EUR/MWh/h
    conversion (P.36.21/P.37). No source operation was begun/applied/
    finalized and no output was created or replaced; retry once the missing
    ECB rate evidence for the required auction date/currency becomes
    available. `normalization` carries the full typed detail (affected
    Auction IDs and stable reason codes) for callers/logs; `str(self)` is
    the same stable, technical-detail-free summary shown to the user."""

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
    total_source_rows: int | None = None
    accepted: int | None = None
    deduplicated: int | None = None

    def summary(self) -> str:
        value = lambda item: "unavailable" if item is None else str(item)
        audit = self.audit_issue_count if self.audit_issue_count is not None else len(self.issues)
        source_rows = self.total_source_rows if self.total_source_rows is not None else self.processed
        accepted = self.accepted if self.accepted is not None else self.processed
        deduplicated = self.deduplicated if self.deduplicated is not None else 0
        return (
            f"{self.message} Source rows: {value(source_rows)}; accepted: {value(accepted)}; "
            f"filtered: {value(self.filtered)}; rejected: {value(self.rejected)}; "
            f"deduplicated: {value(deduplicated)}; inserted: {value(self.inserted)}; "
            f"updated: {value(self.updated)}; unchanged: {value(self.unchanged)}; "
            f"audit issues: {value(audit)}. Output: {self.output_path}"
        )


def _migrate_legacy_json_state(storage: AuctionStorage, legacy_path: Path) -> None:
    """One-time migration of a pre-SQLite accepted-source ledger, if present.

    Only runs while the SQLite ledger is still empty. P.40 correction: each
    valid entry is migrated as-is, with no ordering or per-date uniqueness
    invariant imposed across entries — multiple entries may legitimately
    share a source date, exactly like any other operation now.
    """
    if storage.operations() or not legacy_path.exists():
        return
    try:
        payload = json.loads(legacy_path.read_text(encoding="utf-8"))
        entries = payload["accepted_sources"]
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        raise PrismaWorkflowError("The legacy PRISMA import state could not be read safely.") from exc
    for item in entries:
        try:
            source_date_value = date.fromisoformat(item["source_date"])
            source_name = item["source_name"]
            digest = item["sha256"]
            valid_name = (
                type(source_name) is str and source_name and Path(source_name).name == source_name
            )
            valid_digest = (
                type(digest) is str and len(digest) == 64
                and all(character in "0123456789abcdef" for character in digest)
            )
            if not valid_name or not valid_digest:
                raise ValueError("Invalid legacy accepted source entry.")
        except (KeyError, TypeError, ValueError) as exc:
            raise PrismaWorkflowError("The legacy PRISMA import state could not be read safely.") from exc
        storage.import_legacy_operation(
            f"legacy-{source_date_value.isoformat()}-{digest[:12]}",
            source_date_value.isoformat(), source_name, digest,
        )


def _result_from_operation(
    row,
    output_path: Path,
    status: SourceUpdateStatus,
    message: str,
    issues: tuple[PrismaImportIssue, ...] = (),
    *,
    processed: int | None = None,
    inserted: int | None = None,
    updated: int | None = None,
    unchanged: int | None = None,
    filtered: int | None = None,
    rejected: int | None = None,
    audit_issue_count: int | None = None,
    total_source_rows: int | None = None,
    accepted: int | None = None,
    deduplicated: int | None = None,
) -> PrismaWorkflowResult:
    summary = json.loads(row["summary_json"] or "{}")
    get = lambda key: int(summary[key]) if key in summary else None
    return PrismaWorkflowResult(
        processed if processed is not None else get("processed"),
        inserted if inserted is not None else get("inserted"),
        updated if updated is not None else get("updated"),
        unchanged if unchanged is not None else get("unchanged"),
        filtered if filtered is not None else get("filtered"),
        rejected if rejected is not None else get("rejected"),
        issues, output_path, status, message,
        audit_issue_count if audit_issue_count is not None else get("audit_issues"),
        total_source_rows if total_source_rows is not None else get("total_source_rows"),
        accepted if accepted is not None else get("accepted"),
        deduplicated if deduplicated is not None else get("deduplicated"))


def run_prisma_import_workflow(
    source_path: str | Path, *, source_date: date, evaluated_at: datetime,
    database_path: Path, state_path: Path, publication_directory: Path,
    reference_catalog: PrismaReferenceCatalog = DEFAULT_PRISMA_REFERENCES,
    ecb_source: EcbRateSource | None = None,
) -> PrismaWorkflowResult:
    """Validate, EUR-normalize (P.36.21/P.37), and publish (P.36.16) one
    PRISMA Export CSV as the exact 12-column cumulative EUR/MWh/h output.

    ``ecb_source`` is forwarded unchanged to
    `price_normalization.resolve_ecb_rates_for_rows` for any uncached
    `(auction_date, currency)` pair. Per P.37, this needs no PRISMA lookup
    at all -- the ECB rate is resolved from each row's own `Start of
    Auction` calendar date and each price's own CSV-unit-derived currency,
    so, unlike the pre-P.37 mechanism, a never-before-cached pair still
    resolves on demand (from ECB) instead of permanently blocking. A
    previously resolved pair is served from `storage.AuctionStorage`'s
    durable cache. This function never touches a browser itself.

    P.40 correction: ``source_date``/the source file's name/its whole-file
    sha256 are never compared against any other operation to accept, reject,
    or deduplicate this import — see the module docstring. ``source_date``
    is used only to (a) reject an evaluation-clock-relative future date and
    (b) record provenance on the ledger row; it never gates acceptance
    against other operations.
    """
    if source_date > evaluated_at.date():
        raise PrismaWorkflowError("The source date is later than the evaluation date.")

    detection = detect_csv_format(source_path)
    if detection.format is CsvFormat.MONITORING:
        raise PrismaWorkflowError(
            "Monitoring CSV cannot be imported as detailed PRISMA results."
        )
    if detection.format is CsvFormat.AMBIGUOUS:
        raise PrismaWorkflowError("The CSV contract is ambiguous and cannot be imported safely.")
    if detection.format is not CsvFormat.PRISMA_EXPORT:
        raise PrismaWorkflowError(detection.message)

    path = Path(source_path)
    try:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise PrismaWorkflowError(
            "The PRISMA source did not pass authoritative import validation."
        ) from exc

    storage = AuctionStorage(database_path)
    _migrate_legacy_json_state(storage, state_path)

    try:
        imported = import_prisma_export(path, reference_catalog=reference_catalog)
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError("The PRISMA source changed while it was being validated.")
    except Exception as exc:
        raise PrismaWorkflowError(
            "The PRISMA source did not pass authoritative import validation."
        ) from exc

    # P.36.21/P.37 strict EUR gate: resolved once, before any operation-state
    # transition or output write. A blocked normalization never begins,
    # applies, or finalizes a source operation, and never creates, replaces,
    # or appends any output.
    normalization = normalize_prices_for_output(
        imported.rows, storage=storage, ecb_source=ecb_source,
    )
    if not normalization.succeeded:
        raise PrismaPriceNormalizationError(normalization)

    try:
        operation = storage.begin_operation(source_date.isoformat(), path.name, digest)
        already_accepted = operation["status"] == "accepted"
        if operation["status"] == "pending":
            summary = {"total_source_rows": imported.total_source_rows,
                       "accepted": imported.imported_count,
                       "filtered": imported.filtered_count, "rejected": imported.rejected_count,
                       "audit_issues": len(imported.issues)}
            storage.apply_operation(operation["operation_id"], imported.rows, summary)
            operation = storage.operation_for_digest(digest)

        publication = publish_cumulative_output(
            imported, publication_directory, storage=storage,
            ecb_source=ecb_source,
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
        final = storage.operation_for_digest(digest)
        status = SourceUpdateStatus.UNCHANGED if already_accepted else SourceUpdateStatus.APPLIED
        message = (
            "Exact retry: the accepted PRISMA source and confirmed EUR output are valid."
            if already_accepted else
            "The PRISMA source was validated, confirmed in EUR, published, and accepted."
        )
        current_stats = (
            {
                "processed": imported.imported_count,
                "inserted": 0,
                "updated": 0,
                "unchanged": imported.imported_count,
                "filtered": imported.filtered_count,
                "rejected": imported.rejected_count,
                "audit_issue_count": len(imported.issues),
            }
            if already_accepted else
            {}
        )
        return _result_from_operation(
            final, publication.output_path, status, message, tuple(imported.issues),
            **current_stats,
            total_source_rows=imported.total_source_rows,
            accepted=imported.imported_count,
            deduplicated=publication.deduplicated_row_count,
        )
    except (AuctionStorageError, sqlite3.Error, OSError) as exc:
        raise PrismaWorkflowError(str(exc)) from exc
