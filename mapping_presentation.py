"""Qt-independent P.36.8 boundary: present already-resolved mapping evidence
from one completed P.36.15 import/transformation result.

Per `ROADMAP.md`'s "Authoritative output CSV contract", the mapping
presentation uses exactly this hierarchy and order: `Exit Market`,
`Entry Market`, `Network Point Name`, `TSO Name Exit`, `TSO Name Entry`. It
is a UI view only: it never adds, removes, renames, or reorders the 12-column
output CSV contract, and it never introduces a separate `Exit Storage`/
`Entry Storage` field.

This module performs no parsing, filtering, normalization, or side-specific
Market/Storage resolution of its own: `processor.import_prisma_export`
(P.33/P.36.4, reused unchanged by P.36.15) already implements and tests every
one of those authoritative rules, including exact side-specific evidence
resolution with no fuzzy, substring, geographic, identifier-only, TSO-name,
or cross-side matching. This module only selects and orders already-resolved
fields from one already-completed `processor.PrismaImportResult` into the
five-field presentation; it introduces no matching or inference of its own.
"""
from __future__ import annotations

from dataclasses import dataclass

from processor import PrismaImportResult

__all__ = ["MAPPING_DISPLAY_FIELDS", "MappingDisplayRow", "build_mapping_rows"]

# Authoritative P.36.8 mapping presentation hierarchy (ROADMAP.md "Authoritative
# output CSV contract"). Exact order and spelling; never add, remove, rename,
# or reorder, and never add a separate Exit Storage/Entry Storage field.
MAPPING_DISPLAY_FIELDS = (
    "Exit Market",
    "Entry Market",
    "Network Point Name",
    "TSO Name Exit",
    "TSO Name Entry",
)


@dataclass(frozen=True)
class MappingDisplayRow:
    """One immutable, already-resolved mapping presentation row."""

    exit_market: str
    entry_market: str
    network_point_name: str
    tso_name_exit: str
    tso_name_entry: str


def build_mapping_rows(import_result: PrismaImportResult) -> tuple[MappingDisplayRow, ...]:
    """Build the ordered P.36.8 presentation rows from one completed import.

    Only ``import_result.rows`` (the already-accepted, already-enriched rows)
    are considered, each mapped straight through in its own existing field
    values with no cross-side substitution. Row order is preserved exactly as
    produced by the import. A filtered/rejected-only import result (or any
    import with zero accepted rows) yields an empty tuple, never an error.
    """
    return tuple(
        MappingDisplayRow(
            exit_market=row["exit_market"],
            entry_market=row["entry_market"],
            network_point_name=row["network_point"],
            tso_name_exit=row["tso_exit"],
            tso_name_entry=row["tso_entry"],
        )
        for row in import_result.rows
    )
