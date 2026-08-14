"""Qt-independent P.36.15 boundary: transform one validated official PRISMA
Export CSV into the exact 12-column output CSV contract and write it
atomically.

Per `ROADMAP.md`'s "Authoritative output CSV contract" and `Prisma
Function.odt`, the processed output exposes exactly `Auction Date`,
`Exit Market`, `Entry Market`, `Capacity Type`, `Network Point Name`,
`Product Type`, `Flow Start`, `Flow End`, `Booked Capacity`,
`Flow Duration Hours`, `Tariff Price`, `Premium Price`, in this exact order,
UTF-8 encoded and `;`-delimited. `Exit Market`/`Entry Market` hold the
resolved market or storage name for their own side only; there are no
separate `Exit Storage`/`Entry Storage` columns.

This module performs no parsing, normalization, filtering, enrichment, or
side-specific Market/Storage resolution of its own: `processor.
import_prisma_export` (P.33/P.36.4) already implements and tests every one
of those authoritative rules, including the existing missing-side/unknown-
alias rejection behavior. This module only selects, renames, and formats the
already-enriched row shape into the approved contract, then writes it. It
performs no PRISMA navigation, browser, download, UI, accumulation, or
publication-policy operation; those remain scoped to other increments
(`P.36.16` and later).

P.36.21 strict EUR contract. `Tariff Price`/`Premium Price` must be confirmed
EUR/MWh/h before this module ever creates an output file.
`price_normalization.normalize_prices_for_output` (P.36.21) is called once,
after import, using the exact-Auction-ID rate resolved by P.36.19's
`rate_resolution.resolve_rates_for_rows`; when even one otherwise-publishable
row lacks a confirmed, usable EUR conversion, `write_prisma_output` returns
`PrismaOutputOutcome.PRICE_NORMALIZATION_FAILED` and writes nothing at all —
no reservation, no staged file, no partial output. Only a fully normalized
batch reaches `transform_row`/`_write_rows`.

No customer-approved publication naming/collision policy exists yet for this
specific transformed output (that is explicitly deferred to the blocked
`P.36.16` decision gate, which will define destination, filename, and
overwrite/versioning behavior). Pending that decision, `build_output_filename`
uses the same "<stem>_<distinguishing-suffix>.csv" template `P.36.14`
established for the downloaded source file, and collision handling reuses
`prisma_download.reserve_unique_download_path`'s existing, already-approved
never-overwrite/incrementing-suffix rule unchanged rather than reimplementing
it.
"""
from __future__ import annotations

import csv
import os
import tempfile
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from csv_contracts import CsvFormatError
from download_directory import DownloadDirectoryError, validate_download_directory
from ecb_rates import EcbRateSource
from price_normalization import (
    NormalizedPrice,
    PriceNormalizationResult,
    describe_price_normalization_failure,
    format_price,
    normalize_prices_for_output,
)
from prisma_auction_lookup import PrismaAuctionLookup
from prisma_download import reserve_unique_download_path
from prisma_references import DEFAULT_PRISMA_REFERENCES, PrismaReferenceCatalog
from processor import PrismaImportError, PrismaImportResult, import_prisma_export
from storage import AuctionStorage

__all__ = [
    "OUTPUT_CSV_COLUMNS",
    "PrismaOutputOutcome",
    "PrismaOutputResult",
    "describe_output_failure",
    "build_output_filename",
    "transform_row",
    "write_prisma_output",
]

