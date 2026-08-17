from __future__ import annotations

import json
import math
import os
import sqlite3
import tempfile
import uuid
from contextlib import closing, contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

import pandas as pd
from openpyxl import load_workbook
from openpyxl.utils import get_column_letter

from prisma_references import (
    DEFAULT_PRISMA_REFERENCES,
    PrismaReferenceCatalog,
    ReferenceSide,
)


class AuctionStorageError(RuntimeError):
    pass


class HistoricalBackfillStatus(str, Enum):
    UPDATED = "updated"
    ALREADY_COMPLETE = "unchanged/already_complete"
    UNRESOLVABLE = "skipped/unresolvable"
    CONFLICT = "conflict"
    INVALID = "invalid"


@dataclass(frozen=True)
class HistoricalBackfillAudit:
    run_id: str
    auction_row_id: int
    row_position: int
    auction_id: str
    row_key: str
    previous_exit_market: str | None
    previous_entry_market: str | None
    proposed_exit_market: str | None
    proposed_entry_market: str | None
    final_exit_market: str | None
    final_entry_market: str | None
    status: HistoricalBackfillStatus
    reason_code: str
    message: str
    changed: bool


@dataclass(frozen=True)
class HistoricalBackfillSummary:
    run_id: str
    examined: int
    updated: int
    unchanged: int
    skipped: int
    conflicts: int
    invalid: int
    committed: bool
    audit: tuple[HistoricalBackfillAudit, ...]


class RateResolutionConflictError(AuctionStorageError):
    """A previously fixed P.36.19 rate resolution contradicts newly retrieved
    authoritative data. The previously fixed result is never silently
    overwritten."""


@dataclass(frozen=True)
class RateResolutionRecord:
    """One deterministically fixed P.36.19 auction-end/currency/ECB-rate
    resolution, keyed by Auction ID, sufficient to audit the resolution
    safely without repeating the PRISMA/ECB lookups it required."""

    auction_id: str
    auction_state: str
    auction_end_at: str
    currency: str
    ecb_publication_date: str
    rate_to_eur: str
    resolved_at_utc: str
    source_version: str


class EcbAuctionDateRateConflictError(AuctionStorageError):
    """A previously fixed P.37 (auction_date, currency) rate resolution
    contradicts newly retrieved authoritative ECB data. The previously fixed
    result is never silently overwritten."""


@dataclass(frozen=True)
class EcbAuctionDateRateRecord:
    """One deterministically fixed P.37 ECB rate-to-EUR resolution, keyed by
    (auction_date, currency) -- the calendar date parsed from a row's own
    `Start of Auction` and a price field's own CSV-unit-derived ISO 4217
    currency -- sufficient to audit the resolution safely without repeating
    the ECB lookup. Independent of, and never mixed with,
    `RateResolutionRecord`'s Auction-ID-keyed P.36.19 table, which continues
    to serve only the Mapping UI's own Currency/Rate to EUR/Rate Date
    columns."""

    auction_date: str
    currency: str
    ecb_publication_date: str
    rate_to_eur: str
    resolved_at_utc: str
    source_version: str


