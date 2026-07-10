from storage import AuctionStorage


def test_duplicate_import_does_not_insert_twice(tmp_path) -> None:
    storage = AuctionStorage(tmp_path / "test.db")
    row = {
        "auction_id": "123",
        "auction_date": "2026-07-10T06:00:00",
        "exit_market": "",
        "entry_market": "",
        "direction": "entry",
        "network_point": "Test Point",
        "network_point_id": "NP-1",
        "tso_exit": "",
        "tso_entry": "Test TSO",
        "product_type": "Day Ahead",
        "flow_start": "2026-07-10T06:00:00",
        "flow_end": "2026-07-11T06:00:00",
        "booked_capacity_kwh_h": 1000.0,
        "runtime_hours": 24.0,
        "tariff_eur_mwh_h": 1.0,
        "premium_eur_mwh_h": 0.0,
        "state": "Finished",
    }

    first = storage.upsert([row])
    second = storage.upsert([row])

    assert first["inserted"] == 1
    assert second["inserted"] == 0
    assert second["unchanged"] == 1
