"""Qt-independent boundary for validating and accepting a user-selected date range.

Per `Prisma Function.odt`'s P.36 workflow, the user selects a start date and an
end date inside PrismaFunction before any PRISMA download, transformation, or
publication occurs (P.36.14 and later). This module only defines and validates
that immutable date range; it performs no browser, Playwright, PRISMA-page,
filesystem, CSV, transformation, mapping, persistence, output-writing, or
publication operation, and it never reads the system clock — the caller
supplies both candidate dates explicitly.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum

__all__ = [
    "DateRange",
    "DateRangeOutcome",
    "DateRangeValidationResult",
    "DateRangeSelection",
    "validate_date_range",
    "describe_rejection",
]


class DateRangeOutcome(str, Enum):
    """Typed outcome of validating one candidate start/end date pair."""

    ACCEPTED = "accepted"
    MISSING_START_DATE = "missing_start_date"
    MISSING_END_DATE = "missing_end_date"
    END_BEFORE_START = "end_before_start"


_REJECTION_MESSAGES: dict[DateRangeOutcome, str] = {
    DateRangeOutcome.MISSING_START_DATE: "A start date is required.",
    DateRangeOutcome.MISSING_END_DATE: "An end date is required.",
    DateRangeOutcome.END_BEFORE_START: (
        "The end date must not be earlier than the start date."
    ),
}


def describe_rejection(outcome: DateRangeOutcome) -> str:
    """Return a stable, English message for a rejected outcome."""
    return _REJECTION_MESSAGES.get(outcome, "The selected date range could not be used.")


@dataclass(frozen=True)
class DateRange:
    """An immutable, validated start/end date pair (inclusive, start <= end)."""

    start: date
    end: date


@dataclass(frozen=True)
class DateRangeValidationResult:
    """Immutable typed outcome of validating one candidate date range."""

    outcome: DateRangeOutcome
    date_range: DateRange | None = None

    @property
    def accepted(self) -> bool:
        return self.outcome is DateRangeOutcome.ACCEPTED


def validate_date_range(start: date | None, end: date | None) -> DateRangeValidationResult:
    """Validate a candidate start/end date pair.

    Checks run in a fixed order — missing start, then missing end, then end
    not earlier than start — so a candidate missing both dates always reports
    ``MISSING_START_DATE`` deterministically. Neither ``date.today()`` nor any
    other system-clock read occurs here; both dates are caller-supplied.
    """
    if start is None:
        return DateRangeValidationResult(DateRangeOutcome.MISSING_START_DATE)
    if end is None:
        return DateRangeValidationResult(DateRangeOutcome.MISSING_END_DATE)
    if end < start:
        return DateRangeValidationResult(DateRangeOutcome.END_BEFORE_START)
    return DateRangeValidationResult(DateRangeOutcome.ACCEPTED, DateRange(start, end))


class DateRangeSelection:
    """Tracks the single most recently accepted date range for the session.

    Session-scoped, matching `DownloadDirectorySelection`/`ManualCsvSelection`:
    there is no default accepted range until the user validates one (no
    current-date default is invented here), and a rejected candidate never
    changes ``current``.
    """

    def __init__(self) -> None:
        self._current: DateRange | None = None

    @property
    def current(self) -> DateRange | None:
        return self._current

    def select(self, start: date | None, end: date | None) -> DateRangeValidationResult:
        """Validate ``start``/``end``; on success, activate it as ``current``."""
        result = validate_date_range(start, end)
        if result.accepted:
            self._current = result.date_range
        return result
