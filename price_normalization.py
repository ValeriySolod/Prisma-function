"""P.36.21 Qt-independent boundary: strict EUR normalization of Tariff Price
and Premium Price.

`processor.import_prisma_export` already converts each row's source-currency
price to the physical unit MWh/h (`tariff_source_mwh_h`/
`premium_source_mwh_h`); it performs no currency conversion. This module is
the single place that converts that already-unit-normalized source price into
EUR/MWh/h, using the exact-Auction-ID rate resolved by P.36.19's
`rate_resolution.resolve_rates_for_rows` (currency, historical ECB
rate-to-EUR, or the EUR identity rate). It performs no CSV parsing, market-
mapping inference, PRISMA/ECB transport, or output writing of its own, and
never touches the 12-column output contract's column names or order.

Fail-closed contract. `normalize_prices_for_output()` either normalizes every
row's price successfully (`PriceNormalizationOutcome.SUCCESS`) or blocks the
entire batch (`PriceNormalizationOutcome.BLOCKED`) when at least one
otherwise-publishable row lacks a confirmed, usable EUR conversion —
including every non-`RESOLVED` `rate_resolution.RateResolutionOutcome`, a
missing resolution, and an invalid (non-finite, zero, or negative) rate. A
blocked result carries no partial price data: callers must not publish any
row from a blocked batch. Unlike `rate_resolution.resolve_rates_for_rows`
(which resolves and durably caches a rate outcome even when that outcome is
"unavailable"), this module never silently drops an unresolved row from
output; it fails the whole operation instead.

Arithmetic. `normalized_eur_price = source_price_mwh_h * rate_to_eur`, using
`decimal.Decimal` arithmetic exclusively (the source `float` value is
converted via `Decimal(str(value))`, never `Decimal(value)`, so the exact
decimal text of Python's own round-trip `float` representation is preserved
instead of that float's raw binary fraction). EUR itself is the identity
conversion (`rate_to_eur == 1`, already what `ecb_rates.resolve_rate_to_eur`
and `rate_resolution.resolve_auction_rate` return for `currency == "EUR"`),
so an EUR-denominated row's price is unchanged.

Deterministic serialization policy. `format_price()` quantizes the converted
Decimal to exactly `PRICE_DECIMAL_PLACES` (6) decimal places using
`ROUND_HALF_UP`, then renders it with `format(value, "f")` — always a fixed-
point decimal string using a dot separator, never scientific/exponential
notation and never a locale-dependent separator. The fixed six-place width is
the policy itself (not "unnecessary" padding): it is wide enough that no
source price or ECB rate ever loses a significant digit, and it is applied
identically to every row, so two rows with the same normalized value always
serialize identically. This is the one and only place a price is rounded for
output; `resolve_rates_for_rows`'s own cached rate keeps its full stored
precision.

Decimal input validation. A row's already-unit-normalized source prices
(`tariff_source_mwh_h`/`premium_source_mwh_h`) and a resolution's
`rate_to_eur` are all attacker/data-controlled `Decimal` inputs, not proven
safe by construction. Every value that reaches an EUR conversion — both
source prices, and both resulting multiplied EUR values — is checked finite
and non-negative (`rate_to_eur` additionally strictly positive, already
enforced), and the multiplied EUR values are additionally proven safely
quantizable/serializable under `format_price()`'s six-decimal-place policy
before being accepted. Any row that fails any of these checks is reported as
`invalid_conversion_data` and blocks the batch exactly like an unresolved
rate — never a partial price, and never an uncontrolled `decimal.
DecimalException` escaping this module. Zero is a valid source or converted
price.

Batch binding. A successful `PriceNormalizationResult` carries `batch_binding`
— an immutable, deterministic fingerprint of the exact ordered rows it was
computed for, built by `compute_batch_binding()` from every field that
determines resolution, conversion, output-row association, or price
(Auction ID, auction state, exit/entry market, source Tariff Price, source
Premium Price — row order itself is captured by tuple position). This lets a
caller that accepts a precomputed `PriceNormalizationResult` from elsewhere
(`prisma_publication.publish_cumulative_output`'s `precomputed_normalization`)
cheaply prove it was computed for the exact batch it is about to publish,
rather than merely a same-length batch, before trusting `prices_by_row_index`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, DecimalException, ROUND_HALF_UP
from enum import Enum
from typing import Mapping, Sequence

from ecb_rates import EcbRateSource
from prisma_auction_lookup import PrismaAuctionLookup
from prisma_references import DEFAULT_PRISMA_REFERENCES, PrismaReferenceCatalog
from rate_resolution import RateResolutionOutcome, RateResolutionResult, resolve_rates_for_rows
from storage import AuctionStorage

__all__ = [
    "PRICE_DECIMAL_PLACES",
    "PriceNormalizationOutcome",
    "NormalizedPrice",
    "PriceConversionFailure",
    "PriceNormalizationResult",
    "RowBinding",
    "compute_batch_binding",
    "describe_price_normalization_failure",
    "format_price",
    "normalize_prices_for_output",
]

PRICE_DECIMAL_PLACES = 6
_PRICE_QUANTUM = Decimal(1).scaleb(-PRICE_DECIMAL_PLACES)

_REASON_MISSING_RESOLUTION = "missing_resolution"
_REASON_INVALID_CONVERSION_DATA = "invalid_conversion_data"

# One row's binding tuple: (auction_id, state, exit_market, entry_market,
# source tariff price, source premium price), each rendered via `str()` for a
# stable, hashable, order-sensitive fingerprint field.
RowBinding = tuple[tuple[str, str, str, str, str, str], ...]


class PriceNormalizationOutcome(str, Enum):
    """Typed outcome of one P.36.21 strict EUR price-normalization attempt."""

    SUCCESS = "success"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class PriceConversionFailure:
    """One row's blocked EUR conversion.

    `reason_code` is a stable, machine-readable identifier — either a
    `rate_resolution.RateResolutionOutcome` value (`not_finished`,
    `auction_end_unavailable`, `currency_unknown`, `ecb_rate_unavailable`,
    `conflict`) or one of this module's own (`missing_resolution`,
    `invalid_conversion_data`). `message` is a short, English, technical-
    detail-free summary suitable for logs; it never carries raw exception
    text.
    """

    auction_id: str
    reason_code: str
    message: str


@dataclass(frozen=True)
class NormalizedPrice:
    """One row's Tariff Price/Premium Price, already converted to EUR/MWh/h."""

    tariff_price_eur_mwh_h: Decimal
    premium_price_eur_mwh_h: Decimal