# Authoritative 12-column contract (ROADMAP.md "Authoritative output CSV
# contract"). Exact order and spelling; never add, remove, rename, or reorder.
OUTPUT_CSV_COLUMNS = (
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

_OUTPUT_FILENAME_SUFFIX = "_transformed"
_ENCODING = "utf-8"
_DELIMITER = ";"


class PrismaOutputOutcome(str, Enum):
    """Typed outcome of one P.36.15 transform-and-write operation."""

    SUCCESS = "success"
    INVALID_OUTPUT_DIRECTORY = "invalid_output_directory"
    SOURCE_IMPORT_FAILED = "source_import_failed"
    PRICE_NORMALIZATION_FAILED = "price_normalization_failed"
    WRITE_FAILED = "write_failed"


_FAILURE_MESSAGES: dict[PrismaOutputOutcome, str] = {
    PrismaOutputOutcome.INVALID_OUTPUT_DIRECTORY: (
        "The selected output folder is not valid. Choose an existing, "
        "writable folder."
    ),
    PrismaOutputOutcome.SOURCE_IMPORT_FAILED: (
        "The selected PRISMA export CSV could not be transformed."
    ),
    PrismaOutputOutcome.PRICE_NORMALIZATION_FAILED: (
        "One or more auctions could not be confirmed in EUR/MWh/h, so no "
        "output was created. Resolve the missing currency, auction-end, or "
        "ECB rate evidence, then retry."
    ),
    PrismaOutputOutcome.WRITE_FAILED: (
        "The transformed output could not be written to the selected folder."
    ),
}


def describe_output_failure(outcome: PrismaOutputOutcome) -> str:
    """Return a stable, English, path-free message for a failed outcome."""
    return _FAILURE_MESSAGES.get(
        outcome, "The PRISMA export CSV could not be transformed."
    )


@dataclass(frozen=True)
class PrismaOutputResult:
    """Immutable typed outcome of one transform-and-write operation."""

    outcome: PrismaOutputOutcome
    output_path: Path | None = None
    import_result: PrismaImportResult | None = None
    price_normalization: PriceNormalizationResult | None = None
    error: str | None = None

    @property
    def succeeded(self) -> bool:
        return self.outcome is PrismaOutputOutcome.SUCCESS


def build_output_filename(source_path: str | Path) -> str:
    """Derive the transformed output's filename from the validated source CSV.

    See the module docstring for why this specific template was chosen
    absent an approved P.36.16 publication naming decision.
    """
    return f"{Path(source_path).stem}{_OUTPUT_FILENAME_SUFFIX}.csv"


def transform_row(row: dict, prices: NormalizedPrice) -> dict[str, str]:
    """Map one already-enriched `processor.import_prisma_export` row, plus
    its already-normalized EUR prices, into the exact 12-column output
    contract.

    ``row`` is one entry of `PrismaImportResult.rows`: parsing, unit
    normalization, capacity-threshold filtering, side-specific Market/Storage
    resolution, and Europe/Berlin date/time interpretation already happened
    there and are not repeated here. `Auction Date`/`Flow Start`/`Flow End`
    are passed through unchanged as the already-formatted `YYYY-MM-DD`/
    `YYYY-MM-DD HH:mm` strings `processor.py` (via `prisma_datetime.py`) and
    `storage.py` already treat as the authoritative timestamp representation;
    `Booked Capacity`/`Flow Duration Hours` use Python's own `str(float)`
    representation, which always uses a dot decimal separator.

    ``prices`` must already be a confirmed EUR/MWh/h conversion (P.36.21's
    `price_normalization.normalize_prices_for_output`); this function performs
    no currency resolution, ECB lookup, or conversion of its own — it only
    formats `prices` via `price_normalization.format_price`, so it can never
    perform an uncontrolled network call.
    """
    return {
        "Auction Date": row["auction_date"],
        "Exit Market": row["exit_market"],
        "Entry Market": row["entry_market"],
        "Capacity Type": row["direction"],
        "Network Point Name": row["network_point"],
        "Product Type": row["product_type"],
        "Flow Start": row["flow_start"],
        "Flow End": row["flow_end"],
        "Booked Capacity": str(row["booked_capacity_kwh_h"]),
        "Flow Duration Hours": str(row["runtime_hours"]),
        "Tariff Price": format_price(prices.tariff_price_eur_mwh_h),
        "Premium Price": format_price(prices.premium_price_eur_mwh_h),
    }


def _validate_output_directory(directory: str | Path) -> Path:
    """Accept only an existing, readable, writable directory.

    Reuses `download_directory.validate_download_directory`'s existing
    existence/readability boundary check and adds the writability check
    `prisma_download.validate_download_configuration` already requires for a
    directory PrismaFunction is about to write into.
    """
    resolved = validate_download_directory(directory)
    if not os.access(resolved, os.W_OK):
        raise DownloadDirectoryError(f"Directory is not writable: {directory}")
    return resolved


def _write_rows(target: Path, rows: list[dict[str, str]]) -> None:
    """Stage the complete CSV in the same directory, then atomically replace
    the exclusively reserved placeholder ``target``.

    A failure at any point before the final `os.replace()` leaves the staged
    temporary file only (removed in ``finally``); ``target`` itself, having
    been created by `reserve_unique_download_path`'s exclusive reservation,
    is never partially overwritten. This is the same stage-then-`os.replace`
    pattern `storage.py`'s `export_excel` and `prisma_download.py`'s
    finalize paths already use.
    """
    directory = target.parent
    descriptor, staged_name = tempfile.mkstemp(
        prefix=f".{target.stem}-", suffix=".staging", dir=directory
    )
    staged: Path | None = Path(staged_name)
    try:
        with os.fdopen(descriptor, "w", encoding=_ENCODING, newline="") as staged_file:
            writer = csv.DictWriter(
                staged_file, fieldnames=OUTPUT_CSV_COLUMNS, delimiter=_DELIMITER
            )
            writer.writeheader()
            writer.writerows(rows)
            staged_file.flush()
            os.fsync(staged_file.fileno())
        os.replace(staged, target)
        staged = None
    finally:
        if staged is not None:
            staged.unlink(missing_ok=True)


def write_prisma_output(
    source_path: str | Path,
    output_directory: str | Path,
    *,
    storage: AuctionStorage,
    reference_catalog: PrismaReferenceCatalog = DEFAULT_PRISMA_REFERENCES,
    auction_lookup: PrismaAuctionLookup | None = None,
    page: object = None,
    ecb_source: EcbRateSource | None = None,
) -> PrismaOutputResult:
    """Transform one validated official PRISMA Export CSV into the exact
    12-column output contract and write it atomically to ``output_directory``.

    ``source_path`` must already satisfy the official PRISMA Export CSV
    contract (the P.36.4/P.36.14 boundary already validates this before
    exposing a path); parsing, normalization, filtering, enrichment, and
    side-specific resolution are delegated entirely to
    `processor.import_prisma_export`, never reimplemented here.

    The destination boundary is validated before anything else. Exactly one
    output file is produced per successful call; none is produced if the
    destination is invalid, the transformation itself fails (a malformed
    source file), or — the P.36.21 strict EUR contract — at least one
    otherwise-publishable row lacks a confirmed EUR/MWh/h conversion for its
    Tariff Price/Premium Price (see `price_normalization.py`). This performs
    no accumulation, deduplication, or cross-call state tracking: every call
    is an independent operation over its own ``source_path``, matching the
    excluded scope of `P.36.16`.

    ``storage`` durably caches P.36.19 rate resolutions (reused, never
    repeated, for an Auction ID already resolved elsewhere in the same
    processing operation); ``auction_lookup``/``page``/``ecb_source`` are
    forwarded unchanged to `rate_resolution.resolve_rates_for_rows`.
    """
    try:
        directory = _validate_output_directory(output_directory)
    except DownloadDirectoryError as exc:
        return PrismaOutputResult(
            PrismaOutputOutcome.INVALID_OUTPUT_DIRECTORY, error=str(exc)
        )

    try:
        imported = import_prisma_export(source_path, reference_catalog=reference_catalog)
    except (PrismaImportError, CsvFormatError) as exc:
        return PrismaOutputResult(
            PrismaOutputOutcome.SOURCE_IMPORT_FAILED, error=str(exc)
        )

    normalization = normalize_prices_for_output(
        imported.rows,
        storage=storage,
        reference_catalog=reference_catalog,
        auction_lookup=auction_lookup,
        page=page,
        ecb_source=ecb_source,
    )
    if not normalization.succeeded:
        return PrismaOutputResult(
            PrismaOutputOutcome.PRICE_NORMALIZATION_FAILED,
            import_result=imported,
            price_normalization=normalization,
            error=describe_price_normalization_failure(normalization),
        )

    rows = [
        transform_row(row, normalization.prices_by_row_index[index])
        for index, row in enumerate(imported.rows)
    ]
    filename = build_output_filename(source_path)
    try:
        target = reserve_unique_download_path(directory, filename)
    except OSError as exc:
        return PrismaOutputResult(
            PrismaOutputOutcome.WRITE_FAILED, import_result=imported, error=str(exc)
        )

    try:
        _write_rows(target, rows)
    except OSError as exc:
        target.unlink(missing_ok=True)
        return PrismaOutputResult(
            PrismaOutputOutcome.WRITE_FAILED, import_result=imported, error=str(exc)
        )

    return PrismaOutputResult(
        PrismaOutputOutcome.SUCCESS,
        output_path=target,
        import_result=imported,
        price_normalization=normalization,
    )
