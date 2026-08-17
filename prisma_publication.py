"""Qt-independent P.36.16 boundary: publish a completed PRISMA import's
accepted, transformed rows into one cumulative, deduplicated 12-column
output CSV file, atomically.

Approved publication contract (customer decision, "option 2", 2026-08-04;
see `ROADMAP.md`'s P.36.16 entry for the full record):

- Exactly one cumulative transformed-output CSV lives in the approved
  user-facing publication directory (the same Documents-directory-or-
  user-selected-directory contract `P.36.3` already established for
  downloaded/published user-facing files, never `%LOCALAPPDATA%`).
- The file uses the exact ordered 12-column `prisma_output.OUTPUT_CSV_COLUMNS`
  contract, UTF-8 encoded, `;`-delimited, with exactly one header row.
- Ordering is deterministic: existing unique rows keep their original order;
  new unique rows are appended in their current import order.

P.40 composite-key deduplication (customer decision, 2026-08-17 — supersedes
P.36.16's original exact-full-row-equality dedup rule below).

- The persistent row boundary is the exact composite key **Auction ID +
  Network Point Name + Capacity Type** (`row["auction_id"]`,
  `row["network_point"]`, `row["direction"]` — the same source values
  `prisma_output.transform_row` places into the `Network Point Name`/
  `Capacity Type` output columns). A row is a duplicate of an
  already-published row only when all three components match; the other
  nine output fields (including `Booked Capacity`, `Flow Start`/`Flow End`,
  and the confirmed EUR prices) are never part of the identity.
- PRISMA data is immutable by customer decision. When an incoming row's
  composite key already has a durably recorded counterpart — whether
  published in an earlier call/session or earlier in the very same import
  batch (a partial-overlap import) — the already-stored row is kept
  unchanged and the incoming row is skipped outright, even if its non-key
  values differ. There is no update-in-place, no conflict error, and no
  merge.
- Different rows sharing the same source file, source date, product period,
  filename, or file hash remain independently acceptable: none of that
  metadata is part of the identity.
- The composite-key index is durable, cross-session storage
  (`storage.AuctionStorage.published_output_row_keys()`/
  `record_published_output_row_keys()`, table `published_output_row_keys`),
  never derived by re-reading the CSV file (which does not itself carry
  Auction ID). It only ever grows: a key is recorded exactly once, the first
  time its row is accepted for publication, and is never removed or
  rewritten.
- Backward compatibility / migration: `storage.AuctionStorage`'s schema
  migration is purely additive (`CREATE TABLE IF NOT EXISTS
  published_output_row_keys`, run every time `AuctionStorage` opens an
  existing database), so an older database file opens safely under the new
  code without any destructive rewrite. A cumulative *CSV* file already
  populated under the pre-P.40 exact-full-row-equality rule keeps its rows
  exactly as published — nothing in it is rewritten, reinterpreted, or
  deleted — but those pre-existing rows have no recorded composite key
  (Auction ID cannot be recovered from the CSV alone, which never carried
  that column). This is a deliberate, documented, one-time transitional
  limit, the same kind of "never reconcile old data against a new identity
  contract, just stop conflating them" choice already made for the
  unrelated pre-P.36.21 legacy-currency file (see `LEGACY_PUBLISHED_
  OUTPUT_FILENAME` below): if a source file whose rows were already
  published *before* this feature shipped is re-selected again afterward,
  those specific rows are not yet key-tracked and are evaluated fresh,
  exactly like any other incoming row. Every row a session actually
  processes through this function — old auction data included — has its
  key recorded on that first pass, so every import from that point onward,
  in this or any later session, is a genuine exact-retry/partial-overlap
  duplicate and is correctly skipped.
- Exact duplicates (by composite key only, never by content) are removed
  both between the existing published rows and the current completed
  import, and within the current completed import itself.
- If the cumulative file does not exist, it is created from the current
  completed import (even an import with zero accepted rows still produces a
  valid header-only file, matching `prisma_output.write_prisma_output`'s own
  zero-accepted-rows behavior).
- If the completed import has no rows to add (either because it has no
  accepted rows, or because every accepted row already exists in the
  cumulative file), a valid existing cumulative file is left unmodified
  rather than rewritten unnecessarily.
- An existing file that is empty, malformed (including malformed quoting,
  a blank data row, or the exact header repeated among data rows), wrongly
  delimited, undecodable as UTF-8, missing the exact expected header, or a
  symbolic link is a typed failure: it is left completely unchanged
  (a symlink is never followed, read, or replaced) and nothing is published.
  A data field's own quoted value may legitimately contain an embedded
  newline; parsing accounts for this rather than mis-splitting the row.
- Publication is atomic: the complete merged content is staged into a
  temporary file in the same directory, flushed and `fsync`ed, then
  finalized with `os.replace()` — the same stage-then-replace pattern
  `prisma_output.py`'s own `_write_rows` already uses. A failure at any
  point (staging, write, flush, fsync, or replace) never deletes or
  overwrites the previous valid cumulative file, and only the staging
  artifact created by the failed attempt is removed.
- No path outside the validated publication directory is ever read or
  written: the cumulative file's name is fixed, and the staging file is
  always created inside the same directory.
- If the cumulative CSV file itself does not currently exist (deleted, never
  created, or otherwise absent — as opposed to present-but-malformed, which
  is the typed failure above), any composite keys already durably recorded
  no longer correspond to real content in a file that is gone, so they never
  block this call: the file is rebuilt from the current import exactly like
  the pre-P.40 recovery contract, instead of silently staying empty forever
  because its rows' keys are still "known" in storage.

This module performs no parsing, filtering, normalization, or side-specific
Market/Storage resolution of its own: it operates on an already-completed
`processor.PrismaImportResult` (the exact object `processor.import_prisma_export`
already produces, and that `prisma_output.write_prisma_output` already threads
through unchanged on every outcome) and reuses `prisma_output.transform_row`/
`OUTPUT_CSV_COLUMNS` for row formatting, so there remains exactly one
canonical serialization of the 12-column contract in the codebase.
`prisma_output.py` itself is unchanged by this increment: `write_prisma_output`
remains available, unmodified, as an independent single-run writer for any
existing caller; this module adds a new, separate entry point for the
cumulative-publication use case P.36.16 approves. No UI or browser code is
touched here.

P.36.21/P.37 strict EUR contract and legacy-file compatibility decision.
`Tariff Price`/`Premium Price` must be confirmed EUR/MWh/h before any row is
merged into the cumulative file, using the same
`price_normalization.normalize_prices_for_output` boundary
`prisma_output.write_prisma_output` uses — resolving the ECB rate per P.37
by `(auction_date, currency)` parsed directly from each row's own CSV data,
no PRISMA lookup; when at least one otherwise-publishable row lacks a
confirmed conversion, `publish_cumulative_output` returns
`PrismaPublicationOutcome.PRICE_NORMALIZATION_FAILED` and leaves the
existing cumulative file byte-for-byte unchanged (the normalization check
runs before the existing file is even read).

A pre-P.36.21 cumulative file may already exist at the legacy filename
(`Prisma_Output_Published.csv`, preserved below only as
`LEGACY_PUBLISHED_OUTPUT_FILENAME`, for documentation) with prices written
before strict EUR normalization existed. Its 12 columns carry neither
Auction ID nor source currency, so a legacy row's price cannot be proven or
safely reinterpreted as EUR from the file alone. Rather than mutate,
reinterpret, or delete that file, `PUBLISHED_OUTPUT_FILENAME` now names a
separate, clearly distinguished cumulative target,
`Prisma_Output_Published_EUR.csv`: every row this module ever merges into it
has already passed strict EUR normalization, so the file's very existence is
itself the EUR guarantee, and any legacy file at the old name is never read,
written, renamed, or deleted by this module.
"""
from __future__ import annotations