@dataclass(frozen=True)
class PriceNormalizationResult:
    """Immutable outcome of one `normalize_prices_for_output()` call.

    `prices_by_row_index` is populated only when `outcome is
    PriceNormalizationOutcome.SUCCESS`, keyed by each row's position in the
    `rows` sequence that was normalized (the same order
    `processor.PrismaImportResult.rows` preserves). A `BLOCKED` result never
    carries partial price data — `prices_by_row_index` is always empty — so a
    caller cannot accidentally publish a subset of a blocked batch.

    `batch_binding` is populated only on `SUCCESS`, via `compute_batch_binding()`
    over the exact `rows` this result was computed for (see the module
    docstring's "Batch binding" section). A `BLOCKED` result's `batch_binding`
    stays empty — it never carries price data to misattribute either, so no
    caller has a reason to bind it to a batch.
    """

    outcome: PriceNormalizationOutcome
    prices_by_row_index: Mapping[int, NormalizedPrice] = field(default_factory=dict)
    failures: tuple[PriceConversionFailure, ...] = ()
    batch_binding: RowBinding = ()

    @property
    def succeeded(self) -> bool:
        return self.outcome is PriceNormalizationOutcome.SUCCESS


def describe_price_normalization_failure(result: PriceNormalizationResult) -> str:
    """Return a stable, English, technical-detail-free summary of a blocked
    normalization result, safe to show in the UI. Full diagnostic detail
    (`failures`, each with its Auction ID and reason code) is available to
    the caller for logging, but is not repeated verbatim here."""
    if result.succeeded:
        return ""
    affected = len({failure.auction_id for failure in result.failures})
    return (
        f"{affected} auction(s) could not be confirmed in EUR/MWh/h, so no "
        "output was created. Resolve the missing currency, auction-end, or "
        "ECB rate evidence, then retry."
    )


def format_price(value: Decimal) -> str:
    """Render a converted EUR/MWh/h price using this module's one
    deterministic serialization policy (see the module docstring)."""
    quantized = value.quantize(_PRICE_QUANTUM, rounding=ROUND_HALF_UP)
    return format(quantized, "f")


def _to_decimal_source_price(row: Mapping[str, object], field_name: str) -> Decimal:
    return Decimal(str(row[field_name]))


def _stable_field_text(value: object) -> str:
    return "" if value is None else str(value)


def compute_batch_binding(rows: Sequence[Mapping[str, object]]) -> RowBinding:
    """Deterministically fingerprint the exact ordered ``rows`` a
    `PriceNormalizationResult` is (or would be) computed for.

    Covers every field that determines resolution, conversion, output-row
    association, or price — Auction ID, auction state, exit/entry market, and
    both source prices — rendered via `str()` for a stable, hashable
    representation; row order is captured by tuple position itself, so a
    reordered batch of the same rows produces a different binding. Callers
    (`normalize_prices_for_output()` on success, and
    `prisma_publication._validate_precomputed_normalization()` re-deriving a
    fresh binding to compare against a supplied result) always call this same
    function rather than duplicating the fingerprint construction.
    """
    return tuple(
        (
            _stable_field_text(row.get("auction_id")),
            _stable_field_text(row.get("state")),
            _stable_field_text(row.get("exit_market")),
            _stable_field_text(row.get("entry_market")),
            _stable_field_text(row.get("tariff_source_mwh_h")),
            _stable_field_text(row.get("premium_source_mwh_h")),
        )
        for row in rows
    )


