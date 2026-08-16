from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ecb_rates import EcbRateNotFoundError, EcbRateObservation, EcbRateSourceError
from price_normalization import (
    PRICE_DECIMAL_PLACES,
    EcbDateRateResolution,
    EcbRateResolutionOutcome,
    PriceNormalizationOutcome,
    compute_batch_binding,
    describe_price_normalization_failure,
    format_price,
    normalize_prices_for_output,
    resolve_ecb_rates_for_rows,
)
from storage import AuctionStorage, EcbAuctionDateRateConflictError


class FakeEcbSource:
    def __init__(self, observation=None, error=None):
        self.observation = observation
        self.error = error
        self.calls: list[tuple[str, date]] = []

    def fetch(self, currency, *, on_or_before, timeout_seconds):
        self.calls.append((currency, on_or_before))
        if self.error is not None:
            raise self.error
        return self.observation


def _row(
    auction_id="1",
    auction_date="2026-08-03",
    tariff_exit=20.0,
    tariff_exit_currency="EUR",
    tariff_entry=0.0,
    tariff_entry_currency="",
    premium=5.0,
    premium_currency="EUR",
):
    return {
        "auction_id": auction_id,
        "auction_date": auction_date,
        "tariff_exit_source_mwh_h": tariff_exit,
        "tariff_exit_currency": tariff_exit_currency,
        "tariff_entry_source_mwh_h": tariff_entry,
        "tariff_entry_currency": tariff_entry_currency,
        "premium_source_mwh_h": premium,
        "premium_currency": premium_currency,
    }


# --- non-EUR conversion --------------------------------------------------

def test_non_eur_source_is_converted_by_the_historical_rate(tmp_path) -> None:
    storage = AuctionStorage(tmp_path / "t.db")
    ecb = FakeEcbSource(EcbRateObservation(date(2026, 8, 3), Decimal("2")))  # 1 USD = 0.5 EUR
    result = normalize_prices_for_output(
        [_row(tariff_exit=20.0, tariff_exit_currency="USD", premium=5.0, premium_currency="USD")],
        storage=storage, ecb_source=ecb,
    )
    assert result.succeeded
    prices = result.prices_by_row_index[0]
    assert prices.tariff_price_eur_mwh_h == Decimal("10")
    assert prices.premium_price_eur_mwh_h == Decimal("2.5")


def test_ecb_lookup_uses_the_rows_own_auction_date(tmp_path) -> None:
    """Proves the ECB request date is the calendar date parsed from the
    row's own `Start of Auction` (`row["auction_date"]`), never a
    reimplemented or bypassed fallback: `ecb_rates.py`'s own
    `endPeriod`-bounded weekend/holiday fallback is trusted as-is."""
    storage = AuctionStorage(tmp_path / "t.db")
    ecb = FakeEcbSource(EcbRateObservation(date(2026, 8, 1), Decimal("2")))
    normalize_prices_for_output(
        [_row(auction_date="2026-08-03", tariff_exit=20.0, tariff_exit_currency="USD")],
        storage=storage, ecb_source=ecb,
    )
    assert ecb.calls == [("USD", date(2026, 8, 3))]


# --- EUR identity ----------------------------------------------------------

def test_eur_source_uses_identity_conversion_with_no_ecb_access(tmp_path) -> None:
    storage = AuctionStorage(tmp_path / "t.db")

    class ExplodingEcbSource:
        def fetch(self, *args, **kwargs):
            raise AssertionError("EUR must never call the ECB source.")

    result = normalize_prices_for_output(
        [_row(tariff_exit=20.0, premium=5.0)],  # default currency is EUR
        storage=storage, ecb_source=ExplodingEcbSource(),
    )
    assert result.succeeded
    prices = result.prices_by_row_index[0]
    assert prices.tariff_price_eur_mwh_h == Decimal("20")
    assert prices.premium_price_eur_mwh_h == Decimal("5")


# --- exactly-once conversion -------------------------------------------------