import csv
import io
import os
import sqlite3
import tempfile
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from download_directory import DownloadDirectoryError, validate_download_directory
from ecb_rates import EcbRateSource
from price_normalization import (
    PriceNormalizationResult,
    compute_batch_binding,
    describe_price_normalization_failure,
    normalize_prices_for_output,
)
from processor import PrismaImportResult
from prisma_output import OUTPUT_CSV_COLUMNS, transform_row
from storage import AuctionStorage, AuctionStorageError

__all__ = [
    "LEGACY_PUBLISHED_OUTPUT_FILENAME",
    "PUBLISHED_OUTPUT_FILENAME",
    "PrismaPublicationOutcome",
    "PrismaPublicationResult",
    "describe_publication_failure",
    "publish_cumulative_output",
]

_ENCODING = "utf-8"
_DELIMITER = ";"
# Preserved only for documentation (see the module docstring's "legacy-file
# compatibility decision"): this module never reads, writes, renames, or
# deletes a file at this name.
LEGACY_PUBLISHED_OUTPUT_FILENAME = "Prisma_Output_Published.csv"
# No literal cumulative filename is dictated by the approved P.36.16 decision
# text itself (it approves the merge/dedup/atomic-publish *behavior*, not a
# specific name). P.36.21 renamed this constant's value from the original
# P.36.16 choice (`Prisma_Output_Published.csv`, see
# `LEGACY_PUBLISHED_OUTPUT_FILENAME`) to a clearly distinguished name, since
# every row this module writes here is now guaranteed strict-EUR-normalized
# and must never be conflated with a pre-P.36.21 file that cannot make that
# guarantee. Unlike P.36.14/P.36.15's collision-avoiding reservation for
# independent per-run files, this name is intentionally fixed and stable
# across runs, since there is exactly one cumulative file per directory.
PUBLISHED_OUTPUT_FILENAME = "Prisma_Output_Published_EUR.csv"


