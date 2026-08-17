"""P.37 Qt-independent boundary: strict EUR normalization of Tariff Price
and Premium Price, keyed by (auction date, currency).

`processor.import_prisma_export` already converts each price field's
source-currency amount to the physical unit MWh/h
(`tariff_exit_source_mwh_h`/`tariff_entry_source_mwh_h`/
`premium_source_mwh_h`, each paired with its own already-parsed ISO 4217
currency -- `tariff_exit_currency`/`tariff_entry_currency`/
`premium_currency`, `""` meaning the field was absent); it performs no
currency conversion. This module is the single place that converts those
already-unit-normalized source prices into EUR/MWh/h.

P.37 resolution mechanism (supersedes P.36.19/P.36.21's Auction-ID-keyed
mechanism for this Tariff/Premium output path only). The ECB rate is
resolved by `(auction_date, currency)` -- the calendar date parsed directly
from each row's own `Start of Auction` (already `row["auction_date"]`, an
ISO `YYYY-MM-DD` string, since `processor.py` rejects any row whose
`Start of Auction` cannot be parsed) and a price field's own CSV-unit-
derived currency -- never from a market/storage catalog and never via a
live PRISMA auction-detail lookup. This makes the pipeline fully
self-sufficient from the CSV alone: `prisma_auction_lookup.PrismaAuctionLookup`
(which, since P.38 removed all browser/PRISMA-website access, always fails
closed in the running application) is not used here at all. `ecb_rates.py`
(quotation-direction inversion, weekend/ECB-holiday fallback) is reused
unmodified; `storage.AuctionStorage`'s new `(auction_date, currency)` cache
(`get_ecb_auction_date_rate`/`save_ecb_auction_date_rate`) durably persists
each resolution so it is never re-requested from ECB.
`rate_resolution.py`/`prisma_auction_lookup.py` are unmodified by P.37 and
remain in active use for the Mapping UI's own Currency/Rate to EUR/Rate
Date display columns (`mapping_presentation.py`), an entirely separate,
unaffected call graph.

This module performs no CSV parsing, market-mapping inference, PRISMA/ECB
transport, or output writing of its own, and never touches the 12-column
output contract's column names or order.

Fail-closed contract. `normalize_prices_for_output()` either normalizes every
row's price successfully (`PriceNormalizationOutcome.SUCCESS`) or blocks the
entire batch (`PriceNormalizationOutcome.BLOCKED`) when at least one
otherwise-publishable row lacks a confirmed, usable EUR conversion —
including every non-`RESOLVED` `EcbRateResolutionOutcome`, a missing
resolution, and an invalid (non-finite, zero, or negative) rate. A blocked
result carries no partial price data: callers must not publish any row from
a blocked batch. Unlike `resolve_ecb_rates_for_rows` (which resolves and
durably caches a rate outcome even when that outcome is "unavailable"), this
module never silently drops an unresolved row from output; it fails the
whole operation instead. A missing/unsupported currency or an unparseable
auction date can never reach this module: both are rejected by
`processor.py` at import time, before a row is ever accepted.

Side-independent bundle conversion. A row's exit-side and entry-side tariff
may be denominated in different currencies (a bundle, `Direction ==
"Exit/Entry"`, row's two sides are evidenced independently). Each side is
resolved and converted to EUR independently, and only the two already-EUR
values are summed — never a shared or blended rate, and never a pre-
conversion sum of mixed-currency amounts. The same rule applies
independently to the Premium/Surcharge price, which carries its own,
separately resolved currency.

Arithmetic. `normalized_eur_price = source_price_mwh_h * rate_to_eur`, using
`decimal.Decimal` arithmetic exclusively (the source `float` value is
converted via `Decimal(str(value))`, never `Decimal(value)`, so the exact
decimal text of Python's own round-trip `float` representation is preserved
instead of that float's raw binary fraction). EUR itself is the identity
conversion (`rate_to_eur == 1`, already what `ecb_rates.resolve_rate_to_eur`
returns for `currency == "EUR"`), so an EUR-denominated price is unchanged.

Deterministic serialization policy. `format_price()` quantizes the converted
Decimal to exactly `PRICE_DECIMAL_PLACES` (6) decimal places using
`ROUND_HALF_UP`, then renders it with `format(value, "f")` — always a fixed-
point decimal string using a dot separator, never scientific/exponential
notation and never a locale-dependent separator. The fixed six-place width is
the policy itself (not "unnecessary" padding): it is wide enough that no
source price or ECB rate ever loses a significant digit, and it is applied
identically to every row, so two rows with the same normalized value always
serialize identically. This is the one and only place a price is rounded for
output; a resolution's own cached rate keeps its full stored precision.

Decimal input validation. A row's already-unit-normalized source prices and
a resolution's `rate_to_eur` are all attacker/data-controlled `Decimal`
inputs, not proven safe by construction. Every value that reaches an EUR
conversion — each side's source price, and each side's resulting multiplied
EUR value — is checked finite and non-negative (`rate_to_eur` additionally
strictly positive, already enforced), and each multiplied EUR value, plus
the tariff side's summed total, is additionally proven safely
quantizable/serializable under `format_price()`'s six-decimal-place policy
before being accepted (two individually valid EUR values can still sum to
something unserializable). Any row that fails any of these checks is
reported as `invalid_conversion_data` and blocks the batch exactly like an
unresolved rate — never a partial price, and never an uncontrolled
`decimal.DecimalException` escaping this module. Zero is a valid source or
converted price.

Batch binding. A successful `PriceNormalizationResult` carries `batch_binding`
— an immutable, deterministic fingerprint of the exact ordered rows it was
computed for, built by `compute_batch_binding()` from every field that
determines resolution, conversion, output-row association, or price
(Auction ID, auction date, each side's currency and source price — row order
itself is captured by tuple position). This lets a caller that accepts a
precomputed `PriceNormalizationResult` from elsewhere
(`prisma_publication.publish_cumulative_output`'s `precomputed_normalization`)
cheaply prove it was computed for the exact batch it is about to publish,
rather than merely a same-length batch, before trusting `prices_by_row_index`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal, DecimalException, ROUND_HALF_UP
from enum import Enum
from typing import Mapping, Sequence

from prisma_function.ecb_rates import EcbRateNotFoundError, EcbRateSource, EcbRateSourceError, resolve_rate_to_eur
from prisma_function.storage import AuctionStorage, EcbAuctionDateRateConflictError, EcbAuctionDateRateRecord

__all__ = [
    "PRICE_DECIMAL_PLACES",
    "SOURCE_VERSION",
    "EcbRateResolutionOutcome",
    "EcbDateRateResolution",
    "PriceNormalizationOutcome",
    "NormalizedPrice",
    "PriceConversionFailure",
    "PriceNormalizationResult",
    "RowBinding",
    "compute_batch_binding",
    "describe_price_normalization_failure",
    "format_price",
    "normalize_prices_for_output",
    "resolve_ecb_rates_for_rows",
]

PRICE_DECIMAL_PLACES = 6
_PRICE_QUANTUM = Decimal(1).scaleb(-PRICE_DECIMAL_PLACES)

SOURCE_VERSION = "ecb_rates=1;price_normalization=2"

_REASON_MISSING_RESOLUTION = "missing_resolution"
_REASON_INVALID_CONVERSION_DATA = "invalid_conversion_data"

# One row's binding tuple: (auction_id, auction_date, tariff exit currency,
# tariff exit source price, tariff entry currency, tariff entry source
# price, premium currency, premium source price), each rendered via `str()`
# for a stable, hashable, order-sensitive fingerprint field. `state`/
# `exit_market`/`entry_market` no longer participate under P.37 (neither
# determines resolution or price); `auction_id` is kept for row-identity/
# anti-misattribution purposes even though only `auction_date` participates
# in rate resolution.
RowBinding = tuple[tuple[str, str, str, str, str, str, str, str], ...]


class EcbRateResolutionOutcome(str, Enum):
    """Typed outcome of one P.37 (auction_date, currency) ECB rate
    resolution attempt."""

    RESOLVED = "resolved"
    ECB_RATE_UNAVAILABLE = "ecb_rate_unavailable"
    ECB_SOURCE_ERROR = "ecb_source_error"
    CONFLICT = "conflict"


@dataclass(frozen=True)
class EcbDateRateResolution:
    """One (auction_date, currency)-keyed P.37 resolution outcome.

    `rate_to_eur` is populated only when `outcome is
    EcbRateResolutionOutcome.RESOLVED`; every other outcome carries only a
    stable, technical-detail-free-enough-for-logs `message`.
    """

    outcome: EcbRateResolutionOutcome
    rate_to_eur: Decimal | None = None
    message: str | None = None


class PriceNormalizationOutcome(str, Enum):
    """Typed outcome of one P.36.21/P.37 strict EUR price-normalization
    attempt."""

    SUCCESS = "success"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class PriceConversionFailure:
    """One row's blocked EUR conversion.

    `reason_code` is a stable, machine-readable identifier — either an
    `EcbRateResolutionOutcome` value (`ecb_rate_unavailable`,
    `ecb_source_error`, `conflict`) or one of this module's own
    (`missing_resolution`, `invalid_conversion_data`). `message` is a short,
    English, technical-detail-free summary suitable for logs; it never
    carries raw exception text.
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
        "output was created. Resolve the missing ECB rate evidence for the "
        "required auction date and currency, then retry."
    )


