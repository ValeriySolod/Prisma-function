"""Loader for the compact, local ENTSOG reference-data resources checked into
`prisma_function/resources/entsog/`.

See `docs/entsog_reference_data.md` for the source URLs, snapshot date, exact
field meanings, and refresh procedure for every file loaded here. This module
performs no network access: it only reads the already-fetched, already-
compacted JSON resources bundled with the application.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from importlib import resources
from types import MappingProxyType
from typing import Mapping

_RESOURCE_PACKAGE = "prisma_function.resources.entsog"


def _load_json(filename: str):
    with resources.files(_RESOURCE_PACKAGE).joinpath(filename).open(
        "r", encoding="utf-8"
    ) as handle:
        return json.load(handle)


@dataclass(frozen=True)
class OperatorPointDirection:
    """One ENTSOG operator-point-direction record, trimmed to the fields this
    application resolves market/storage references with."""

    point_eic: str
    operator_key: str
    tso_eic: str
    direction: str
    own_zone: str
    adjacent_zone: str
    adjacent_country: str
    point_type: str
    point_label: str


@dataclass(frozen=True)
class EntsogOperator:
    operator_key: str
    tso_eic: str
    short_name: str
    long_name: str
    country: str


@dataclass(frozen=True)
class CuratedFallbackEntry:
    point_eic: str
    operator_key: str
    direction: str
    exit_market: str
    entry_market: str
    route: str
    source_url: str


@lru_cache(maxsize=1)
def operator_point_directions() -> tuple[OperatorPointDirection, ...]:
    raw = _load_json("operator_point_directions.json")
    return tuple(
        OperatorPointDirection(
            point_eic=r["point_eic"],
            operator_key=r["operator_key"],
            tso_eic=r["tso_eic"],
            direction=r["direction"],
            own_zone=r["own_zone"],
            adjacent_zone=r["adjacent_zone"],
            adjacent_country=r["adjacent_country"],
            point_type=r["point_type"],
            point_label=r["point_label"],
        )
        for r in raw
    )


@lru_cache(maxsize=1)
def operator_point_direction_index() -> Mapping[tuple[str, str, str], OperatorPointDirection]:
    """Index keyed by the exact (point_eic, tso_eic, direction) resolution key."""
    index: dict[tuple[str, str, str], OperatorPointDirection] = {}
    for record in operator_point_directions():
        key = (record.point_eic, record.tso_eic, record.direction)
        # Keep the first record for a given key; the compact export has no
        # duplicate (point_eic, tso_eic, direction) triples in practice.
        index.setdefault(key, record)
    return MappingProxyType(index)


@lru_cache(maxsize=1)
def operators() -> tuple[EntsogOperator, ...]:
    raw = _load_json("operators.json")
    return tuple(
        EntsogOperator(
            operator_key=r["operator_key"],
            tso_eic=r["tso_eic"],
            short_name=r["short_name"],
            long_name=r["long_name"],
            country=r["country"],
        )
        for r in raw
    )


@lru_cache(maxsize=1)
def operator_key_by_tso_eic() -> Mapping[str, str]:
    """Reverse index from an ENTSOG TSO EIC to its operatorKey."""
    index: dict[str, str] = {}
    for operator in operators():
        index.setdefault(operator.tso_eic, operator.operator_key)
    return MappingProxyType(index)


@lru_cache(maxsize=1)
def prisma_tso_aliases() -> Mapping[str, tuple[str, str]]:
    """Exact PRISMA 'TSO Entry' display name -> (operator_key, tso_eic).

    Used only for Entry-side rows where PRISMA leaves 'TSO EIC Entry' blank;
    see `docs/entsog_reference_data.md` for the exact evidence and the known
    gap versus the approved specification's "29 observed" count.
    """
    raw = _load_json("prisma_tso_aliases.json")
    return MappingProxyType(
        {
            entry["prisma_tso_name"]: (entry["operator_key"], entry["tso_eic"])
            for entry in raw["aliases"]
        }
    )


@lru_cache(maxsize=1)
def curated_fallback_index() -> Mapping[tuple[str, str, str], CuratedFallbackEntry]:
    """Index keyed by the exact (point_eic, operator_key, direction) resolution
    key, for the customer-approved fallback routes documented in
    `docs/entsog_reference_data.md`."""
    raw = _load_json("curated_fallback_routes.json")
    index: dict[tuple[str, str, str], CuratedFallbackEntry] = {}
    for route in raw["routes"]:
        for entry in route["entries"]:
            key = (entry["point_eic"], entry["operator_key"], entry["direction"])
            index[key] = CuratedFallbackEntry(
                point_eic=entry["point_eic"],
                operator_key=entry["operator_key"],
                direction=entry["direction"],
                exit_market=entry["exit_market"],
                entry_market=entry["entry_market"],
                route=route["route"],
                source_url=route["source_url"],
            )
    return MappingProxyType(index)


@lru_cache(maxsize=1)
def balancing_zones() -> tuple[dict, ...]:
    return tuple(_load_json("balancing_zones.json"))


@lru_cache(maxsize=1)
def interconnections() -> tuple[dict, ...]:
    return tuple(_load_json("interconnections.json"))


@lru_cache(maxsize=1)
def aggregate_interconnections() -> tuple[dict, ...]:
    return tuple(_load_json("aggregate_interconnections.json"))
