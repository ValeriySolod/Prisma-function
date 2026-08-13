from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from prisma_auction_lookup import (
    AUCTION_DETAIL_URL_TEMPLATE,
    FIELD_AUCTION_END,
    FIELD_AUCTION_ID,
    FIELD_STATE,
    FINISHED_STATE,
    AuctionEndRecord,
    PlaywrightAuctionDetailFetcher,
    PrismaAuctionDetailTransportError,
    PrismaAuctionEndFieldMalformedError,
    PrismaAuctionEndFieldMissingError,
    PrismaAuctionLookup,
    PrismaAuctionLookupError,
    PrismaAuctionNotFinishedError,
    PrismaAuctionRecordMismatchError,
    authoritative_end_date,
    parse_auction_end_record,
)


def test_finished_state_is_eligible() -> None:
    record = parse_auction_end_record(
        "62333921",
        {
            FIELD_AUCTION_ID: "62333921",
            FIELD_STATE: "Finished",
            FIELD_AUCTION_END: "03.08.2026 14:30",
        },
    )
    assert record.auction_id == "62333921"
    assert record.state == "Finished"


def test_cancelled_state_is_not_eligible() -> None:
    with pytest.raises(PrismaAuctionNotFinishedError):
        parse_auction_end_record(
            "1",
            {
                FIELD_AUCTION_ID: "1",
                FIELD_STATE: "Cancelled",
                FIELD_AUCTION_END: "03.08.2026 14:30",
            },
        )


@pytest.mark.parametrize("other_state", ["Open", "Pending", "Suspended", "unknown"])
def test_other_non_finished_states_are_not_eligible(other_state: str) -> None:
    with pytest.raises(PrismaAuctionNotFinishedError):
        parse_auction_end_record(
            "1",
            {
                FIELD_AUCTION_ID: "1",
                FIELD_STATE: other_state,
                FIELD_AUCTION_END: "03.08.2026 14:30",
            },
        )


def test_absent_state_field_is_not_treated_as_a_rejection() -> None:
    # "verify the authoritative finished state when PRISMA exposes it" — a
    # detail payload without a state field at all is not itself a rejection.
    record = parse_auction_end_record(
        "1", {FIELD_AUCTION_ID: "1", FIELD_AUCTION_END: "03.08.2026 14:30"}
    )
    assert record.state is None


def test_lookup_requests_the_exact_auction_id() -> None:
    class RecordingFetcher:
        def __init__(self) -> None:
            self.requested: list[str] = []

        def fetch(self, page, auction_id, *, timeout_ms):
            self.requested.append(auction_id)
            return {
                FIELD_AUCTION_ID: auction_id,
                FIELD_STATE: "Finished",
                FIELD_AUCTION_END: "03.08.2026 14:30",
            }

    fetcher = RecordingFetcher()
    lookup = PrismaAuctionLookup(fetcher)
    lookup.lookup(page=object(), auction_id="998877")
    assert fetcher.requested == ["998877"]


def test_mismatched_returned_auction_id_is_rejected() -> None:
    with pytest.raises(PrismaAuctionRecordMismatchError):
        parse_auction_end_record(
            "998877",
            {
                FIELD_AUCTION_ID: "different-id",
                FIELD_STATE: "Finished",
                FIELD_AUCTION_END: "03.08.2026 14:30",
            },
        )


def test_missing_returned_auction_id_is_rejected_as_mismatch() -> None:
    with pytest.raises(PrismaAuctionRecordMismatchError):
        parse_auction_end_record(
            "998877", {FIELD_STATE: "Finished", FIELD_AUCTION_END: "03.08.2026 14:30"}
        )


def test_explicit_iso_offset_timestamp_is_parsed_correctly() -> None:
    record = parse_auction_end_record(
        "1",
        {
            FIELD_AUCTION_ID: "1",
            FIELD_STATE: "Finished",
            FIELD_AUCTION_END: "2026-08-03T14:30:00+02:00",
        },
    )
    assert record.end_at == datetime(2026, 8, 3, 14, 30, tzinfo=timezone(timedelta(hours=2)))


def test_explicit_zulu_timestamp_is_parsed_correctly() -> None:
    record = parse_auction_end_record(
        "1",
        {
            FIELD_AUCTION_ID: "1",
            FIELD_STATE: "Finished",
            FIELD_AUCTION_END: "2026-08-03T12:30:00Z",
        },
    )
    assert record.end_at.utcoffset().total_seconds() == 0
    assert record.end_at.hour == 12


def test_prisma_local_format_gets_explicit_europe_berlin_timezone() -> None:
    record = parse_auction_end_record(
        "1",
        {
            FIELD_AUCTION_ID: "1",
            FIELD_STATE: "Finished",
            FIELD_AUCTION_END: "03.08.2026 14:30",
        },
    )
    assert record.end_at.tzinfo is not None
    assert record.end_at.utcoffset().total_seconds() == 2 * 3600  # CEST in August


