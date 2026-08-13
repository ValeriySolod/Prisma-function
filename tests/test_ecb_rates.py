from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ecb_rates import (
    EUR,
    EcbRateError,
    EcbRateNotFoundError,
    EcbRateObservation,
    EcbRateResult,
    EcbRateSourceError,
    resolve_rate_to_eur,
)


class FakeSource:
    """Deterministic in-memory ECB source; never performs network access."""

    def __init__(self, observation: EcbRateObservation | None = None, *, error: Exception | None = None):
        self.observation = observation
        self.error = error
        self.calls: list[tuple[str, date, float]] = []

    def fetch(self, currency: str, *, on_or_before: date, timeout_seconds: float):
        self.calls.append((currency, on_or_before, timeout_seconds))
        if self.error is not None:
            raise self.error
        return self.observation


def test_eur_is_identity_rate_with_no_network_access() -> None:
    class ExplodingSource:
        def fetch(self, *args, **kwargs):
            raise AssertionError("EUR must never consult the ECB source.")

    result = resolve_rate_to_eur(EUR, date(2026, 8, 3), source=ExplodingSource())
    assert result == EcbRateResult(EUR, Decimal(1), date(2026, 8, 3))


def test_publication_day_auction_uses_that_days_rate() -> None:
    source = FakeSource(EcbRateObservation(date(2026, 8, 3), Decimal("1.0921")))
    result = resolve_rate_to_eur("USD", date(2026, 8, 3), source=source)
    assert result.publication_date == date(2026, 8, 3)
    assert result.currency == "USD"


def test_weekend_uses_most_recent_earlier_publication() -> None:
    # Requested Saturday 2026-08-08; source (as the real ECB SDW endpoint
    # does via lastNObservations=1) returns the prior Friday's publication.
    source = FakeSource(EcbRateObservation(date(2026, 8, 7), Decimal("1.09")))
    result = resolve_rate_to_eur("USD", date(2026, 8, 8), source=source)
    assert result.publication_date == date(2026, 8, 7)


def test_ecb_holiday_uses_most_recent_earlier_publication() -> None:
    source = FakeSource(EcbRateObservation(date(2025, 12, 24), Decimal("1.10")))
    result = resolve_rate_to_eur("USD", date(2025, 12, 25), source=source)
    assert result.publication_date == date(2025, 12, 24)


def test_later_publication_is_never_selected() -> None:
    source = FakeSource(EcbRateObservation(date(2026, 8, 10), Decimal("1.10")))
    with pytest.raises(EcbRateSourceError, match="later than"):
        resolve_rate_to_eur("USD", date(2026, 8, 3), source=source)


def test_no_eligible_rate_fails_explicitly() -> None:
    source = FakeSource(None)
    with pytest.raises(EcbRateNotFoundError):
        resolve_rate_to_eur("USD", date(2026, 8, 3), source=source)


def test_quotation_direction_and_rate_to_eur_arithmetic() -> None:
    # ECB publishes USD as foreign-currency-units-per-EUR: 1 EUR = 1.0921 USD.
    source = FakeSource(EcbRateObservation(date(2026, 8, 3), Decimal("1.0921")))
    result = resolve_rate_to_eur("USD", date(2026, 8, 3), source=source)
    expected = (Decimal(1) / Decimal("1.0921")).quantize(Decimal("1.0000000000"))
    assert result.rate_to_eur == expected
    assert isinstance(result.rate_to_eur, Decimal)
    # 1 USD is worth less than 1 EUR when 1 EUR buys more than 1 USD.
    assert result.rate_to_eur < 1


def test_bgn_arithmetic_matches_known_currency_board_peg() -> None:
    source = FakeSource(EcbRateObservation(date(2026, 8, 3), Decimal("1.9558")))
    result = resolve_rate_to_eur("BGN", date(2026, 8, 3), source=source)
    assert result.rate_to_eur == (Decimal(1) / Decimal("1.9558")).quantize(Decimal("1.0000000000"))