class PrismaPublicationOutcome(str, Enum):
    """Typed outcome of one P.36.16 cumulative-publication operation."""

    SUCCESS = "success"
    INVALID_PUBLICATION_DIRECTORY = "invalid_publication_directory"
    INVALID_EXISTING_FILE = "invalid_existing_file"
    PRICE_NORMALIZATION_FAILED = "price_normalization_failed"
    WRITE_FAILED = "write_failed"
    STORAGE_FAILED = "storage_failed"


_FAILURE_MESSAGES: dict[PrismaPublicationOutcome, str] = {
    PrismaPublicationOutcome.INVALID_PUBLICATION_DIRECTORY: (
        "The selected publication folder is not valid. Choose an existing, "
        "writable folder."
    ),
    PrismaPublicationOutcome.INVALID_EXISTING_FILE: (
        "The existing published output file is invalid, so nothing was "
        "published. Resolve or move the existing file, then try again."
    ),
    PrismaPublicationOutcome.PRICE_NORMALIZATION_FAILED: (
        "One or more auctions could not be confirmed in EUR/MWh/h, so "
        "nothing was published. Resolve the missing ECB rate evidence for "
        "the required auction date and currency, then retry."
    ),
    PrismaPublicationOutcome.WRITE_FAILED: (
        "The transformed output could not be published to the selected "
        "folder."
    ),
    PrismaPublicationOutcome.STORAGE_FAILED: (
        "The composite-key publication index could not be updated, so "
        "nothing was published."
    ),
}


def describe_publication_failure(outcome: PrismaPublicationOutcome) -> str:
    """Return a stable, English, path-free message for a failed outcome."""
    return _FAILURE_MESSAGES.get(
        outcome, "The PRISMA transformed output could not be published."
    )


@dataclass(frozen=True)
class PrismaPublicationResult:
    """Immutable typed outcome of one cumulative-publication operation."""

    outcome: PrismaPublicationOutcome
    output_path: Path | None = None
    import_result: PrismaImportResult | None = None
    price_normalization: PriceNormalizationResult | None = None
    appended_row_count: int = 0
    total_row_count: int | None = None
    error: str | None = None

    @property
    def succeeded(self) -> bool:
        return self.outcome is PrismaPublicationOutcome.SUCCESS


class _MalformedPublicationFileError(ValueError):
    """The existing cumulative publication file failed its contract check."""


def _validate_publication_directory(directory: str | Path) -> Path:
    """Accept only an existing, readable, writable directory.

    Reuses `download_directory.validate_download_directory`'s existing
    existence/readability boundary check, plus the same writability check
    `prisma_output._validate_output_directory` already applies.
    """
    resolved = validate_download_directory(directory)
    if not os.access(resolved, os.W_OK):
        raise DownloadDirectoryError(f"Directory is not writable: {directory}")
    return resolved


