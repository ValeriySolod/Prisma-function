from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from ecb_rates import EcbRateNotFoundError, EcbRateObservation
from prisma_auction_lookup import AuctionEndRecord, PrismaAuctionLookupError
from prisma_references import (
    PrismaReference,
    PrismaReferenceCatalog,
    ReferenceAlias,
    ReferenceClassification,
    ReferenceSide,
)
from price_normalization import (
    PRICE_DECIMAL_PLACES,
    PriceNormalizationOutcome,
    compute_batch_binding,
    describe_price_normalization_failure,
    format_price,
    normalize_prices_for_output,
)
from rate_resolution import RateResolutionOutcome, resolve_rates_for_rows
from storage import AuctionStorage, RateResolutionConflictError


class FakeAuctionLookup:
    def __init__(self, records=None, errors=None):
        self.records = records or {}
        self.errors = errors or {}
        self.calls: list[str] = []

    def lookup(self, page, auction_id):
        self.calls.append(auction_id)
        if auction_id in self.errors:
            raise self.errors[auction_id]
        if auction_id not in self.records:
            raise PrismaAuctionLookupError(f"no fake record for {auction_id}")
        return self.records[auction_id]


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


def _catalog(currency: str | None, canonical_name: str = "TEST") -> PrismaReferenceCatalog:
    return PrismaReferenceCatalog((
        PrismaReference(
            canonical_name, ReferenceClassification.MARKET,
            (ReferenceAlias("alias", ReferenceSide.EXIT),), exit_currency=currency,
        ),
    ))


def _row(auction_id="1", state="Finished", exit_market="TEST", entry_market="",
         tariff=20.0, premium=5.0):
    return {
        "auction_id": auction_id, "state": state,
        "exit_market": exit_market, "entry_market": entry_market,
        "tariff_source_mwh_h": tariff, "premium_source_mwh_h": premium,
    }


def _end_record(auction_id="1", end_at=None, state="Finished"):
    return AuctionEndRecord(
        auction_id, end_at or datetime(2026, 8, 3, 14, 30, tzinfo=timezone.utc), state
    )


# --- non-EUR conversion --------------------------------------------------

def test_non_eur_source_is_converted_by_the_historical_rate(tmp_path) -> None:
    storage = AuctionStorage(tmp_path / "t.db")
    lookup = FakeAuctionLookup(records={"1": _end_record("1")})
    ecb = FakeEcbSource(EcbRateObservation(date(2026, 8, 3), Decimal("2")))  # 1 USD = 0.5 EUR
    result = normalize_prices_for_output(
        [_row("1", tariff=20.0, premium=5.0)],
        storage=storage, reference_catalog=_catalog("USD"),
        auction_lookup=lookup, ecb_source=ecb,
    )
    assert result.succeeded
    prices = result.prices_by_row_index[0]
    assert prices.tariff_price_eur_mwh_h == Decimal("10")
    assert prices.premium_price_eur_mwh_h == Decimal("2.5")


# --- EUR identity ----------------------------------------------------------

def test_eur_source_uses_identity_conversion_with_no_ecb_access(tmp_path) -> None:
    storage = AuctionStorage(tmp_path / "t.db")
    lookup = FakeAuctionLookup(records={"1": _end_record("1")})

    class ExplodingEcbSource:
        def fetch(self, *args, **kwargs):
            raise AssertionError("EUR must never call the ECB source.")

    result = normalize_prices_for_output(
        [_row("1", tariff=20.0, premium=5.0)],
        storage=storage, reference_catalog=_catalog("EUR"),
        auction_lookup=lookup, ecb_source=ExplodingEcbSource(),
    )
    assert result.succeeded
    prices = result.prices_by_row_index[0]
    assert prices.tariff_price_eur_mwh_h == Decimal("20")
    assert prices.premium_price_eur_mwh_h == Decimal("5")


# --- exactly-once conversion -------------------------------------------------