def test_tariff_and_premium_are_each_converted_exactly_once(tmp_path) -> None:
    storage = AuctionStorage(tmp_path / "t.db")
    ecb = FakeEcbSource(EcbRateObservation(date(2026, 8, 3), Decimal("4")))  # rate_to_eur == 0.25
    result = normalize_prices_for_output(
        [_row(tariff_exit=100.0, tariff_exit_currency="USD", premium=40.0, premium_currency="USD")],
        storage=storage, ecb_source=ecb,
    )
    prices = result.prices_by_row_index[0]
    # 100 * 0.25 == 25 (not 100 * 0.25 * 0.25); each field uses its own
    # single multiplication by the same resolved rate.
    assert prices.tariff_price_eur_mwh_h == Decimal("25")
    assert prices.premium_price_eur_mwh_h == Decimal("10")
    assert len(ecb.calls) == 1


def test_repeated_normalization_of_a_cached_pair_does_not_reconvert_differently(tmp_path) -> None:
    """Reusing a cached (auction_date, currency) resolution must reproduce
    the identical converted price, never drift or apply the rate a second
    time."""
    storage = AuctionStorage(tmp_path / "t.db")
    ecb = FakeEcbSource(EcbRateObservation(date(2026, 8, 3), Decimal("2")))
    row = _row(tariff_exit=20.0, tariff_exit_currency="USD", premium=5.0, premium_currency="USD")

    first = normalize_prices_for_output([row], storage=storage, ecb_source=ecb)
    second = normalize_prices_for_output([row], storage=storage, ecb_source=ecb)
    assert first.prices_by_row_index[0] == second.prices_by_row_index[0]
    assert len(ecb.calls) == 1  # the second call reused the durable cache


# --- Decimal precision / deterministic serialization -------------------------

def test_conversion_uses_decimal_arithmetic_not_binary_float(tmp_path) -> None:
    """0.1 + 0.2 != 0.3 in binary float; a source price/rate pair chosen to
    expose float drift must still produce an exact Decimal result."""
    storage = AuctionStorage(tmp_path / "t.db")
    ecb = FakeEcbSource(EcbRateObservation(date(2026, 8, 3), Decimal("10")))  # rate_to_eur = 0.1
    result = normalize_prices_for_output(
        [_row(tariff_exit=3.0, tariff_exit_currency="USD", premium=0.0, premium_currency="")],
        storage=storage, ecb_source=ecb,
    )
    assert result.prices_by_row_index[0].tariff_price_eur_mwh_h == Decimal("0.3")


def test_format_price_is_fixed_point_six_decimals_never_scientific_or_locale() -> None:
    assert PRICE_DECIMAL_PLACES == 6
    assert format_price(Decimal("20")) == "20.000000"
    assert format_price(Decimal("0")) == "0.000000"
    assert format_price(Decimal("1234567.891234567")) == "1234567.891235"  # rounded, not truncated
    for value in (Decimal("0.0000001"), Decimal("123456789.123456789"), Decimal("0")):
        rendered = format_price(value)
        assert "E" not in rendered and "e" not in rendered
        assert "," not in rendered
        assert rendered.count(".") == 1


def test_format_price_uses_round_half_up_on_an_exact_tie() -> None:
    assert format_price(Decimal("1.0000005")) == "1.000001"
    assert format_price(Decimal("1.0000015")) == "1.000002"


def test_per_import_and_cumulative_writers_would_format_identical_price_strings(tmp_path) -> None:
    """`prisma_output.write_prisma_output` and
    `prisma_publication.publish_cumulative_output` both call
    `normalize_prices_for_output` then `format_price`; verify that pipeline
    alone (independent of either writer) is deterministic across two
    separate calls for the same row."""
    storage = AuctionStorage(tmp_path / "t.db")
    ecb = FakeEcbSource(EcbRateObservation(date(2026, 8, 3), Decimal("3")))
    row = _row(tariff_exit=9.0, tariff_exit_currency="USD", premium=3.0, premium_currency="USD")

    per_import = normalize_prices_for_output([row], storage=storage, ecb_source=ecb)
    cumulative = normalize_prices_for_output([row], storage=storage, ecb_source=ecb)
    assert format_price(per_import.prices_by_row_index[0].tariff_price_eur_mwh_h) == format_price(
        cumulative.prices_by_row_index[0].tariff_price_eur_mwh_h
    )


# --- shared/cached resolution reuse ------------------------------------------

