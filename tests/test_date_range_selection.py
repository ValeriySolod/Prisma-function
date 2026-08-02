from datetime import date

from date_range_selection import (
    DateRange,
    DateRangeOutcome,
    DateRangeSelection,
    describe_rejection,
    validate_date_range,
)


def test_accepts_valid_same_day_range():
    result = validate_date_range(date(2026, 3, 1), date(2026, 3, 1))

    assert result.outcome is DateRangeOutcome.ACCEPTED
    assert result.accepted is True
    assert result.date_range == DateRange(date(2026, 3, 1), date(2026, 3, 1))


def test_accepts_valid_multi_day_range():
    result = validate_date_range(date(2026, 3, 1), date(2026, 3, 10))

    assert result.outcome is DateRangeOutcome.ACCEPTED
    assert result.date_range == DateRange(date(2026, 3, 1), date(2026, 3, 10))


def test_rejects_missing_start_date():
    result = validate_date_range(None, date(2026, 3, 10))

    assert result.outcome is DateRangeOutcome.MISSING_START_DATE
    assert result.accepted is False
    assert result.date_range is None


def test_rejects_missing_end_date():
    result = validate_date_range(date(2026, 3, 1), None)

    assert result.outcome is DateRangeOutcome.MISSING_END_DATE
    assert result.accepted is False
    assert result.date_range is None


def test_rejects_when_both_dates_missing_deterministically_as_missing_start():
    result = validate_date_range(None, None)

    assert result.outcome is DateRangeOutcome.MISSING_START_DATE
    assert result.date_range is None


def test_rejects_reversed_range():
    result = validate_date_range(date(2026, 3, 10), date(2026, 3, 1))

    assert result.outcome is DateRangeOutcome.END_BEFORE_START
    assert result.date_range is None


def test_date_range_is_frozen():
    date_range = DateRange(date(2026, 3, 1), date(2026, 3, 2))

    try:
        date_range.start = date(2026, 3, 3)
    except AttributeError:
        pass
    else:
        raise AssertionError("DateRange must be immutable")


def test_describe_rejection_returns_stable_english_messages():
    assert describe_rejection(DateRangeOutcome.MISSING_START_DATE) == "A start date is required."
    assert describe_rejection(DateRangeOutcome.MISSING_END_DATE) == "An end date is required."
    assert describe_rejection(DateRangeOutcome.END_BEFORE_START) == (
        "The end date must not be earlier than the start date."
    )


def test_selection_starts_with_no_accepted_range():
    selection = DateRangeSelection()

    assert selection.current is None


def test_selection_accepts_valid_same_day_range():
    selection = DateRangeSelection()

    result = selection.select(date(2026, 3, 1), date(2026, 3, 1))

    assert result.accepted is True
    assert selection.current == DateRange(date(2026, 3, 1), date(2026, 3, 1))


def test_selection_accepts_valid_multi_day_range():
    selection = DateRangeSelection()

    result = selection.select(date(2026, 3, 1), date(2026, 3, 10))

    assert result.accepted is True
    assert selection.current == DateRange(date(2026, 3, 1), date(2026, 3, 10))


def test_selection_preserves_previous_range_after_missing_start_rejection():
    selection = DateRangeSelection()
    selection.select(date(2026, 3, 1), date(2026, 3, 5))

    result = selection.select(None, date(2026, 3, 5))

    assert result.accepted is False
    assert selection.current == DateRange(date(2026, 3, 1), date(2026, 3, 5))


def test_selection_preserves_previous_range_after_missing_end_rejection():
    selection = DateRangeSelection()
    selection.select(date(2026, 3, 1), date(2026, 3, 5))

    result = selection.select(date(2026, 3, 1), None)

    assert result.accepted is False
    assert selection.current == DateRange(date(2026, 3, 1), date(2026, 3, 5))


def test_selection_preserves_previous_range_after_reversed_rejection():
    selection = DateRangeSelection()
    selection.select(date(2026, 3, 1), date(2026, 3, 5))

    result = selection.select(date(2026, 3, 9), date(2026, 3, 1))

    assert result.accepted is False
    assert selection.current == DateRange(date(2026, 3, 1), date(2026, 3, 5))


def test_selection_preserves_no_range_after_rejection_before_any_acceptance():
    selection = DateRangeSelection()

    result = selection.select(None, None)

    assert result.accepted is False
    assert selection.current is None


def test_selection_allows_successful_retry_after_correction():
    selection = DateRangeSelection()

    rejected = selection.select(date(2026, 3, 10), date(2026, 3, 1))
    assert rejected.accepted is False
    assert selection.current is None

    accepted = selection.select(date(2026, 3, 1), date(2026, 3, 10))

    assert accepted.accepted is True
    assert selection.current == DateRange(date(2026, 3, 1), date(2026, 3, 10))


def test_selection_returns_stable_typed_result_object():
    selection = DateRangeSelection()

    result = selection.select(date(2026, 3, 1), date(2026, 3, 2))

    assert result.outcome is DateRangeOutcome.ACCEPTED
    assert result.date_range is selection.current