def test_tariff_and_premium_are_each_converted_exactly_once(tmp_path) -> None:
    storage = AuctionStorage(tmp_path / "t.db")
    lookup = FakeAuctionLookup(records={"1": _end_record("1")})
    ecb = FakeEcbSource(EcbRateObservation(date(2026, 8, 3), Decimal("4")))  # rate_to_eur == 0.25
    result = normalize_prices_for_output(
        [_row("1", tariff=100.0, premium=40.0)],
        storage=storage, reference_catalog=_catalog("USD"),
        auction_lookup=lookup, ecb_source=ecb,
    )
    prices = result.prices_by_row_index[0]
    # 100 * 0.25 == 25 (not 100 * 0.25 * 0.25); each field uses its own
    # single multiplication by the same resolved rate.
    assert prices.tariff_price_eur_mwh_h == Decimal("25")
    assert prices.premium_price_eur_mwh_h == Decimal("10")
    assert len(ecb.calls) == 1


def test_repeated_normalization_of_a_cached_auction_does_not_reconvert_differently(tmp_path) -> None:
    """Reusing a cached resolution must reproduce the identical converted
    price, never drift or apply the rate a second time."""
    storage = AuctionStorage(tmp_path / "t.db")
    lookup = FakeAuctionLookup(records={"1": _end_record("1")})
    ecb = FakeEcbSource(EcbRateObservation(date(2026, 8, 3), Decimal("2")))
    row = _row("1", tariff=20.0, premium=5.0)

    first = normalize_prices_for_output(
        [row], storage=storage, reference_catalog=_catalog("USD"),
        auction_lookup=lookup, ecb_source=ecb,
    )
    second = normalize_prices_for_output(
        [row], storage=storage, reference_catalog=_catalog("USD"),
        auction_lookup=lookup, ecb_source=ecb,
    )
    assert first.prices_by_row_index[0] == second.prices_by_row_index[0]
    assert len(ecb.calls) == 1  # the second call reused the durable cache


# --- Decimal precision / deterministic serialization -------------------------