def test_multiple_rows_sharing_one_auction_date_currency_pair_reuse_one_resolution(tmp_path) -> None:
    storage = AuctionStorage(tmp_path / "t.db")
    ecb = FakeEcbSource(EcbRateObservation(date(2026, 8, 3), Decimal("2")))
    rows = [
        _row("1", tariff_exit=20.0, tariff_exit_currency="USD", premium=0.0, premium_currency=""),
        _row("2", tariff_exit=40.0, tariff_exit_currency="USD", premium=0.0, premium_currency=""),
        _row("3", tariff_exit=60.0, tariff_exit_currency="USD", premium=0.0, premium_currency=""),
    ]
    result = normalize_prices_for_output(rows, storage=storage, ecb_source=ecb)
    assert result.succeeded
    assert len(ecb.calls) == 1
    assert [result.prices_by_row_index[i].tariff_price_eur_mwh_h for i in range(3)] == [
        Decimal("10"), Decimal("20"), Decimal("30"),
    ]


def test_cached_resolution_works_without_a_live_ecb_source(tmp_path) -> None:
    storage = AuctionStorage(tmp_path / "t.db")
    ecb = FakeEcbSource(EcbRateObservation(date(2026, 8, 3), Decimal("2")))
    row = _row(tariff_exit=20.0, tariff_exit_currency="USD", premium=0.0, premium_currency="")
    # Populate the cache first via resolve_ecb_rates_for_rows directly.
    resolve_ecb_rates_for_rows([row], storage=storage, ecb_source=ecb)
    assert len(ecb.calls) == 1

    class ExplodingEcbSource:
        def fetch(self, *args, **kwargs):
            raise AssertionError("A cached resolution must never call ECB again.")

    result = normalize_prices_for_output([row], storage=storage, ecb_source=ExplodingEcbSource())
    assert result.succeeded
    assert result.prices_by_row_index[0].tariff_price_eur_mwh_h == Decimal("10")


def test_normalize_accepts_precomputed_resolutions_without_a_second_resolve_pass(tmp_path) -> None:
    storage = AuctionStorage(tmp_path / "t.db")
    ecb = FakeEcbSource(EcbRateObservation(date(2026, 8, 3), Decimal("2")))
    row = _row(tariff_exit=20.0, tariff_exit_currency="USD", premium=0.0, premium_currency="")
    resolutions = resolve_ecb_rates_for_rows([row], storage=storage, ecb_source=ecb)
    assert len(ecb.calls) == 1

    class ExplodingEcbSource:
        def fetch(self, *args, **kwargs):
            raise AssertionError("resolutions was supplied; must not resolve again.")

    result = normalize_prices_for_output(
        [row], storage=storage, resolutions=resolutions, ecb_source=ExplodingEcbSource(),
    )
    assert result.succeeded
    assert result.prices_by_row_index[0].tariff_price_eur_mwh_h == Decimal("10")


# --- side-independent bundle conversion (P.37) --------------------------

def test_bundle_exit_and_entry_with_different_currencies_are_each_converted_and_summed(tmp_path) -> None:
    class MultiCurrencyEcbSource:
        def __init__(self):
            self.calls: list[tuple[str, date]] = []
            self._rates = {"GBP": Decimal("2"), "CZK": Decimal("25")}  # 1 GBP=0.5 EUR, 1 CZK=0.04 EUR

        def fetch(self, currency, *, on_or_before, timeout_seconds):
            self.calls.append((currency, on_or_before))
            return EcbRateObservation(on_or_before, self._rates[currency])

    storage = AuctionStorage(tmp_path / "t.db")
    ecb = MultiCurrencyEcbSource()
    result = normalize_prices_for_output(
        [_row(
            tariff_exit=20.0, tariff_exit_currency="GBP",
            tariff_entry=100.0, tariff_entry_currency="CZK",
            premium=0.0, premium_currency="",
        )],
        storage=storage, ecb_source=ecb,
    )
    assert result.succeeded
    # 20 GBP-side * 0.5 + 100 CZK-side * 0.04 == 10 + 4 == 14 -- never a
    # shared/blended rate, and never a pre-conversion sum of mixed
    # currencies.
    assert result.prices_by_row_index[0].tariff_price_eur_mwh_h == Decimal("14")
    assert {call[0] for call in ecb.calls} == {"GBP", "CZK"}


