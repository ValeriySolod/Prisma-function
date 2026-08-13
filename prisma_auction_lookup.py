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
thin Playwright-facing transport seam (`AuctionDetailFetcher`,
`PlaywrightAuctionDetailFetcher`) that keeps page/selector/navigation
mechanics out of the business rules, mirroring `prisma_download.py`'s
existing split between `PrismaDownloadOrchestrator` (transport) and its own
typed, page-independent result/error types.

Real-environment evidence (2026-08-13, see ROADMAP.md P.36.19). Live
Windows/PRISMA DevTools inspection of a real finished auction (Auction ID
`62756895`) found that its public details page
(`https://app.prisma-capacity.eu/reporting/auctions/details/{auction_id}`)
itself performs `GET https://platform.prisma-capacity.eu/rest/auctions/{auction_id}`,
returning a JSON object exposing `id`, `phase` (e.g. `"FINISHED"`), and the
authoritative `auctionEnd` ISO-8601 UTC timestamp. The same response also
contains `auctionStart`, `runtime.start`, and `runtime.end` — different
fields that `PlaywrightAuctionDetailFetcher.fetch()` never reads, matching
the approved "never substitute" list for the auction-end value.
`PlaywrightAuctionDetailFetcher.fetch()` issues this request through the
managed session's own `page.request` (Playwright's `APIRequestContext`,
which automatically carries the browser context's cookies), so the lookup
stays part of `PrismaLifecycleController`'s existing managed PRISMA session
rather than opening an independent, unauthenticated connection. The business
layer below (accepting already-retrieved raw detail fields) is unchanged;
the fetcher normalizes the live JSON shape into that same
transport-agnostic `raw_fields` contract. Live-Windows visual validation of
the resulting Mapping display remains outstanding (see ROADMAP.md); wiring a
real `page` object into `app.py`'s resolution call is a separate, not-yet-
scheduled follow-up (`PrismaLifecycleController` does not currently expose
its managed page outside its own worker thread).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Mapping, Protocol
from urllib.parse import quote
from zoneinfo import ZoneInfo

__all__ = [
    "FIELD_AUCTION_ID",
    "FIELD_STATE",
    "FIELD_AUCTION_END",
    "FINISHED_STATE",
    "DEFAULT_TIMEOUT_MS",
    "AUCTION_DETAIL_URL_TEMPLATE",
    "PrismaAuctionLookupError",
    "PrismaAuctionRecordMismatchError",
    "PrismaAuctionNotFinishedError",
    "PrismaAuctionEndFieldMissingError",
    "PrismaAuctionEndFieldMalformedError",
    "PrismaAuctionDetailTransportError",
    "AuctionEndRecord",
    "AuctionDetailFetcher",
    "PlaywrightAuctionDetailFetcher",
    "PrismaAuctionLookup",
    "parse_auction_end_record",
    "authoritative_end_date",
]

FIELD_AUCTION_ID = "Auction ID"
FIELD_STATE = "State"
# This module's own transport-agnostic `raw_fields` key, not a live PRISMA
# field name: `PlaywrightAuctionDetailFetcher.fetch()` normalizes the live
# JSON response's `auctionEnd` field (see the module docstring) into this key
# before handing it to `parse_auction_end_record`.
FIELD_AUCTION_END = "End of Auction"
FINISHED_STATE = "Finished"
DEFAULT_TIMEOUT_MS = 10_000

# Live Windows/PRISMA DevTools evidence (Auction ID 62756895, 2026-08-13; see
# ROADMAP.md's P.36.19 entry): the public auction-details page performs this
# exact request against the platform host (distinct from the public
# `app.prisma-capacity.eu` host `PrismaSessionValidator` validates the
# managed session against).
AUCTION_DETAIL_URL_TEMPLATE = "https://platform.prisma-capacity.eu/rest/auctions/{auction_id}"
_RESPONSE_FIELD_ID = "id"
_RESPONSE_FIELD_PHASE = "phase"
_RESPONSE_FIELD_AUCTION_END = "auctionEnd"
_RESPONSE_FINISHED_PHASE = "FINISHED"

# Europe/Berlin is this project's already-established, live-verified
# authoritative timezone for PRISMA date interpretation (see
# `prisma_download.py`'s date-filter fill, verified across the CET/CEST DST
# boundary). The authoritative calendar date used for ECB rate selection is
# always this timezone's local date, never a UTC-shifted one.
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


