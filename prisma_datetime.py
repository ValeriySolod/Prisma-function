"""Qt- and infrastructure-independent P.36 output date/time contract boundary.

Per `Prisma Function.odt`/`ROADMAP.md`'s authoritative 12-column output
contract and `README.md`'s recorded field formats, the processed output must
serialize `Auction Date` as `YYYY-MM-DD` and `Flow Start`/`Flow End` as
`YYYY-MM-DD HH:mm` — never the ISO 8601 `T`-separated, seconds-carrying
`datetime.isoformat()` shape this codebase previously wrote. All three values
originate from the authoritative PRISMA local input format `DD.MM.YYYY
HH:MM`, which must be interpreted as an explicit Europe/Berlin local time (CET
during standard time, CEST during daylight saving), never a fixed UTC+1/UTC+2
offset and never left naive. This module is the sole place that
interpretation happens; every caller downstream (CSV writer, publication,
storage, UI) only ever sees the already-formatted, timezone-suffix-free
strings this module produces.

DST-boundary policy (no authoritative rule currently resolves either case, so
both are rejected rather than guessed):

- A local time that does not exist (the spring-forward gap, e.g. 02:30 on the
  transition date) is rejected with `PrismaLocalTimestampNonexistentError`.
- A local time that occurs twice (the autumn-back overlap, e.g. 02:30 on that
  transition date) is rejected with `PrismaLocalTimestampAmbiguousError`.

Both are distinguished deterministically via a UTC round-trip check (PEP 495):
for a naive local time whose two possible UTC offsets differ, only a genuinely
ambiguous (overlap) time round-trips back to the same wall-clock value from
either candidate offset; a nonexistent (gap) time does not round-trip from
either.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

__all__ = [
    "PRISMA_LOCAL_TIMEZONE",
    "PRISMA_LOCAL_INPUT_FORMAT",
    "AUCTION_DATE_OUTPUT_FORMAT",
    "FLOW_TIMESTAMP_OUTPUT_FORMAT",
    "PrismaLocalTimestampError",
    "PrismaLocalTimestampFormatError",
    "PrismaLocalTimestampNonexistentError",
    "PrismaLocalTimestampAmbiguousError",
    "parse_prisma_local_timestamp",
    "elapsed_hours",
    "local_wall_clock_hours",
    "format_auction_date",
    "format_flow_timestamp",
]

# Europe/Berlin is this project's already-established, live-verified
# authoritative timezone for PRISMA local date/time interpretation (see
# `prisma_download.py`'s date-filter fill and `prisma_auction_lookup.py`'s
# auction-end resolution, both already live-verified across the CET/CEST DST
# boundary). Resolved via the standard-library `zoneinfo`, backed by the
# `tzdata` package already present in this project's environment; no new
# dependency is introduced.
PRISMA_LOCAL_TIMEZONE = ZoneInfo("Europe/Berlin")

PRISMA_LOCAL_INPUT_FORMAT = "%d.%m.%Y %H:%M"
AUCTION_DATE_OUTPUT_FORMAT = "%Y-%m-%d"
FLOW_TIMESTAMP_OUTPUT_FORMAT = "%Y-%m-%d %H:%M"

_INPUT_PATTERN = re.compile(r"\d{2}\.\d{2}\.\d{4} \d{2}:\d{2}\Z")


class PrismaLocalTimestampError(ValueError):
    """Base error for a PRISMA local timestamp that cannot be safely
    interpreted. Carries a stable, path-free, generic English message
    (``str(self)``); the offending raw text is preserved separately on
    ``raw_value`` for internal audit context only, never included in the
    public message."""

    def __init__(self, message: str, *, raw_value: str) -> None:
        super().__init__(message)
        self.raw_value = raw_value


class PrismaLocalTimestampFormatError(PrismaLocalTimestampError):
    """The raw text is not a valid `DD.MM.YYYY HH:MM` PRISMA local timestamp."""


class PrismaLocalTimestampNonexistentError(PrismaLocalTimestampError):
    """The local wall-clock time does not exist (spring-forward DST gap)."""


class PrismaLocalTimestampAmbiguousError(PrismaLocalTimestampError):
    """The local wall-clock time is ambiguous (autumn-back DST overlap) and
    no authoritative rule resolves which of the two real instants applies."""


def parse_prisma_local_timestamp(raw_value: str) -> datetime:
    """Parse an authoritative PRISMA local `DD.MM.YYYY HH:MM` timestamp into
    an explicit, timezone-aware Europe/Berlin `datetime`.

    Rejects, and never guesses a value for:
    - text not in the exact `DD.MM.YYYY HH:MM` shape;
    - text in that shape but not a valid calendar date/time;
    - a nonexistent local time (spring DST transition);
    - an ambiguous local time (autumn DST transition).
    """
    text = "" if raw_value is None else str(raw_value).strip()
    if not _INPUT_PATTERN.fullmatch(text):
        raise PrismaLocalTimestampFormatError(
            "is not in DD.MM.YYYY HH:MM format.", raw_value=text
        )
    try:
        naive = datetime.strptime(text, PRISMA_LOCAL_INPUT_FORMAT)
    except ValueError as exc:
        raise PrismaLocalTimestampFormatError(
            "is not a valid date.", raw_value=text
        ) from exc

    early = naive.replace(tzinfo=PRISMA_LOCAL_TIMEZONE, fold=0)
    late = naive.replace(tzinfo=PRISMA_LOCAL_TIMEZONE, fold=1)
    if early.utcoffset() == late.utcoffset():
        # Fold does not matter away from a DST transition: unambiguous.
        return early

    # The two candidate offsets disagree, so this local time falls exactly on
    # a DST transition. Distinguish gap (nonexistent) from overlap
    # (ambiguous) via a UTC round-trip: only a real, ambiguous instant
    # reproduces the original wall-clock time when converted back.
    round_trip = early.astimezone(timezone.utc).astimezone(PRISMA_LOCAL_TIMEZONE)
    if round_trip.replace(tzinfo=None) != naive:
        raise PrismaLocalTimestampNonexistentError(
            "does not exist in the Europe/Berlin local calendar (spring "
            "daylight-saving transition).",
            raw_value=text,
        )
    raise PrismaLocalTimestampAmbiguousError(
        "is ambiguous in the Europe/Berlin local calendar (autumn "
        "daylight-saving transition) and no authoritative rule resolves "
        "which offset applies.",
        raw_value=text,
    )


def elapsed_hours(start: datetime, end: datetime) -> float:
    """Real elapsed hours between two already-resolved, timezone-aware
    datetimes, correct across a CET/CEST transition.

    Plain subtraction of two aware `datetime` objects that share the same
    `tzinfo` object (as `start`/`end` normally do here, both carrying
    `PRISMA_LOCAL_TIMEZONE`) is documented Python behavior to ignore
    `tzinfo` entirely and subtract the naive wall-clock fields directly
    (see the `datetime` docs' subtraction rules) — silently wrong whenever
    `start` and `end` fall on opposite sides of a DST transition (a
    same-day 01:00-04:00 spring-forward span is 3 naive wall-clock hours
    but only 2 real elapsed hours). Converting both to the fixed-offset UTC
    zone first forces a correct, offset-aware subtraction.
    """
    return (
        end.astimezone(timezone.utc) - start.astimezone(timezone.utc)
    ).total_seconds() / 3600


def local_wall_clock_hours(start: datetime, end: datetime) -> float:
    """Local Europe/Berlin wall-clock duration in hours between two
    already-resolved datetimes, deliberately ignoring any DST offset
    difference between them (i.e. the naive `HH:MM` field difference, as a
    calendar/clock reader would count it).

    This is the basis for the pre-existing Product Type classification
    thresholds (`WD`/`Day Ahead` up to 24h, `Month` up to 31*24h, `Quarter`
    up to 93*24h, `Year` above that) — which are, and always have been,
    defined in local wall-clock hours, not real elapsed time. Contrast with
    `elapsed_hours()` (used for `Flow Duration Hours`), which computes real
    UTC elapsed time and DOES differ from this whenever `start` and `end`
    fall on opposite sides of a DST transition — an interval that stays a
    calendar-day-boundary case (e.g. exactly 93 local calendar days) under
    this function must not silently shift by an hour into a different
    Product Type bucket merely because it happens to cross a transition.
    """
    return (
        end.replace(tzinfo=None) - start.replace(tzinfo=None)
    ).total_seconds() / 3600


def format_auction_date(value: datetime) -> str:
    """Serialize an already-resolved Europe/Berlin `datetime` as the
    authoritative `Auction Date` contract: `YYYY-MM-DD`, no offset."""
    return value.strftime(AUCTION_DATE_OUTPUT_FORMAT)


def format_flow_timestamp(value: datetime) -> str:
    """Serialize an already-resolved Europe/Berlin `datetime` as the
    authoritative `Flow Start`/`Flow End` contract: `YYYY-MM-DD HH:mm`, no
    seconds, no `T` separator, no offset."""
    return value.strftime(FLOW_TIMESTAMP_OUTPUT_FORMAT)
