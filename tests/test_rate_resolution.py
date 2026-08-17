from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from prisma_function.ecb_rates import EcbRateNotFoundError, EcbRateObservation
from prisma_function.prisma_auction_lookup import AuctionEndRecord, PrismaAuctionLookupError
from prisma_function.prisma_references import (
    PrismaReference,
    PrismaReferenceCatalog,
    ReferenceAlias,
    ReferenceClassification,
    ReferenceSide,
)
from prisma_function.rate_resolution import (
    RateResolutionOutcome,
    resolve_auction_rate,
    resolve_rates_for_rows,
)
from prisma_function.storage import AuctionStorage, RateResolutionConflictError


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


def _row(auction_id="1", state="Finished", exit_market="TEST", entry_market=""):
    return {
        "auction_id": auction_id, "state": state,
        "exit_market": exit_market, "entry_market": entry_market,
    }


def _end_record(auction_id="1", end_at=None, state="Finished"):
    return AuctionEndRecord(
        auction_id, end_at or datetime(2026, 8, 3, 14, 30, tzinfo=timezone.utc), state
    )


def test_cancelled_state_is_not_eligible_and_never_calls_lookup(tmp_path) -> None:
    storage = AuctionStorage(tmp_path / "t.db")
    lookup = FakeAuctionLookup()
    result = resolve_auction_rate(
        "1", "Cancelled", _row(state="Cancelled"),
        storage=storage, reference_catalog=_catalog("USD"), auction_lookup=lookup,
    )
    assert result.outcome is RateResolutionOutcome.NOT_FINISHED
    assert lookup.calls == []


@pytest.mark.parametrize("other_state", ["Open", "Pending", ""])
def test_other_non_finished_states_are_not_eligible(tmp_path, other_state) -> None:
    storage = AuctionStorage(tmp_path / "t.db")
    lookup = FakeAuctionLookup()
    result = resolve_auction_rate(
        "1", other_state, _row(state=other_state),
        storage=storage, reference_catalog=_catalog("USD"), auction_lookup=lookup,
    )
    assert result.outcome is RateResolutionOutcome.NOT_FINISHED
    assert lookup.calls == []


def test_finished_state_triggers_lookup_using_exact_auction_id(tmp_path) -> None:
    storage = AuctionStorage(tmp_path / "t.db")
    lookup = FakeAuctionLookup(records={"1": _end_record("1")})
    ecb = FakeEcbSource(EcbRateObservation(date(2026, 8, 3), Decimal("1.0921")))
    result = resolve_auction_rate(
        "1", "Finished", _row(),
        storage=storage, reference_catalog=_catalog("USD"),
        auction_lookup=lookup, ecb_source=ecb,
    )
    assert lookup.calls == ["1"]
    assert result.outcome is RateResolutionOutcome.RESOLVED
    assert result.currency == "USD"


def test_currency_unknown_when_no_approved_metadata(tmp_path) -> None:
    storage = AuctionStorage(tmp_path / "t.db")
    lookup = FakeAuctionLookup(records={"1": _end_record("1")})
    result = resolve_auction_rate(
        "1", "Finished", _row(),
        storage=storage, reference_catalog=_catalog(None), auction_lookup=lookup,
    )
    assert result.outcome is RateResolutionOutcome.CURRENCY_UNKNOWN
    assert result.currency is None


def test_currency_falls_back_to_entry_market_when_exit_unresolved(tmp_path) -> None:
    storage = AuctionStorage(tmp_path / "t.db")
    catalog = PrismaReferenceCatalog((
        PrismaReference(
            "ENTRY-MKT", ReferenceClassification.MARKET,
            (ReferenceAlias("a", ReferenceSide.ENTRY),), entry_currency="USD",
        ),
    ))
    lookup = FakeAuctionLookup(records={"1": _end_record("1")})
    ecb = FakeEcbSource(EcbRateObservation(date(2026, 8, 3), Decimal("1.0921")))
    result = resolve_auction_rate(
        "1", "Finished", _row(exit_market="", entry_market="ENTRY-MKT"),
        storage=storage, reference_catalog=catalog, auction_lookup=lookup, ecb_source=ecb,
    )
    assert result.outcome is RateResolutionOutcome.RESOLVED
    assert result.currency == "USD"


