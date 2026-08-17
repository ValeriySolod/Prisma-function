from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from prisma_function.prisma_auction_lookup import (
    FIELD_AUCTION_END,
    FIELD_AUCTION_ID,
    FIELD_STATE,
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


# --- No live PRISMA transport exists ---------------------------------------
#
# Per the revised specification, PrismaFunction never opens, controls, or
# downloads anything from the PRISMA website, so `PrismaAuctionLookup` has no
# default transport implementation to fall back to (see its docstring). A
# previously resolved auction's rate is unaffected: it is served from
# `storage.AuctionStorage`'s durable cache and never reaches this lookup
# again (see `rate_resolution.py`/`tests/test_rate_resolution.py`).


def test_lookup_fails_closed_when_no_fetcher_is_configured() -> None:
    lookup = PrismaAuctionLookup()
    with pytest.raises(PrismaAuctionDetailTransportError):
        lookup.lookup(page=object(), auction_id="998877")