def test_conversion_uses_decimal_arithmetic_not_binary_float(tmp_path) -> None:
    """0.1 + 0.2 != 0.3 in binary float; a source price/rate pair chosen to
    expose float drift must still produce an exact Decimal result."""
    storage = AuctionStorage(tmp_path / "t.db")
    lookup = FakeAuctionLookup(records={"1": _end_record("1")})
    ecb = FakeEcbSource(EcbRateObservation(date(2026, 8, 3), Decimal("10")))  # rate_to_eur = 0.1
    result = normalize_prices_for_output(
        [_row("1", tariff=3.0, premium=0.0)],
        storage=storage, reference_catalog=_catalog("USD"),
        auction_lookup=lookup, ecb_source=ecb,
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
    separate calls for the same Auction ID."""
    storage = AuctionStorage(tmp_path / "t.db")
    lookup = FakeAuctionLookup(records={"1": _end_record("1")})
    ecb = FakeEcbSource(EcbRateObservation(date(2026, 8, 3), Decimal("3")))
    row = _row("1", tariff=9.0, premium=3.0)

    per_import = normalize_prices_for_output(
        [row], storage=storage, reference_catalog=_catalog("USD"),
        auction_lookup=lookup, ecb_source=ecb,
    )
    cumulative = normalize_prices_for_output(
        [row], storage=storage, reference_catalog=_catalog("USD"),
        auction_lookup=lookup, ecb_source=ecb,
    )
    assert format_price(per_import.prices_by_row_index[0].tariff_price_eur_mwh_h) == format_price(
        cumulative.prices_by_row_index[0].tariff_price_eur_mwh_h
    )


# --- shared/cached resolution reuse ------------------------------------------

def test_multiple_rows_with_one_auction_id_reuse_one_resolution(tmp_path) -> None:
    storage = AuctionStorage(tmp_path / "t.db")
    lookup = FakeAuctionLookup(records={"1": _end_record("1")})
    ecb = FakeEcbSource(EcbRateObservation(date(2026, 8, 3), Decimal("2")))
    rows = [_row("1", tariff=20.0), _row("1", tariff=40.0), _row("1", tariff=60.0)]
    result = normalize_prices_for_output(
        rows, storage=storage, reference_catalog=_catalog("USD"),
        auction_lookup=lookup, ecb_source=ecb,
    )
    assert result.succeeded
    assert lookup.calls == ["1"]
    assert len(ecb.calls) == 1
    assert [result.prices_by_row_index[i].tariff_price_eur_mwh_h for i in range(3)] == [
        Decimal("10"), Decimal("20"), Decimal("30"),
    ]


def test_cached_resolution_works_without_a_live_prisma_lookup(tmp_path) -> None:
    storage = AuctionStorage(tmp_path / "t.db")
    lookup = FakeAuctionLookup(records={"1": _end_record("1")})
    ecb = FakeEcbSource(EcbRateObservation(date(2026, 8, 3), Decimal("2")))
    row = _row("1", tariff=20.0)
    # Populate the cache first via rate_resolution directly.
    resolve_rates_for_rows(
        [row], storage=storage, reference_catalog=_catalog("USD"),
        auction_lookup=lookup, ecb_source=ecb,
    )
    assert lookup.calls == ["1"]

    class ExplodingLookup:
        def lookup(self, page, auction_id):
            raise AssertionError("A cached resolution must never call PRISMA again.")

    result = normalize_prices_for_output(
        [row], storage=storage, reference_catalog=_catalog("USD"),
        auction_lookup=ExplodingLookup(),
    )
    assert result.succeeded
    assert result.prices_by_row_index[0].tariff_price_eur_mwh_h == Decimal("10")


def test_mapping_and_output_use_the_same_resolution_for_a_row(tmp_path) -> None:
    """Mapping (`rate_resolution.resolve_rates_for_rows`, used directly by
    `app.py`) and output (`price_normalization.normalize_prices_for_output`,
    which also calls `resolve_rates_for_rows`) must observe the identical
    resolved rate for the same Auction ID and storage, since both read
    through the same durable cache — never a second, independent
    conversion/rate-selection implementation."""
    storage = AuctionStorage(tmp_path / "t.db")
    lookup = FakeAuctionLookup(records={"1": _end_record("1")})
    ecb = FakeEcbSource(EcbRateObservation(date(2026, 8, 3), Decimal("2")))
    row = _row("1")

    mapping_resolution = resolve_rates_for_rows(
        [row], storage=storage, reference_catalog=_catalog("USD"),
        auction_lookup=lookup, ecb_source=ecb,
    )["1"]
    output_result = normalize_prices_for_output(
        [row], storage=storage, reference_catalog=_catalog("USD"), auction_lookup=lookup,
    )
    assert output_result.succeeded
    assert mapping_resolution.outcome is RateResolutionOutcome.RESOLVED
    assert mapping_resolution.rate_to_eur == Decimal("0.5")
    assert output_result.prices_by_row_index[0].tariff_price_eur_mwh_h == Decimal(
        str(row["tariff_source_mwh_h"])
    ) * mapping_resolution.rate_to_eur


def test_normalize_accepts_precomputed_resolutions_without_a_second_resolve_pass(tmp_path) -> None:
    storage = AuctionStorage(tmp_path / "t.db")
    lookup = FakeAuctionLookup(records={"1": _end_record("1")})
    ecb = FakeEcbSource(EcbRateObservation(date(2026, 8, 3), Decimal("2")))
    row = _row("1", tariff=20.0)
    resolutions = resolve_rates_for_rows(
        [row], storage=storage, reference_catalog=_catalog("USD"),
        auction_lookup=lookup, ecb_source=ecb,
    )
    assert len(lookup.calls) == 1

    class ExplodingLookup:
        def lookup(self, page, auction_id):
            raise AssertionError("resolutions was supplied; must not resolve again.")

    result = normalize_prices_for_output(
        [row], storage=storage, resolutions=resolutions, auction_lookup=ExplodingLookup(),
    )
    assert result.succeeded
    assert result.prices_by_row_index[0].tariff_price_eur_mwh_h == Decimal("10")


# --- fail-closed: every unresolved outcome blocks -----------------------

def test_not_finished_blocks_and_reports_reason_code(tmp_path) -> None:
    storage = AuctionStorage(tmp_path / "t.db")
    lookup = FakeAuctionLookup()
    result = normalize_prices_for_output(
        [_row("1", state="Cancelled")], storage=storage,
        reference_catalog=_catalog("USD"), auction_lookup=lookup,
    )
    assert result.outcome is PriceNormalizationOutcome.BLOCKED
    assert result.prices_by_row_index == {}
    assert result.failures[0].reason_code == RateResolutionOutcome.NOT_FINISHED.value
    assert result.failures[0].auction_id == "1"


def test_auction_end_unavailable_blocks(tmp_path) -> None:
    storage = AuctionStorage(tmp_path / "t.db")
    lookup = FakeAuctionLookup(errors={"1": PrismaAuctionLookupError("boom")})
    result = normalize_prices_for_output(
        [_row("1")], storage=storage, reference_catalog=_catalog("USD"), auction_lookup=lookup,
    )
    assert result.outcome is PriceNormalizationOutcome.BLOCKED
    assert result.failures[0].reason_code == RateResolutionOutcome.AUCTION_END_UNAVAILABLE.value


def test_currency_unknown_blocks_and_never_defaults_to_eur(tmp_path) -> None:
    storage = AuctionStorage(tmp_path / "t.db")
    lookup = FakeAuctionLookup(records={"1": _end_record("1")})
    result = normalize_prices_for_output(
        [_row("1")], storage=storage, reference_catalog=_catalog(None), auction_lookup=lookup,
    )
    assert result.outcome is PriceNormalizationOutcome.BLOCKED
    assert result.prices_by_row_index == {}
    assert result.failures[0].reason_code == RateResolutionOutcome.CURRENCY_UNKNOWN.value


def test_ecb_rate_unavailable_blocks(tmp_path) -> None:
    storage = AuctionStorage(tmp_path / "t.db")
    lookup = FakeAuctionLookup(records={"1": _end_record("1")})
    ecb = FakeEcbSource(error=EcbRateNotFoundError("no rate"))
    result = normalize_prices_for_output(
        [_row("1")], storage=storage, reference_catalog=_catalog("USD"),
        auction_lookup=lookup, ecb_source=ecb,
    )
    assert result.outcome is PriceNormalizationOutcome.BLOCKED
    assert result.failures[0].reason_code == RateResolutionOutcome.ECB_RATE_UNAVAILABLE.value


def test_conflict_blocks(tmp_path, monkeypatch) -> None:
    storage = AuctionStorage(tmp_path / "t.db")
    lookup = FakeAuctionLookup(records={"1": _end_record("1")})
    ecb = FakeEcbSource(EcbRateObservation(date(2026, 8, 3), Decimal("1.5")))

    def raise_conflict(record):
        raise RateResolutionConflictError("simulated concurrent conflict")

    monkeypatch.setattr(storage, "save_rate_resolution", raise_conflict)
    result = normalize_prices_for_output(
        [_row("1")], storage=storage, reference_catalog=_catalog("USD"),
        auction_lookup=lookup, ecb_source=ecb,
    )
    assert result.outcome is PriceNormalizationOutcome.BLOCKED
    assert result.failures[0].reason_code == RateResolutionOutcome.CONFLICT.value


def test_missing_resolution_blocks(tmp_path) -> None:
    """A row whose Auction ID is absent from a caller-supplied `resolutions`
    mapping (never produced by `resolve_rates_for_rows` itself, but a
    defensive case for a caller-supplied mapping) is blocked, never silently
    treated as EUR."""
    storage = AuctionStorage(tmp_path / "t.db")
    result = normalize_prices_for_output(
        [_row("1")], storage=storage, resolutions={},
    )
    assert result.outcome is PriceNormalizationOutcome.BLOCKED
    assert result.failures[0].reason_code == "missing_resolution"


def test_invalid_rate_value_blocks_as_invalid_conversion_data(tmp_path) -> None:
    from rate_resolution import RateResolutionResult

    storage = AuctionStorage(tmp_path / "t.db")
    resolutions = {
        "1": RateResolutionResult(RateResolutionOutcome.RESOLVED, currency="USD", rate_to_eur=Decimal("0")),
    }
    result = normalize_prices_for_output([_row("1")], storage=storage, resolutions=resolutions)
    assert result.outcome is PriceNormalizationOutcome.BLOCKED
    assert result.failures[0].reason_code == "invalid_conversion_data"


# --- one unresolved row blocks the entire mixed batch -------------------

def test_one_unresolved_row_blocks_publication_of_the_entire_mixed_batch(tmp_path) -> None:
    storage = AuctionStorage(tmp_path / "t.db")
    lookup = FakeAuctionLookup(records={"1": _end_record("1"), "2": _end_record("2")})
    ecb = FakeEcbSource(EcbRateObservation(date(2026, 8, 3), Decimal("2")))
    rows = [
        _row("1", exit_market="TEST"),  # resolves fine (USD via catalog "TEST")
        _row("2", exit_market="UNKNOWN"),  # unresolvable currency
    ]
    result = normalize_prices_for_output(
        rows, storage=storage, reference_catalog=_catalog("USD"),
        auction_lookup=lookup, ecb_source=ecb,
    )
    assert result.outcome is PriceNormalizationOutcome.BLOCKED
    assert result.prices_by_row_index == {}
    reasons = {failure.reason_code for failure in result.failures}
    assert RateResolutionOutcome.CURRENCY_UNKNOWN.value in reasons


def test_failures_are_deduplicated_per_auction_id(tmp_path) -> None:
    storage = AuctionStorage(tmp_path / "t.db")
    lookup = FakeAuctionLookup()
    rows = [_row("1", state="Open"), _row("1", state="Open"), _row("1", state="Open")]
    result = normalize_prices_for_output(
        rows, storage=storage, reference_catalog=_catalog("USD"), auction_lookup=lookup,
    )
    assert len(result.failures) == 1


# --- EXIT/ENTRY currency evidence never leaks --------------------------------

def test_exit_only_currency_evidence_does_not_leak_to_entry(tmp_path) -> None:
    storage = AuctionStorage(tmp_path / "t.db")
    catalog = PrismaReferenceCatalog((
        PrismaReference(
            "BOTH-SIDES", ReferenceClassification.STORAGE,
            (
                ReferenceAlias("both", ReferenceSide.EXIT),
                ReferenceAlias("both", ReferenceSide.ENTRY),
            ),
            exit_currency="EUR",
        ),
    ))
    lookup = FakeAuctionLookup(records={"1": _end_record("1")})
    result = normalize_prices_for_output(
        [_row("1", exit_market="", entry_market="BOTH-SIDES")],
        storage=storage, reference_catalog=catalog, auction_lookup=lookup,
    )
    assert result.outcome is PriceNormalizationOutcome.BLOCKED
    assert result.failures[0].reason_code == RateResolutionOutcome.CURRENCY_UNKNOWN.value


# --- retry after resolution becomes available --------------------------------

def test_retry_succeeds_after_currency_evidence_becomes_available(tmp_path) -> None:
    storage = AuctionStorage(tmp_path / "t.db")
    lookup = FakeAuctionLookup(records={"1": _end_record("1")})

    first = normalize_prices_for_output(
        [_row("1")], storage=storage, reference_catalog=_catalog(None), auction_lookup=lookup,
    )
    assert first.outcome is PriceNormalizationOutcome.BLOCKED

    ecb = FakeEcbSource(EcbRateObservation(date(2026, 8, 3), Decimal("2")))
    second = normalize_prices_for_output(
        [_row("1", tariff=20.0)], storage=storage, reference_catalog=_catalog("USD"),
        auction_lookup=lookup, ecb_source=ecb,
    )
    assert second.succeeded
    assert second.prices_by_row_index[0].tariff_price_eur_mwh_h == Decimal("10")


def test_retry_succeeds_after_ecb_rate_becomes_available(tmp_path) -> None:
    storage = AuctionStorage(tmp_path / "t.db")
    lookup = FakeAuctionLookup(records={"1": _end_record("1")})
    failing_ecb = FakeEcbSource(error=EcbRateNotFoundError("no rate yet"))

    first = normalize_prices_for_output(
        [_row("1")], storage=storage, reference_catalog=_catalog("USD"),
        auction_lookup=lookup, ecb_source=failing_ecb,
    )
    assert first.outcome is PriceNormalizationOutcome.BLOCKED
    assert storage.get_rate_resolution("1") is None  # no partial commit

    working_ecb = FakeEcbSource(EcbRateObservation(date(2026, 8, 3), Decimal("2")))
    second = normalize_prices_for_output(
        [_row("1", tariff=20.0)], storage=storage, reference_catalog=_catalog("USD"),
        auction_lookup=lookup, ecb_source=working_ecb,
    )
    assert second.succeeded
    assert second.prices_by_row_index[0].tariff_price_eur_mwh_h == Decimal("10")


# --- description helper -----------------------------------------------------

def test_describe_price_normalization_failure_is_stable_and_technical_detail_free(tmp_path) -> None:
    storage = AuctionStorage(tmp_path / "t.db")
    lookup = FakeAuctionLookup()
    result = normalize_prices_for_output(
        [_row("1", state="Open"), _row("2", state="Open")],
        storage=storage, reference_catalog=_catalog("USD"), auction_lookup=lookup,
    )
    message = describe_price_normalization_failure(result)
    assert isinstance(message, str) and message
    assert "2 auction(s)" in message
    for failure in result.failures:
        assert failure.message not in message  # UI text stays generic, not raw diagnostics


def test_describe_price_normalization_failure_is_empty_on_success(tmp_path) -> None:
    storage = AuctionStorage(tmp_path / "t.db")
    lookup = FakeAuctionLookup(records={"1": _end_record("1")})
    result = normalize_prices_for_output(
        [_row("1")], storage=storage, reference_catalog=_catalog("EUR"), auction_lookup=lookup,
    )
    assert describe_price_normalization_failure(result) == ""


# --- P.36.21 review correction: Decimal input validation ---------------------
# `normalize_prices_for_output` must reject a non-finite, negative, or
# unserializable source/converted price as `invalid_conversion_data` — never
# raise an uncontrolled `decimal.DecimalException` and never publish a
# partial batch. All of these use `reference_catalog=_catalog("EUR")` (a
# finite, positive, identity `rate_to_eur == 1`) so the failure is provably
# caused by the source/converted price itself, not the rate.

def test_nan_source_tariff_is_blocked(tmp_path) -> None:
    storage = AuctionStorage(tmp_path / "t.db")
    lookup = FakeAuctionLookup(records={"1": _end_record("1")})
    result = normalize_prices_for_output(
        [_row("1", tariff=float("nan"), premium=5.0)],
        storage=storage, reference_catalog=_catalog("EUR"), auction_lookup=lookup,
    )
    assert result.outcome is PriceNormalizationOutcome.BLOCKED
    assert result.prices_by_row_index == {}
    assert result.failures[0].reason_code == "invalid_conversion_data"


def test_infinite_source_premium_is_blocked(tmp_path) -> None:
    storage = AuctionStorage(tmp_path / "t.db")
    lookup = FakeAuctionLookup(records={"1": _end_record("1")})
    result = normalize_prices_for_output(
        [_row("1", tariff=20.0, premium=float("inf"))],
        storage=storage, reference_catalog=_catalog("EUR"), auction_lookup=lookup,
    )
    assert result.outcome is PriceNormalizationOutcome.BLOCKED
    assert result.prices_by_row_index == {}
    assert result.failures[0].reason_code == "invalid_conversion_data"


def test_negative_source_tariff_is_blocked(tmp_path) -> None:
    storage = AuctionStorage(tmp_path / "t.db")
    lookup = FakeAuctionLookup(records={"1": _end_record("1")})
    result = normalize_prices_for_output(
        [_row("1", tariff=-20.0, premium=5.0)],
        storage=storage, reference_catalog=_catalog("EUR"), auction_lookup=lookup,
    )
    assert result.outcome is PriceNormalizationOutcome.BLOCKED
    assert result.failures[0].reason_code == "invalid_conversion_data"


def test_negative_source_premium_is_blocked(tmp_path) -> None:
    storage = AuctionStorage(tmp_path / "t.db")
    lookup = FakeAuctionLookup(records={"1": _end_record("1")})
    result = normalize_prices_for_output(
        [_row("1", tariff=20.0, premium=-0.01)],
        storage=storage, reference_catalog=_catalog("EUR"), auction_lookup=lookup,
    )
    assert result.outcome is PriceNormalizationOutcome.BLOCKED
    assert result.failures[0].reason_code == "invalid_conversion_data"


def test_zero_source_prices_remain_valid(tmp_path) -> None:
    storage = AuctionStorage(tmp_path / "t.db")
    lookup = FakeAuctionLookup(records={"1": _end_record("1")})
    result = normalize_prices_for_output(
        [_row("1", tariff=0.0, premium=0.0)],
        storage=storage, reference_catalog=_catalog("EUR"), auction_lookup=lookup,
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
    lookup = FakeAuctionLookup(records={"1": _end_record("1")})
    huge = float(Decimal("1E50"))
    result = normalize_prices_for_output(
        [_row("1", tariff=huge, premium=5.0)],
        storage=storage, reference_catalog=_catalog("EUR"), auction_lookup=lookup,
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
    from rate_resolution import RateResolutionOutcome, RateResolutionResult

    storage = AuctionStorage(tmp_path / "t.db")
    resolutions = {
        "1": RateResolutionResult(
            RateResolutionOutcome.RESOLVED, currency="USD", rate_to_eur=Decimal("1E50"),
        ),
    }
    result = normalize_prices_for_output(
        [_row("1", tariff=1000.0, premium=5.0)], storage=storage, resolutions=resolutions,
    )
    assert result.outcome is PriceNormalizationOutcome.BLOCKED
    assert result.prices_by_row_index == {}
    assert result.failures[0].reason_code == "invalid_conversion_data"


def test_invalid_decimal_in_a_mixed_batch_blocks_the_whole_batch_with_no_partial_prices(
    tmp_path,
) -> None:
    storage = AuctionStorage(tmp_path / "t.db")
    lookup = FakeAuctionLookup(records={"1": _end_record("1"), "2": _end_record("2")})
    rows = [
        _row("1", tariff=20.0, premium=5.0),  # otherwise valid
        _row("2", tariff=float("nan"), premium=5.0),  # invalid
    ]
    result = normalize_prices_for_output(
        rows, storage=storage, reference_catalog=_catalog("EUR"), auction_lookup=lookup,
    )
    assert result.outcome is PriceNormalizationOutcome.BLOCKED
    assert result.prices_by_row_index == {}


# --- P.36.21 review correction: immutable batch binding -----------------------

def test_successful_result_batch_binding_matches_compute_batch_binding(tmp_path) -> None:
    storage = AuctionStorage(tmp_path / "t.db")
    lookup = FakeAuctionLookup(records={"1": _end_record("1")})
    rows = [_row("1", tariff=20.0, premium=5.0)]
    result = normalize_prices_for_output(
        rows, storage=storage, reference_catalog=_catalog("EUR"), auction_lookup=lookup,
    )
    assert result.succeeded
    assert result.batch_binding == compute_batch_binding(rows)
    assert len(result.batch_binding) == 1


def test_blocked_result_has_no_batch_binding(tmp_path) -> None:
    storage = AuctionStorage(tmp_path / "t.db")
    lookup = FakeAuctionLookup()
    result = normalize_prices_for_output(
        [_row("1", state="Open")], storage=storage,
        reference_catalog=_catalog("USD"), auction_lookup=lookup,
    )
    assert result.outcome is PriceNormalizationOutcome.BLOCKED
    assert result.batch_binding == ()


def test_compute_batch_binding_differs_when_row_order_changes() -> None:
    row_a = _row("1", tariff=20.0)
    row_b = _row("2", tariff=40.0)
    assert compute_batch_binding([row_a, row_b]) != compute_batch_binding([row_b, row_a])


def test_compute_batch_binding_differs_when_auction_id_changes() -> None:
    row = _row("1", tariff=20.0)
    other = _row("2", tariff=20.0)
    assert compute_batch_binding([row]) != compute_batch_binding([other])


def test_compute_batch_binding_differs_when_source_tariff_or_premium_changes() -> None:
    base = compute_batch_binding([_row("1", tariff=20.0, premium=5.0)])
    different_tariff = compute_batch_binding([_row("1", tariff=21.0, premium=5.0)])
    different_premium = compute_batch_binding([_row("1", tariff=20.0, premium=6.0)])
    assert base != different_tariff
    assert base != different_premium