class AuctionStorage:
    AUCTION_IDENTITY_FIELDS = (
        "auction_id", "network_point_id", "direction", "flow_start", "flow_end",
    )
    AUCTION_PERSISTED_FIELDS = (
        "auction_id", "auction_date", "exit_market", "entry_market", "direction",
        "network_point", "network_point_id", "tso_exit", "tso_entry", "product_type",
        "flow_start", "flow_end", "booked_capacity_kwh_h", "runtime_hours",
        "tariff_eur_mwh_h", "premium_eur_mwh_h", "state",
    )
    # This pre-P.36 `auctions` table/Excel export predates, and is explicitly
    # out of scope for, the P.36.21 strict-EUR-normalization contract (see
    # ROADMAP.md): it still persists the physical-unit-normalized
    # source-currency price under its original historical column names,
    # never reinterpreted as confirmed EUR. `processor.py` was corrected by
    # P.36.21 to stop mislabeling that same value as EUR in its own row
    # shape (`tariff_source_mwh_h`/`premium_source_mwh_h`); this mapping
    # translates those corrected field names back to this table's unchanged
    # legacy columns so this unrelated, unconverted persistence path keeps
    # working unmodified.
    _LEGACY_PRICE_FIELD_ALIASES = {
        "tariff_source_mwh_h": "tariff_eur_mwh_h",
        "premium_source_mwh_h": "premium_eur_mwh_h",
    }
    AUDIT_ROW_INDEX = "idx_historical_market_storage_audit_auction_row_id"
    EXPERIMENTAL_AUDIT_COLUMNS = (
        ("auction_row_id", "INTEGER", 0, None, 1),
    )
    RUNS_SQL = """CREATE TABLE historical_market_storage_runs (
        run_id TEXT PRIMARY KEY,
        run_timestamp_utc TEXT NOT NULL,
        examined INTEGER NOT NULL, updated INTEGER NOT NULL,
        unchanged INTEGER NOT NULL, skipped INTEGER NOT NULL,
        conflicts INTEGER NOT NULL, invalid INTEGER NOT NULL,
        status TEXT NOT NULL CHECK(status = 'committed'),
        CHECK(examined = updated + unchanged + skipped + conflicts + invalid)
    )"""
    AUDIT_SQL = """CREATE TABLE historical_market_storage_audit (
        run_id TEXT NOT NULL,
        auction_row_id INTEGER NOT NULL,
        row_position INTEGER NOT NULL,
        auction_id TEXT NOT NULL,
        row_key TEXT NOT NULL,
        previous_exit_market TEXT,
        previous_entry_market TEXT,
        proposed_exit_market TEXT,
        proposed_entry_market TEXT,
        final_exit_market TEXT,
        final_entry_market TEXT,
        status TEXT NOT NULL,
        reason_code TEXT NOT NULL,
        message TEXT NOT NULL,
        changed INTEGER NOT NULL CHECK(changed IN (0, 1)),
        PRIMARY KEY(run_id, auction_row_id),
        UNIQUE(run_id, row_position),
        FOREIGN KEY(run_id) REFERENCES historical_market_storage_runs(run_id)
            ON DELETE RESTRICT,
        FOREIGN KEY(auction_row_id) REFERENCES auctions(id)
            ON DELETE RESTRICT
    )"""
    EXCEL_COLUMNS = (
        "Auction Date", "Exit Market/Storage", "Entry Market/Storage",
        "Capacity Type", "Network Point Name", "Product Type", "Flow Start",
        "Flow End", "Booked Capacity, kWh/h", "Runtime Hours",
        "Tariff, EUR/MWh/h", "Premium, EUR/MWh/h", "Auction ID",
        "TSO Exit", "TSO Entry", "Status",
    )
    EXCEL_COLUMN_WIDTHS = {
        "Auction Date": 21,
        "Exit Market/Storage": 22,
        "Entry Market/Storage": 22,
        "Capacity Type": 15,
        "Network Point Name": 36,
        "Product Type": 14,
        "Flow Start": 21,
        "Flow End": 21,
        "Booked Capacity, kWh/h": 24,
        "Runtime Hours": 15,
        "Tariff, EUR/MWh/h": 20,
        "Premium, EUR/MWh/h": 21,
        "Auction ID": 16,
        "TSO Exit": 30,
        "TSO Entry": 30,
        "Status": 14,
    }
    EXCEL_WIDTH_TOLERANCE = 1e-6
    RATE_RESOLUTION_FIELDS = (
        "auction_id", "auction_state", "auction_end_at", "currency",
        "ecb_publication_date", "rate_to_eur", "resolved_at_utc", "source_version",
    )
    RATE_RESOLUTIONS_SQL = """CREATE TABLE IF NOT EXISTS auction_rate_resolutions (
        auction_id TEXT PRIMARY KEY,
        auction_state TEXT NOT NULL,
        auction_end_at TEXT NOT NULL,
        currency TEXT NOT NULL,
        ecb_publication_date TEXT NOT NULL,
        rate_to_eur TEXT NOT NULL,
        resolved_at_utc TEXT NOT NULL,
        source_version TEXT NOT NULL
    )"""
    ECB_AUCTION_DATE_RATE_FIELDS = (
        "auction_date", "currency", "ecb_publication_date",
        "rate_to_eur", "resolved_at_utc", "source_version",
    )
    ECB_AUCTION_DATE_RATES_SQL = """CREATE TABLE IF NOT EXISTS ecb_auction_date_rates (
        auction_date TEXT NOT NULL,
        currency TEXT NOT NULL,
        ecb_publication_date TEXT NOT NULL,
        rate_to_eur TEXT NOT NULL,
        resolved_at_utc TEXT NOT NULL,
        source_version TEXT NOT NULL,
        PRIMARY KEY (auction_date, currency)
    )"""
    # P.37: row-dict keys `processor.py` produces that describe the
    # side-specific source-currency price/currency breakdown, needed by
    # `price_normalization.py` but not part of the dormant `auctions` table
    # schema. Dropped by `_translate_legacy_price_fields` before a row ever
    # reaches `_upsert_rows`, whose INSERT/UPDATE column list is built
    # directly from the row dict's own keys.
    _P37_ONLY_FIELDS = (
        "tariff_exit_source_mwh_h", "tariff_exit_currency",
        "tariff_entry_source_mwh_h", "tariff_entry_currency",
        "premium_currency",
    )
    # P.40 correction (2026-08-17, real-Windows validation finding): the
    # source-operation ledger's identity moved from `UNIQUE(source_date)` to
    # `UNIQUE(sha256)`. Rejecting a second distinct import for a date that
    # already has an accepted source was the exact regression this corrects;
    # row-level idempotence is provided exclusively by
    # `published_output_row_keys` below, never by this ledger, so multiple
    # genuinely different CSV files sharing a source date must never
    # conflict here. `sha256` is still consulted (never source_date) so a
    # literal exact-content retry of a still in-flight or already-accepted
    # operation resumes/short-circuits instead of creating a redundant
    # duplicate ledger row for identical bytes.
    SOURCE_OPERATIONS_SQL = """CREATE TABLE IF NOT EXISTS prisma_source_operations (
        operation_id TEXT PRIMARY KEY,
        source_date TEXT NOT NULL,
        source_name TEXT NOT NULL,
        sha256 TEXT NOT NULL,
        status TEXT NOT NULL CHECK(status IN ('pending','data_committed','accepted')),
        summary_json TEXT,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(sha256)
    )"""
    # P.40 composite-key cumulative-publication identity boundary: "Auction
    # ID + Network Point Name + Capacity Type" is the exact, sole persistent
    # row key `prisma_publication.publish_cumulative_output` uses to decide
    # whether an incoming row already has a durably published counterpart,
    # across sessions and across otherwise-unrelated source files/dates. The
    # PRIMARY KEY enforces this at the database level for every row this
    # table ever records; there is no separate content-based key. This table
    # is created additively (`CREATE TABLE IF NOT EXISTS`) so an existing
    # database predating this increment opens safely with no rewrite of any
    # other table; rows already published under the pre-P.40 exact-full-row
    # rule have no key here until the next time their source is processed
    # (a documented, one-time transitional limit — see
    # `prisma_publication.py`'s module docstring for the full contract,
    # including the immutable-row, never-update-only-skip policy).
    PUBLISHED_OUTPUT_KEYS_SQL = """CREATE TABLE IF NOT EXISTS published_output_row_keys (
        auction_id TEXT NOT NULL,
        network_point_name TEXT NOT NULL,
        capacity_type TEXT NOT NULL,
        recorded_at_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (auction_id, network_point_name, capacity_type)
    )"""

    def __init__(self, database_path: Path) -> None:
        database_path.parent.mkdir(parents=True, exist_ok=True)
        self.database_path = database_path
        self._create_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        if connection.execute("PRAGMA foreign_keys").fetchone()[0] != 1:
            primary = AuctionStorageError(
                "SQLite foreign key enforcement could not be enabled."
            )
            try:
                connection.close()
            except BaseException as close_error:
                self._add_exception_note(
                    primary, f"Connection close also failed: {close_error!r}"
                )
            raise primary
        return connection

    @staticmethod
    def _add_exception_note(primary: BaseException, diagnostic: str) -> None:
        """Attach failure context without ever replacing the primary exception."""
        try:
            add_note = getattr(primary, "add_note", None)
            if callable(add_note):
                add_note(diagnostic)
        except BaseException:
            pass

    @contextmanager
    def _connection(self):
        """Close one production connection without masking an active failure."""
        connection = self._connect()
        try:
            yield connection
        except BaseException as primary:
            try:
                connection.close()
            except BaseException as close_error:
                self._add_exception_note(
                    primary, f"Connection close also failed: {close_error!r}"
                )
            raise
        else:
            connection.close()

    @staticmethod
    @contextmanager
    def _transaction(connection: sqlite3.Connection):
        try:
            yield connection
            connection.commit()
        except BaseException as primary:
            try:
                connection.rollback()
            except BaseException as rollback_error:
                AuctionStorage._add_exception_note(
                    primary, f"Transaction rollback also failed: {rollback_error!r}"
                )
            raise

    @staticmethod
    def _after_schema_reservation(connection: sqlite3.Connection) -> None:
        """Private coordination seam used after the initialization write reservation."""

    def _create_schema(self) -> None:
        with self._connection() as connection, self._transaction(connection):
            connection.execute("BEGIN IMMEDIATE")
            self._after_schema_reservation(connection)
            for statement in (
                    """
                CREATE TABLE IF NOT EXISTS auctions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    auction_id TEXT NOT NULL, auction_date TEXT NOT NULL,
                    exit_market TEXT NOT NULL DEFAULT '', entry_market TEXT NOT NULL DEFAULT '',
                    direction TEXT NOT NULL, network_point TEXT NOT NULL,
                    network_point_id TEXT NOT NULL DEFAULT '', tso_exit TEXT NOT NULL DEFAULT '',
                    tso_entry TEXT NOT NULL DEFAULT '', product_type TEXT NOT NULL,
                    flow_start TEXT NOT NULL, flow_end TEXT NOT NULL,
                    booked_capacity_kwh_h REAL NOT NULL, runtime_hours REAL NOT NULL,
                    tariff_eur_mwh_h REAL NOT NULL, premium_eur_mwh_h REAL NOT NULL,
                    state TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE (auction_id, network_point_id, direction, flow_start, flow_end)
                )""",
                    self.RATE_RESOLUTIONS_SQL,
                    self.ECB_AUCTION_DATE_RATES_SQL,
                    self.PUBLISHED_OUTPUT_KEYS_SQL,
            ):
                connection.execute(statement)
            self._ensure_source_operations_schema(connection)
            self._ensure_historical_schema(connection)

    @staticmethod
    def _table_columns(connection: sqlite3.Connection, table: str) -> tuple[tuple[Any, ...], ...]:
        return tuple(
            (row[1], row[2], row[3], row[4], row[5])
            for row in connection.execute(f"PRAGMA table_info({table})")
        )

    @staticmethod
    def _foreign_keys(connection: sqlite3.Connection, table: str) -> tuple[tuple[Any, ...], ...]:
        return tuple(sorted(tuple(row[2:8]) for row in connection.execute(
            f"PRAGMA foreign_key_list({table})"
        )))

    @staticmethod
    def _indexes(connection: sqlite3.Connection, table: str) -> tuple[tuple[Any, ...], ...]:
        result = []
        for row in connection.execute(f"PRAGMA index_list({table})"):
            columns = tuple(item[2] for item in connection.execute(
                f"PRAGMA index_info({row[1]})"
            ))
            result.append((row[1], row[2], row[3], columns))
        return tuple(sorted(result))

    @classmethod
    def _schema_fingerprint(cls, connection: sqlite3.Connection) -> tuple[Any, ...]:
        return (
            cls._table_columns(connection, "historical_market_storage_runs"),
            cls._foreign_keys(connection, "historical_market_storage_runs"),
            cls._indexes(connection, "historical_market_storage_runs"),
            cls._table_columns(connection, "historical_market_storage_audit"),
            cls._foreign_keys(connection, "historical_market_storage_audit"),
            cls._indexes(connection, "historical_market_storage_audit"),
        )

    @classmethod
    def _create_historical_tables(cls, connection: sqlite3.Connection) -> None:
        connection.execute(cls.RUNS_SQL)
        connection.execute(cls.AUDIT_SQL)
        connection.execute(
            f"CREATE INDEX {cls.AUDIT_ROW_INDEX} "
            "ON historical_market_storage_audit(auction_row_id)"
        )

    @classmethod
    def _expected_historical_fingerprint(cls) -> tuple[Any, ...]:
        with closing(sqlite3.connect(":memory:")) as expected:
            expected.execute("CREATE TABLE auctions (id INTEGER PRIMARY KEY)")
            cls._create_historical_tables(expected)
            return cls._schema_fingerprint(expected)

    @classmethod
    def _ensure_source_operations_schema(cls, connection: sqlite3.Connection) -> None:
        """Create `prisma_source_operations`, migrating a pre-P.40-correction
        database in place.

        A database created before this correction has `UNIQUE(source_date)`
        baked into the table itself; `CREATE TABLE IF NOT EXISTS` is a no-op
        against an already-existing table, so it alone cannot lift that
        constraint on an existing installation — exactly the database state
        that reproduced the real-Windows regression this corrects. When the
        old constraint is detected, the table is losslessly rebuilt under
        `SOURCE_OPERATIONS_SQL`'s `UNIQUE(sha256)` identity within the same
        transaction `_create_schema` already holds, so this either fully
        applies or leaves the database completely unchanged.
        """
        existing_sql = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='prisma_source_operations'"
        ).fetchone()
        if existing_sql is None:
            connection.execute(cls.SOURCE_OPERATIONS_SQL)
            return
        normalized = "".join((existing_sql[0] or "").split())
        if "UNIQUE(source_date)" not in normalized:
            return
        connection.execute(
            "ALTER TABLE prisma_source_operations RENAME TO prisma_source_operations_pre_p40"
        )
        connection.execute(cls.SOURCE_OPERATIONS_SQL)
        connection.execute(
            "INSERT OR IGNORE INTO prisma_source_operations "
            "(operation_id, source_date, source_name, sha256, status, summary_json, "
            "created_at, updated_at) "
            "SELECT operation_id, source_date, source_name, sha256, status, summary_json, "
            "created_at, updated_at FROM prisma_source_operations_pre_p40"
        )
        connection.execute("DROP TABLE prisma_source_operations_pre_p40")

    @classmethod
    def _ensure_historical_schema(cls, connection: sqlite3.Connection) -> None:
        audit_exists = bool(cls._table_columns(connection, "historical_market_storage_audit"))
        runs_exists = bool(cls._table_columns(connection, "historical_market_storage_runs"))
        if not audit_exists and not runs_exists:
            cls._create_historical_tables(connection)
            return
        experimental = (
            not runs_exists
            and cls._table_columns(connection, "historical_market_storage_audit")
            == cls.EXPERIMENTAL_AUDIT_COLUMNS
            and not cls._foreign_keys(connection, "historical_market_storage_audit")
            and not cls._indexes(connection, "historical_market_storage_audit")
        )
        if experimental:
            connection.execute("DROP TABLE historical_market_storage_audit")
            cls._create_historical_tables(connection)
            return
        if cls._schema_fingerprint(connection) != cls._expected_historical_fingerprint():
            raise AuctionStorageError(
                "Unknown or partial historical Market / Storage schema; database unchanged."
            )

    def historical_market_storage_audit(self) -> list[sqlite3.Row]:
        with self._connection() as connection:
            return list(connection.execute(
                "SELECT a.* FROM historical_market_storage_audit AS a "
                "JOIN historical_market_storage_runs AS r USING(run_id) "
                "ORDER BY r.rowid, a.row_position"
            ))

    def historical_market_storage_runs(self) -> list[sqlite3.Row]:
        with self._connection() as connection:
            return list(connection.execute(
                "SELECT * FROM historical_market_storage_runs ORDER BY rowid"
            ))

    def backfill_historical_market_storage(
        self,
        catalog: PrismaReferenceCatalog = DEFAULT_PRISMA_REFERENCES,
    ) -> HistoricalBackfillSummary:
        """Explicitly backfill missing historical Market / Storage values atomically."""
        run_id = uuid.uuid4().hex
        run_timestamp = datetime.now(timezone.utc).isoformat(timespec="microseconds")
        audit: list[HistoricalBackfillAudit] = []
        with self._connection() as connection, self._transaction(connection):
            connection.execute("BEGIN IMMEDIATE")
            rows = connection.execute("SELECT * FROM auctions ORDER BY id").fetchall()
            for position, row in enumerate(rows, start=1):
                item = self._resolve_historical_market_storage(
                    row, catalog, run_id, position
                )
                audit.append(item)
            counts = self._historical_backfill_counts(audit)
            connection.execute(
                "INSERT INTO historical_market_storage_runs "
                "(run_id, run_timestamp_utc, examined, updated, unchanged, skipped, "
                "conflicts, invalid, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'committed')",
                (run_id, run_timestamp, len(audit), *counts),
            )
            for item in audit:
                if item.changed:
                    connection.execute(
                        "UPDATE auctions SET exit_market=?, entry_market=?, "
                        "updated_at=CURRENT_TIMESTAMP WHERE id=?",
                        (item.final_exit_market, item.final_entry_market,
                         item.auction_row_id),
                    )
                connection.execute(
                    "INSERT INTO historical_market_storage_audit "
                    "(run_id, auction_row_id, row_position, auction_id, row_key, "
                    "previous_exit_market, previous_entry_market, proposed_exit_market, "
                    "proposed_entry_market, final_exit_market, final_entry_market, "
                    "status, reason_code, message, changed) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        item.run_id, item.auction_row_id, item.row_position,
                        item.auction_id, item.row_key, item.previous_exit_market,
                        item.previous_entry_market, item.proposed_exit_market,
                        item.proposed_entry_market, item.final_exit_market,
                        item.final_entry_market, item.status.value, item.reason_code,
                        item.message, int(item.changed),
                    ),
                )
            self._validate_historical_backfill(connection, audit, run_id)
        counts_by_status = {
            HistoricalBackfillStatus.UPDATED: 0,
            HistoricalBackfillStatus.ALREADY_COMPLETE: 0,
            HistoricalBackfillStatus.UNRESOLVABLE: 0,
            HistoricalBackfillStatus.CONFLICT: 0,
            HistoricalBackfillStatus.INVALID: 0,
        }
        for item in audit:
            counts_by_status[item.status] += 1
        return HistoricalBackfillSummary(
            run_id, len(audit), counts_by_status[HistoricalBackfillStatus.UPDATED],
            counts_by_status[HistoricalBackfillStatus.ALREADY_COMPLETE],
            counts_by_status[HistoricalBackfillStatus.UNRESOLVABLE],
            counts_by_status[HistoricalBackfillStatus.CONFLICT],
            counts_by_status[HistoricalBackfillStatus.INVALID], True, tuple(audit),
        )

    @staticmethod
    def _historical_backfill_counts(audit: list[HistoricalBackfillAudit]) -> tuple[int, ...]:
        return tuple(sum(item.status is status for item in audit) for status in (
            HistoricalBackfillStatus.UPDATED, HistoricalBackfillStatus.ALREADY_COMPLETE,
            HistoricalBackfillStatus.UNRESOLVABLE, HistoricalBackfillStatus.CONFLICT,
            HistoricalBackfillStatus.INVALID,
        ))

    @staticmethod
    def _resolve_historical_market_storage(
        row: sqlite3.Row, catalog: PrismaReferenceCatalog, run_id: str, row_position: int
    ) -> HistoricalBackfillAudit:
        row_key = "|".join(str(row[key]) for key in (
            "auction_id", "network_point_id", "direction", "flow_start", "flow_end"
        ))
        previous_exit = row["exit_market"]
        previous_entry = row["entry_market"]

        def result(status, code, message, proposed_exit=previous_exit,
                   proposed_entry=previous_entry, final_exit=previous_exit,
                   final_entry=previous_entry, changed=False):
            return HistoricalBackfillAudit(
                run_id, row["id"], row_position, str(row["auction_id"]), row_key,
                previous_exit, previous_entry, proposed_exit, proposed_entry,
                final_exit, final_entry, status, code, message, changed,
            )

        if not AuctionStorage._valid_historical_row(row):
            return result(HistoricalBackfillStatus.INVALID, "invalid_historical_row",
                          "The stored row has invalid backfill coordinates.")
        if row["direction"] == "bundle":
            return result(HistoricalBackfillStatus.UNRESOLVABLE,
                          "insufficient_bundle_identity",
                          "The stored bundle row does not retain both original side identities.")
        sides = {
            "exit": (ReferenceSide.EXIT,),
            "entry": (ReferenceSide.ENTRY,),
        }[row["direction"]]
        references = {side: catalog.lookup(row["network_point"], side) for side in sides}
        if any(reference is None for reference in references.values()):
            return result(HistoricalBackfillStatus.UNRESOLVABLE, "reference_unresolvable",
                          "The stored network point cannot be resolved for every required side.")
        proposed_exit = references[ReferenceSide.EXIT].canonical_name if ReferenceSide.EXIT in sides else previous_exit
        proposed_entry = references[ReferenceSide.ENTRY].canonical_name if ReferenceSide.ENTRY in sides else previous_entry
        missing = lambda value: value is None or (isinstance(value, str) and not value.strip())
        equivalent = lambda value, canonical: (
            isinstance(value, str) and value.strip().casefold() == canonical.casefold()
        )
        conflicts = (
            (ReferenceSide.EXIT in sides and not missing(previous_exit)
             and not equivalent(previous_exit, proposed_exit))
            or (ReferenceSide.ENTRY in sides and not missing(previous_entry)
                and not equivalent(previous_entry, proposed_entry))
        )
        if conflicts:
            return result(HistoricalBackfillStatus.CONFLICT, "reference_conflict",
                          "A stored non-empty value conflicts with the reference-derived value.",
                          proposed_exit, proposed_entry)
        final_exit = proposed_exit if ReferenceSide.EXIT in sides and missing(previous_exit) else previous_exit
        final_entry = proposed_entry if ReferenceSide.ENTRY in sides and missing(previous_entry) else previous_entry
        if (final_exit, final_entry) == (previous_exit, previous_entry):
            return result(HistoricalBackfillStatus.ALREADY_COMPLETE, "already_complete",
                          "All required Market / Storage values are already complete.")
        return result(HistoricalBackfillStatus.UPDATED, "missing_values_filled",
                      "Missing Market / Storage values were filled from the reference catalog.",
                      proposed_exit, proposed_entry, final_exit, final_entry, True)

    @staticmethod
    def _valid_historical_row(row: sqlite3.Row) -> bool:
        # `fromisoformat` intentionally stays generic here (not narrowed to
        # `prisma_datetime.py`'s exact `YYYY-MM-DD[ HH:mm]` output contract):
        # it already accepts both that corrected representation and the
        # previous `T`-separated, seconds-carrying one, so rows persisted
        # before this correction remain valid without a migration.
        text_fields = ("auction_id", "network_point", "network_point_id", "auction_date",
                       "flow_start", "flow_end", "product_type")
        if row["direction"] not in {"exit", "entry", "bundle"} or any(
            not isinstance(row[key], str) or not row[key].strip() for key in text_fields
        ):
            return False
        try:
            auction_date = datetime.fromisoformat(row["auction_date"])
            flow_start = datetime.fromisoformat(row["flow_start"])
            flow_end = datetime.fromisoformat(row["flow_end"])
        except (TypeError, ValueError):
            return False
        if (flow_start.utcoffset() is None) != (flow_end.utcoffset() is None):
            return False
        try:
            invalid_order = flow_start >= flow_end
        except (TypeError, ValueError):
            return False
        if invalid_order or not isinstance(auction_date, datetime):
            return False
        for key in ("booked_capacity_kwh_h", "runtime_hours", "tariff_eur_mwh_h",
                    "premium_eur_mwh_h"):
            value = row[key]
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                return False
        return True

    @staticmethod
    def _validate_historical_backfill(
        connection: sqlite3.Connection, audit: list[HistoricalBackfillAudit], run_id: str
    ) -> None:
        if len({item.auction_row_id for item in audit}) != len(audit):
            raise AuctionStorageError("Historical backfill audit row identifiers are not unique.")
        if len(audit) != sum(
            item.status is status
            for status in HistoricalBackfillStatus
            for item in audit
        ):
            raise AuctionStorageError("Historical backfill summary accounting failed.")
        changed_ids = [item.auction_row_id for item in audit if item.changed]
        for item in audit:
            stored = connection.execute(
                "SELECT exit_market, entry_market FROM auctions WHERE id=?",
                (item.auction_row_id,),
            ).fetchone()
            if stored is None or (stored["exit_market"], stored["entry_market"]) != (
                item.final_exit_market,
                item.final_entry_market,
            ):
                raise AuctionStorageError("Historical backfill validation failed.")
        if len(changed_ids) != sum(item.changed for item in audit):
            raise AuctionStorageError("Historical backfill change accounting failed.")
        persisted = connection.execute(
            "SELECT examined, updated, unchanged, skipped, conflicts, invalid "
            "FROM historical_market_storage_runs WHERE run_id=?", (run_id,)
        ).fetchone()
        if persisted is None or tuple(persisted) != (len(audit), *AuctionStorage._historical_backfill_counts(audit)):
            raise AuctionStorageError("Historical backfill run summary validation failed.")
        if connection.execute(
            "SELECT count(*) FROM historical_market_storage_audit WHERE run_id=?", (run_id,)
        ).fetchone()[0] != len(audit):
            raise AuctionStorageError("Historical backfill persisted audit validation failed.")

    def operations(self) -> list[sqlite3.Row]:
        with self._connection() as connection, connection:
            return list(connection.execute(
                "SELECT * FROM prisma_source_operations ORDER BY source_date"
            ))

    def import_legacy_operation(
        self, operation_id: str, source_date: str, source_name: str, digest: str
    ) -> None:
        with self._connection() as connection, connection:
            connection.execute(
                "INSERT OR IGNORE INTO prisma_source_operations "
                "(operation_id, source_date, source_name, sha256, status) "
                "VALUES (?, ?, ?, ?, 'accepted')",
                (operation_id, source_date, source_name, digest),
            )

    def operation_for_digest(self, digest: str) -> sqlite3.Row | None:
        with self._connection() as connection, connection:
            return connection.execute(
                "SELECT * FROM prisma_source_operations WHERE sha256 = ?", (digest,)
            ).fetchone()

    def begin_operation(self, source_date: str, source_name: str, digest: str) -> sqlite3.Row:
        """Begin (or resume) the source-operation ledger entry for one CSV's
        exact byte content.

        P.40 correction: identity is `sha256` only, never `source_date` — a
        different file for a date that already has an accepted or
        in-progress operation is always its own independent operation, never
        rejected or blocked. Resuming by digest is purely an internal
        bookkeeping optimization for crash recovery (an interrupted retry of
        the exact same bytes continues the same ledger row instead of
        creating a redundant duplicate); it provides no row-level dedup
        guarantee of its own — that is `prisma_publication`'s composite-key
        responsibility exclusively.
        """
        existing = self.operation_for_digest(digest)
        if existing is not None:
            return existing
        operation_id = uuid.uuid4().hex
        with self._connection() as connection, connection:
            connection.execute(
                "INSERT INTO prisma_source_operations "
                "(operation_id, source_date, source_name, sha256, status) VALUES (?, ?, ?, ?, 'pending')",
                (operation_id, source_date, source_name, digest),
            )
        return self.operation_for_digest(digest)  # type: ignore[return-value]

    @classmethod
    def _translate_legacy_price_fields(cls, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """See `_LEGACY_PRICE_FIELD_ALIASES` for why the rename exists, and
        `_P37_ONLY_FIELDS` for why those keys are dropped: both exist so a
        `processor.py` row dict -- which now also carries P.37's
        side-specific source-price/currency breakdown for
        `price_normalization.py` -- can still be passed unmodified into
        `_upsert_rows`, whose INSERT/UPDATE column list is built directly
        from the row dict's own keys and must match the `auctions` table
        schema exactly."""
        translated = []
        for row in rows:
            if not any(
                field in row
                for field in (*cls._LEGACY_PRICE_FIELD_ALIASES, *cls._P37_ONLY_FIELDS)
            ):
                translated.append(row)
                continue
            updated = dict(row)
            for new_name, legacy_name in cls._LEGACY_PRICE_FIELD_ALIASES.items():
                if new_name in updated:
                    updated[legacy_name] = updated.pop(new_name)
            for field in cls._P37_ONLY_FIELDS:
                updated.pop(field, None)
            translated.append(updated)
        return translated

    def apply_operation(self, operation_id: str, rows: list[dict[str, Any]], summary: dict[str, Any]) -> dict[str, int]:
        rows = self._translate_legacy_price_fields(rows)
        with self._connection() as connection, connection:
            operation = connection.execute(
                "SELECT status, summary_json FROM prisma_source_operations WHERE operation_id = ?",
                (operation_id,),
            ).fetchone()
            if operation is None:
                raise AuctionStorageError("The pending PRISMA operation was not found.")
            if operation["status"] != "pending":
                stored = json.loads(operation["summary_json"] or "{}")
                return {key: int(stored[key]) for key in ("processed", "inserted", "updated", "unchanged")}
            stats = self._upsert_rows(connection, rows)
            summary.update(stats)
            connection.execute(
                "UPDATE prisma_source_operations SET status='data_committed', summary_json=?, "
                "updated_at=CURRENT_TIMESTAMP WHERE operation_id=? AND status='pending'",
                (json.dumps(summary, sort_keys=True), operation_id),
            )
        return stats

    @staticmethod
    def _validate_upsert_batch(rows: list[dict[str, Any]]) -> None:
        rows_by_identity: dict[tuple[Any, ...], dict[str, Any]] = {}
        for row in rows:
            network_point_id = row.get("network_point_id")
            if not isinstance(network_point_id, str) or not network_point_id.strip():
                raise AuctionStorageError(
                    "Auction network_point_id must be a nonblank string."
                )
            identity = tuple(row.get(field) for field in AuctionStorage.AUCTION_IDENTITY_FIELDS)
            previous = rows_by_identity.get(identity)
            if previous is not None and any(
                previous.get(field) != row.get(field)
                for field in AuctionStorage.AUCTION_PERSISTED_FIELDS
            ):
                raise AuctionStorageError(
                    "The auction batch contains conflicting rows with the same identity."
                )
            rows_by_identity[identity] = row

    @staticmethod
    def _upsert_rows(
        connection: sqlite3.Connection, rows: list[dict[str, Any]]
    ) -> dict[str, int]:
        AuctionStorage._validate_upsert_batch(rows)
        inserted = updated = unchanged = 0
        for row in rows:
            existing = connection.execute(
                "SELECT * FROM auctions WHERE auction_id=? AND network_point_id=? "
                "AND direction=? AND flow_start=? AND flow_end=?",
                (row["auction_id"], row["network_point_id"], row["direction"],
                 row["flow_start"], row["flow_end"]),
            ).fetchone()
            if existing is None:
                columns = ", ".join(row)
                connection.execute(
                    f"INSERT INTO auctions ({columns}) VALUES ({', '.join('?' for _ in row)})",
                    tuple(row.values()),
                )
                inserted += 1
            elif any(
                existing[key] != value for key, value in row.items()
                if key in existing.keys()
            ):
                assignments = ", ".join(f"{key}=?" for key in row)
                connection.execute(
                    f"UPDATE auctions SET {assignments}, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                    (*row.values(), existing["id"]),
                )
                updated += 1
            else:
                unchanged += 1
        return {"processed": len(rows), "inserted": inserted,
                "updated": updated, "unchanged": unchanged}

    def finalize_operation(self, operation_id: str) -> None:
        with self._connection() as connection, connection:
            changed = connection.execute(
                "UPDATE prisma_source_operations SET status='accepted', updated_at=CURRENT_TIMESTAMP "
                "WHERE operation_id=? AND status='data_committed'", (operation_id,)
            ).rowcount
            if changed != 1:
                raise AuctionStorageError("The PRISMA operation could not be finalized safely.")

    def get_rate_resolution(self, auction_id: str) -> RateResolutionRecord | None:
        """Return the previously fixed P.36.19 rate resolution for `auction_id`,
        or `None` when no resolution has been fixed yet."""
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM auction_rate_resolutions WHERE auction_id = ?",
                (auction_id,),
            ).fetchone()
        if row is None:
            return None
        return RateResolutionRecord(**{
            field: row[field] for field in self.RATE_RESOLUTION_FIELDS
        })

    def save_rate_resolution(self, record: RateResolutionRecord) -> RateResolutionRecord:
        """Atomically fix one new P.36.19 rate resolution.

        Reusing an identical previously fixed resolution is a no-op that
        returns the existing record unchanged (`resolved_at_utc` is excluded
        from the equality check, since reuse must not fail merely because
        time has passed). Any other difference from a previously fixed
        record for the same Auction ID is a contradiction between cached
        data and newly retrieved authoritative data, and raises
        `RateResolutionConflictError` with both records for diagnostics
        instead of silently overwriting the previously fixed result.
        """
        with self._connection() as connection, self._transaction(connection):
            connection.execute("BEGIN IMMEDIATE")
            existing_row = connection.execute(
                "SELECT * FROM auction_rate_resolutions WHERE auction_id = ?",
                (record.auction_id,),
            ).fetchone()
            if existing_row is not None:
                existing = RateResolutionRecord(**{
                    field: existing_row[field] for field in self.RATE_RESOLUTION_FIELDS
                })
                comparable = [
                    field for field in self.RATE_RESOLUTION_FIELDS
                    if field != "resolved_at_utc"
                ]
                if all(getattr(existing, field) == getattr(record, field) for field in comparable):
                    return existing
                raise RateResolutionConflictError(
                    "A previously fixed rate resolution for Auction ID "
                    f"{record.auction_id} contradicts newly retrieved data: "
                    f"existing={existing!r} new={record!r}."
                )
            connection.execute(
                "INSERT INTO auction_rate_resolutions "
                "(auction_id, auction_state, auction_end_at, currency, "
                "ecb_publication_date, rate_to_eur, resolved_at_utc, source_version) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    record.auction_id, record.auction_state, record.auction_end_at,
                    record.currency, record.ecb_publication_date, record.rate_to_eur,
                    record.resolved_at_utc, record.source_version,
                ),
            )
        return record

    def get_ecb_auction_date_rate(
        self, auction_date: str, currency: str
    ) -> EcbAuctionDateRateRecord | None:
        """Return the previously fixed P.37 rate resolution for
        `(auction_date, currency)`, or `None` when no resolution has been
        fixed yet."""
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM ecb_auction_date_rates WHERE auction_date = ? AND currency = ?",
                (auction_date, currency),
            ).fetchone()
        if row is None:
            return None
        return EcbAuctionDateRateRecord(**{
            field: row[field] for field in self.ECB_AUCTION_DATE_RATE_FIELDS
        })

    def save_ecb_auction_date_rate(
        self, record: EcbAuctionDateRateRecord
    ) -> EcbAuctionDateRateRecord:
        """Atomically fix one new P.37 `(auction_date, currency)` rate
        resolution.

        Reusing an identical previously fixed resolution is a no-op that
        returns the existing record unchanged (`resolved_at_utc` is excluded
        from the equality check, since reuse must not fail merely because
        time has passed). Any other difference from a previously fixed
        record for the same `(auction_date, currency)` is a contradiction
        between cached data and newly retrieved authoritative ECB data, and
        raises `EcbAuctionDateRateConflictError` with both records for
        diagnostics instead of silently overwriting the previously fixed
        result.
        """
        with self._connection() as connection, self._transaction(connection):
            connection.execute("BEGIN IMMEDIATE")
            existing_row = connection.execute(
                "SELECT * FROM ecb_auction_date_rates WHERE auction_date = ? AND currency = ?",
                (record.auction_date, record.currency),
            ).fetchone()
            if existing_row is not None:
                existing = EcbAuctionDateRateRecord(**{
                    field: existing_row[field] for field in self.ECB_AUCTION_DATE_RATE_FIELDS
                })
                comparable = [
                    field for field in self.ECB_AUCTION_DATE_RATE_FIELDS
                    if field != "resolved_at_utc"
                ]
                if all(getattr(existing, field) == getattr(record, field) for field in comparable):
                    return existing
                raise EcbAuctionDateRateConflictError(
                    "A previously fixed ECB rate resolution for "
                    f"{record.auction_date}/{record.currency} contradicts newly "
                    f"retrieved data: existing={existing!r} new={record!r}."
                )
            connection.execute(
                "INSERT INTO ecb_auction_date_rates "
                "(auction_date, currency, ecb_publication_date, rate_to_eur, "
                "resolved_at_utc, source_version) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    record.auction_date, record.currency, record.ecb_publication_date,
                    record.rate_to_eur, record.resolved_at_utc, record.source_version,
                ),
            )
        return record

    def published_output_row_keys(self) -> set[tuple[str, str, str]]:
        """Return every P.40 composite key ("Auction ID + Network Point Name
        + Capacity Type") ever durably recorded as published, across every
        prior call and every prior session. An incoming row whose key is in
        this set already has a stored, immutable counterpart and must be
        skipped, never replaced, by the caller."""
        with self._connection() as connection:
            return {
                (row["auction_id"], row["network_point_name"], row["capacity_type"])
                for row in connection.execute(
                    "SELECT auction_id, network_point_name, capacity_type "
                    "FROM published_output_row_keys"
                )
            }

    def record_published_output_row_keys(
        self, keys: list[tuple[str, str, str]]
    ) -> None:
        """Atomically record newly published P.40 composite keys.

        Each ``(auction_id, network_point_name, capacity_type)`` tuple must
        not already be recorded; the caller (`prisma_publication.
        publish_cumulative_output`) always pre-checks against
        `published_output_row_keys()` before calling this, so a collision
        here indicates a caller ordering defect, not stale/racing data, and
        is raised as `AuctionStorageError` rather than silently ignored or
        overwritten.
        """
        if not keys:
            return
        with self._connection() as connection, self._transaction(connection):
            connection.execute("BEGIN IMMEDIATE")
            for auction_id, network_point_name, capacity_type in keys:
                try:
                    connection.execute(
                        "INSERT INTO published_output_row_keys "
                        "(auction_id, network_point_name, capacity_type) "
                        "VALUES (?, ?, ?)",
                        (auction_id, network_point_name, capacity_type),
                    )
                except sqlite3.IntegrityError as exc:
                    raise AuctionStorageError(
                        "A P.40 composite publication key was already "
                        "recorded; the stored row is never replaced."
                    ) from exc

    @staticmethod
    def apply_excel_widths(path: Path) -> None:
        workbook = load_workbook(path)
        try:
            sheet = workbook["Auctions"]
            for index, header in enumerate(AuctionStorage.EXCEL_COLUMNS, start=1):
                sheet.column_dimensions[get_column_letter(index)].width = (
                    AuctionStorage.EXCEL_COLUMN_WIDTHS[header]
                )
            workbook.save(path)
        finally:
            workbook.close()

    @staticmethod
    def validate_excel(path: Path) -> bool:
        workbook = None
        try:
            workbook = load_workbook(path, read_only=False, data_only=True)
            valid = False
            if "Auctions" in workbook.sheetnames:
                sheet = workbook["Auctions"]
                headers = tuple(
                    cell.value for cell in next(sheet.iter_rows(min_row=1, max_row=1))
                )
                widths_are_valid = all(
                    abs(
                        sheet.column_dimensions[get_column_letter(index)].width
                        - AuctionStorage.EXCEL_COLUMN_WIDTHS[header]
                    ) <= AuctionStorage.EXCEL_WIDTH_TOLERANCE
                    for index, header in enumerate(AuctionStorage.EXCEL_COLUMNS, start=1)
                )
                valid = headers == AuctionStorage.EXCEL_COLUMNS and widths_are_valid
            return valid
        except Exception:
            return False
        finally:
            if workbook is not None:
                workbook.close()

    def export_excel(self, output_path: Path) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as connection, connection:
            frame = pd.read_sql_query("""
                SELECT auction_date AS "Auction Date", exit_market AS "Exit Market/Storage",
                entry_market AS "Entry Market/Storage", direction AS "Capacity Type",
                network_point AS "Network Point Name", product_type AS "Product Type",
                flow_start AS "Flow Start", flow_end AS "Flow End",
                booked_capacity_kwh_h AS "Booked Capacity, kWh/h", runtime_hours AS "Runtime Hours",
                tariff_eur_mwh_h AS "Tariff, EUR/MWh/h", premium_eur_mwh_h AS "Premium, EUR/MWh/h",
                auction_id AS "Auction ID", tso_exit AS "TSO Exit", tso_entry AS "TSO Entry", state AS "Status"
                FROM auctions ORDER BY auction_date, auction_id, network_point_id, direction, flow_start, flow_end
            """, connection)
        staged: Path | None = None
        try:
            descriptor, name = tempfile.mkstemp(prefix=f".{output_path.stem}-", suffix=".xlsx", dir=output_path.parent)
            os.close(descriptor)
            staged = Path(name)
            frame.to_excel(staged, index=False, sheet_name="Auctions")
            self.apply_excel_widths(staged)
            if not self.validate_excel(staged):
                raise AuctionStorageError("The staged Excel workbook failed validation.")
            try:
                os.replace(staged, output_path)
            except PermissionError as exc:
                raise AuctionStorageError(
                    "The Excel output is open or locked. Close it and retry the import."
                ) from exc
            staged = None
        except AuctionStorageError:
            raise
        except Exception as exc:
            raise AuctionStorageError("The Excel output could not be staged safely.") from exc
        finally:
            if staged is not None:
                try:
                    staged.unlink(missing_ok=True)
                except OSError:
                    pass
        return output_path

    def upsert(self, rows: list[dict[str, Any]]) -> dict[str, int]:
        """Compatibility API for storage-only callers."""
        rows = self._translate_legacy_price_fields(rows)
        with self._connection() as connection, connection:
            return self._upsert_rows(connection, rows)
