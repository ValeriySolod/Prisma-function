"""Qt-independent boundary for selecting one manually downloaded official PRISMA
Export CSV from disk.

Per `Prisma Function.odt`, PrismaFunction never downloads, stages, monitors, or
scans files itself: the user manually downloads the official CSV export from
PRISMA and later hands the single downloaded file to the program separately
(P.36.4). This module only validates that one user-selected candidate file
satisfies the exact official PRISMA Export CSV contract and tracks which
single validated selection the current session currently accepts. It performs
no row processing, filtering, mapping, accumulation, or output writing; those
remain scoped to later P.36 increments.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from csv_contracts import PRISMA_EXPORT_COLUMNS

__all__ = [
    "ManualCsvOutcome",
    "ManualCsvValidationResult",
    "ManualCsvSelection",
    "validate_manual_csv",
    "describe_rejection",
]

_ENCODING = "cp1252"
_DELIMITER = ";"
_BOM_PREFIX_LENGTH = 4
_CHUNK_SIZE = 65536

# Standard BOM signatures. Every one of them is rejected identically as
# BOM_DETECTED: the accepted contract requires no BOM at all, so the specific
# encoding a BOM implies is never distinguished or acted on.
_BOM_SIGNATURES = (
    b"\x00\x00\xfe\xff",  # UTF-32 BE
    b"\xff\xfe\x00\x00",  # UTF-32 LE
    b"\xef\xbb\xbf",  # UTF-8
    b"\xfe\xff",  # UTF-16 BE
    b"\xff\xfe",  # UTF-16 LE
)


class ManualCsvOutcome(str, Enum):
    """Typed outcome of validating one candidate manual PRISMA Export CSV."""

    ACCEPTED = "accepted"
    NOT_FOUND = "not_found"
    NOT_A_FILE = "not_a_file"
    UNREADABLE = "unreadable"
    EMPTY_FILE = "empty_file"
    BOM_DETECTED = "bom_detected"
    ENCODING = "encoding"
    DELIMITER = "delimiter"
    HEADER_MISMATCH = "header_mismatch"


_REJECTION_MESSAGES: dict[ManualCsvOutcome, str] = {
    ManualCsvOutcome.NOT_FOUND: "The selected file does not exist.",
    ManualCsvOutcome.NOT_A_FILE: "The selected item is not a file.",
    ManualCsvOutcome.UNREADABLE: "The selected file could not be read.",
    ManualCsvOutcome.EMPTY_FILE: "The selected file is empty.",
    ManualCsvOutcome.BOM_DETECTED: (
        "The selected file has an unexpected byte-order mark and cannot be "
        "accepted as an official PRISMA Export CSV."
    ),
    ManualCsvOutcome.ENCODING: (
        "The selected file is not encoded as an official PRISMA Export CSV."
    ),
    ManualCsvOutcome.DELIMITER: (
        "The selected file does not use the official PRISMA Export CSV delimiter."
    ),
    ManualCsvOutcome.HEADER_MISMATCH: (
        "The selected file's header does not match the official PRISMA Export "
        "CSV contract."
    ),
}


def describe_rejection(outcome: ManualCsvOutcome) -> str:
    """Return a stable, English, path-free message for a rejected outcome."""
    return _REJECTION_MESSAGES.get(outcome, "The selected file could not be used.")


@dataclass(frozen=True)
class ManualCsvValidationResult:
    """Immutable typed outcome of validating one candidate file."""

    outcome: ManualCsvOutcome
    path: Path | None = None

    @property
    def accepted(self) -> bool:
        return self.outcome is ManualCsvOutcome.ACCEPTED


def _has_bom(prefix: bytes) -> bool:
    return any(prefix.startswith(signature) for signature in _BOM_SIGNATURES)


def _validate_remaining_encoding(csv_file) -> ManualCsvOutcome | None:
    """Validate strict cp1252 decoding for the rest of the open file.

    Reads in bounded chunks so the complete file is never held in memory at
    once. This is an encoding check only: each chunk is decoded to prove it
    is valid cp1252 and then discarded; no chunk, row, or decoded text is
    parsed, retained, returned, or logged.
    """
    while True:
        chunk = csv_file.read(_CHUNK_SIZE)
        if not chunk:
            return None
        try:
            chunk.decode(_ENCODING)
        except UnicodeDecodeError:
            return ManualCsvOutcome.ENCODING


def _validate_open_file(path: Path) -> ManualCsvValidationResult:
    with path.open("rb") as csv_file:
        prefix = csv_file.read(_BOM_PREFIX_LENGTH)
        if not prefix:
            return ManualCsvValidationResult(ManualCsvOutcome.EMPTY_FILE)
        if _has_bom(prefix):
            return ManualCsvValidationResult(ManualCsvOutcome.BOM_DETECTED)
        csv_file.seek(0)

        line = csv_file.readline()
        try:
            header_text = line.decode(_ENCODING)
        except UnicodeDecodeError:
            return ManualCsvValidationResult(ManualCsvOutcome.ENCODING)

        if _DELIMITER not in header_text:
            return ManualCsvValidationResult(ManualCsvOutcome.DELIMITER)

        try:
            fields = next(csv.reader([header_text], delimiter=_DELIMITER, strict=True))
        except (csv.Error, StopIteration):
            return ManualCsvValidationResult(ManualCsvOutcome.HEADER_MISMATCH)

        if tuple(fields) != PRISMA_EXPORT_COLUMNS:
            return ManualCsvValidationResult(ManualCsvOutcome.HEADER_MISMATCH)

        encoding_failure = _validate_remaining_encoding(csv_file)
        if encoding_failure is not None:
            return ManualCsvValidationResult(encoding_failure)

    return ManualCsvValidationResult(ManualCsvOutcome.ACCEPTED, path=path.resolve())


def validate_manual_csv(candidate: str | Path) -> ManualCsvValidationResult:
    """Validate ``candidate`` against the exact official PRISMA Export CSV contract.

    The header line is matched exactly against ``PRISMA_EXPORT_COLUMNS``, and
    the complete file (not only the header) is validated as strict cp1252 in
    bounded chunks. No delimiter guessing, encoding fallback, header
    normalization, or partial header matching is performed; no row is
    parsed, retained, or logged; every rejection reason is distinguishable
    via ``ManualCsvOutcome``.
    """
    path = Path(candidate)
    if not path.exists():
        return ManualCsvValidationResult(ManualCsvOutcome.NOT_FOUND)
    if not path.is_file():
        return ManualCsvValidationResult(ManualCsvOutcome.NOT_A_FILE)

    try:
        return _validate_open_file(path)
    except OSError:
        return ManualCsvValidationResult(ManualCsvOutcome.UNREADABLE)


class ManualCsvSelection:
    """Tracks the single most recently accepted manual PRISMA Export CSV file.

    Session-scoped only, matching `DownloadDirectorySelection`'s P.36.3
    persistence decision: there is no active selection until the user
    validates one, and a rejected candidate never changes ``current``.
    """

    def __init__(self) -> None:
        self._current: Path | None = None

    @property
    def current(self) -> Path | None:
        return self._current

    def select(self, candidate: str | Path) -> ManualCsvValidationResult:
        """Validate ``candidate``; on success, activate it as ``current``."""
        result = validate_manual_csv(candidate)
        if result.accepted:
            self._current = result.path
        return result
