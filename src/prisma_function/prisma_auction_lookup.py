"""Focused, UI-independent official PRISMA auction-end resolution (P.36.19).

`State = Finished` (already retained per source row by `processor.py`) proves
an auction ended, but the PRISMA Export CSV never carries the exact end
timestamp: it has no `End of Auction` column and `Start of Auction`,
`Product Runtime Start`/`End`, the selected report end date, the CSV download
date, the processing date, and the current date must never be substituted
for it (see `ROADMAP.md`'s P.36.19 entry and the approved customer
decisions it records). The authoritative end timestamp must come from
official PRISMA auction data, looked up by the exact `Auction ID`.

This module is split, per the approved scope, into a transport-independent
business layer (`parse_auction_end_record`, fully testable with fakes) and a
thin transport seam (`AuctionDetailFetcher`) that keeps
transport/selector/navigation mechanics out of the business rules.

Per the revised specification, PrismaFunction no longer opens, controls, or
downloads anything from the PRISMA website: there is no managed browser
session, so no `AuctionDetailFetcher` implementation is ever supplied in
practice. `PrismaAuctionLookup` therefore fails closed (a typed
`PrismaAuctionDetailTransportError`, the same "Unavailable" outcome this
module always produced when no live PRISMA surface was reachable) whenever
no explicit `fetcher` is given. A previously resolved auction's rate remains
available indefinitely from `storage.AuctionStorage`'s durable per-Auction-ID
cache (see `rate_resolution.py`), so this only affects an auction that has
never been resolved before.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Mapping, Protocol
from zoneinfo import ZoneInfo

__all__ = [
    "FIELD_AUCTION_ID",
    "FIELD_STATE",
    "FIELD_AUCTION_END",
    "FINISHED_STATE",
    "DEFAULT_TIMEOUT_MS",
    "PrismaAuctionLookupError",
    "PrismaAuctionRecordMismatchError",
    "PrismaAuctionNotFinishedError",
    "PrismaAuctionEndFieldMissingError",
    "PrismaAuctionEndFieldMalformedError",
    "PrismaAuctionDetailTransportError",
    "AuctionEndRecord",
    "AuctionDetailFetcher",
    "PrismaAuctionLookup",
    "parse_auction_end_record",
    "authoritative_end_date",
]

FIELD_AUCTION_ID = "Auction ID"
FIELD_STATE = "State"
# This module's own transport-agnostic `raw_fields` key, not a live PRISMA
# field name: an `AuctionDetailFetcher` implementation normalizes its own raw
# response shape into this key before handing it to `parse_auction_end_record`.
FIELD_AUCTION_END = "End of Auction"
FINISHED_STATE = "Finished"
DEFAULT_TIMEOUT_MS = 10_000

# Europe/Berlin is this project's already-established, live-verified
# authoritative timezone for PRISMA date interpretation. The authoritative
# calendar date used for ECB rate selection is always this timezone's local
# date, never a UTC-shifted one.
_SOURCE_ZONE = ZoneInfo("Europe/Berlin")
_LOCAL_TIMESTAMP_PATTERN = re.compile(r"\d{2}\.\d{2}\.\d{4} \d{2}:\d{2}\Z")


class PrismaAuctionLookupError(RuntimeError):
    """Base failure raised by official PRISMA auction-end resolution."""


class PrismaAuctionRecordMismatchError(PrismaAuctionLookupError):
    """The returned detail record's own Auction ID does not match the request."""


class PrismaAuctionNotFinishedError(PrismaAuctionLookupError):
    """The official detail's own state contradicts the required Finished state."""


class PrismaAuctionEndFieldMissingError(PrismaAuctionLookupError):
    """The official detail has no explicit auction-end field."""


class PrismaAuctionEndFieldMalformedError(PrismaAuctionLookupError):
    """The official auction-end field could not be parsed as an explicit,
    timezone-carrying timestamp."""


class PrismaAuctionDetailTransportError(PrismaAuctionLookupError):
    """The live PRISMA auction-detail transport (navigation/connection/read)
    failed. Never exposes sensitive session data; preserves actionable
    context only (Auction ID, timeout, and the underlying failure class)."""


@dataclass(frozen=True)
class AuctionEndRecord:
    """A focused, UI- and transport-independent official auction-end result."""

    auction_id: str
    end_at: datetime
    state: str | None


class AuctionDetailFetcher(Protocol):
    def fetch(
        self, page: object, auction_id: str, *, timeout_ms: int
    ) -> Mapping[str, str]:
        """Return the raw official detail fields for an exact Auction ID.

        Implementations own all page/selector/navigation transport concerns
        and must use explicit navigation, connection, and read timeouts.
        Raises `PrismaAuctionDetailTransportError` (or a subclass) on any
        transport-level failure; never returns fabricated field values."""
        ...