@pytest.mark.parametrize("missing_value", [None, "", "   "])
def test_missing_end_field_is_rejected(missing_value) -> None:
    fields = {FIELD_AUCTION_ID: "1", FIELD_STATE: "Finished"}
    if missing_value is not None:
        fields[FIELD_AUCTION_END] = missing_value
    with pytest.raises(PrismaAuctionEndFieldMissingError):
        parse_auction_end_record("1", fields)


@pytest.mark.parametrize(
    "malformed_value",
    ["not-a-date", "2026-13-40", "03/08/2026 14:30", "03.08.2026", "14:30"],
)
def test_malformed_end_field_is_rejected(malformed_value: str) -> None:
    with pytest.raises(PrismaAuctionEndFieldMalformedError):
        parse_auction_end_record(
            "1",
            {
                FIELD_AUCTION_ID: "1",
                FIELD_STATE: "Finished",
                FIELD_AUCTION_END: malformed_value,
            },
        )


def test_naive_end_field_without_recognized_local_shape_is_rejected() -> None:
    # A naive ISO-like value that is not the recognized DD.MM.YYYY HH:MM
    # local shape either must be rejected, never silently assumed to be UTC.
    with pytest.raises(PrismaAuctionEndFieldMalformedError):
        parse_auction_end_record(
            "1",
            {
                FIELD_AUCTION_ID: "1",
                FIELD_STATE: "Finished",
                FIELD_AUCTION_END: "2026-08-03T14:30:00",
            },
        )


def test_start_of_auction_field_is_never_consulted() -> None:
    # Only FIELD_AUCTION_END is ever read for the end timestamp, even when a
    # "Start of Auction" value is present in the same payload.
    record = parse_auction_end_record(
        "1",
        {
            FIELD_AUCTION_ID: "1",
            FIELD_STATE: "Finished",
            "Start of Auction": "01.01.2020 00:00",
            FIELD_AUCTION_END: "03.08.2026 14:30",
        },
    )
    assert authoritative_end_date(record) == date(2026, 8, 3)


def test_product_runtime_end_field_is_never_consulted() -> None:
    record = parse_auction_end_record(
        "1",
        {
            FIELD_AUCTION_ID: "1",
            FIELD_STATE: "Finished",
            "Product Runtime End": "01.01.2020 00:00",
            FIELD_AUCTION_END: "03.08.2026 14:30",
        },
    )
    assert authoritative_end_date(record) == date(2026, 8, 3)


def test_timezone_handling_produces_correct_authoritative_calendar_date() -> None:
    # 2026-08-03T23:30:00 UTC is already 2026-08-04 01:30 in Europe/Berlin
    # (CEST, UTC+2): the authoritative calendar date must be the Berlin
    # date, not the UTC date, proving timezone conversion is applied before
    # taking the calendar date rather than reading a naive/UTC date.
    record = parse_auction_end_record(
        "1",
        {
            FIELD_AUCTION_ID: "1",
            FIELD_STATE: "Finished",
            FIELD_AUCTION_END: "2026-08-03T23:30:00Z",
        },
    )
    assert record.end_at.date() == date(2026, 8, 3)
    assert authoritative_end_date(record) == date(2026, 8, 4)


def test_no_raw_fields_is_rejected() -> None:
    with pytest.raises(PrismaAuctionLookupError):
        parse_auction_end_record("1", {})
    with pytest.raises(PrismaAuctionLookupError):
        parse_auction_end_record("1", None)


@pytest.mark.parametrize("blank_id", ["", "   "])
def test_blank_requested_auction_id_is_rejected(blank_id: str) -> None:
    with pytest.raises(PrismaAuctionLookupError):
        parse_auction_end_record(
            blank_id,
            {
                FIELD_AUCTION_ID: blank_id,
                FIELD_STATE: "Finished",
                FIELD_AUCTION_END: "03.08.2026 14:30",
            },
        )


# --- PlaywrightAuctionDetailFetcher: live-evidenced production transport ---
#
# Live Windows/PRISMA DevTools inspection (Auction ID 62756895, 2026-08-13;
# see ROADMAP.md's P.36.19 entry) found the official endpoint
# `GET https://platform.prisma-capacity.eu/rest/auctions/{auction_id}`.
# These fakes model Playwright's `page.request` (`APIRequestContext`) and
# its `APIResponse` closely enough to exercise the real fetcher without any
# network access.