def _is_finite_nonnegative(value: Decimal) -> bool:
    return value.is_finite() and value >= 0


def _is_safely_serializable(value: Decimal) -> bool:
    """Whether `format_price(value)` can render ``value`` without raising.

    Guards against a `Decimal` that is finite and non-negative but whose
    magnitude cannot be quantized to `PRICE_DECIMAL_PLACES` within the active
    `decimal` context precision (`quantize()` raises `decimal.InvalidOperation`
    — a `DecimalException` — for such a value rather than silently rounding
    it), which must never escape this module as an uncontrolled exception.
    """
    try:
        format_price(value)
    except DecimalException:
        return False
    return True


def normalize_prices_for_output(
    rows: Sequence[Mapping[str, object]],
    *,
    storage: AuctionStorage,
    reference_catalog: PrismaReferenceCatalog = DEFAULT_PRISMA_REFERENCES,
    auction_lookup: PrismaAuctionLookup | None = None,
    page: object = None,
    ecb_source: EcbRateSource | None = None,
    resolutions: Mapping[str, RateResolutionResult] | None = None,
) -> PriceNormalizationResult:
    """Strictly convert every row's already-unit-normalized source price to
    EUR/MWh/h, or block the entire batch.

    `resolutions` may be supplied by a caller that already resolved rates for
    the same rows in this processing operation (for example to share one
    resolution with the Mapping display); when omitted, this function
    resolves them itself via `rate_resolution.resolve_rates_for_rows`, which
    already resolves each unique Auction ID at most once and reuses the
    existing durable cache — so passing `resolutions` explicitly changes
    nothing about caching or network behavior, only whether this call repeats
    a resolution pass an earlier caller already performed for the exact same
    processing operation.
    """
    if resolutions is None:
        resolutions = resolve_rates_for_rows(
            rows,
            storage=storage,
            reference_catalog=reference_catalog,
            auction_lookup=auction_lookup,
            page=page,
            ecb_source=ecb_source,
        )

    failures: list[PriceConversionFailure] = []
    prices: dict[int, NormalizedPrice] = {}
    reported_auction_ids: set[str] = set()

    def _report(auction_id: str, reason_code: str, message: str) -> None:
        if auction_id in reported_auction_ids:
            return
        reported_auction_ids.add(auction_id)
        failures.append(PriceConversionFailure(auction_id, reason_code, message))

    for index, row in enumerate(rows):
        auction_id = str(row.get("auction_id") or "")
        resolution = resolutions.get(auction_id)
        if resolution is None:
            _report(
                auction_id, _REASON_MISSING_RESOLUTION,
                f"No rate resolution is available for Auction ID {auction_id}.",
            )
            continue
        if resolution.outcome is not RateResolutionOutcome.RESOLVED:
            _report(
                auction_id, resolution.outcome.value,
                resolution.message
                or f"Auction ID {auction_id} has no confirmed EUR conversion.",
            )
            continue
        rate = resolution.rate_to_eur
        if rate is None or not rate.is_finite() or rate <= 0:
            _report(
                auction_id, _REASON_INVALID_CONVERSION_DATA,
                f"Auction ID {auction_id} has an invalid rate-to-EUR value.",
            )
            continue
        try:
            tariff_source = _to_decimal_source_price(row, "tariff_source_mwh_h")
            premium_source = _to_decimal_source_price(row, "premium_source_mwh_h")
        except (KeyError, TypeError, ArithmeticError, ValueError):
            _report(
                auction_id, _REASON_INVALID_CONVERSION_DATA,
                f"Auction ID {auction_id} has an invalid source price value.",
            )
            continue
        if not (
            _is_finite_nonnegative(tariff_source) and _is_finite_nonnegative(premium_source)
        ):
            _report(
                auction_id, _REASON_INVALID_CONVERSION_DATA,
                f"Auction ID {auction_id} has an invalid source price value.",
            )
            continue
        try:
            tariff_eur = tariff_source * rate
            premium_eur = premium_source * rate
        except ArithmeticError:
            _report(
                auction_id, _REASON_INVALID_CONVERSION_DATA,
                f"Auction ID {auction_id} has an invalid converted price value.",
            )
            continue
        if not (
            _is_finite_nonnegative(tariff_eur)
            and _is_finite_nonnegative(premium_eur)
            and _is_safely_serializable(tariff_eur)
            and _is_safely_serializable(premium_eur)
        ):
            _report(
                auction_id, _REASON_INVALID_CONVERSION_DATA,
                f"Auction ID {auction_id} has an invalid converted price value.",
            )
            continue
        prices[index] = NormalizedPrice(
            tariff_price_eur_mwh_h=tariff_eur,
            premium_price_eur_mwh_h=premium_eur,
        )

    if failures:
        return PriceNormalizationResult(PriceNormalizationOutcome.BLOCKED, {}, tuple(failures))
    return PriceNormalizationResult(
        PriceNormalizationOutcome.SUCCESS, prices, (), compute_batch_binding(rows)
    )
