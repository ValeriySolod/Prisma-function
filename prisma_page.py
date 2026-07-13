from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Mapping, Sequence

from auction_csv import AuctionCsvRecord


class PrismaPageAdapterError(RuntimeError):
    """Base failure raised by live PRISMA page access and parsing."""


class PrismaPageStructureError(PrismaPageAdapterError):
    """The live page does not expose the required auction table structure."""


class PrismaStatusParseError(PrismaPageAdapterError):
    """A live status value cannot be represented by the monitoring domain."""


class PrismaAuctionMatchError(PrismaPageAdapterError):
    """A CSV auction does not have exactly one matching live row."""


class PrismaPageUnavailableError(PrismaPageAdapterError):
    """The active browser page cannot service a live status request."""


@dataclass(frozen=True)
class PrismaAuctionRow:
    auction_id: str
    raw_status: str


REQUIRED_TABLE_HEADERS = {
    "auction_id": ("Auction ID",),
    # The checked-in PRISMA export calls this field State; Status is also the
    # user-facing name already used by the application's exported workbook.
    "status": ("State", "Status"),
}

_STATUS_BY_KEY = {
    "scheduled": "Scheduled",
    "open": "Open",
    "in progress": "In Progress",
    "completed": "Completed",
    "finished": "Completed",
    "cancelled": "Cancelled",
    "canceled": "Cancelled",
    "unknown": "Unknown",
    "error": "Error",
}


def normalize_page_text(value: str) -> str:
    """Collapse page whitespace while keeping parsing independent of Playwright."""
    return re.sub(r"\s+", " ", value or "").strip()


def normalize_prisma_status(raw_status: str) -> str:
    text = normalize_page_text(raw_status)
    if not text:
        raise PrismaStatusParseError("The live auction status is empty.")
    normalized = _STATUS_BY_KEY.get(text.casefold())
    if normalized is None:
        raise PrismaStatusParseError(
            f"Unsupported live auction status: {text}."
        )
    return normalized


def _header_key(value: str) -> str:
    return normalize_page_text(value).casefold()


def resolve_required_columns(headers: Sequence[str]) -> dict[str, int]:
    positions: dict[str, list[int]] = {}
    for index, header in enumerate(headers):
        positions.setdefault(_header_key(header), []).append(index)

    resolved: dict[str, int] = {}
    for field, aliases in REQUIRED_TABLE_HEADERS.items():
        matches = [
            index
            for alias in aliases
            for index in positions.get(_header_key(alias), [])
        ]
        if not matches:
            raise PrismaPageStructureError(
                f"The live auction table is missing the required column: {aliases[0]}."
            )
        if len(matches) != 1:
            raise PrismaPageStructureError(
                f"The live auction table has an ambiguous required column: {aliases[0]}."
            )
        resolved[field] = matches[0]
    return resolved


def parse_auction_rows(
    headers: Sequence[str], rows: Sequence[Sequence[str]]
) -> list[PrismaAuctionRow]:
    columns = resolve_required_columns(headers)
    required_width = max(columns.values()) + 1
    parsed: list[PrismaAuctionRow] = []
    for row_number, cells in enumerate(rows, start=1):
        if len(cells) < required_width:
            raise PrismaPageStructureError(
                f"Live auction row {row_number} does not contain all required cells."
            )
        auction_id = normalize_page_text(cells[columns["auction_id"]])
        status = normalize_page_text(cells[columns["status"]])
        if not auction_id:
            raise PrismaPageStructureError(
                f"Live auction row {row_number} has an empty Auction ID."
            )
        if not status:
            raise PrismaStatusParseError(
                f"Live auction row {row_number} has an empty status."
            )
        parsed.append(PrismaAuctionRow(auction_id, status))
    return parsed


def match_auction_row(
    record: AuctionCsvRecord, rows: Sequence[PrismaAuctionRow]
) -> PrismaAuctionRow:
    key = normalize_page_text(record.auction_id).casefold()
    matches = [
        row for row in rows
        if normalize_page_text(row.auction_id).casefold() == key
    ]
    if not matches:
        raise PrismaAuctionMatchError(
            f"No live auction row matches Auction ID {record.auction_id}."
        )
    if len(matches) > 1:
        raise PrismaAuctionMatchError(
            f"Multiple live auction rows match Auction ID {record.auction_id}."
        )
    return matches[0]


class PrismaPageReader:
    """Read auction rows through semantic Playwright table roles."""

    TIMEOUT_MS = 10_000

    def _read_table_headers(self, table) -> list[str]:
        """Use rendered header rows; PRISMA keeps empty ARIA sorting headers."""
        try:
            header_rows = table.locator("thead tr").all()
        except Exception:
            header_rows = []
        for row in header_rows:
            headers = row.locator("th").all_inner_texts()
            try:
                resolve_required_columns(headers)
                return headers
            except PrismaPageStructureError:
                continue

        headers = table.get_by_role("columnheader").all_inner_texts()
        resolve_required_columns(headers)
        return headers

    @staticmethod
    def _read_table_rows(table) -> list[list[str]]:
        try:
            body_rows = table.locator("tbody tr").all()
            rows = [row.locator("td").all_inner_texts() for row in body_rows]
            if rows:
                return rows
        except Exception:
            pass
        return [
            row.get_by_role("cell").all_inner_texts()
            for row in table.get_by_role("row").all()
        ]

    def read_rows(self, page) -> list[PrismaAuctionRow]:
        try:
            tables = page.get_by_role("table")
            table_count = tables.count()
        except Exception as exc:
            raise PrismaPageUnavailableError(
                "The active PRISMA page could not be inspected."
            ) from exc

        structure_errors: list[PrismaPageStructureError] = []
        for index in range(table_count):
            table = tables.nth(index)
            try:
                table.wait_for(state="visible", timeout=self.TIMEOUT_MS)
                headers = self._read_table_headers(table)
                columns = resolve_required_columns(headers)
            except PrismaPageStructureError as exc:
                structure_errors.append(exc)
                continue
            except Exception as exc:
                raise PrismaPageUnavailableError(
                    "The live PRISMA auction table could not be read."
                ) from exc

            try:
                raw_rows = self._read_table_rows(table)
                data_rows = [cells for cells in raw_rows if cells]
                # Reuse the pure parser; resolving above ensures this is the
                # intended table and keeps DOM access separate from parsing.
                return parse_auction_rows(headers, data_rows)
            except PrismaPageAdapterError:
                raise
            except Exception as exc:
                raise PrismaPageUnavailableError(
                    "The live PRISMA auction rows could not be read."
                ) from exc

        if table_count == 0:
            raise PrismaPageStructureError(
                "No live auction table was found on the PRISMA page."
            )
        if structure_errors:
            raise PrismaPageStructureError(
                "No live auction table contains the required Auction ID and State columns."
            )
        raise PrismaPageStructureError(
            "No usable live auction table was found on the PRISMA page."
        )

    def read_status(self, page, record: AuctionCsvRecord) -> str:
        row = match_auction_row(record, self.read_rows(page))
        return normalize_prisma_status(row.raw_status)


class LivePrismaStatusAdapter:
    """Monitoring adapter backed by the active BrowserController page."""

    def __init__(self, browser_controller) -> None:
        self._browser_controller = browser_controller

    def __call__(self, record: AuctionCsvRecord) -> str:
        return self._browser_controller.read_live_auction_status(record)
