import os
import threading
from unittest.mock import Mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication, QMessageBox

import app
from auction_csv import AuctionCsvRecord
from browser import LaunchResult
from prisma_page import LivePrismaStatusAdapter
from prisma_page import PrismaLookupTimeoutError, PrismaPageStructureError


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(qt_app, monkeypatch):
    browser = Mock()
    monkeypatch.setattr(app, "BrowserController", Mock(return_value=browser))
    widget = app.PrismaMonitorApp()
    yield widget, browser
    widget._is_closing = True
    widget.close()


def record(auction_id="A1", enabled=True, item_name="Item"):
    return AuctionCsvRecord(auction_id, "https://example.com", "L1", item_name,
                            "Open", "Scheduled", 30, enabled)


def test_core_controls_and_english_status(window):
    widget, _ = window
    assert widget.windowTitle() == "PRISMA Monitor"
    assert widget.status.text() == "Ready"
    assert [button.text() for button in (
        widget.open_button, widget.process_button, widget.open_result_button,
        widget.start_monitoring_button, widget.stop_monitoring_button,
        widget.stop_browser_button,
    )] == ["Open PRISMA", "Process CSV", "Open Result", "Start Monitoring",
           "Stop Monitoring", "Stop Browser"]
    assert widget.csv_table.columnCount() == 7


def test_cancel_csv_dialog_preserves_state(window, monkeypatch):
    widget, _ = window
    dialog = Mock(return_value=("", ""))
    monkeypatch.setattr(app.QFileDialog, "getOpenFileName", dialog)
    load = Mock(); monkeypatch.setattr(app, "load_auction_csv", load)
    widget.select_csv()
    load.assert_not_called()
    assert widget.csv_path.text() == "" and widget.status.text() == "Ready"


def test_valid_csv_populates_table(window, monkeypatch):
    widget, _ = window
    monkeypatch.setattr(app.QFileDialog, "getOpenFileName",
                        Mock(return_value=("C:/data/Auction_overview.csv", "CSV")))
    monkeypatch.setattr(app, "load_auction_csv",
                        Mock(return_value=[record(), record("A2", False, "Second")]))
    widget.select_csv()
    assert widget.csv_path.text() == "C:/data/Auction_overview.csv"
    assert widget.status.text() == "Loaded Auction_overview.csv: 2 records"
    assert widget.csv_table.rowCount() == 2
    assert widget.csv_table.item(1, 6).text() == "No"


def test_invalid_csv_uses_qmessagebox_and_preserves_selection(window, monkeypatch):
    widget, _ = window
    widget.csv_path.setText("existing.csv")
    monkeypatch.setattr(app.QFileDialog, "getOpenFileName", Mock(return_value=("bad.csv", "CSV")))
    monkeypatch.setattr(app, "load_auction_csv", Mock(side_effect=app.CsvValidationError("bad data")))
    critical = Mock(); monkeypatch.setattr(QMessageBox, "critical", critical)
    widget.select_csv()
    assert widget.csv_path.text() == "existing.csv"
    critical.assert_called_once_with(widget, "CSV Error", "bad data")


def test_browser_result_is_polled_on_gui_thread(window, monkeypatch):
    widget, browser = window
    browser.open.return_value = 7
    browser.get_launch_results.return_value = [LaunchResult(7, True)]
    monkeypatch.setattr(widget._browser_timer, "start", Mock())
    monkeypatch.setattr(widget._browser_timer, "stop", Mock())
    widget.open_prisma()
    assert not widget.open_button.isEnabled()
    widget._poll_browser_launch()
    assert widget.open_button.isEnabled()
    assert widget.status.text() == "PRISMA opened in the default browser"


def test_manual_browser_closure_stops_monitoring_and_restores_retry_ui(window):
    widget, browser = window
    widget._active_browser_launch = 7
    stop_event = threading.Event()
    widget._monitoring_stop_event = stop_event
    browser.get_launch_results.return_value = [LaunchResult(
        7, False, "The managed PRISMA page or browser was closed.", "closed"
    )]

    widget._poll_browser_launch()

    assert stop_event.is_set()
    assert widget.open_button.isEnabled()
    assert "Open it again to retry" in widget.status.text()


@pytest.mark.parametrize(("error", "expected"), [
    (PrismaLookupTimeoutError("raw playwright timeout"), "status lookup timed out"),
    (PrismaPageStructureError("raw selector"), "page structure could not be read"),
])
def test_monitoring_failure_messages_are_stable_and_actionable(error, expected):
    message = app.PrismaMonitorApp._monitoring_failure_message(error)
    assert expected in message
    assert "raw" not in message


def test_monitoring_worker_emits_signal_instead_of_touching_widgets(window, monkeypatch):
    widget, _ = window
    scheduler = Mock(); emitted = Mock()
    widget.signals.monitoring_finished.connect(emitted)
    widget._monitoring_worker(scheduler, threading.Event())
    emitted.assert_called_once_with(None)


def test_start_stop_monitoring_matches_existing_behavior(window, monkeypatch):
    widget, _ = window
    widget._auction_records = [record()]
    scheduler = Mock(); monkeypatch.setattr(widget, "create_monitoring_scheduler", Mock(return_value=scheduler))
    created = []
    class FakeThread:
        def __init__(self, **kwargs): self.kwargs = kwargs; self.started = False; created.append(self)
        def start(self): self.started = True
        def is_alive(self): return False
    monkeypatch.setattr(app.threading, "Thread", FakeThread)
    widget.start_monitoring()
    assert created[0].started and not widget.start_monitoring_button.isEnabled()
    event = widget._monitoring_stop_event
    widget.stop_monitoring()
    assert event.is_set()


def test_default_monitoring_engine_uses_live_browser_adapter(window):
    widget, browser = window
    engine = widget.create_monitoring_engine()
    assert isinstance(engine._status_checker, LivePrismaStatusAdapter)
    assert engine._status_checker._browser_controller is browser


def test_start_without_records_shows_existing_error(window, monkeypatch):
    widget, _ = window
    critical = Mock(); monkeypatch.setattr(QMessageBox, "critical", critical)
    widget.start_monitoring()
    critical.assert_called_once_with(widget, "Monitoring Error",
                                     "No usable auction records are available.")


def test_close_stops_monitoring_browser_and_joins_worker(window):
    widget, browser = window
    event = threading.Event(); worker = Mock()
    worker.is_alive.return_value = True
    widget._monitoring_stop_event = event; widget._monitoring_thread = worker
    close_event = Mock()
    widget.closeEvent(close_event)
    assert event.is_set(); browser.stop.assert_called_once(); worker.join.assert_called_once_with()
    close_event.accept.assert_called_once_with()
