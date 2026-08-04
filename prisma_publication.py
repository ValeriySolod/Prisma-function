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
- Deduplication compares the complete, exact 12-field canonical output row
  (see `prisma_output.transform_row`) for equality only. There is no
  narrower business key (e.g. Auction ID, which is not one of the 12 output
  fields), no fuzzy/substring matching, and no update-in-place semantics.
- Exact duplicates are removed both between the existing published rows and
  the current completed import, and within the current completed import
  itself.
- Ordering is deterministic: existing unique rows keep their original order;
  new unique rows are appended in their current import order.
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
"""
from __future__ import annotations

import csv
import io
import os
import tempfile
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from download_directory import DownloadDirectoryError, validate_download_directory
from processor import PrismaImportResult
from prisma_output import OUTPUT_CSV_COLUMNS, transform_row

__all__ = [
    "PUBLISHED_OUTPUT_FILENAME",
    "PrismaPublicationOutcome",
    "PrismaPublicationResult",
    "describe_publication_failure",
    "publish_cumulative_output",
]

_ENCODING = "utf-8"
_DELIMITER = ";"
# No literal cumulative filename is dictated by the approved P.36.16 decision
# text itself (it approves the merge/dedup/atomic-publish *behavior*, not a
# specific name); this fixed name is the safest available assumption,
# documented explicitly here per the same pattern
# `prisma_output.build_output_filename` used for its own undecided naming
# detail. Unlike P.36.14/P.36.15's collision-avoiding reservation for
# independent per-run files, this name is intentionally fixed and stable
# across runs, since there is exactly one cumulative file per directory.
PUBLISHED_OUTPUT_FILENAME = "Prisma_Output_Published.csv"


class PrismaPublicationOutcome(str, Enum):
    """Typed outcome of one P.36.16 cumulative-publication operation."""

    SUCCESS = "success"
    INVALID_PUBLICATION_DIRECTORY = "invalid_publication_directory"
    INVALID_EXISTING_FILE = "invalid_existing_file"
    WRITE_FAILED = "write_failed"


_FAILURE_MESSAGES: dict[PrismaPublicationOutcome, str] = {
    PrismaPublicationOutcome.INVALID_PUBLICATION_DIRECTORY: (
        "The selected publication folder is not valid. Choose an existing, "
        "writable folder."
    ),
    PrismaPublicationOutcome.INVALID_EXISTING_FILE: (
        "The existing published output file is invalid, so nothing was "
        "published. Resolve or move the existing file, then try again."
    ),
    PrismaPublicationOutcome.WRITE_FAILED: (
        "The transformed output could not be published to the selected "
        "folder."
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


def publish_cumulative_output(
    import_result: PrismaImportResult,
    publication_directory: str | Path,
) -> PrismaPublicationResult:
    """Merge ``import_result``'s accepted rows into the one cumulative,
    deduplicated 12-column output CSV in ``publication_directory``.

    ``import_result`` is an already-completed `processor.PrismaImportResult`
    (parsing, filtering, and enrichment already happened there and are not
    repeated here); this function only formats accepted rows via
    `prisma_output.transform_row` and merges them into the cumulative file
    under the approved exact-full-row deduplication rule. See the module
    docstring for the complete approved contract.
    """
    try:
        directory = _validate_publication_directory(publication_directory)
    except DownloadDirectoryError as exc:
        return PrismaPublicationResult(
            PrismaPublicationOutcome.INVALID_PUBLICATION_DIRECTORY,
            import_result=import_result,
            error=str(exc),
        )

    target = directory / PUBLISHED_OUTPUT_FILENAME

    try:
        existing_rows = _read_existing_rows(target)
    except _MalformedPublicationFileError as exc:
        return PrismaPublicationResult(
            PrismaPublicationOutcome.INVALID_EXISTING_FILE,
            import_result=import_result,
            error=str(exc),
        )

    file_previously_existed = existing_rows is not None
    existing_rows = existing_rows or []
    existing_set = set(existing_rows)

    new_rows: list[tuple[str, ...]] = []
    seen_in_import: set[tuple[str, ...]] = set()
    for row in import_result.rows:
        formatted = transform_row(row)
        as_tuple = tuple(formatted[column] for column in OUTPUT_CSV_COLUMNS)
        if as_tuple in existing_set or as_tuple in seen_in_import:
            continue
        seen_in_import.add(as_tuple)
        new_rows.append(as_tuple)

    if file_previously_existed and not new_rows:
        return PrismaPublicationResult(
            PrismaPublicationOutcome.SUCCESS,
            output_path=target,
            import_result=import_result,
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
            error=str(exc),
        )

    return PrismaPublicationResult(
        PrismaPublicationOutcome.SUCCESS,
        output_path=target,
        import_result=import_result,
        appended_row_count=len(new_rows),
        total_row_count=len(all_rows),
    )