def test_currency_evidenced_only_on_exit_does_not_leak_to_entry_side_lookup(tmp_path) -> None:
    """Regression guard for the EXIT/ENTRY currency-leak defect (2026-08-13):
    a canonical market/storage name with EXIT-only currency evidence must
    not resolve a currency when the very same name is reached through the
    row's entry_market side."""
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
    result = resolve_auction_rate(
        "1", "Finished", _row(exit_market="", entry_market="BOTH-SIDES"),
        storage=storage, reference_catalog=catalog, auction_lookup=lookup,
    )
    assert result.outcome is RateResolutionOutcome.CURRENCY_UNKNOWN
    assert result.currency is None


def test_eur_currency_skips_ecb_and_uses_auction_end_as_rate_date(tmp_path) -> None:
    storage = AuctionStorage(tmp_path / "t.db")
    lookup = FakeAuctionLookup(records={"1": _end_record("1", datetime(2026, 8, 3, 10, 0, tzinfo=timezone.utc))})

    class ExplodingEcbSource:
        def fetch(self, *args, **kwargs):
            raise AssertionError("EUR must never call the ECB source.")

    result = resolve_auction_rate(
        "1", "Finished", _row(),
        storage=storage, reference_catalog=_catalog("EUR"),
        auction_lookup=lookup, ecb_source=ExplodingEcbSource(),
    )
    assert result.outcome is RateResolutionOutcome.RESOLVED
    assert result.currency == "EUR"
    assert result.rate_to_eur == Decimal(1)
    assert result.rate_date == date(2026, 8, 3)


def test_auction_end_unavailable_outcome_on_lookup_failure(tmp_path) -> None:
    storage = AuctionStorage(tmp_path / "t.db")
    lookup = FakeAuctionLookup(errors={"1": PrismaAuctionLookupError("boom")})
    result = resolve_auction_rate(
        "1", "Finished", _row(),
        storage=storage, reference_catalog=_catalog("USD"), auction_lookup=lookup,
    )
    assert result.outcome is RateResolutionOutcome.AUCTION_END_UNAVAILABLE
    assert "boom" in result.message


def test_ecb_rate_unavailable_outcome_on_ecb_failure(tmp_path) -> None:
    storage = AuctionStorage(tmp_path / "t.db")
    lookup = FakeAuctionLookup(records={"1": _end_record("1")})
    ecb = FakeEcbSource(error=EcbRateNotFoundError("no rate"))
    result = resolve_auction_rate(
        "1", "Finished", _row(),
        storage=storage, reference_catalog=_catalog("USD"),
        auction_lookup=lookup, ecb_source=ecb,
    )
    assert result.outcome is RateResolutionOutcome.ECB_RATE_UNAVAILABLE
    assert "no rate" in result.message


def test_cached_auction_id_is_reused_without_duplicate_retrieval(tmp_path) -> None:
    storage = AuctionStorage(tmp_path / "t.db")
    lookup = FakeAuctionLookup(records={"1": _end_record("1")})
    ecb = FakeEcbSource(EcbRateObservation(date(2026, 8, 3), Decimal("1.0921")))
    first = resolve_auction_rate(
        "1", "Finished", _row(), storage=storage, reference_catalog=_catalog("USD"),
        auction_lookup=lookup, ecb_source=ecb,
    )
    second = resolve_auction_rate(
        "1", "Finished", _row(), storage=storage, reference_catalog=_catalog("USD"),
        auction_lookup=lookup, ecb_source=ecb,
    )
    assert first == second
    assert lookup.calls == ["1"]
    assert len(ecb.calls) == 1


def test_reprocessing_remains_deterministic_after_newer_ecb_data(tmp_path) -> None:
    storage = AuctionStorage(tmp_path / "t.db")
    lookup = FakeAuctionLookup(records={"1": _end_record("1")})
    first_ecb = FakeEcbSource(EcbRateObservation(date(2026, 8, 3), Decimal("1.0921")))
    first = resolve_auction_rate(
        "1", "Finished", _row(), storage=storage, reference_catalog=_catalog("USD"),
        auction_lookup=lookup, ecb_source=first_ecb,
    )

    newer_ecb = FakeEcbSource(EcbRateObservation(date(2026, 8, 3), Decimal("999")))
    second = resolve_auction_rate(
        "1", "Finished", _row(), storage=storage, reference_catalog=_catalog("USD"),
        auction_lookup=lookup, ecb_source=newer_ecb,
    )
    assert second == first
    assert newer_ecb.calls == []  # never consulted: the cached result was reused