def test_premium_currency_is_independent_of_tariff_currencies(tmp_path) -> None:
    class MultiCurrencyEcbSource:
        def __init__(self):
            self.calls: list[tuple[str, date]] = []
            self._rates = {"GBP": Decimal("2"), "USD": Decimal("4"), "CHF": Decimal("1.25")}

        def fetch(self, currency, *, on_or_before, timeout_seconds):
            self.calls.append((currency, on_or_before))
            return EcbRateObservation(on_or_before, self._rates[currency])

    storage = AuctionStorage(tmp_path / "t.db")
    ecb = MultiCurrencyEcbSource()
    result = normalize_prices_for_output(
        [_row(
            tariff_exit=20.0, tariff_exit_currency="GBP",
            tariff_entry=40.0, tariff_entry_currency="USD",
            premium=10.0, premium_currency="CHF",
        )],
        storage=storage, ecb_source=ecb,
    )
    assert result.succeeded
    prices = result.prices_by_row_index[0]
    assert prices.tariff_price_eur_mwh_h == Decimal("10") + Decimal("10")  # 20/2 + 40/4
    assert prices.premium_price_eur_mwh_h == Decimal("8")  # 10/1.25
    assert {call[0] for call in ecb.calls} == {"GBP", "USD", "CHF"}


# --- fail-closed: every unresolved outcome blocks -----------------------

def test_ecb_rate_unavailable_blocks(tmp_path) -> None:
    storage = AuctionStorage(tmp_path / "t.db")
    ecb = FakeEcbSource(error=EcbRateNotFoundError("no rate"))
    result = normalize_prices_for_output(
        [_row(tariff_exit=20.0, tariff_exit_currency="USD", premium=0.0, premium_currency="")],
        storage=storage, ecb_source=ecb,
    )
    assert result.outcome is PriceNormalizationOutcome.BLOCKED
    assert result.failures[0].reason_code == EcbRateResolutionOutcome.ECB_RATE_UNAVAILABLE.value


def test_ecb_source_error_blocks(tmp_path) -> None:
    storage = AuctionStorage(tmp_path / "t.db")
    ecb = FakeEcbSource(error=EcbRateSourceError("unreachable"))
    result = normalize_prices_for_output(
        [_row(tariff_exit=20.0, tariff_exit_currency="USD", premium=0.0, premium_currency="")],
        storage=storage, ecb_source=ecb,
    )
    assert result.outcome is PriceNormalizationOutcome.BLOCKED
    assert result.failures[0].reason_code == EcbRateResolutionOutcome.ECB_SOURCE_ERROR.value


def test_conflict_blocks(tmp_path, monkeypatch) -> None:
    storage = AuctionStorage(tmp_path / "t.db")
    ecb = FakeEcbSource(EcbRateObservation(date(2026, 8, 3), Decimal("1.5")))

    def raise_conflict(record):
        raise EcbAuctionDateRateConflictError("simulated concurrent conflict")

    monkeypatch.setattr(storage, "save_ecb_auction_date_rate", raise_conflict)
    result = normalize_prices_for_output(
        [_row(tariff_exit=20.0, tariff_exit_currency="USD", premium=0.0, premium_currency="")],
        storage=storage, ecb_source=ecb,
    )
    assert result.outcome is PriceNormalizationOutcome.BLOCKED
    assert result.failures[0].reason_code == EcbRateResolutionOutcome.CONFLICT.value


def test_missing_resolution_blocks(tmp_path) -> None:
    """A row whose (auction_date, currency) pair is absent from a
    caller-supplied `resolutions` mapping (never produced by
    `resolve_ecb_rates_for_rows` itself, but a defensive case for a
    caller-supplied mapping) is blocked, never silently treated as EUR."""
    storage = AuctionStorage(tmp_path / "t.db")
    result = normalize_prices_for_output(
        [_row(tariff_exit=20.0, tariff_exit_currency="USD")], storage=storage, resolutions={},
    )
    assert result.outcome is PriceNormalizationOutcome.BLOCKED
    assert result.failures[0].reason_code == "missing_resolution"


