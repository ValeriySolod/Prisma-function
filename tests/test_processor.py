from pathlib import Path

from processor import process_csv


def test_process_real_sample_when_available() -> None:
    sample = Path("Auction_overview.csv")
    if not sample.exists():
        return

    rows = process_csv(sample)

    assert isinstance(rows, list)
    assert all(row["booked_capacity_kwh_h"] >= 1000 for row in rows)
    assert all(row["runtime_hours"] > 0 for row in rows)
