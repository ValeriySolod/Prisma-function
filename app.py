from __future__ import annotations

import os
import sys
import threading
from pathlib import Path

from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QApplication, QFileDialog, QGridLayout, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QMainWindow, QMessageBox, QPushButton, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

from auction_csv import AuctionCsvRecord, CsvValidationError, load_auction_csv
from browser import BrowserController
from monitoring import MonitoringEngine
from processor import process_csv
from scheduler import MonitoringScheduler
from storage import AuctionStorage

APP_DIR = Path(__file__).resolve().parent
DATA_DIR = APP_DIR / "data"
RESULT_DIR = DATA_DIR / "result"
DATABASE_PATH = DATA_DIR / "prisma_monitor.db"
DEFAULT_MONITORING_INTERVAL_SECONDS = 30.0


class WorkerSignals(QObject):
    processing_succeeded = Signal(str)
    processing_failed = Signal(str)
    monitoring_finished = Signal(object)


class PrismaMonitorApp(QMainWindow):
    COLUMNS = (
        "auction_id", "lot_number", "item_name", "expected_status",
        "last_known_status", "check_interval_seconds", "enabled",
    )

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("PRISMA Monitor")
        self.setFixedSize(940, 540)
        DATA_DIR.mkdir(exist_ok=True)
        RESULT_DIR.mkdir(parents=True, exist_ok=True)
        self.browser = BrowserController()
        self._is_closing = False
        self._active_browser_launch: int | None = None
        self._auction_records: list[AuctionCsvRecord] = []
        self._monitoring_thread: threading.Thread | None = None
        self._monitoring_stop_event: threading.Event | None = None
        self._processing_threads: set[threading.Thread] = set()
        self.signals = WorkerSignals(self)
        self.signals.processing_succeeded.connect(self._processing_succeeded)
        self.signals.processing_failed.connect(self._processing_failed)
        self.signals.monitoring_finished.connect(self._monitoring_finished)
        self._browser_timer = QTimer(self)
        self._browser_timer.setInterval(50)
        self._browser_timer.timeout.connect(self._poll_browser_launch)
        self._build_ui()

    def _build_ui(self) -> None:
        central = QWidget(self)
        layout = QVBoxLayout(central)
        title = QLabel("PRISMA Monitor")
        font = title.font(); font.setPointSize(18); font.setBold(True); title.setFont(font)
        layout.addWidget(title)
        self.open_button = QPushButton("Open PRISMA")
        self.open_button.clicked.connect(self.open_prisma)
        layout.addWidget(self.open_button, alignment=Qt.AlignLeft)

        file_row = QGridLayout()
        file_row.addWidget(QLabel("CSV file:"), 0, 0)
        self.csv_path = QLineEdit()
        file_row.addWidget(self.csv_path, 0, 1)
        select_button = QPushButton("Select")
        select_button.clicked.connect(self.select_csv)
        file_row.addWidget(select_button, 0, 2)
        layout.addLayout(file_row)

        self.csv_table = QTableWidget(0, len(self.COLUMNS))
        self.csv_table.setHorizontalHeaderLabels(self.COLUMNS)
        self.csv_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.csv_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        layout.addWidget(self.csv_table)

        controls = QHBoxLayout()
        self.process_button = QPushButton("Process CSV")
        self.open_result_button = QPushButton("Open Result")
        self.start_monitoring_button = QPushButton("Start Monitoring")
        self.stop_monitoring_button = QPushButton("Stop Monitoring")
        self.stop_browser_button = QPushButton("Stop Browser")
        self.stop_monitoring_button.setEnabled(False)
        for button, handler in (
            (self.process_button, self.start_processing),
            (self.open_result_button, self.open_result),
            (self.start_monitoring_button, self.start_monitoring),
            (self.stop_monitoring_button, self.stop_monitoring),
            (self.stop_browser_button, self.stop_work),
        ):
            button.clicked.connect(handler); controls.addWidget(button)
        controls.addStretch()
        layout.addLayout(controls)
        status_row = QHBoxLayout(); status_row.addWidget(QLabel("Status:"))
        self.status = QLabel("Ready"); self.status.setWordWrap(True)
        status_row.addWidget(self.status, 1); layout.addLayout(status_row)
        close_button = QPushButton("Close Application")
        close_button.clicked.connect(self.close)
        layout.addWidget(close_button, alignment=Qt.AlignCenter)
        self.setCentralWidget(central)

    def select_csv(self) -> None:
        selected, _ = QFileDialog.getOpenFileName(
            self, "Select Auction_overview.csv", "", "CSV files (*.csv)"
        )
        if not selected:
            return
        try:
            records = load_auction_csv(selected)
        except CsvValidationError as exc:
            QMessageBox.critical(self, "CSV Error", str(exc)); return
        except Exception as exc:
            QMessageBox.critical(self, "CSV Error", f"Failed to load CSV: {exc}"); return
        self._display_csv_records(records)
        self._auction_records = records
        self.csv_path.setText(selected)
        self.status.setText(f"Loaded {Path(selected).name}: {len(records)} records")

    def _display_csv_records(self, records: list[AuctionCsvRecord]) -> None:
        self.csv_table.setRowCount(len(records))
        for row, record in enumerate(records):
            values = (record.auction_id, record.lot_number, record.item_name,
                      record.expected_status, record.last_known_status,
                      record.check_interval_seconds, "Yes" if record.enabled else "No")
            for column, value in enumerate(values):
                self.csv_table.setItem(row, column, QTableWidgetItem(str(value)))

    def open_prisma(self) -> None:
        try:
            self.open_button.setEnabled(False)
            self.status.setText("Starting PRISMA in the default browser...")
            self._active_browser_launch = self.browser.open()
            self._browser_timer.start()
        except Exception as exc:
            self._browser_start_failed(exc)

    def _poll_browser_launch(self) -> None:
        if self._is_closing or self._active_browser_launch is None:
            self._browser_timer.stop(); return
        for result in self.browser.get_launch_results():
            if result.generation != self._active_browser_launch:
                continue
            self._active_browser_launch = None; self._browser_timer.stop()
            if result.success:
                self.open_button.setEnabled(True)
                self.status.setText("PRISMA opened in the default browser")
            else:
                self._browser_start_failed(result.error or "Unknown error")
            return

    def _browser_start_failed(self, exc: Exception | str) -> None:
        if self._is_closing: return
        self._active_browser_launch = None; self._browser_timer.stop()
        self.open_button.setEnabled(True)
        reason = str(exc).strip() or exc.__class__.__name__
        QMessageBox.critical(self, "Browser Error", f"Failed to open the browser. Reason: {reason}")
        self.status.setText("Failed to open the browser")

    def start_processing(self) -> None:
        source = Path(self.csv_path.text())
        if not source.is_file():
            QMessageBox.warning(self, "CSV Not Selected", "Select a CSV file first."); return
        self.process_button.setEnabled(False); self.status.setText("Processing CSV...")
        thread = threading.Thread(target=self._process_worker, args=(source,), daemon=False,
                                  name="prisma-processing")
        self._processing_threads.add(thread); thread.start()

    def _process_worker(self, source: Path) -> None:
        try:
            rows = process_csv(source); storage = AuctionStorage(DATABASE_PATH)
            stats = storage.upsert(rows)
            result_path = storage.export_excel(RESULT_DIR / "prisma_auctions.xlsx")
            self.signals.processing_succeeded.emit(
                f"Done. Processed: {stats['processed']}; inserted: {stats['inserted']}; "
                f"updated: {stats['updated']}; unchanged: {stats['unchanged']}. Result: {result_path.name}")
        except Exception as exc:
            self.signals.processing_failed.emit(str(exc))

    def _processing_succeeded(self, text: str) -> None:
        if not self._is_closing: self.status.setText(text); self.process_button.setEnabled(True)

    def _processing_failed(self, error: str) -> None:
        if not self._is_closing:
            QMessageBox.critical(self, "Processing Error", error)
            self.status.setText("Processing failed"); self.process_button.setEnabled(True)

    def open_result(self) -> None:
        result = RESULT_DIR / "prisma_auctions.xlsx"
        if not result.exists():
            QMessageBox.information(self, "Result Not Found", "Process a CSV file first."); return
        os.startfile(result)

    def create_monitoring_engine(self) -> MonitoringEngine:
        return MonitoringEngine(lambda record: record.last_known_status)

    def create_monitoring_scheduler(self, records: list[AuctionCsvRecord]) -> MonitoringScheduler:
        return MonitoringScheduler(self.create_monitoring_engine(), lambda: records)

    def start_monitoring(self) -> None:
        if self._monitoring_thread is not None: return
        records = [record for record in self._auction_records if record.enabled]
        if not records:
            QMessageBox.critical(self, "Monitoring Error", "No usable auction records are available."); return
        stop_event = threading.Event(); scheduler = self.create_monitoring_scheduler(records)
        thread = threading.Thread(target=self._monitoring_worker, args=(scheduler, stop_event),
                                  daemon=False, name="prisma-monitoring")
        self._monitoring_stop_event = stop_event; self._monitoring_thread = thread
        self.start_monitoring_button.setEnabled(False); self.stop_monitoring_button.setEnabled(True)
        self.status.setText("Monitoring started")
        try: thread.start()
        except Exception as exc:
            self._set_monitoring_idle(); reason = str(exc).strip() or exc.__class__.__name__
            self.status.setText("Failed to start monitoring")
            QMessageBox.critical(self, "Monitoring Error", f"Failed to start monitoring: {reason}")

    def stop_monitoring(self) -> None:
        if self._monitoring_stop_event is not None: self._monitoring_stop_event.set()

    def _monitoring_worker(self, scheduler: MonitoringScheduler, stop_event: threading.Event) -> None:
        error = None
        try: scheduler.run_forever(stop_event, DEFAULT_MONITORING_INTERVAL_SECONDS)
        except Exception as exc: error = exc
        self.signals.monitoring_finished.emit(error)

    def _monitoring_finished(self, error: object = None) -> None:
        if self._is_closing: return
        self._set_monitoring_idle()
        if error is not None:
            reason = str(error).strip() or error.__class__.__name__
            self.status.setText("Monitoring failed")
            QMessageBox.critical(self, "Monitoring Error", f"Monitoring stopped because of an error: {reason}")
        else: self.status.setText("Monitoring stopped")

    def _set_monitoring_idle(self) -> None:
        self._monitoring_thread = None; self._monitoring_stop_event = None
        self.start_monitoring_button.setEnabled(True); self.stop_monitoring_button.setEnabled(False)

    def stop_work(self) -> None:
        self.browser.stop(); self._active_browser_launch = None; self._browser_timer.stop()
        self.open_button.setEnabled(True)
        self.status.setText("Browser closed. Current CSV processing will finish safely.")

    def closeEvent(self, event) -> None:
        self._is_closing = True; self._browser_timer.stop(); self._active_browser_launch = None
        if self._monitoring_stop_event is not None: self._monitoring_stop_event.set()
        self.browser.stop()
        threads = ([self._monitoring_thread] if self._monitoring_thread else []) + list(self._processing_threads)
        for thread in threads:
            if thread is not threading.current_thread() and thread.is_alive(): thread.join()
        event.accept()


def main() -> int:
    application = QApplication.instance() or QApplication(sys.argv)
    window = PrismaMonitorApp(); window.show()
    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
