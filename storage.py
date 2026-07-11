from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import pandas as pd


class AuctionStorage:
    def __init__(self, database_path: Path) -> None:
        database_path.parent.mkdir(parents=True, exist_ok=True)
        self.database_path = database_path
        self._create_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _create_schema(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS auctions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    auction_id TEXT NOT NULL,
                    auction_date TEXT NOT NULL,
                    exit_market TEXT NOT NULL DEFAULT '',
                    entry_market TEXT NOT NULL DEFAULT '',
                    direction TEXT NOT NULL,
                    network_point TEXT NOT NULL,
                    network_point_id TEXT NOT NULL DEFAULT '',
                    tso_exit TEXT NOT NULL DEFAULT '',
                    tso_entry TEXT NOT NULL DEFAULT '',
                    product_type TEXT NOT NULL,
                    flow_start TEXT NOT NULL,
                    flow_end TEXT NOT NULL,
                    booked_capacity_kwh_h REAL NOT NULL,
                    runtime_hours REAL NOT NULL,
                    tariff_eur_mwh_h REAL NOT NULL,
                    premium_eur_mwh_h REAL NOT NULL,
                    state TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE (
                        auction_id,
                        network_point_id,
                        direction,
                        flow_start,
                        flow_end
                    )
                )
                """
            )

    def upsert(self, rows: list[dict[str, Any]]) -> dict[str, int]:
        inserted = updated = unchanged = 0

        with self._connect() as connection:
            for row in rows:
                existing = connection.execute(
                    """
                    SELECT * FROM auctions
                    WHERE auction_id = ?
                      AND network_point_id = ?
                      AND direction = ?
                      AND flow_start = ?
                      AND flow_end = ?
                    """,
                    (
                        row["auction_id"],
                        row["network_point_id"],
                        row["direction"],
                        row["flow_start"],
                        row["flow_end"],
                    ),
                ).fetchone()

                if existing is None:
                    columns = ", ".join(row.keys())
                    placeholders = ", ".join("?" for _ in row)
                    connection.execute(
                        f"INSERT INTO auctions ({columns}) VALUES ({placeholders})",
                        tuple(row.values()),
                    )
                    inserted += 1
                    continue

                changed = any(
                    existing[key] != value
                    for key, value in row.items()
                    if key in existing.keys()
                )
                if not changed:
                    unchanged += 1
                    continue

                assignments = ", ".join(f"{key} = ?" for key in row)
                connection.execute(
                    f"""
                    UPDATE auctions
                    SET {assignments}, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (*row.values(), existing["id"]),
                )
                updated += 1

        return {
            "processed": len(rows),
            "inserted": inserted,
            "updated": updated,
            "unchanged": unchanged,
        }

    def export_excel(self, output_path: Path) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            frame = pd.read_sql_query(
                """
                SELECT
                    auction_date AS "Auction Date",
                    exit_market AS "Exit Market/Storage",
                    entry_market AS "Entry Market/Storage",
                    direction AS "Capacity Type",
                    network_point AS "Network Point Name",
                    product_type AS "Product Type",
                    flow_start AS "Flow Start",
                    flow_end AS "Flow End",
                    booked_capacity_kwh_h AS "Booked Capacity, kWh/h",
                    runtime_hours AS "Runtime Hours",
                    tariff_eur_mwh_h AS "Tariff, EUR/MWh/h",
                    premium_eur_mwh_h AS "Premium, EUR/MWh/h",
                    auction_id AS "Auction ID",
                    tso_exit AS "TSO Exit",
                    tso_entry AS "TSO Entry",
                    state AS "Status"
                FROM auctions
                ORDER BY auction_date, auction_id
                """,
                connection,
            )

        frame.to_excel(output_path, index=False, sheet_name="Auctions")
        return output_path