def test_invalid_rate_value_blocks_as_invalid_conversion_data(tmp_path) -> None:
    storage = AuctionStorage(tmp_path / "t.db")
    resolutions = {
        ("2026-08-03", "USD"): EcbDateRateResolution(
            EcbRateResolutionOutcome.RESOLVED, rate_to_eur=Decimal("0")
        ),
    }
    result = normalize_prices_for_output(
        [_row(tariff_exit=20.0, tariff_exit_currency="USD")], storage=storage, resolutions=resolutions,
    )
    assert result.outcome is PriceNormalizationOutcome.BLOCKED
    assert result.failures[0].reason_code == "invalid_conversion_data"


# --- one unresolved row blocks the entire mixed batch -------------------

def test_one_unresolved_row_blocks_publication_of_the_entire_mixed_batch(tmp_path) -> None:
    storage = AuctionStorage(tmp_path / "t.db")
    ecb = FakeEcbSource(error=EcbRateNotFoundError("no rate"))
    rows = [
        _row("1", tariff_exit=20.0, tariff_exit_currency="EUR"),  # resolves fine (identity)
        _row("2", tariff_exit=20.0, tariff_exit_currency="GBP"),  # unresolvable
    ]
    result = normalize_prices_for_output(rows, storage=storage, ecb_source=ecb)
    assert result.outcome is PriceNormalizationOutcome.BLOCKED
    assert result.prices_by_row_index == {}
    reasons = {failure.reason_code for failure in result.failures}
    assert EcbRateResolutionOutcome.ECB_RATE_UNAVAILABLE.value in reasons


def test_failures_are_deduplicated_per_auction_id(tmp_path) -> None:
    storage = AuctionStorage(tmp_path / "t.db")
    ecb = FakeEcbSource(error=EcbRateNotFoundError("no rate"))
    rows = [
        _row("1", tariff_exit=20.0, tariff_exit_currency="GBP"),
        _row("1", tariff_exit=20.0, tariff_exit_currency="GBP"),
        _row("1", tariff_exit=20.0, tariff_exit_currency="GBP"),
    ]
    result = normalize_prices_for_output(rows, storage=storage, ecb_source=ecb)
    assert len(result.failures) == 1


# --- retry after resolution becomes available --------------------------------

def test_retry_succeeds_after_ecb_rate_becomes_available(tmp_path) -> None:
    storage = AuctionStorage(tmp_path / "t.db")
    failing_ecb = FakeEcbSource(error=EcbRateNotFoundError("no rate yet"))

    first = normalize_prices_for_output(
        [_row(tariff_exit=20.0, tariff_exit_currency="USD")], storage=storage, ecb_source=failing_ecb,
    )
    assert first.outcome is PriceNormalizationOutcome.BLOCKED
    assert storage.get_ecb_auction_date_rate("2026-08-03", "USD") is None  # no partial commit

    working_ecb = FakeEcbSource(EcbRateObservation(date(2026, 8, 3), Decimal("2")))
    second = normalize_prices_for_output(
        [_row(tariff_exit=20.0, tariff_exit_currency="USD")], storage=storage, ecb_source=working_ecb,
    )
    assert second.succeeded
    assert second.prices_by_row_index[0].tariff_price_eur_mwh_h == Decimal("10")


# --- description helper -----------------------------------------------------

def test_describe_price_normalization_failure_is_stable_and_technical_detail_free(tmp_path) -> None:
    storage = AuctionStorage(tmp_path / "t.db")
    ecb = FakeEcbSource(error=EcbRateNotFoundError("no rate"))
    result = normalize_prices_for_output(
        [
            _row("1", tariff_exit=20.0, tariff_exit_currency="GBP"),
            _row("2", tariff_exit=20.0, tariff_exit_currency="GBP"),
        ],
        storage=storage, ecb_source=ecb,
    )
    message = describe_price_normalization_failure(result)
    assert isinstance(message, str) and message
    assert "2 auction(s)" in message
    for failure in result.failures:
        assert failure.message not in message  # UI text stays generic, not raw diagnostics


def test_describe_price_normalization_failure_is_empty_on_success(tmp_path) -> None:
    storage = AuctionStorage(tmp_path / "t.db")
    result = normalize_prices_for_output([_row(tariff_exit=20.0)], storage=storage)
    assert describe_price_normalization_failure(result) == ""