def _read_existing_rows(path: Path) -> list[tuple[str, ...]] | None:
    """Return the existing cumulative file's data rows, or ``None`` if the
    file does not exist yet (the "create it from the current import" case).

    Raises `_MalformedPublicationFileError` for every other rejected case: a
    symbolic link at ``path`` (never followed, read, or replaced), an
    unreadable, empty, undecodable, wrongly delimited, or malformed-quoting
    file, a file missing the exact expected header, or one containing a
    blank data row or the exact header repeated among data rows. Never
    mutates ``path``.
    """
    if path.is_symlink():
        raise _MalformedPublicationFileError(
            "The existing cumulative file path is a symbolic link and was "
            "not read."
        )
    if not path.exists():
        return None
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise _MalformedPublicationFileError(
            f"The existing cumulative file could not be read: {exc}"
        ) from exc
    if not raw:
        raise _MalformedPublicationFileError(
            "The existing cumulative file is empty."
        )
    try:
        text = raw.decode(_ENCODING)
    except UnicodeDecodeError as exc:
        raise _MalformedPublicationFileError(
            "The existing cumulative file is not valid UTF-8."
        ) from exc
    # `newline=""` plus a real file-like object (never `text.splitlines()`,
    # which would incorrectly split a correctly quoted field's own embedded
    # newline into two records) is the same convention `_write_rows` already
    # uses; `strict=True` rejects malformed quoting instead of silently
    # tolerating it.
    try:
        parsed_rows = [
            tuple(row)
            for row in csv.reader(
                io.StringIO(text, newline=""), delimiter=_DELIMITER, strict=True
            )
        ]
    except csv.Error as exc:
        raise _MalformedPublicationFileError(
            f"The existing cumulative file could not be parsed as CSV: {exc}"
        ) from exc
    if not parsed_rows:
        raise _MalformedPublicationFileError(
            "The existing cumulative file has no header row."
        )
    header, *data_rows = parsed_rows
    if header != OUTPUT_CSV_COLUMNS:
        raise _MalformedPublicationFileError(
            "The existing cumulative file does not have the exact expected "
            "12-column header."
        )
    for row in data_rows:
        if not row:
            raise _MalformedPublicationFileError(
                "The existing cumulative file contains a blank data row."
            )
        if len(row) != len(OUTPUT_CSV_COLUMNS):
            raise _MalformedPublicationFileError(
                "The existing cumulative file contains a malformed row."
            )
        if row == OUTPUT_CSV_COLUMNS:
            raise _MalformedPublicationFileError(
                "The existing cumulative file repeats the header row among "
                "its data rows."
            )
    return data_rows


def _write_rows(target: Path, rows: list[tuple[str, ...]]) -> None:
    """Stage the complete merged CSV in the same directory, flush and fsync
    it, then atomically replace ``target`` via `os.replace()`.

    A failure at any point before the final `os.replace()` leaves only the
    staged temporary file, which is removed in ``finally``; ``target`` (the
    previous valid cumulative file, if any) is never partially overwritten,
    since `os.replace()` itself is atomic and only ever called with a
    complete, fully flushed and fsynced staged file. This is the same
    stage-then-`os.replace` pattern `prisma_output.py`'s own `_write_rows`
    already uses.
    """
    directory = target.parent
    descriptor, staged_name = tempfile.mkstemp(
        prefix=f".{target.stem}-", suffix=".staging", dir=directory
    )
    staged: Path | None = Path(staged_name)
    try:
        with os.fdopen(descriptor, "w", encoding=_ENCODING, newline="") as staged_file:
            writer = csv.writer(staged_file, delimiter=_DELIMITER)
            writer.writerow(OUTPUT_CSV_COLUMNS)
            writer.writerows(rows)
            staged_file.flush()
            os.fsync(staged_file.fileno())
        os.replace(staged, target)
        staged = None
    finally:
        if staged is not None:
            staged.unlink(missing_ok=True)


