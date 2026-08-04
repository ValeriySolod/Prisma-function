# Prisma Function — Auction Data Processing

## Overview

Prisma Function is a desktop application that automates the retrieval and
transformation of capacity auction data from the official Prisma Capacity
platform. The user launches the app, opens the Prisma website in a new
browser tab via the **Open Prisma** button, selects the desired dates on the
Prisma site, and downloads the resulting CSV export. All processing of the
downloaded file happens exclusively inside Prisma Function, which parses the
CSV and outputs it according to the mapping described below. When finished,
the user closes the session with the **Close Prisma** button.

## 1. Data Source

- Data is downloaded from the official auction platform via the provided link.
- The user navigates to the auctions section and sets the starting date of
  the month.
- Filtering is applied so that only auctions with at least the minimum
  booked capacity (**≥ 1 MWh**) are retained.

## 2. Input Format

- A CSV file (PDF if needed) exported from the auction system.
- Contains information about all trades conducted during the selected period.

## 3. Data Transformation Requirements

The output CSV/table must contain the following fields:

| # | Field | Details |
|---|-------|---------|
| 1 | Auction date | Format: `YYYY-MM-DD` |
| 2 | Exit market | Name of the market/storage from which capacity exits |
| 3 | Entry market | Name of the market/storage into which capacity enters |
| 4 | Capacity type | Allowed values: `entry`, `exit`, `bundle` |
| 5 | Point name | e.g. `VGS Storage Hub` |
| 6 | Product type | Allowed values: `WD`, `Day ahead`, `Month`, `Quarter`, `Year` |
| 7 | Flow start date | Format: `YYYY-MM-DD HH:mm` |
| 8 | Flow end date | Format: `YYYY-MM-DD HH:mm` |
| 9 | Booked capacity | Unit: kWh/h |
| 10 | Number of hours between fields 7 and 8 | Automatically calculated as the difference between flow start and end dates |
| 11 | Auction tariff price | Unit: EUR/MWh/h |
| 12 | Auction premium price | Unit: EUR/MWh/h |

## 4. Output Requirements

- The output file must be CSV, delimited by `;`.
- Encoding: UTF-8.
- All numeric values must use a standard format (decimal separator — dot).
- Dates and times must use a single, consistent time zone (CET/CEST).
- Prices must be normalized to a single standard: EUR/MWh/h.

## 5. Expected Result

- An automated CSV file containing only relevant auctions (booked capacity
  ≥ 1 MWh).
- Structured data ready for further analysis and integration into the
  monitoring system.
- The application must also display the market mapping according to the
  attached reference screenshot.

## Notes

- All processing actions on downloaded files must be performed only within
  the Prisma Function application — no manual editing outside the app.
- This document is derived from the original specification
  (`Prisma Function.odt`). For updated business rules, packaging notes, and
  implementation increments, see the project's implementation log.