class FakeApiResponse:
    def __init__(self, *, status=200, ok=None, json_body=None, json_error=None):
        self.status = status
        self.ok = ok if ok is not None else 200 <= status < 300
        self._json_body = json_body
        self._json_error = json_error

    def json(self):
        if self._json_error is not None:
            raise self._json_error
        return self._json_body


class FakeApiRequestContext:
    def __init__(self, response=None, *, error=None):
        self._response = response
        self._error = error
        self.calls: list[tuple[str, int]] = []

    def get(self, url, *, timeout):
        self.calls.append((url, timeout))
        if self._error is not None:
            raise self._error
        return self._response


class FakePage:
    def __init__(self, request):
        self.request = request


def _live_evidence_payload(**overrides) -> dict:
    """The exact sanitized live response shape recorded in ROADMAP.md's
    P.36.19 entry, including the fields that must never be substituted for
    `auctionEnd` (`auctionStart`, `runtime.start`/`runtime.end`)."""
    payload = {
        "id": 62756895,
        "phase": "FINISHED",
        "auctionStart": "2026-08-01T14:30:00.008Z",
        "auctionEnd": "2026-08-01T15:00:23.589Z",
        "runtime": {
            "start": "2026-08-02T04:00:00.000Z",
            "end": "2026-08-03T04:00:00.000Z",
        },
    }
    payload.update(overrides)
    return payload


def test_fetcher_constructs_exact_endpoint_and_issues_get_with_explicit_timeout() -> None:
    request_context = FakeApiRequestContext(
        FakeApiResponse(json_body=_live_evidence_payload())
    )
    page = FakePage(request_context)
    PlaywrightAuctionDetailFetcher().fetch(page, "62756895", timeout_ms=7_500)
    assert request_context.calls == [
        (AUCTION_DETAIL_URL_TEMPLATE.format(auction_id="62756895"), 7_500)
    ]


def test_fetcher_uses_the_default_timeout_when_not_overridden() -> None:
    request_context = FakeApiRequestContext(
        FakeApiResponse(json_body=_live_evidence_payload())
    )
    page = FakePage(request_context)
    PlaywrightAuctionDetailFetcher().fetch(page, "62756895")
    assert request_context.calls[0][1] == 10_000


def test_fetcher_rejects_non_success_http_status() -> None:
    page = FakePage(FakeApiRequestContext(FakeApiResponse(status=404, ok=False)))
    with pytest.raises(PrismaAuctionDetailTransportError, match="404"):
        PlaywrightAuctionDetailFetcher().fetch(page, "1", timeout_ms=10_000)


def test_fetcher_rejects_connection_failure() -> None:
    page = FakePage(FakeApiRequestContext(error=OSError("connection reset")))
    with pytest.raises(PrismaAuctionDetailTransportError):
        PlaywrightAuctionDetailFetcher().fetch(page, "1", timeout_ms=10_000)


def test_fetcher_rejects_invalid_json() -> None:
    page = FakePage(
        FakeApiRequestContext(FakeApiResponse(json_error=ValueError("bad json")))
    )
    with pytest.raises(PrismaAuctionDetailTransportError):
        PlaywrightAuctionDetailFetcher().fetch(page, "1", timeout_ms=10_000)


def test_fetcher_rejects_non_object_json() -> None:
    page = FakePage(FakeApiRequestContext(FakeApiResponse(json_body=[1, 2, 3])))
    with pytest.raises(PrismaAuctionDetailTransportError):
        PlaywrightAuctionDetailFetcher().fetch(page, "1", timeout_ms=10_000)


def test_fetcher_rejects_mismatched_response_id() -> None:
    page = FakePage(
        FakeApiRequestContext(
            FakeApiResponse(json_body=_live_evidence_payload(id=1))
        )
    )
    with pytest.raises(PrismaAuctionRecordMismatchError):
        PlaywrightAuctionDetailFetcher().fetch(page, "62756895", timeout_ms=10_000)


def test_fetcher_rejects_missing_response_id() -> None:
    payload = _live_evidence_payload()
    del payload["id"]
    page = FakePage(FakeApiRequestContext(FakeApiResponse(json_body=payload)))
    with pytest.raises(PrismaAuctionRecordMismatchError):
        PlaywrightAuctionDetailFetcher().fetch(page, "62756895", timeout_ms=10_000)


def test_fetcher_normalizes_numeric_response_id_for_exact_comparison() -> None:
    # Explicit, permitted system-boundary normalization: the live API
    # returns `id` as a JSON number, `auction_id` is this module's own
    # string identity; only the type difference is tolerated here.
    page = FakePage(
        FakeApiRequestContext(
            FakeApiResponse(json_body=_live_evidence_payload(id=62756895))
        )
    )
    raw_fields = PlaywrightAuctionDetailFetcher().fetch(
        page, "62756895", timeout_ms=10_000
    )
    assert raw_fields[FIELD_AUCTION_ID] == "62756895"