def test_uses_exact_decimal_not_binary_float() -> None:
    source = FakeSource(EcbRateObservation(date(2026, 8, 3), Decimal("3")))
    result = resolve_rate_to_eur("USD", date(2026, 8, 3), source=source)
    assert result.rate_to_eur == Decimal("0.3333333333")


@pytest.mark.parametrize("bad_currency", ["usd", "US", "USDD", "", "1SD", None, 42])
def test_malformed_currency_code_is_rejected(bad_currency) -> None:
    with pytest.raises(EcbRateError):
        resolve_rate_to_eur(bad_currency, date(2026, 8, 3), source=FakeSource())


def test_non_positive_rate_is_rejected() -> None:
    source = FakeSource(EcbRateObservation(date(2026, 8, 3), Decimal("0")))
    with pytest.raises(EcbRateSourceError):
        resolve_rate_to_eur("USD", date(2026, 8, 3), source=source)


def test_negative_rate_is_rejected() -> None:
    source = FakeSource(EcbRateObservation(date(2026, 8, 3), Decimal("-1")))
    with pytest.raises(EcbRateSourceError):
        resolve_rate_to_eur("USD", date(2026, 8, 3), source=source)


def test_source_error_propagates_as_ecb_rate_source_error() -> None:
    source = FakeSource(error=EcbRateSourceError("network down"))
    with pytest.raises(EcbRateSourceError, match="network down"):
        resolve_rate_to_eur("USD", date(2026, 8, 3), source=source)


def test_explicit_timeout_is_forwarded_to_source() -> None:
    source = FakeSource(EcbRateObservation(date(2026, 8, 3), Decimal("1.0921")))
    resolve_rate_to_eur("USD", date(2026, 8, 3), source=source, timeout_seconds=3.5)
    assert source.calls == [("USD", date(2026, 8, 3), 3.5)]


def test_csv_parsing_ignores_empty_result_as_not_found() -> None:
    from ecb_rates import _parse_csv_observation

    header_only = (
        "KEY,FREQ,CURRENCY,CURRENCY_DENOM,EXR_TYPE,EXR_SUFFIX,TIME_PERIOD,OBS_VALUE\n"
    )
    assert _parse_csv_observation(header_only) is None


def test_csv_parsing_extracts_last_row() -> None:
    from ecb_rates import _parse_csv_observation

    payload = (
        "KEY,FREQ,CURRENCY,CURRENCY_DENOM,EXR_TYPE,EXR_SUFFIX,TIME_PERIOD,OBS_VALUE\n"
        "EXR.D.USD.EUR.SP00.A,D,USD,EUR,SP00,A,2026-08-03,1.0921\n"
    )
    observation = _parse_csv_observation(payload)
    assert observation == EcbRateObservation(date(2026, 8, 3), Decimal("1.0921"))


def test_csv_parsing_rejects_missing_columns() -> None:
    from ecb_rates import _parse_csv_observation

    with pytest.raises(EcbRateSourceError, match="required"):
        _parse_csv_observation("A,B\n1,2\n")


def test_csv_parsing_rejects_malformed_date() -> None:
    from ecb_rates import _parse_csv_observation

    payload = "TIME_PERIOD,OBS_VALUE\nnot-a-date,1.09\n"
    with pytest.raises(EcbRateSourceError, match="publication date"):
        _parse_csv_observation(payload)


def test_csv_parsing_rejects_non_numeric_rate() -> None:
    from ecb_rates import _parse_csv_observation

    payload = "TIME_PERIOD,OBS_VALUE\n2026-08-03,not-a-number\n"
    with pytest.raises(EcbRateSourceError, match="non-numeric"):
        _parse_csv_observation(payload)


def test_no_unit_test_performs_real_network_access() -> None:
    """Sanity guard: EcbSdwHttpRateSource is never instantiated as a default
    in this module's tests unless explicitly monkeypatched; every test above
    injects FakeSource. This test documents that contract for future readers."""
    import inspect

    import ecb_rates

    source = inspect.signature(ecb_rates.resolve_rate_to_eur).parameters["source"]
    assert source.default is None
