# Prisma Function — Auction Data Processing

Prisma Function is a Windows desktop application that processes official PRISMA Export CSV files into cumulative structured auction data.

## Workflow

1. Download one or more official PRISMA Export CSV files independently.
2. Select each file in Prisma Function with Select CSV.
3. Prisma Function reads the complete CSV, validates and transforms every row, filters irrelevant auctions, normalizes prices, persists new rows without duplicates, publishes the result, and refreshes Mapping.

The application does not open, control, or download from the PRISMA website.

## Input

- Official 34-column PRISMA Export CSV.
- Encoding: Windows-1252.
- Delimiter: semicolon.
- Detection: exact headers, never filename.
- Every row is processed to end-of-file; Prisma Function has no 5,000-row limit.
- Multiple CSV files for the same date or period may be selected.
- PDF input is not supported.

## Filtering

Only auctions with normalized booked capacity of at least 1 MWh are retained.

## Mapping and output

Mapping and the published CSV contain exactly these columns:

| # | Column | Contract |
|---:|---|---|
| 1 | Auction Date | YYYY-MM-DD |
| 2 | Exit Market | Exact exit-side market or storage |
| 3 | Entry Market | Exact entry-side market or storage |
| 4 | Capacity Type | entry, exit, or bundle |
| 5 | Network Point Name | Official point name |
| 6 | Product Type | WD, Day Ahead, Month, Quarter, or Year |
| 7 | Flow Start | YYYY-MM-DD HH:mm |
| 8 | Flow End | YYYY-MM-DD HH:mm |
| 9 | Booked Capacity | kWh/h |
| 10 | Flow Duration Hours | Difference between Flow Start and Flow End |
| 11 | Tariff Price | EUR/MWh/h |
| 12 | Premium Price | EUR/MWh/h |

Mapping displays all cumulative accepted rows and supports vertical and horizontal scrolling without a row limit.

The published file is UTF-8 and semicolon-delimited. Decimal values use a dot.

## Data rules

- Previously accepted data persists across sessions.
- New distinct rows are added atomically.
- Exact re-import and partial overlap do not create duplicates.
- Files are not rejected merely because another file has the same source date.
- Dates and times use the approved Europe/Berlin CET/CEST contract.
- Prices are normalized to EUR/MWh/h using the calendar date from Start of Auction and official ECB reference rates.
- Market/storage resolution uses exact, side-specific, Auction-ID-linked approved evidence only.

See AGENTS.md for repository rules, ROADMAP.md for active work, and CHANGELOG.md for historical implementation records.