def _validate_precomputed_normalization(
    import_result: PrismaImportResult, normalization: PriceNormalizationResult
) -> None:
    """Reject a caller-supplied `PriceNormalizationResult` that does not
    provably belong to ``import_result``'s exact ordered row batch.

    A mismatched row count/index set alone is too weak a check: a result
    successfully computed for a *different* batch of the exact same length
    (or the same rows in a different order) would pass an index-set-only
    check while its prices belong to the wrong rows. `price_normalization.
    compute_batch_binding()` is re-derived here from ``import_result.rows``
    and compared against ``normalization.batch_binding`` — the immutable
    fingerprint (Auction ID, state, exit/entry market, source Tariff Price,
    source Premium Price, all in row order) `normalize_prices_for_output()`
    already attaches to every successful result — so only a result computed
    for this exact ordered batch is accepted. Only the successful case is
    checked here — a `BLOCKED` precomputed result is used as-is by the caller
    regardless of row count or binding, since it never carries any price data
    to potentially misattribute.
    """
    if not normalization.succeeded:
        return
    expected_indices = set(range(len(import_result.rows)))
    if set(normalization.prices_by_row_index) != expected_indices:
        raise ValueError(
            "The supplied precomputed price normalization result does not "
            "match this import result's row batch."
        )
    if normalization.batch_binding != compute_batch_binding(import_result.rows):
        raise ValueError(
            "The supplied precomputed price normalization result does not "
            "match this import result's row batch."
        )