def test_fetcher_normalizes_finished_phase_to_the_business_layer_convention() -> None:
    page = FakePage(
        FakeApiRequestContext(FakeApiResponse(json_body=_live_evidence_payload()))
    )
    raw_fields = PlaywrightAuctionDetailFetcher().fetch(
        page, "62756895", timeout_ms=10_000
    )
    assert raw_fields[FIELD_STATE] == FINISHED_STATE


@pytest.mark.parametrize("phase", ["CANCELLED", "OPEN", "PENDING", "finished"])
def test_fetcher_rejects_non_finished_phase(phase: str) -> None:
    page = FakePage(
        FakeApiRequestContext(
            FakeApiResponse(json_body=_live_evidence_payload(phase=phase))
        )
    )
    with pytest.raises(PrismaAuctionNotFinishedError):
        PlaywrightAuctionDetailFetcher().fetch(page, "62756895", timeout_ms=10_000)


def test_fetcher_rejects_missing_phase() -> None:
    payload = _live_evidence_payload()
    del payload["phase"]
    page = FakePage(FakeApiRequestContext(FakeApiResponse(json_body=payload)))
    with pytest.raises(PrismaAuctionNotFinishedError):
        PlaywrightAuctionDetailFetcher().fetch(page, "62756895", timeout_ms=10_000)


def test_fetcher_extracts_only_the_explicit_auction_end_field() -> None:
    page = FakePage(
        FakeApiRequestContext(FakeApiResponse(json_body=_live_evidence_payload()))
    )
    raw_fields = PlaywrightAuctionDetailFetcher().fetch(
        page, "62756895", timeout_ms=10_000
    )
    assert raw_fields[FIELD_AUCTION_END] == "2026-08-01T15:00:23.589Z"


def test_transport_error_never_includes_headers_or_cookies() -> None:
    page = FakePage(FakeApiRequestContext(FakeApiResponse(status=500, ok=False)))
    with pytest.raises(PrismaAuctionDetailTransportError) as excinfo:
        PlaywrightAuctionDetailFetcher().fetch(page, "1", timeout_ms=10_000)
    message = str(excinfo.value)
    assert "cookie" not in message.lower()
    assert "authorization" not in message.lower()
    assert "token" not in message.lower()


def test_lookup_end_to_end_with_the_live_evidenced_payload() -> None:
    page = FakePage(
        FakeApiRequestContext(FakeApiResponse(json_body=_live_evidence_payload()))
    )
    lookup = PrismaAuctionLookup(PlaywrightAuctionDetailFetcher())
    record = lookup.lookup(page, "62756895")
    assert record.auction_id == "62756895"
    assert record.end_at == datetime(
        2026, 8, 1, 15, 0, 23, 589000, tzinfo=timezone.utc
    )
    # 15:00:23.589 UTC is 17:00:23.589 CEST (Europe/Berlin, UTC+2 in August),
    # still calendar date 2026-08-01, matching the live-verified example.
    assert authoritative_end_date(record) == date(2026, 8, 1)


def test_lookup_never_substitutes_auction_start_or_runtime_fields() -> None:
    # `auctionStart` and `runtime.start`/`runtime.end` in this fixture are
    # deliberately different from `auctionEnd`; if any were substituted the
    # resulting instant would not match the one asserted below.
    page = FakePage(
        FakeApiRequestContext(FakeApiResponse(json_body=_live_evidence_payload()))
    )
    lookup = PrismaAuctionLookup(PlaywrightAuctionDetailFetcher())
    record = lookup.lookup(page, "62756895")
    assert record.end_at.isoformat() == "2026-08-01T15:00:23.589000+00:00"


def test_lookup_default_uses_the_production_playwright_transport() -> None:
    # A bare object() has no `.request` attribute, so the production
    # fetcher's own request call fails with a sanitized transport error
    # rather than silently returning a placeholder result.
    lookup = PrismaAuctionLookup()
    with pytest.raises(PrismaAuctionDetailTransportError):
        lookup.lookup(page=object(), auction_id="998877")


def test_lookup_fails_when_only_prohibited_dates_are_present_without_auction_end() -> None:
    # A fixture with valid prohibited dates (auctionStart, runtime) but a
    # missing `auctionEnd` must fail, never fall back to a prohibited field.
    payload = _live_evidence_payload()
    del payload["auctionEnd"]
    page = FakePage(FakeApiRequestContext(FakeApiResponse(json_body=payload)))
    lookup = PrismaAuctionLookup(PlaywrightAuctionDetailFetcher())
    with pytest.raises(PrismaAuctionEndFieldMissingError):
        lookup.lookup(page, "62756895")
