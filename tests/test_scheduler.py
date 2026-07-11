from unittest.mock import Mock

import pytest

from auction_csv import AuctionCsvRecord
from monitoring import MonitoringResult
from scheduler import MonitoringScheduler


def record(auction_id: str = "A-001") -> AuctionCsvRecord:
    return AuctionCsvRecord(
        auction_id, "https://example.com/a", "1", "Item", "Open", "Open", 60, True
    )


def test_run_once_passes_records_and_event_and_returns_results_unchanged():
    records = [record()]
    results = [Mock(spec=MonitoringResult)]
    provider = Mock(return_value=records)
    engine = Mock()
    engine.check_records.return_value = results
    stop_event = Mock()

    returned = MonitoringScheduler(engine, provider).run_once(stop_event)

    provider.assert_called_once_with()
    engine.check_records.assert_called_once_with(records, stop_event)
    assert returned is results


def test_run_once_passes_empty_records_and_returns_empty_result():
    engine = Mock()
    engine.check_records.return_value = []

    result = MonitoringScheduler(engine, lambda: []).run_once()

    engine.check_records.assert_called_once_with([], None)
    assert result == []


def test_run_once_does_not_hide_provider_exception():
    expected = RuntimeError("provider failed")

    def fail():
        raise expected

    engine = Mock()
    with pytest.raises(RuntimeError) as caught:
        MonitoringScheduler(engine, fail).run_once()

    assert caught.value is expected
    engine.check_records.assert_not_called()


def test_run_once_does_not_hide_engine_exception():
    records = [record()]
    provider = Mock(return_value=records)
    expected = RuntimeError("engine failed")
    engine = Mock()
    engine.check_records.side_effect = expected
    stop_event = Mock()

    with pytest.raises(RuntimeError) as caught:
        MonitoringScheduler(engine, provider).run_once(stop_event)

    assert caught.value is expected
    provider.assert_called_once_with()
    engine.check_records.assert_called_once_with(records, stop_event)


class ControlledEvent:
    def __init__(self, *, initially_set: bool = False, stop_after_waits: int = 2) -> None:
        self.set = initially_set
        self.stop_after_waits = stop_after_waits
        self.wait_calls: list[float | None] = []

    def is_set(self) -> bool:
        return self.set

    def wait(self, timeout: float | None = None) -> bool:
        self.wait_calls.append(timeout)
        if len(self.wait_calls) >= self.stop_after_waits:
            self.set = True
        return self.set


def test_run_forever_runs_immediately_then_after_each_interruptible_wait():
    event = ControlledEvent(stop_after_waits=2)
    provider = Mock(return_value=[])
    engine = Mock()
    engine.check_records.return_value = []

    MonitoringScheduler(engine, provider).run_forever(event, 5.0)

    assert provider.call_count == 2
    assert engine.check_records.call_count == 2
    assert event.wait_calls == [5.0, 5.0]


def test_run_forever_does_not_start_cycle_when_already_stopped():
    event = ControlledEvent(initially_set=True)
    provider = Mock()
    engine = Mock()

    MonitoringScheduler(engine, provider).run_forever(event, 1.0)

    provider.assert_not_called()
    engine.check_records.assert_not_called()
    assert event.wait_calls == []


@pytest.mark.parametrize("interval", [0, -1.0])
def test_run_forever_rejects_non_positive_interval(interval: float):
    with pytest.raises(ValueError):
        MonitoringScheduler(Mock(), Mock()).run_forever(ControlledEvent(), interval)


def test_run_forever_does_not_start_new_cycle_when_wait_is_interrupted():
    event = ControlledEvent(stop_after_waits=1)
    provider = Mock(return_value=[])
    engine = Mock()
    engine.check_records.return_value = []

    MonitoringScheduler(engine, provider).run_forever(event, 3.0)

    provider.assert_called_once_with()
    engine.check_records.assert_called_once_with([], event)
    assert event.wait_calls == [3.0]