def publish_cumulative_output(
    import_result: PrismaImportResult,
    publication_directory: str | Path,
    *,
    storage: AuctionStorage,
    ecb_source: EcbRateSource | None = None,
    precomputed_normalization: PriceNormalizationResult | None = None,
) -> PrismaPublicationResult:
    """Merge ``import_result``'s accepted rows into the one cumulative,
    deduplicated 12-column output CSV in ``publication_directory``.

    ``import_result`` is an already-completed `processor.PrismaImportResult`
    (parsing, filtering, and enrichment already happened there and are not
    repeated here); this function only formats accepted rows via
    `prisma_output.transform_row` and merges them into the cumulative file
    under the P.40 composite-key ("Auction ID + Network Point Name +
    Capacity Type") deduplication rule. See the module docstring for the
    complete approved contract, including the immutable-row policy, the
    legacy-file transitional limit, the P.36.21/P.37 strict EUR gate, and the
    separate pre-P.36.21 legacy-filename compatibility decision.

    ``storage``/``ecb_source`` are forwarded unchanged to
    `price_normalization.normalize_prices_for_output`, which reuses P.37's
    durable `(auction_date, currency)` cache — so republishing an
    already-normalized import never repeats an ECB lookup.

    ``precomputed_normalization``, when supplied, must be the exact
    `PriceNormalizationResult` already computed for ``import_result.rows`` in
    this same processing operation (see `prisma_import_workflow.
    run_prisma_import_workflow`, which resolves and normalizes prices once,
    strictly before any source-operation-state transition, then reuses that
    exact result here instead of normalizing the same batch a second time).
    It is validated to cover exactly ``import_result.rows``'s indices *and*
    to carry a matching `price_normalization.compute_batch_binding()`
    fingerprint before use (`_validate_precomputed_normalization`); a
    mismatch — including a same-length result computed for a different or
    reordered batch — raises `ValueError` rather than silently normalizing
    (or skipping, or misattributing) the wrong batch. A standalone caller
    that omits it (the default) still receives the identical fail-closed
    normalization this function has always performed internally.
    """
    try:
        directory = _validate_publication_directory(publication_directory)
    except DownloadDirectoryError as exc:
        return PrismaPublicationResult(
            PrismaPublicationOutcome.INVALID_PUBLICATION_DIRECTORY,
            import_result=import_result,
            error=str(exc),
        )

    if precomputed_normalization is not None:
        _validate_precomputed_normalization(import_result, precomputed_normalization)
        normalization = precomputed_normalization
    else:
        normalization = normalize_prices_for_output(
            import_result.rows,
            storage=storage,
            ecb_source=ecb_source,
        )
    if not normalization.succeeded:
        return PrismaPublicationResult(
            PrismaPublicationOutcome.PRICE_NORMALIZATION_FAILED,
            import_result=import_result,
            price_normalization=normalization,
            error=describe_price_normalization_failure(normalization),
        )

    target = directory / PUBLISHED_OUTPUT_FILENAME

    try:
        existing_rows = _read_existing_rows(target)
    except _MalformedPublicationFileError as exc:
        return PrismaPublicationResult(
            PrismaPublicationOutcome.INVALID_EXISTING_FILE,
            import_result=import_result,
            price_normalization=normalization,
            error=str(exc),
        )

    file_previously_existed = existing_rows is not None
    existing_rows = existing_rows or []

    try:
        known_keys = storage.published_output_row_keys()
    except (AuctionStorageError, sqlite3.Error) as exc:
        return PrismaPublicationResult(
            PrismaPublicationOutcome.STORAGE_FAILED,
            import_result=import_result,
            price_normalization=normalization,
            error=str(exc),
        )

    # If the cumulative file itself does not currently exist, any composite
    # keys already recorded no longer correspond to real content in a file
    # that is gone, so they must not block this rebuild: a missing output
    # file self-heals from the next import, exactly like the pre-P.40
    # contract, instead of silently staying empty forever because its rows'
    # keys are still "known". `known_keys` is still consulted afterward so
    # a stale key is recorded again only if genuinely absent from storage.
    blocking_keys = known_keys if file_previously_existed else set()

    new_rows: list[tuple[str, ...]] = []
    new_keys: list[tuple[str, str, str]] = []
    seen_keys_in_import: set[tuple[str, str, str]] = set()
    for index, row in enumerate(import_result.rows):
        # P.40 composite key: Auction ID + Network Point Name + Capacity
        # Type is the sole persistent row identity — never full-row content.
        # PRISMA data is immutable by customer decision, so a key already
        # recorded — durably (`blocking_keys`) or earlier in this same
        # partial-overlap batch (`seen_keys_in_import`) — always wins: the
        # stored row is kept unchanged and this incoming row is skipped
        # outright, regardless of whether its other field values differ. A
        # row whose key is genuinely new is always appended, even if its
        # formatted content happens to coincide with another row's, since
        # "different rows ... must remain independently acceptable" and the
        # key is the only identity that matters.
        key = (row["auction_id"], row["network_point"], row["direction"])
        if key in blocking_keys or key in seen_keys_in_import:
            continue
        seen_keys_in_import.add(key)

        formatted = transform_row(row, normalization.prices_by_row_index[index])
        as_tuple = tuple(formatted[column] for column in OUTPUT_CSV_COLUMNS)
        if key not in known_keys:
            new_keys.append(key)
        new_rows.append(as_tuple)

    if file_previously_existed and not new_rows:
        return PrismaPublicationResult(
            PrismaPublicationOutcome.SUCCESS,
            output_path=target,
            import_result=import_result,
            price_normalization=normalization,
            appended_row_count=0,
            total_row_count=len(existing_rows),
        )

    all_rows = existing_rows + new_rows
    try:
        _write_rows(target, all_rows)
    except OSError as exc:
        return PrismaPublicationResult(
            PrismaPublicationOutcome.WRITE_FAILED,
            import_result=import_result,
            price_normalization=normalization,
            error=str(exc),
        )

    if new_keys:
        # Recorded only after the CSV write above has already succeeded: if
        # persisting the keys themselves then fails, the CSV already
        # reflects the new content, so a later republish would only ever
        # re-derive/re-record the same keys, never lose or duplicate a row.
        try:
            storage.record_published_output_row_keys(new_keys)
        except (AuctionStorageError, sqlite3.Error) as exc:
            return PrismaPublicationResult(
                PrismaPublicationOutcome.STORAGE_FAILED,
                output_path=target,
                import_result=import_result,
                price_normalization=normalization,
                appended_row_count=len(new_rows),
                total_row_count=len(all_rows),
                error=str(exc),
            )

    return PrismaPublicationResult(
        PrismaPublicationOutcome.SUCCESS,
        output_path=target,
        import_result=import_result,
        price_normalization=normalization,
        appended_row_count=len(new_rows),
        total_row_count=len(all_rows),
    )
