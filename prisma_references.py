from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Iterable, Mapping


class ReferenceClassification(str, Enum):
    MARKET = "market"
    STORAGE = "storage"


class ReferenceSide(str, Enum):
    EXIT = "exit"
    ENTRY = "entry"


@dataclass(frozen=True)
class ReferenceAlias:
    source_value: str
    side: ReferenceSide


@dataclass(frozen=True)
class PrismaReference:
    canonical_name: str
    classification: ReferenceClassification
    aliases: tuple[ReferenceAlias, ...]


def normalize_reference_alias(value: str) -> str:
    """Normalize only surrounding whitespace and case for explicit aliases."""
    return value.strip().casefold()


class PrismaReferenceCatalog:
    """Immutable, side-aware index of explicitly declared PRISMA aliases."""

    def __init__(self, entries: Iterable[PrismaReference]) -> None:
        immutable_entries = tuple(entries)
        index: dict[tuple[ReferenceSide, str], PrismaReference] = {}
        canonical_names: set[str] = set()
        for entry in immutable_entries:
            if not entry.canonical_name.strip():
                raise ValueError("Reference canonical names must not be blank.")
            if entry.canonical_name != entry.canonical_name.strip():
                raise ValueError(
                    "Reference canonical names must not have surrounding whitespace."
                )
            canonical_key = entry.canonical_name.strip().casefold()
            if canonical_key in canonical_names:
                raise ValueError(
                    f"Duplicate reference canonical name: {entry.canonical_name}."
                )
            canonical_names.add(canonical_key)
            for alias in entry.aliases:
                normalized = normalize_reference_alias(alias.source_value)
                if not normalized:
                    raise ValueError("Reference aliases must not be blank.")
                key = (alias.side, normalized)
                if key in index:
                    raise ValueError(
                        "Conflicting or duplicate reference alias for "
                        f"{alias.side.value}: {alias.source_value}."
                    )
                index[key] = entry
        self._entries = immutable_entries
        self._index: Mapping[tuple[ReferenceSide, str], PrismaReference] = (
            MappingProxyType(index)
        )

    @property
    def entries(self) -> tuple[PrismaReference, ...]:
        return self._entries

    def lookup(self, source_value: str, side: ReferenceSide) -> PrismaReference | None:
        return self._index.get((side, normalize_reference_alias(source_value)))


def _market(
    canonical_name: str, *, exit_aliases: tuple[str, ...] = (), entry_aliases: tuple[str, ...] = ()
) -> PrismaReference:
    aliases = tuple(ReferenceAlias(value, ReferenceSide.EXIT) for value in exit_aliases)
    aliases += tuple(ReferenceAlias(value, ReferenceSide.ENTRY) for value in entry_aliases)
    return PrismaReference(canonical_name, ReferenceClassification.MARKET, aliases)


def _storage(canonical_name: str, *aliases: str) -> PrismaReference:
    side_aliases = tuple(
        ReferenceAlias(value, side)
        for value in aliases
        for side in (ReferenceSide.EXIT, ReferenceSide.ENTRY)
    )
    return PrismaReference(
        canonical_name, ReferenceClassification.STORAGE, side_aliases
    )


# Deliberately small seed catalog. Market aliases are the exact network-point
# mappings checked into mapping.csv. The storage alias is evidenced by the
# checked-in Auction_overview.csv export. Add entries only from confirmed source
# data; the constructor rejects every duplicate side/alias pair.
DEFAULT_PRISMA_REFERENCES = PrismaReferenceCatalog(
    (
        _market(
            "BG",
            exit_aliases=("Kulata (BG)/Sidirokastron (GR)", "Kireevo (BG) / Zaychar (RS)"),
        ),
        _market("HTP", entry_aliases=("Kulata (BG)/Sidirokastron (GR)",)),
        _market("RS", entry_aliases=("Kireevo (BG) / Zaychar (RS)",)),
        _market(
            "CEGH",
            exit_aliases=(
                "Mosonmagyarovar (AT) / Mosonmagyaróvár (HU)",
                "Arnoldstein Exit",
                "Baumgarten WAG AT->SK",
            ),
        ),
        _market("MGP", entry_aliases=("Mosonmagyarovar (AT) / Mosonmagyaróvár (HU)",)),
        _market("PSV", entry_aliases=("Arnoldstein Exit",)),
        _market("SK", entry_aliases=("Baumgarten WAG AT->SK",)),
        _storage("VGS Storage Hub", "VGS Storage Hub (4290)"),
    )
)
