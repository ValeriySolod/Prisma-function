"""P.36.19 orchestration: eligibility, currency, ECB rate, and durable caching.

Ties together, for one already-imported PRISMA row's `auction_id`/`state`:

1. eligibility — only `State == "Finished"` is eligible (see
   `prisma_auction_lookup.FINISHED_STATE`); `Cancelled` and every other
   state are not;
2. the exact-Auction-ID official PRISMA auction-end lookup
   (`prisma_auction_lookup.PrismaAuctionLookup`);
3. currency resolution from the already-resolved exact market mapping
   (`prisma_references.PrismaReferenceCatalog.currency_for`) — never
   inferred, never guessed;
4. historical ECB rate-to-EUR resolution (`ecb_rates.resolve_rate_to_eur`);
5. durable per-Auction-ID caching (`storage.AuctionStorage`), so each unique
   Auction ID is resolved at most once per processing operation and a
   previously fixed valid result is reused deterministically thereafter,
   even after newer ECB data is published.

This module performs no CSV parsing, market-mapping inference, or output
writing of its own, and never touches the 12-column output contract.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Iterable, Mapping

from prisma_function.ecb_rates import EcbRateError, EcbRateSource, resolve_rate_to_eur
from prisma_function.prisma_auction_lookup import (
    FINISHED_STATE,
    PrismaAuctionLookup,
    PrismaAuctionLookupError,
    authoritative_end_date,
)
from prisma_function.prisma_references import DEFAULT_PRISMA_REFERENCES, PrismaReferenceCatalog, ReferenceSide
from prisma_function.storage import AuctionStorage, RateResolutionConflictError, RateResolutionRecord

__all__ = [
    "SOURCE_VERSION",
    "RateResolutionOutcome",
    "RateResolutionResult",
    "resolve_auction_rate",
    "resolve_rates_for_rows",
]

SOURCE_VERSION = "prisma_auction_lookup=1;ecb_rates=1;rate_resolution=1"


class RateResolutionOutcome(str, Enum):
    RESOLVED = "resolved"
    NOT_FINISHED = "not_finished"
    AUCTION_END_UNAVAILABLE = "auction_end_unavailable"
    CURRENCY_UNKNOWN = "currency_unknown"
    ECB_RATE_UNAVAILABLE = "ecb_rate_unavailable"
    CONFLICT = "conflict"


@dataclass(frozen=True)
class RateResolutionResult:
    """One Mapping-ready resolution outcome for a single Auction ID.

    `currency`/`rate_to_eur`/`rate_date` are populated only when
    `outcome is RateResolutionOutcome.RESOLVED`; every other outcome carries
    only a stable, technical-detail-free `message` for display, with full
    diagnostic context preserved only in logs by the caller.
    """

    outcome: RateResolutionOutcome
    currency: str | None = None
    rate_to_eur: Decimal | None = None
    rate_date: date | None = None
    message: str | None = None


def _select_currency(
    row: Mapping[str, object], catalog: PrismaReferenceCatalog
) -> str | None:
    """Prefer the exit-market currency; fall back to the entry-market currency.

    Mirrors this codebase's existing exit-before-entry convention (see
    `mapping_presentation.MAPPING_DISPLAY_FIELDS` and
    `storage.AuctionStorage.EXCEL_COLUMNS`, both `Exit` before `Entry`) for a
    row whose exit side has no resolved market or no approved currency
    metadata. Each side is resolved through its own exact `ReferenceSide`, so
    currency evidence approved for only one side (e.g. EXIT) can never leak
    onto the other side's lookup, even when both sides share one canonical
    market/storage name. Never guesses: an unresolved or currency-unevidenced
    market simply yields `None` from `catalog.currency_for`.
    """
    exit_market = row.get("exit_market") or ""
    if exit_market:
        currency = catalog.currency_for(str(exit_market), ReferenceSide.EXIT)
        if currency is not None:
            return currency
    entry_market = row.get("entry_market") or ""
    if entry_market:
        return catalog.currency_for(str(entry_market), ReferenceSide.ENTRY)
    return None


def resolve_auction_rate(
    auction_id: str,
    state: str,
    row: Mapping[str, object],
    *,
    storage: AuctionStorage,
    reference_catalog: PrismaReferenceCatalog = DEFAULT_PRISMA_REFERENCES,
    auction_lookup: PrismaAuctionLookup | None = None,
    page: object = None,
    ecb_source: EcbRateSource | None = None,
) -> RateResolutionResult:
    """Resolve (or reuse a cached resolution for) one Auction ID.

    A previously fixed cached result for `auction_id` is always reused as-is
    without repeating any PRISMA or ECB retrieval, regardless of `state`,
    `row`, or newer ECB data — this is what makes reprocessing the same
    Auction ID deterministic. Only a cache miss performs a new resolution
    attempt, which is committed atomically via `storage.save_rate_resolution`;
    a contradiction against data another concurrent resolution already fixed
    is reported as `RateResolutionOutcome.CONFLICT`, never silently
    overwritten.
    """
    cached = storage.get_rate_resolution(auction_id)
    if cached is not None:
        return RateResolutionResult(
            RateResolutionOutcome.RESOLVED,
            currency=cached.currency,
            rate_to_eur=Decimal(cached.rate_to_eur),
            rate_date=date.fromisoformat(cached.ecb_publication_date),
        )

    if state != FINISHED_STATE:
        return RateResolutionResult(
            RateResolutionOutcome.NOT_FINISHED,
            message=f"Auction ID {auction_id} state is {state!r}, not {FINISHED_STATE!r}.",
        )

    lookup = auction_lookup if auction_lookup is not None else PrismaAuctionLookup()
    try:
        record = lookup.lookup(page, auction_id)
    except PrismaAuctionLookupError as exc:
        return RateResolutionResult(
            RateResolutionOutcome.AUCTION_END_UNAVAILABLE, message=str(exc)
        )

    currency = _select_currency(row, reference_catalog)
    if currency is None:
        return RateResolutionResult(
            RateResolutionOutcome.CURRENCY_UNKNOWN,
            message=(
                f"No approved ISO 4217 currency metadata is recorded for "
                f"Auction ID {auction_id}'s resolved market/storage."
            ),
        )

    end_date = authoritative_end_date(record)
    try:
        ecb_result = resolve_rate_to_eur(currency, end_date, source=ecb_source)
    except EcbRateError as exc:
        return RateResolutionResult(
            RateResolutionOutcome.ECB_RATE_UNAVAILABLE, message=str(exc)
        )

    new_record = RateResolutionRecord(
        auction_id=auction_id,
        auction_state=state,
        auction_end_at=record.end_at.isoformat(),
        currency=ecb_result.currency,
        ecb_publication_date=ecb_result.publication_date.isoformat(),
        rate_to_eur=str(ecb_result.rate_to_eur),
        resolved_at_utc=datetime.now(timezone.utc).isoformat(timespec="microseconds"),
        source_version=SOURCE_VERSION,
    )
    try:
        saved = storage.save_rate_resolution(new_record)
    except RateResolutionConflictError as exc:
        return RateResolutionResult(RateResolutionOutcome.CONFLICT, message=str(exc))

    return RateResolutionResult(
        RateResolutionOutcome.RESOLVED,
        currency=saved.currency,
        rate_to_eur=Decimal(saved.rate_to_eur),
        rate_date=date.fromisoformat(saved.ecb_publication_date),
    )


def resolve_rates_for_rows(
    rows: Iterable[Mapping[str, object]],
    *,
    storage: AuctionStorage,
    reference_catalog: PrismaReferenceCatalog = DEFAULT_PRISMA_REFERENCES,
    auction_lookup: PrismaAuctionLookup | None = None,
    page: object = None,
    ecb_source: EcbRateSource | None = None,
) -> dict[str, RateResolutionResult]:
    """Resolve each unique Auction ID present in `rows` at most once.

    Multiple rows sharing the same Auction ID (for example several network
    points belonging to one auction) reuse a single resolution attempt and
    result; this is the "no uncontrolled network request per Mapping
    repaint" boundary for one processing operation. Rows with a blank
    `auction_id` are skipped (no eligible identity to resolve).
    """
    lookup = auction_lookup if auction_lookup is not None else PrismaAuctionLookup()
    results: dict[str, RateResolutionResult] = {}
    for row in rows:
        auction_id = row.get("auction_id")
        if not auction_id or auction_id in results:
            continue
        state = str(row.get("state", ""))
        results[str(auction_id)] = resolve_auction_rate(
            str(auction_id), state, row,
            storage=storage, reference_catalog=reference_catalog,
            auction_lookup=lookup, page=page, ecb_source=ecb_source,
        )
    return results
