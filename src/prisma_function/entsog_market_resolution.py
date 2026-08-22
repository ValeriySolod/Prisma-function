"""ENTSOG-based network-point market/storage reference resolution.

Resolves the Exit Market/Entry Market pair for one unidirectional PRISMA
Export CSV row whose Network Point Type (on the row's own `Direction` side)
is `BORDER_TRANSITION_POINT` or `RESERVOIR`, using the compact local ENTSOG
reference data in `entsog_reference_data.py`. See
`docs/entsog_reference_data.md` for the source data, snapshot date, exact
field meanings, and the resolution rules this module implements.

This module is a pure domain module: it performs no CSV parsing, no UI, and
no persistence, and never rejects a row -- every failure to resolve exactly
(a missing point EIC, an unrecognized TSO, an ENTSOG record with a blank
zone, an ambiguous match) simply returns a blank market for the affected
side, per the fail-closed rule that governs every reference resolution in
this application: never infer, never guess.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from prisma_function.entsog_reference_data import (
    curated_fallback_index,
    operator_key_by_tso_eic,
    operator_point_direction_index,
    prisma_tso_aliases,
)


class EntsogResolvedPointType(str, Enum):
    BORDER_TRANSITION_POINT = "BORDER_TRANSITION_POINT"
    RESERVOIR = "RESERVOIR"


_RESOLVED_POINT_TYPES = frozenset(item.value for item in EntsogResolvedPointType)

# Bacton (GB) Entry: PRISMA's own point EIC for this aggregated point,
# "48YBI-EC-------0", is also carried by ENTSOG's own operator-point-direction
# export for the unrelated Moffat (GB<->Ireland) interconnection under the
# same operator (National Gas Transmission PLC / UK-TSO-0001) and the same
# "entry" direction -- an ENTSOG source-data ambiguity, not a PRISMA one, that
# the exact (point_eic, operator_key, direction) curated-fallback key alone
# cannot disambiguate. Bacton's aggregated point can physically lead to either
# Belgium (ZTP) or the Netherlands (TTF), per the customer-approved decision
# to represent it with the combined "TTF/ZTP" label rather than leave it
# blank. Matched here, before any curated-fallback lookup, by the row's own
# exact "Network Point Name Entry" text -- the only evidence that actually
# distinguishes real Bacton PRISMA rows from the unrelated Moffat entry --
# so the pre-existing Moffat resolution is never affected.
_BACTON_ENTRY_POINT_NAME = "BactonUKEn (48YBI-EC-------0)"
_BACTON_ENTRY_MARKET = "TTF/ZTP"


@dataclass(frozen=True)
class EntsogMarketPair:
    """A resolved Exit Market/Entry Market pair. Either field may be `None`
    when only one side could be resolved exactly (e.g. a RESERVOIR row, or a
    BORDER_TRANSITION_POINT whose ENTSOG record only carries its own zone)."""

    exit_market: str | None
    entry_market: str | None


def _resolve_operator_identity(
    tso_eic: str, tso_name: str
) -> tuple[str | None, str | None]:
    """Return (operator_key, tso_eic_for_entsog_join).

    `tso_eic` (from the row's own `TSO EIC Exit/Entry` field) is authoritative
    for the ENTSOG join whenever present. `operator_key` is resolved first
    from that exact EIC via the local ENTSOG operator table; when that EIC is
    blank (PRISMA regularly omits it on Entry rows) or is not a recognized
    ENTSOG TSO EIC, `operator_key` -- and, only when `tso_eic` was itself
    blank, the EIC used for the ENTSOG join -- fall back to the exact,
    versioned PRISMA-TSO-name alias table. Never fuzzy, substring, country,
    or geographic matching.
    """
    operator_key: str | None = None
    if tso_eic:
        operator_key = operator_key_by_tso_eic().get(tso_eic)
    join_eic = tso_eic or None
    if operator_key is None and tso_name:
        alias = prisma_tso_aliases().get(tso_name)
        if alias is not None:
            operator_key, alias_eic = alias
            if join_eic is None:
                join_eic = alias_eic
    return operator_key, join_eic


def resolve_entsog_market_pair(
    *,
    point_eic: str,
    tso_eic: str,
    tso_name: str,
    direction: str,
    point_type: str,
    point_name: str = "",
) -> EntsogMarketPair | None:
    """Resolve one unidirectional row's Exit Market/Entry Market pair.

    ``direction`` must be the row's own resolved side, ``"exit"`` or
    ``"entry"`` (never ``"bundle"`` -- per the approved specification, a
    two-sided Exit/Entry row keeps its existing direct per-side resolution
    and never reaches this module). ``point_type`` is the row's own-side
    `Network Point Type Exit/Entry` value; any value other than
    `BORDER_TRANSITION_POINT`/`RESERVOIR` returns `None` immediately.

    Returns `None` when nothing can be resolved at all (never a partially
    populated result of all-`None` fields); otherwise returns an
    `EntsogMarketPair` whose individual fields may still be `None`.

    ``point_name`` (the row's own exact `Network Point Name Exit/Entry` text)
    is consulted only for the single explicit Bacton exception documented
    above; every other point is resolved exactly as before regardless of its
    name.
    """
    if point_type not in _RESOLVED_POINT_TYPES:
        return None
    if direction not in ("exit", "entry"):
        return None
    if direction == "entry" and point_name == _BACTON_ENTRY_POINT_NAME:
        return EntsogMarketPair(exit_market=None, entry_market=_BACTON_ENTRY_MARKET)
    if not point_eic:
        return None

    operator_key, join_eic = _resolve_operator_identity(tso_eic, tso_name)

    if operator_key is not None:
        curated = curated_fallback_index().get((point_eic, operator_key, direction))
        if curated is not None:
            return EntsogMarketPair(
                exit_market=curated.exit_market or None,
                entry_market=curated.entry_market or None,
            )

    if not join_eic:
        return None
    record = operator_point_direction_index().get((point_eic, join_eic, direction))
    if record is None:
        return None

    own_zone = record.own_zone or None
    adjacent_zone = record.adjacent_zone or None

    if point_type == EntsogResolvedPointType.RESERVOIR.value:
        if own_zone is None:
            return None
        if direction == "exit":
            return EntsogMarketPair(exit_market=own_zone, entry_market=None)
        return EntsogMarketPair(exit_market=None, entry_market=own_zone)

    # BORDER_TRANSITION_POINT: the row's own side gets the TSO's own
    # balancing zone; the opposite side gets the adjacent zone, per the
    # approved specification. Either may stay blank when ENTSOG's own record
    # is itself incomplete -- never guessed from the other side.
    if own_zone is None and adjacent_zone is None:
        return None
    if direction == "exit":
        return EntsogMarketPair(exit_market=own_zone, entry_market=adjacent_zone)
    return EntsogMarketPair(exit_market=adjacent_zone, entry_market=own_zone)