# --- P.36.21/P.37 Decimal input validation ------------------------------------
# `normalize_prices_for_output` must reject a non-finite, negative, or
# unserializable source/converted price as `invalid_conversion_data` — never
# raise an uncontrolled `decimal.DecimalException` and never publish a
# partial batch. All of these default to EUR (identity `rate_to_eur == 1`,
# no ECB access) so the failure is provably caused by the source/converted
# price itself, not the rate.

def test_nan_source_tariff_is_blocked(tmp_path) -> None:
    storage = AuctionStorage(tmp_path / "t.db")
    result = normalize_prices_for_output(
        [_row(tariff_exit=float("nan"), premium=5.0)], storage=storage,
    )
    assert result.outcome is PriceNormalizationOutcome.BLOCKED
    assert result.prices_by_row_index == {}
    assert result.failures[0].reason_code == "invalid_conversion_data"


def test_infinite_source_premium_is_blocked(tmp_path) -> None:
    storage = AuctionStorage(tmp_path / "t.db")
    result = normalize_prices_for_output(
        [_row(tariff_exit=20.0, premium=float("inf"))], storage=storage,
    )
    assert result.outcome is PriceNormalizationOutcome.BLOCKED
    assert result.prices_by_row_index == {}
    assert result.failures[0].reason_code == "invalid_conversion_data"


def test_negative_source_tariff_is_blocked(tmp_path) -> None:
    storage = AuctionStorage(tmp_path / "t.db")
    result = normalize_prices_for_output(
        [_row(tariff_exit=-20.0, premium=5.0)], storage=storage,
    )
    assert result.outcome is PriceNormalizationOutcome.BLOCKED
    assert result.failures[0].reason_code == "invalid_conversion_data"


def test_negative_source_premium_is_blocked(tmp_path) -> None:
    storage = AuctionStorage(tmp_path / "t.db")
    result = normalize_prices_for_output(
        [_row(tariff_exit=20.0, premium=-0.01)], storage=storage,
    )
    assert result.outcome is PriceNormalizationOutcome.BLOCKED
    assert result.failures[0].reason_code == "invalid_conversion_data"


def test_zero_source_prices_remain_valid(tmp_path) -> None:
    storage = AuctionStorage(tmp_path / "t.db")
    result = normalize_prices_for_output(
        [_row(tariff_exit=0.0, premium=0.0)], storage=storage,
    )
    assert result.succeeded
    prices = result.prices_by_row_index[0]
    assert prices.tariff_price_eur_mwh_h == Decimal("0")
    assert prices.premium_price_eur_mwh_h == Decimal("0")


def test_excessively_large_source_price_is_blocked_rather_than_raising(tmp_path) -> None:
    """A source price whose magnitude cannot be quantized to
    `PRICE_DECIMAL_PLACES` within the `decimal` context's precision must be
    blocked, never let `quantize()`'s `decimal.InvalidOperation` escape this
    module uncontrolled."""
    storage = AuctionStorage(tmp_path / "t.db")
    huge = float(Decimal("1E50"))
    result = normalize_prices_for_output(
        [_row(tariff_exit=huge, premium=5.0)], storage=storage,
    )
    assert result.outcome is PriceNormalizationOutcome.BLOCKED
    assert result.prices_by_row_index == {}
    assert result.failures[0].reason_code == "invalid_conversion_data"


def test_invalid_multiplied_eur_result_is_blocked_even_with_individually_valid_factors(
    tmp_path,
) -> None:
    """A finite, positive, non-huge source price multiplied by a finite,
    positive (but huge) `rate_to_eur` can still produce a converted EUR value
    too large to serialize — the check on the multiplied result itself, not
    only on the pre-multiplication source, must catch this."""
    storage = AuctionStorage(tmp_path / "t.db")
    resolutions = {
        ("2026-08-03", "USD"): EcbDateRateResolution(
            EcbRateResolutionOutcome.RESOLVED, rate_to_eur=Decimal("1E50")
        ),
    }
    result = normalize_prices_for_output(
        [_row(tariff_exit=1000.0, tariff_exit_currency="USD", premium=5.0, premium_currency="USD")],
        storage=storage, resolutions=resolutions,
    )
    assert result.outcome is PriceNormalizationOutcome.BLOCKED
    assert result.prices_by_row_index == {}
    assert result.failures[0].reason_code == "invalid_conversion_data"