def _parse_end_timestamp(raw_value: str, auction_id: str) -> datetime:
    iso_candidate = raw_value[:-1] + "+00:00" if raw_value.endswith("Z") else raw_value
    try:
        parsed = datetime.fromisoformat(iso_candidate)
    except ValueError:
        parsed = None
    if parsed is not None:
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise PrismaAuctionEndFieldMalformedError(
                f"Auction ID {auction_id} official end timestamp {raw_value!r} "
                "has no explicit timezone."
            )
        return parsed
    if _LOCAL_TIMESTAMP_PATTERN.fullmatch(raw_value):
        try:
            naive = datetime.strptime(raw_value, "%d.%m.%Y %H:%M")
        except ValueError as exc:
            raise PrismaAuctionEndFieldMalformedError(
                f"Auction ID {auction_id} official end timestamp {raw_value!r} "
                "is not a valid date."
            ) from exc
        return naive.replace(tzinfo=_SOURCE_ZONE)
    raise PrismaAuctionEndFieldMalformedError(
        f"Auction ID {auction_id} official end timestamp {raw_value!r} is not "
        "in a recognized explicit-timezone or Europe/Berlin local format."
    )


def parse_auction_end_record(
    auction_id: str,
    raw_fields: Mapping[str, str] | None,
    *,
    required_state: str = FINISHED_STATE,
) -> AuctionEndRecord:
    """Validate and parse one already-retrieved raw official detail payload.

    Rejects missing, malformed, contradictory, or mismatched data; never
    substitutes another date. `raw_fields` is whatever
    `AuctionDetailFetcher.fetch()` returned for the exact `auction_id`
    requested — this function performs no fetching of its own.
    """
    if not isinstance(auction_id, str) or not auction_id.strip():
        raise PrismaAuctionLookupError("Auction ID must be a non-blank string.")
    if not raw_fields:
        raise PrismaAuctionLookupError(
            f"No official auction detail was returned for Auction ID {auction_id}."
        )
    returned_id = raw_fields.get(FIELD_AUCTION_ID)
    if returned_id is None or not str(returned_id).strip():
        raise PrismaAuctionRecordMismatchError(
            f"The auction detail response for Auction ID {auction_id} did not "
            "include its own Auction ID."
        )
    if str(returned_id).strip() != auction_id:
        raise PrismaAuctionRecordMismatchError(
            f"The auction detail response Auction ID {str(returned_id).strip()!r} "
            f"does not match the requested Auction ID {auction_id!r}."
        )
    raw_state = raw_fields.get(FIELD_STATE)
    state = str(raw_state).strip() if raw_state is not None else None
    if state and state != required_state:
        raise PrismaAuctionNotFinishedError(
            f"Auction ID {auction_id} official state is {state!r}, not "
            f"{required_state!r}."
        )
    raw_end = raw_fields.get(FIELD_AUCTION_END)
    if raw_end is None or not str(raw_end).strip():
        raise PrismaAuctionEndFieldMissingError(
            f"Auction ID {auction_id} official detail has no explicit "
            f"{FIELD_AUCTION_END!r} field."
        )
    end_at = _parse_end_timestamp(str(raw_end).strip(), auction_id)
    return AuctionEndRecord(auction_id, end_at, state or None)


def authoritative_end_date(record: AuctionEndRecord) -> date:
    """The authoritative Europe/Berlin local calendar date for ECB rate selection."""
    return record.end_at.astimezone(_SOURCE_ZONE).date()


class PrismaAuctionLookup:
    """Accepts an exact Auction ID and returns a validated `AuctionEndRecord`.

    ``fetcher`` has no default implementation: per the revised specification,
    PrismaFunction never opens, controls, or downloads anything from the
    PRISMA website, so there is no live transport to fall back to. Omitting
    ``fetcher`` (the normal case for every real caller today) makes `lookup()`
    fail closed with `PrismaAuctionDetailTransportError` — the same typed,
    safe "Unavailable" outcome this module always produced for an
    unreachable live PRISMA surface — instead of raising an unrelated
    `AttributeError`. A previously resolved auction's rate is unaffected: it
    is served from `storage.AuctionStorage`'s durable cache and never reaches
    this fetch path again (see `rate_resolution.py`).
    """

    def __init__(
        self,
        fetcher: AuctionDetailFetcher | None = None,
        *,
        timeout_ms: int = DEFAULT_TIMEOUT_MS,
    ) -> None:
        self._fetcher = fetcher
        self._timeout_ms = timeout_ms

    def lookup(self, page: object, auction_id: str) -> AuctionEndRecord:
        if not isinstance(auction_id, str) or not auction_id.strip():
            raise PrismaAuctionLookupError("Auction ID must be a non-blank string.")
        if self._fetcher is None:
            raise PrismaAuctionDetailTransportError(
                "No official PRISMA auction-detail transport is available to "
                f"resolve Auction ID {auction_id}."
            )
        raw_fields = self._fetcher.fetch(page, auction_id, timeout_ms=self._timeout_ms)
        return parse_auction_end_record(auction_id, raw_fields)
