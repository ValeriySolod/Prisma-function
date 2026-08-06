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

Per P.36.18, the presentation orders rows by `Flow Start` descending (latest
first), parsed from each row's already-parsed `flow_start` value (an ISO
datetime string produced by `processor._parse_row`/`_parse_date` from the
authoritative `DD.MM.YYYY HH:MM` PRISMA export contract), never by lexical
comparison of a formatted string. This affects only the order rows are
displayed in; `import_result.rows` itself, the 12-column output CSV, and
publication order are untouched.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

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


def _flow_start_sort_key(row: dict[str, Any]) -> datetime:
    return datetime.fromisoformat(row["flow_start"])


def build_mapping_rows(import_result: PrismaImportResult) -> tuple[MappingDisplayRow, ...]:
    """Build the ordered P.36.18 presentation rows from one completed import.

    Only ``import_result.rows`` (the already-accepted, already-enriched rows)
    are considered, each mapped straight through in its own existing field
    values with no cross-side substitution. Rows are ordered by ``flow_start``
    descending (the latest Flow Start first), parsed chronologically rather
    than compared as formatted strings; equal ``flow_start`` values retain
    their original import order, since ``sorted()`` is stable and reversing
    it does not disturb tie order. ``import_result.rows`` itself is read, not
    mutated, so this presentation ordering never affects the accepted rows,
    the 12-column output CSV, or publication order. A filtered/rejected-only
    import result (or any import with zero accepted rows) yields an empty
    tuple, never an error.
    """
    ordered_rows = sorted(import_result.rows, key=_flow_start_sort_key, reverse=True)
    return tuple(
        MappingDisplayRow(
            exit_market=row["exit_market"],
            entry_market=row["entry_market"],
            network_point_name=row["network_point"],
            tso_name_exit=row["tso_exit"],
            tso_name_entry=row["tso_entry"],
        )
        for row in ordered_rows
    )