def test_two_finished_auctions_with_different_end_dates_receive_different_rates(tmp_path) -> None:
    storage = AuctionStorage(tmp_path / "t.db")
    lookup = FakeAuctionLookup(records={
        "1": _end_record("1", datetime(2026, 8, 3, 10, 0, tzinfo=timezone.utc)),
        "2": _end_record("2", datetime(2026, 8, 5, 10, 0, tzinfo=timezone.utc)),
    })

    class DateVaryingEcbSource:
        def fetch(self, currency, *, on_or_before, timeout_seconds):
            value = "1.10" if on_or_before == date(2026, 8, 3) else "1.20"
            return EcbRateObservation(on_or_before, Decimal(value))

    rows = [_row("1"), _row("2")]
    results = resolve_rates_for_rows(
        rows, storage=storage, reference_catalog=_catalog("USD"),
        auction_lookup=lookup, ecb_source=DateVaryingEcbSource(),
    )
    assert results["1"].rate_to_eur != results["2"].rate_to_eur
    assert results["1"].rate_date == date(2026, 8, 3)
    assert results["2"].rate_date == date(2026, 8, 5)


def test_rows_sharing_one_auction_id_resolve_only_once(tmp_path) -> None:
    storage = AuctionStorage(tmp_path / "t.db")
    lookup = FakeAuctionLookup(records={"1": _end_record("1")})
    ecb = FakeEcbSource(EcbRateObservation(date(2026, 8, 3), Decimal("1.0921")))
    rows = [_row("1"), _row("1"), _row("1")]
    results = resolve_rates_for_rows(
        rows, storage=storage, reference_catalog=_catalog("USD"),
        auction_lookup=lookup, ecb_source=ecb,
    )
    assert list(results) == ["1"]
    assert lookup.calls == ["1"]
    assert len(ecb.calls) == 1


def test_blank_auction_id_rows_are_skipped(tmp_path) -> None:
    storage = AuctionStorage(tmp_path / "t.db")
    lookup = FakeAuctionLookup()
    results = resolve_rates_for_rows(
        [_row("")], storage=storage, reference_catalog=_catalog("USD"), auction_lookup=lookup,
    )
    assert results == {}
    assert lookup.calls == []


def test_storage_conflict_surfaces_as_typed_conflict_outcome(tmp_path, monkeypatch) -> None:
    storage = AuctionStorage(tmp_path / "t.db")
    lookup = FakeAuctionLookup(records={"1": _end_record("1")})
    ecb = FakeEcbSource(EcbRateObservation(date(2026, 8, 3), Decimal("1.0921")))

    def raise_conflict(record):
        raise RateResolutionConflictError("simulated concurrent conflict")

    monkeypatch.setattr(storage, "save_rate_resolution", raise_conflict)
    result = resolve_auction_rate(
        "1", "Finished", _row(), storage=storage, reference_catalog=_catalog("USD"),
        auction_lookup=lookup, ecb_source=ecb,
    )
    assert result.outcome is RateResolutionOutcome.CONFLICT
    assert "simulated concurrent conflict" in result.message


def test_no_partial_commit_on_prisma_failure(tmp_path) -> None:
    storage = AuctionStorage(tmp_path / "t.db")
    lookup = FakeAuctionLookup(errors={"1": PrismaAuctionLookupError("boom")})
    resolve_auction_rate(
        "1", "Finished", _row(), storage=storage, reference_catalog=_catalog("USD"),
        auction_lookup=lookup,
    )
    assert storage.get_rate_resolution("1") is None


def test_no_partial_commit_on_ecb_failure(tmp_path) -> None:
    storage = AuctionStorage(tmp_path / "t.db")
    lookup = FakeAuctionLookup(records={"1": _end_record("1")})
    ecb = FakeEcbSource(error=EcbRateNotFoundError("no rate"))
    resolve_auction_rate(
        "1", "Finished", _row(), storage=storage, reference_catalog=_catalog("USD"),
        auction_lookup=lookup, ecb_source=ecb,
    )
    assert storage.get_rate_resolution("1") is None
