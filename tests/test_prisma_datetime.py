from __future__ import annotations

import pytest

from prisma_function.prisma_datetime import (
    PRISMA_LOCAL_TIMEZONE,
    PrismaLocalTimestampAmbiguousError,
    PrismaLocalTimestampFormatError,
    PrismaLocalTimestampNonexistentError,
    elapsed_hours,
    format_auction_date,
    format_flow_timestamp,
    parse_prisma_local_timestamp,
)


# --- normal (non-DST-boundary) interpretation --------------------------------

def test_normal_cet_period_input_uses_utc_plus_1_offset() -> None:
    parsed = parse_prisma_local_timestamp("10.01.2026 09:00")
    assert parsed.utcoffset().total_seconds() == 3600
    assert parsed.tzinfo is PRISMA_LOCAL_TIMEZONE


def test_normal_cest_period_input_uses_utc_plus_2_offset() -> None:
    parsed = parse_prisma_local_timestamp("10.07.2026 09:00")
    assert parsed.utcoffset().total_seconds() == 7200


# --- output formatting --------------------------------------------------------

def test_format_auction_date_is_exactly_yyyy_mm_dd() -> None:
    parsed = parse_prisma_local_timestamp("10.07.2026 09:30")
    assert format_auction_date(parsed) == "2026-07-10"


def test_format_flow_timestamp_is_exactly_yyyy_mm_dd_hh_mm() -> None:
    parsed = parse_prisma_local_timestamp("10.07.2026 09:30")
    assert format_flow_timestamp(parsed) == "2026-07-10 09:30"


@pytest.mark.parametrize("raw", ["10.07.2026 09:30", "10.01.2026 00:00"])
def test_formatted_output_never_contains_t_seconds_or_offset(raw: str) -> None:
    parsed = parse_prisma_local_timestamp(raw)
    for value in (format_auction_date(parsed), format_flow_timestamp(parsed)):
        assert "T" not in value
        assert "+" not in value
        assert value.count(":") <= 1


# --- format rejection ----------------------------------------------------

@pytest.mark.parametrize("raw", [
    "not a date", "2026-07-10 09:30", "10/07/2026 09:30", "10.07.2026", "",
    "1.07.2026 09:30", "10.7.2026 09:30", "10.07.2026 9:30",
])
def test_malformed_shape_is_rejected(raw: str) -> None:
    with pytest.raises(PrismaLocalTimestampFormatError):
        parse_prisma_local_timestamp(raw)


def test_invalid_calendar_date_is_rejected() -> None:
    with pytest.raises(PrismaLocalTimestampFormatError):
        parse_prisma_local_timestamp("31.02.2026 09:00")


# --- DST boundary policy -------------------------------------------------

def test_nonexistent_spring_gap_local_time_is_rejected() -> None:
    # Europe/Berlin 2026 spring-forward: 2026-03-29, 02:00 CET -> 03:00 CEST.
    with pytest.raises(PrismaLocalTimestampNonexistentError):
        parse_prisma_local_timestamp("29.03.2026 02:30")


def test_ambiguous_autumn_overlap_local_time_is_rejected() -> None:
    # Europe/Berlin 2026 autumn-back: 2026-10-25, 03:00 CEST -> 02:00 CET.
    with pytest.raises(PrismaLocalTimestampAmbiguousError):
        parse_prisma_local_timestamp("25.10.2026 02:30")


@pytest.mark.parametrize("raw", ["29.03.2026 01:59", "29.03.2026 03:00"])
def test_times_immediately_around_the_spring_gap_are_unambiguous(raw: str) -> None:
    parse_prisma_local_timestamp(raw)  # must not raise


@pytest.mark.parametrize("raw", ["25.10.2026 01:59", "25.10.2026 03:00"])
def test_times_immediately_around_the_autumn_overlap_are_unambiguous(raw: str) -> None:
    parse_prisma_local_timestamp(raw)  # must not raise


def test_error_messages_are_stable_and_no_filesystem_path_is_present() -> None:
    with pytest.raises(PrismaLocalTimestampNonexistentError) as excinfo:
        parse_prisma_local_timestamp("29.03.2026 02:30")
    message = str(excinfo.value)
    assert "does not exist" in message
    assert "\\" not in message and ":\\" not in message and ".csv" not in message

    with pytest.raises(PrismaLocalTimestampAmbiguousError) as excinfo:
        parse_prisma_local_timestamp("25.10.2026 02:30")
    message = str(excinfo.value)
    assert "ambiguous" in message
    assert "\\" not in message and ":\\" not in message and ".csv" not in message


# --- DST-crossing duration correctness (elapsed time, not wall-clock diff) --

def test_naive_subtraction_of_same_tzinfo_datetimes_is_a_documented_trap() -> None:
    # Regression guard for the exact bug `elapsed_hours` exists to avoid:
    # Python's datetime subtraction ignores tzinfo entirely (and subtracts
    # naive wall-clock fields directly) when both operands share the same
    # tzinfo object, which `parse_prisma_local_timestamp` always returns
    # (the single `PRISMA_LOCAL_TIMEZONE` instance). Plain `end - start`
    # here yields the wrong, naive 3-hour wall-clock difference, not the
    # true 2-hour elapsed time.
    start = parse_prisma_local_timestamp("29.03.2026 01:00")
    end = parse_prisma_local_timestamp("29.03.2026 04:00")
    assert (end - start).total_seconds() / 3600 == 3.0


def test_spring_gap_crossing_elapsed_time_accounts_for_the_missing_hour() -> None:
    start = parse_prisma_local_timestamp("29.03.2026 01:00")
    end = parse_prisma_local_timestamp("29.03.2026 04:00")
    assert elapsed_hours(start, end) == 2.0  # not the naive 3.0


def test_autumn_overlap_crossing_elapsed_time_accounts_for_the_extra_hour() -> None:
    start = parse_prisma_local_timestamp("25.10.2026 01:00")
    end = parse_prisma_local_timestamp("25.10.2026 04:00")
    assert elapsed_hours(start, end) == 4.0  # not the naive 3.0


def test_elapsed_hours_matches_naive_subtraction_away_from_a_dst_transition() -> None:
    start = parse_prisma_local_timestamp("10.07.2026 10:00")
    end = parse_prisma_local_timestamp("10.07.2026 16:00")
    assert elapsed_hours(start, end) == 6.0