def format_price(value: Decimal) -> str:
    """Render a converted EUR/MWh/h price using this module's one
    deterministic serialization policy (see the module docstring)."""
    quantized = value.quantize(_PRICE_QUANTUM, rounding=ROUND_HALF_UP)
    return format(quantized, "f")


def _stable_field_text(value: object) -> str:
    return "" if value is None else str(value)


def compute_batch_binding(rows: Sequence[Mapping[str, object]]) -> RowBinding:
    """Deterministically fingerprint the exact ordered ``rows`` a
    `PriceNormalizationResult` is (or would be) computed for.

    Covers every field that determines resolution, conversion, output-row
    association, or price under P.37 — Auction ID, auction date, and each
    side's currency and source price — rendered via `str()` for a stable,
    hashable representation; row order is captured by tuple position itself,
    so a reordered batch of the same rows produces a different binding.
    Callers (`normalize_prices_for_output()` on success, and
    `prisma_publication._validate_precomputed_normalization()` re-deriving a
    fresh binding to compare against a supplied result) always call this same
    function rather than duplicating the fingerprint construction.
    """
    return tuple(
        (
            _stable_field_text(row.get("auction_id")),
            _stable_field_text(row.get("auction_date")),
            _stable_field_text(row.get("tariff_exit_currency")),
            _stable_field_text(row.get("tariff_exit_source_mwh_h")),
            _stable_field_text(row.get("tariff_entry_currency")),
            _stable_field_text(row.get("tariff_entry_source_mwh_h")),
            _stable_field_text(row.get("premium_currency")),
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


def _resolve_ecb_date_rate(
    auction_date: str,
    currency: str,
    *,
    storage: AuctionStorage,
    ecb_source: EcbRateSource | None,
) -> EcbDateRateResolution:
    """Resolve (or reuse a durably cached) P.37 ECB rate for one
    (auction_date, currency) pair.

    A previously fixed cached result is always reused as-is without
    repeating any ECB retrieval, regardless of newer ECB data — this is what
    makes reprocessing the same auction date/currency deterministic. Only a
    cache miss performs a new resolution attempt, which is committed
    atomically via `storage.save_ecb_auction_date_rate`; a contradiction
    against data another concurrent resolution already fixed is reported as
    `EcbRateResolutionOutcome.CONFLICT`, never silently overwritten. Mirrors
    `rate_resolution.resolve_auction_rate`'s structure one-to-one, re-keyed
    by `(auction_date, currency)` instead of Auction ID and with no
    Finished-state/PRISMA-lookup gate (P.37 has none — see the module
    docstring). EUR goes through this same path uniformly:
    `ecb_rates.resolve_rate_to_eur` already short-circuits it to the
    identity rate with zero network access, so no special-casing is needed
    here.
    """
    cached = storage.get_ecb_auction_date_rate(auction_date, currency)
    if cached is not None:
        return EcbDateRateResolution(
            EcbRateResolutionOutcome.RESOLVED, rate_to_eur=Decimal(cached.rate_to_eur)
        )

    try:
        parsed_date = date.fromisoformat(auction_date)
    except ValueError as exc:
        # Unreachable via the active application: `processor.py` already
        # rejects any row whose "Start of Auction" cannot be parsed, so
        # every accepted row's `auction_date` is a valid ISO date. Guarded
        # here only so this function never raises an uncontrolled exception
        # for a malformed caller-supplied row.
        return EcbDateRateResolution(
            EcbRateResolutionOutcome.ECB_SOURCE_ERROR,
            message=f"Auction date {auction_date!r} is not a valid ISO date: {exc}",
        )

    try:
        result = resolve_rate_to_eur(currency, parsed_date, source=ecb_source)
    except EcbRateNotFoundError as exc:
        return EcbDateRateResolution(EcbRateResolutionOutcome.ECB_RATE_UNAVAILABLE, message=str(exc))
    except EcbRateSourceError as exc:
        return EcbDateRateResolution(EcbRateResolutionOutcome.ECB_SOURCE_ERROR, message=str(exc))

    new_record = EcbAuctionDateRateRecord(
        auction_date=auction_date,
        currency=currency,
        ecb_publication_date=result.publication_date.isoformat(),
        rate_to_eur=str(result.rate_to_eur),
        resolved_at_utc=datetime.now(timezone.utc).isoformat(timespec="microseconds"),
        source_version=SOURCE_VERSION,
    )
    try:
        saved = storage.save_ecb_auction_date_rate(new_record)
    except EcbAuctionDateRateConflictError as exc:
        return EcbDateRateResolution(EcbRateResolutionOutcome.CONFLICT, message=str(exc))

    return EcbDateRateResolution(
        EcbRateResolutionOutcome.RESOLVED, rate_to_eur=Decimal(saved.rate_to_eur)
    )


def resolve_ecb_rates_for_rows(
    rows: Sequence[Mapping[str, object]],
    *,
    storage: AuctionStorage,
    ecb_source: EcbRateSource | None = None,
) -> dict[tuple[str, str], EcbDateRateResolution]:
    """Resolve each unique `(auction_date, currency)` pair present in
    ``rows`` at most once.

    Every row's `tariff_exit_currency`/`tariff_entry_currency`/
    `premium_currency` (each `""` when that price field is absent) paired
    with the row's own `auction_date` is collected into one deduplicated set
    before any ECB access, so a batch with many rows sharing the same
    auction date and currency triggers exactly one ECB lookup for that pair
    — the "no uncontrolled ECB request per row" boundary for one processing
    operation, mirroring `rate_resolution.resolve_rates_for_rows`'s
    equivalent per-Auction-ID guarantee. A row with a blank currency for a
    given field contributes no key for that field (no eligible price to
    resolve).
    """
    keys: set[tuple[str, str]] = set()
    for row in rows:
        auction_date = str(row.get("auction_date") or "")
        for field_name in ("tariff_exit_currency", "tariff_entry_currency", "premium_currency"):
            currency = str(row.get(field_name) or "")
            if currency:
                keys.add((auction_date, currency))
    return {
        key: _resolve_ecb_date_rate(key[0], key[1], storage=storage, ecb_source=ecb_source)
        for key in sorted(keys)
    }


class _ConversionBlocked(Exception):
    """Internal signal that one side's EUR conversion could not be
    completed; carries the exact reason code/message `normalize_prices_for_
    output()` reports for the row. Never escapes this module."""

    def __init__(self, reason_code: str, message: str) -> None:
        super().__init__(message)
        self.reason_code = reason_code
        self.message = message


def _convert_side(
    auction_id: str,
    value: object,
    currency: str,
    auction_date: str,
    resolutions: Mapping[tuple[str, str], EcbDateRateResolution],
) -> Decimal:
    """Convert one already-unit-normalized source-currency price field to
    EUR, or raise `_ConversionBlocked`.

    ``currency == ""`` means the field was absent (see
    `processor._ParsedPrice`); such a side contributes exactly `Decimal(0)`
    with no rate lookup needed — this is how a row missing one side of a
    bundle (or missing Premium entirely) is handled without requiring a
    currency that was never present.
    """
    if not currency:
        return Decimal(0)
    resolution = resolutions.get((auction_date, currency))
    if resolution is None:
        raise _ConversionBlocked(
            _REASON_MISSING_RESOLUTION,
            f"No ECB rate resolution is available for Auction ID {auction_id} "
            f"({auction_date}, {currency}).",
        )
    if resolution.outcome is not EcbRateResolutionOutcome.RESOLVED:
        raise _ConversionBlocked(
            resolution.outcome.value,
            resolution.message
            or f"Auction ID {auction_id} has no confirmed EUR conversion for "
            f"{auction_date}/{currency}.",
        )
    rate = resolution.rate_to_eur
    if rate is None or not rate.is_finite() or rate <= 0:
        raise _ConversionBlocked(
            _REASON_INVALID_CONVERSION_DATA,
            f"Auction ID {auction_id} has an invalid rate-to-EUR value for "
            f"{auction_date}/{currency}.",
        )
    try:
        source = Decimal(str(value))
    except (DecimalException, TypeError, ValueError):
        raise _ConversionBlocked(
            _REASON_INVALID_CONVERSION_DATA,
            f"Auction ID {auction_id} has an invalid source price value.",
        )
    if not _is_finite_nonnegative(source):
        raise _ConversionBlocked(
            _REASON_INVALID_CONVERSION_DATA,
            f"Auction ID {auction_id} has an invalid source price value.",
        )
    try:
        converted = source * rate
    except ArithmeticError:
        raise _ConversionBlocked(
            _REASON_INVALID_CONVERSION_DATA,
            f"Auction ID {auction_id} has an invalid converted price value.",
        )
    if not (_is_finite_nonnegative(converted) and _is_safely_serializable(converted)):
        raise _ConversionBlocked(
            _REASON_INVALID_CONVERSION_DATA,
            f"Auction ID {auction_id} has an invalid converted price value.",
        )
    return converted


def normalize_prices_for_output(
    rows: Sequence[Mapping[str, object]],
    *,
    storage: AuctionStorage,
    ecb_source: EcbRateSource | None = None,
    resolutions: Mapping[tuple[str, str], EcbDateRateResolution] | None = None,
) -> PriceNormalizationResult:
    """Strictly convert every row's already-unit-normalized source prices to
    EUR/MWh/h, or block the entire batch.

    Tariff Price sums the exit side and entry side, each independently
    resolved and converted to EUR by its own `(auction_date, currency)` pair
    before the addition — never a shared or pre-conversion sum. Premium
    Price is resolved and converted independently, by its own currency.

    ``resolutions`` may be supplied by a caller that already resolved rates
    for the same rows in this processing operation; when omitted, this
    function resolves them itself via `resolve_ecb_rates_for_rows`, which
    already resolves each unique `(auction_date, currency)` pair at most
    once and reuses the existing durable cache — so passing ``resolutions``
    explicitly changes nothing about caching or network behavior, only
    whether this call repeats a resolution pass an earlier caller already
    performed for the exact same processing operation.
    """
    if resolutions is None:
        resolutions = resolve_ecb_rates_for_rows(rows, storage=storage, ecb_source=ecb_source)

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
        auction_date = str(row.get("auction_date") or "")
        try:
            tariff_eur = _convert_side(
                auction_id,
                row.get("tariff_exit_source_mwh_h"),
                str(row.get("tariff_exit_currency") or ""),
                auction_date,
                resolutions,
            ) + _convert_side(
                auction_id,
                row.get("tariff_entry_source_mwh_h"),
                str(row.get("tariff_entry_currency") or ""),
                auction_date,
                resolutions,
            )
            if not (_is_finite_nonnegative(tariff_eur) and _is_safely_serializable(tariff_eur)):
                raise _ConversionBlocked(
                    _REASON_INVALID_CONVERSION_DATA,
                    f"Auction ID {auction_id} has an invalid converted price value.",
                )
            premium_eur = _convert_side(
                auction_id,
                row.get("premium_source_mwh_h"),
                str(row.get("premium_currency") or ""),
                auction_date,
                resolutions,
            )
        except _ConversionBlocked as exc:
            _report(auction_id, exc.reason_code, exc.message)
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