class PlaywrightAuctionDetailFetcher:
    """Production transport seam, backed by the live-evidenced official
    PRISMA auction-detail endpoint (see the module docstring):
    `GET {AUCTION_DETAIL_URL_TEMPLATE}`.

    The request is issued through the managed session's own `page.request`
    (Playwright's `APIRequestContext`), so it automatically reuses the
    managed browser context's cookies instead of opening an independent,
    unauthenticated connection — the same "stay inside the managed session"
    property `PrismaDownloadOrchestrator` already relies on for its own page
    interactions. Only `id`, `phase`, and `auctionEnd` are ever read from the
    response; `auctionStart`, `runtime.start`, `runtime.end`, and every other
    response field are never consulted (see the module docstring's
    prohibited-substitution list).
    """

    def fetch(
        self, page: object, auction_id: str, *, timeout_ms: int = DEFAULT_TIMEOUT_MS
    ) -> Mapping[str, str]:
        url = AUCTION_DETAIL_URL_TEMPLATE.format(
            auction_id=quote(str(auction_id), safe="")
        )
        try:
            response = page.request.get(url, timeout=timeout_ms)
        except Exception as exc:
            raise PrismaAuctionDetailTransportError(
                f"The official PRISMA auction-detail request for Auction ID "
                f"{auction_id} failed: {type(exc).__name__}."
            ) from exc

        if not self._response_ok(response):
            status = getattr(response, "status", None)
            raise PrismaAuctionDetailTransportError(
                f"The official PRISMA auction-detail request for Auction ID "
                f"{auction_id} returned an unsuccessful HTTP status "
                f"({status if status is not None else 'unknown'})."
            )

        payload = self._parse_json_object(response, auction_id)

        raw_id = payload.get(_RESPONSE_FIELD_ID)
        if raw_id is None or not str(raw_id).strip():
            raise PrismaAuctionRecordMismatchError(
                f"The auction detail response for Auction ID {auction_id} did "
                "not include its own id."
            )
        # System-boundary normalization (explicitly permitted here, never
        # inside the transport-independent business layer below): the live
        # API returns `id` as a JSON number, while `auction_id` is this
        # module's own string identity; both sides are compared as stripped
        # strings so a numeric/string type difference is never itself a
        # mismatch, but any other difference is rejected.
        if str(raw_id).strip() != str(auction_id).strip():
            raise PrismaAuctionRecordMismatchError(
                f"The auction detail response id {str(raw_id).strip()!r} does "
                f"not match the requested Auction ID {auction_id!r}."
            )

        raw_phase = payload.get(_RESPONSE_FIELD_PHASE)
        phase_text = str(raw_phase).strip() if raw_phase is not None else ""
        if phase_text != _RESPONSE_FINISHED_PHASE:
            raise PrismaAuctionNotFinishedError(
                f"Auction ID {auction_id} official phase is "
                f"{(phase_text or 'missing')!r}, not {_RESPONSE_FINISHED_PHASE!r}."
            )

        raw_fields: dict[str, str] = {
            FIELD_AUCTION_ID: str(raw_id).strip(),
            FIELD_STATE: FINISHED_STATE,
        }
        raw_end = payload.get(_RESPONSE_FIELD_AUCTION_END)
        if raw_end is not None and str(raw_end).strip():
            raw_fields[FIELD_AUCTION_END] = str(raw_end).strip()
        return raw_fields

    @staticmethod
    def _response_ok(response: object) -> bool:
        ok = getattr(response, "ok", None)
        if isinstance(ok, bool):
            return ok
        status = getattr(response, "status", None)
        return isinstance(status, int) and 200 <= status < 300

    @staticmethod
    def _parse_json_object(response: object, auction_id: str) -> dict:
        try:
            payload = response.json()
        except Exception as exc:
            raise PrismaAuctionDetailTransportError(
                f"The official PRISMA auction-detail response for Auction ID "
                f"{auction_id} was not valid JSON."
            ) from exc
        if not isinstance(payload, dict):
            raise PrismaAuctionDetailTransportError(
                f"The official PRISMA auction-detail response for Auction ID "
                f"{auction_id} was not a JSON object."
            )
        return payload


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
    """Accepts an exact Auction ID and returns a validated `AuctionEndRecord`."""

    def __init__(
        self,
        fetcher: AuctionDetailFetcher | None = None,
        *,
        timeout_ms: int = DEFAULT_TIMEOUT_MS,
    ) -> None:
        self._fetcher = fetcher if fetcher is not None else PlaywrightAuctionDetailFetcher()
        self._timeout_ms = timeout_ms

    def lookup(self, page: object, auction_id: str) -> AuctionEndRecord:
        if not isinstance(auction_id, str) or not auction_id.strip():
            raise PrismaAuctionLookupError("Auction ID must be a non-blank string.")
        raw_fields = self._fetcher.fetch(page, auction_id, timeout_ms=self._timeout_ms)
        return parse_auction_end_record(auction_id, raw_fields)