def test_invalid_summed_eur_result_is_blocked_even_with_individually_valid_sides(tmp_path) -> None:
    """Two individually-valid, independently-converted EUR side values can
    still sum to something that cannot be safely quantized/serialized;
    `normalize_prices_for_output` must catch this on the summed tariff
    value, not only on each side individually -- a new edge case under
    P.37's side-independent bundle conversion, which the old single-rate
    mechanism never needed to check."""
    storage = AuctionStorage(tmp_path / "t.db")
    huge_but_individually_valid = float(Decimal("9" * 22))
    result = normalize_prices_for_output(
        [_row(
            tariff_exit=huge_but_individually_valid, tariff_exit_currency="EUR",
            tariff_entry=huge_but_individually_valid, tariff_entry_currency="EUR",
        )],
        storage=storage,
    )
    assert result.outcome is PriceNormalizationOutcome.BLOCKED
    assert result.prices_by_row_index == {}
    assert result.failures[0].reason_code == "invalid_conversion_data"


def test_invalid_decimal_in_a_mixed_batch_blocks_the_whole_batch_with_no_partial_prices(
    tmp_path,
) -> None:
    storage = AuctionStorage(tmp_path / "t.db")
    rows = [
        _row("1", tariff_exit=20.0, premium=5.0),  # otherwise valid
        _row("2", tariff_exit=float("nan"), premium=5.0),  # invalid
    ]
    result = normalize_prices_for_output(rows, storage=storage)
    assert result.outcome is PriceNormalizationOutcome.BLOCKED
    assert result.prices_by_row_index == {}


# --- P.36.21 review correction: immutable batch binding -----------------------

def test_successful_result_batch_binding_matches_compute_batch_binding(tmp_path) -> None:
    storage = AuctionStorage(tmp_path / "t.db")
    rows = [_row(tariff_exit=20.0, premium=5.0)]
    result = normalize_prices_for_output(rows, storage=storage)
    assert result.succeeded
    assert result.batch_binding == compute_batch_binding(rows)
    assert len(result.batch_binding) == 1


def test_blocked_result_has_no_batch_binding(tmp_path) -> None:
    storage = AuctionStorage(tmp_path / "t.db")
    ecb = FakeEcbSource(error=EcbRateNotFoundError("no rate"))
    result = normalize_prices_for_output(
        [_row(tariff_exit=20.0, tariff_exit_currency="GBP")], storage=storage, ecb_source=ecb,
    )
    assert result.outcome is PriceNormalizationOutcome.BLOCKED
    assert result.batch_binding == ()


def test_compute_batch_binding_differs_when_row_order_changes() -> None:
    row_a = _row("1", tariff_exit=20.0)
    row_b = _row("2", tariff_exit=40.0)
    assert compute_batch_binding([row_a, row_b]) != compute_batch_binding([row_b, row_a])


def test_compute_batch_binding_differs_when_auction_id_changes() -> None:
    row = _row("1", tariff_exit=20.0)
    other = _row("2", tariff_exit=20.0)
    assert compute_batch_binding([row]) != compute_batch_binding([other])


def test_compute_batch_binding_differs_when_auction_date_changes() -> None:
    row = _row(auction_date="2026-08-03", tariff_exit=20.0)
    other = _row(auction_date="2026-08-04", tariff_exit=20.0)
    assert compute_batch_binding([row]) != compute_batch_binding([other])


def test_compute_batch_binding_differs_when_currency_changes() -> None:
    row = _row(tariff_exit=20.0, tariff_exit_currency="EUR")
    other = _row(tariff_exit=20.0, tariff_exit_currency="USD")
    assert compute_batch_binding([row]) != compute_batch_binding([other])


def test_compute_batch_binding_differs_when_source_tariff_or_premium_changes() -> None:
    base = compute_batch_binding([_row(tariff_exit=20.0, premium=5.0)])
    different_tariff = compute_batch_binding([_row(tariff_exit=21.0, premium=5.0)])
    different_premium = compute_batch_binding([_row(tariff_exit=20.0, premium=6.0)])
    assert base != different_tariff
    assert base != different_premium
