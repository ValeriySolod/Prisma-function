from __future__ import annotations

import logging
import sys
import threading
import time
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from collections.abc import Callable

from PySide6.QtCore import QDate, QObject, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QDateEdit,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLayout,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from csv_contracts import CsvFormatError
from date_range_selection import (
    DateRange,
    DateRangeSelection,
    describe_rejection as describe_date_range_rejection,
)
from download_directory import (
    DownloadDirectoryError,
    DownloadDirectorySelection,
    default_managed_download_directory,
    ensure_directory_exists,
)
from manual_csv_selection import ManualCsvSelection, describe_rejection
from mapping_presentation import build_mapping_rows
from prisma_download import (
    PrismaDownloadValidationOutcome,
    describe_validation_rejection,
    validate_download_configuration,
)
from prisma_import_workflow import PrismaWorkflowResult, run_prisma_import_workflow
from prisma_lifecycle import PrismaLifecycleController, PrismaLifecycleEvent, PrismaLifecycleState
from processor import PrismaImportError, import_prisma_export
from runtime_logging import (
    LOGGER_NAME,
    initialize_runtime_logging,
    safe_log,
)
from runtime_paths import RuntimePathError, RuntimePaths, migrate_legacy_runtime_data, runtime_paths
from ui_components import APP_STYLE, MappingTableModel
from version import APP_DISPLAY_NAME, __version__

PRISMA_SHUTDOWN_GRACE_SECONDS = 5.0


def _current_local_date() -> date:
    """Return today's local calendar date, isolated so tests can inject a fixed value."""
    return date.today()


@dataclass(frozen=True)
class ProcessingOutcome:
    result: PrismaWorkflowResult | None
    error: str | None
    generation: int


class WorkerSignals(QObject):
    processing_finished = Signal(object)


class PrismaMonitorApp(QMainWindow):
    def __init__(self, paths: RuntimePaths, download_directory: Path) -> None:
        super().__init__()
        self._runtime_paths = paths
        self._download_directory = DownloadDirectorySelection(download_directory)
        self._manual_csv_selection = ManualCsvSelection()
        self._date_range_selection = DateRangeSelection()
        self.setWindowTitle(f"{APP_DISPLAY_NAME} v{__version__}")
        self.setMinimumSize(1080, 680)
        self.resize(1280, 800)
        self.prisma_lifecycle = PrismaLifecycleController()
        self._logger = logging.getLogger(LOGGER_NAME)
        self._is_closing = False
        self._active_prisma_generation: int | None = None
        self._prisma_open = False
        self._prisma_closing = False
        self._prisma_close_error = False
        self._prisma_shutdown_deadline: float | None = None
        self._processing_threads: set[threading.Thread] = set()
        self._active_processing_thread: threading.Thread | None = None
        self._processing_active = False
        self._processing_generation = 0
        self._shutdown_started = False
        self.signals = WorkerSignals(self)
        self.signals.processing_finished.connect(self._processing_finished)
        self._prisma_timer = QTimer(self)
        self._prisma_timer.setInterval(50)
        self._prisma_timer.timeout.connect(self._poll_prisma_lifecycle)
        self._build_ui()
        self._update_controls()

    def _button(
        self,
        text: str,
        handler: Callable[[], None],
        *,
        primary: bool = False,
        sidebar: bool = True,
        tooltip: str = "",
    ) -> QPushButton:
        button = QPushButton(text)
        button.clicked.connect(handler)
        button.setProperty("primary", primary)
        button.setProperty("sidebar", sidebar)
        button.setToolTip(tooltip)
        button.setAccessibleName(text)
        return button

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("workspace")
        outer = QHBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(260)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(22, 24, 22, 22)
        side.setSpacing(9)
        brand = QLabel("PrismaFunction")
        brand.setObjectName("brand")
        subtitle = QLabel("PRISMA Export processing")
        subtitle.setObjectName("subtitle")
        side.addWidget(brand)
        side.addWidget(subtitle)
        side.addSpacing(20)
        self.open_prisma_button = self._button(
            "Open Prisma", self._open_prisma_session, primary=True,
            tooltip=(
                "Open the official PRISMA auctions page in an "
                "application-owned browser session"
            ),
        )
        self.close_prisma_button = self._button(
            "Close Prisma", self._close_prisma_session,
            tooltip="Close the PrismaFunction-managed PRISMA browser session",
        )
        self._side_group(side, "PRISMA", self.open_prisma_button, self.close_prisma_button)
        self.choose_download_directory_button = self._button(
            "Choose Download Folder", self._select_download_directory,
            tooltip="Choose the folder where the downloaded PRISMA CSV is saved",
        )
        self.download_directory_label = QLabel(str(self._download_directory.current))
        self.download_directory_label.setObjectName("filename")
        self.download_directory_label.setWordWrap(True)
        self.download_directory_label.setAccessibleName("Expected download folder")
        self._side_group(
            side, "DOWNLOAD FOLDER", self.choose_download_directory_button, self.download_directory_label
        )
        self.choose_manual_csv_button = self._button(
            "Select CSV", self._select_manual_csv,
            tooltip="Select the manually downloaded official PRISMA Export CSV",
        )
        self.manual_csv_label = QLabel("No CSV selected")
        self.manual_csv_label.setObjectName("filename")
        self.manual_csv_label.setWordWrap(True)
        self.manual_csv_label.setAccessibleName("Selected PRISMA Export CSV")
        self._side_group(
            side, "PRISMA EXPORT CSV", self.choose_manual_csv_button, self.manual_csv_label
        )
        today = _current_local_date()
        initial_date_range_qdate = QDate(today.year, today.month, today.day)
        self.start_date_edit = QDateEdit()
        self.start_date_edit.setCalendarPopup(True)
        self.start_date_edit.setDisplayFormat("yyyy-MM-dd")
        self.start_date_edit.setSpecialValueText("Not set")
        self.start_date_edit.setDate(initial_date_range_qdate)
        self.start_date_edit.setAccessibleName("Start date")
        self.end_date_edit = QDateEdit()
        self.end_date_edit.setCalendarPopup(True)
        self.end_date_edit.setDisplayFormat("yyyy-MM-dd")
        self.end_date_edit.setSpecialValueText("Not set")
        self.end_date_edit.setDate(initial_date_range_qdate)
        self.end_date_edit.setAccessibleName("End date")
        self.validate_date_range_button = self._button(
            "Validate Date Range", self._validate_date_range,
            tooltip="Validate and accept the selected start and end date",
        )
        self.date_range_label = QLabel("No date range selected")
        self.date_range_label.setObjectName("filename")
        self.date_range_label.setWordWrap(True)
        self.date_range_label.setAccessibleName("Accepted date range")
        self._side_group(
            side, "DATE RANGE",
            self.start_date_edit, self.end_date_edit,
            self.validate_date_range_button, self.date_range_label,
        )
        side.addStretch()
        self.import_date = QDateEdit(QDate.currentDate())
        self.import_date.setCalendarPopup(True)
        self.import_date.setDisplayFormat("yyyy-MM-dd")
        self.import_date.setAccessibleName("PRISMA export source date")
        self.import_date_label = QLabel("PRISMA EXPORT DATE")
        self.import_date_label.setObjectName("subtitle")
        source_date_help = (
            "Identifies the daily PRISMA source and is used for controlled "
            "update and exact-retry validation."
        )
        self.import_date_label.setToolTip(source_date_help)
        self.import_date.setToolTip(source_date_help)
        self.process_button = self._button(
            "Import PRISMA Export", self.start_processing, sidebar=True,
            tooltip="Import a complete original PRISMA Export CSV"
        )
        side.addWidget(self.import_date_label)
        side.addWidget(self.import_date)
        self.open_result_button = self._button("Open Result", self.open_result, sidebar=True)
        side.addWidget(self.process_button)
        side.addWidget(self.open_result_button)
        version = QLabel(f"Version {__version__}")
        version.setObjectName("subtitle")
        side.addWidget(version)

        content = QWidget()
        content.setObjectName("contentArea")
        main = QVBoxLayout(content)
        main.setContentsMargins(28, 22, 28, 20)
        main.setSpacing(16)
        header = QHBoxLayout()
        titles = QVBoxLayout()
        title = QLabel("PRISMA Export processing")
        title.setStyleSheet("font-size: 19pt; font-weight: 700; color: #152033")
        titles.addWidget(title)
        content_subtitle = QLabel(
            "Select a date range, obtain a PRISMA Export CSV, and publish the transformed output."
        )
        content_subtitle.setObjectName("contentSubtitle")
        titles.addWidget(content_subtitle)
        header.addLayout(titles)
        header.addStretch()
        self.prisma_badge = QLabel("Prisma closed")
        self.prisma_badge.setObjectName("browserBadge")
        header.addWidget(self.prisma_badge)
        main.addLayout(header)
        mapping_panel = QFrame()
        mapping_panel.setObjectName("panel")
        mapping_layout = QVBoxLayout(mapping_panel)
        mapping_layout.setContentsMargins(16, 14, 16, 10)
        mapping_header = QHBoxLayout()
        mapping_title = QLabel("Mapping")
        mapping_title.setObjectName("contentSectionLabel")
        mapping_header.addWidget(mapping_title)
        mapping_header.addStretch()
        mapping_layout.addLayout(mapping_header)
        self.mapping_table_model = MappingTableModel(self)
        self.mapping_table = QTableView()
        self.mapping_table.setModel(self.mapping_table_model)
        self.mapping_table.setAlternatingRowColors(True)
        self.mapping_table.setSelectionBehavior(QTableView.SelectRows)
        self.mapping_table.setAccessibleName("Mapping")
        self.mapping_table.verticalHeader().hide()
        mapping_hdr = self.mapping_table.horizontalHeader()
        mapping_hdr.setSectionResizeMode(QHeaderView.Stretch)
        mapping_layout.addWidget(self.mapping_table, 1)
        self.mapping_empty_label = QLabel(
            "No mapping evidence to display. Select or download a PRISMA Export CSV."
        )
        self.mapping_empty_label.setAlignment(Qt.AlignCenter)
        self.mapping_empty_label.setStyleSheet("color:#718096; padding:18px")
        mapping_layout.addWidget(self.mapping_empty_label)
        main.addWidget(mapping_panel, 1)
        status_row = QHBoxLayout()
        status_caption = QLabel("Status:")
        status_caption.setObjectName("contentSectionLabel")
        status_row.addWidget(status_caption)
        self.status = QLabel("Ready")
        self.status.setObjectName("primaryStatus")
        self.status.setWordWrap(True)
        status_row.addWidget(self.status, 1)
        main.addLayout(status_row)
        outer.addWidget(sidebar)
        outer.addWidget(content, 1)
        self.setCentralWidget(root)
        self.setStyleSheet(APP_STYLE)
        self._set_badge(self.prisma_badge, "Prisma closed", "idle")
        self._update_mapping_empty_state()

    @staticmethod
    def _side_group(layout: QLayout, label: str, *widgets: QWidget) -> QLabel:
        heading = QLabel(label)
        heading.setObjectName("section")
        layout.addWidget(heading)
        for widget in widgets:
            layout.addWidget(widget)
        layout.addSpacing(13)
        return heading

    def _set_badge(self, badge: QLabel, text: str, state: str) -> None:
        badge.setText(text)
        badge.setProperty("state", state)
        badge.style().unpolish(badge)
        badge.style().polish(badge)

    def _update_controls(self) -> None:
        self.process_button.setEnabled(not self._processing_active)
        self.import_date.setEnabled(not self._processing_active)
        prisma_opening = self._active_prisma_generation is not None and not self._prisma_open
        prisma_locked = self._prisma_closing or self._prisma_close_error
        self.open_prisma_button.setEnabled(
            not prisma_opening and not self._prisma_open and not prisma_locked
        )
        self.close_prisma_button.setEnabled(
            (prisma_opening or self._prisma_open) and not prisma_locked
        )

    def _select_download_directory(self) -> None:
        selected = QFileDialog.getExistingDirectory(
            self, "Choose Download Folder", str(self._download_directory.current)
        )
        if not selected:
            return
        try:
            directory = self._download_directory.select(selected)
        except DownloadDirectoryError as exc:
            safe_log(self._logger, logging.ERROR, "Download directory selection rejected: %s", exc)
            self._show_error(
                "Download Folder",
                "The selected folder is not valid. Choose an existing, accessible folder.",
            )
            return
        self.download_directory_label.setText(str(directory))
        self.status.setText("Download folder updated.")

    def _update_mapping_empty_state(self) -> None:
        has_rows = self.mapping_table_model.rowCount() > 0
        self.mapping_table.setVisible(has_rows)
        self.mapping_empty_label.setVisible(not has_rows)

    def _clear_mapping_display(self) -> None:
        """Discard any displayed mapping rows and show the empty state.

        Used whenever a CSV replacement attempt does not end in a freshly
        refreshed mapping display, so a rejected candidate can never leave a
        previous selection's rows visible.
        """
        self.mapping_table_model.set_rows(())
        self._update_mapping_empty_state()

    def _refresh_mapping_display(self, path: Path) -> None:
        """Refresh the P.36.8 mapping presentation for the current CSV selection.

        Re-runs the read-only P.36.15 import/enrichment boundary
        (`processor.import_prisma_export`, the same boundary
        `prisma_output.write_prisma_output` already uses) purely to obtain
        already-resolved mapping evidence for display; it writes no output
        file and touches no browser, network, or publication behavior. A
        failure clears the table rather than leaving stale rows from a
        previous selection.
        """
        try:
            imported = import_prisma_export(path)
        except (PrismaImportError, CsvFormatError, OSError) as exc:
            safe_log(self._logger, logging.ERROR, "Mapping preview failed: %s", exc)
            self._clear_mapping_display()
            self._show_error(
                "Mapping",
                "The mapping evidence for the selected PRISMA Export CSV could not be displayed.",
            )
            return
        self.mapping_table_model.set_rows(build_mapping_rows(imported))
        self._update_mapping_empty_state()

    def _select_manual_csv(self) -> None:
        selected, _ = QFileDialog.getOpenFileName(
            self, "Select PRISMA Export CSV", str(self._download_directory.current), "CSV files (*.csv)"
        )
        if not selected:
            return
        result = self._manual_csv_selection.select(selected)
        if not result.accepted:
            safe_log(
                self._logger, logging.WARNING,
                "Manual PRISMA Export CSV selection rejected: %s", result.outcome.value,
            )
            self._clear_mapping_display()
            self._show_error("Select CSV", describe_rejection(result.outcome))
            return
        self.manual_csv_label.setText(result.path.name)
        self.status.setText("PRISMA Export CSV selected.")
        self._refresh_mapping_display(result.path)

    @staticmethod
    def _read_optional_date(widget: QDateEdit) -> date | None:
        if widget.date() == widget.minimumDate():
            return None
        return widget.date().toPython()

    def _set_date_range_widgets(self, date_range: DateRange) -> None:
        self.start_date_edit.setDate(
            QDate(date_range.start.year, date_range.start.month, date_range.start.day)
        )
        self.end_date_edit.setDate(
            QDate(date_range.end.year, date_range.end.month, date_range.end.day)
        )

    @staticmethod
    def _format_date_range(date_range: DateRange) -> str:
        return f"Accepted: {date_range.start.isoformat()} to {date_range.end.isoformat()}"

    def _validate_date_range(self) -> None:
        start = self._read_optional_date(self.start_date_edit)
        end = self._read_optional_date(self.end_date_edit)
        result = self._date_range_selection.select(start, end)
        if not result.accepted:
            safe_log(
                self._logger, logging.WARNING,
                "Date range validation rejected: %s", result.outcome.value,
            )
            self._show_error("Date Range", describe_date_range_rejection(result.outcome))
            return
        self._set_date_range_widgets(result.date_range)
        self.date_range_label.setText(self._format_date_range(result.date_range))
        self.status.setText("Date range accepted.")

    def _open_prisma_session(self) -> None:
        if (
            self._active_prisma_generation is not None
            or self._prisma_open
            or self._prisma_closing
            or self._prisma_close_error
        ):
            return
        date_range = self._date_range_selection.current
        download_directory = self._download_directory.current
        validation_outcome = validate_download_configuration(date_range, download_directory)
        if validation_outcome is not PrismaDownloadValidationOutcome.ACCEPTED:
            safe_log(
                self._logger, logging.WARNING,
                "Open Prisma rejected: %s", validation_outcome.value,
            )
            self._show_error("Open Prisma", describe_validation_rejection(validation_outcome))
            return
        try:
            self.status.setText("Opening PRISMA…")
            self._set_badge(self.prisma_badge, "Opening PRISMA…", "working")
            self._active_prisma_generation = self.prisma_lifecycle.open(
                date_range=date_range, download_directory=download_directory,
            )
            self._prisma_timer.start()
            self._update_controls()
        except Exception as exc:
            self._prisma_open_failed(exc)

    def _poll_prisma_lifecycle(self) -> None:
        if self._is_closing or self._active_prisma_generation is None:
            self._prisma_timer.stop()
            return
        target_generation = self._active_prisma_generation
        terminal_reached = False
        controls_dirty = False
        events = self.prisma_lifecycle.get_events()
        for event in events:
            if terminal_reached or event.generation != target_generation:
                continue
            if event.kind == "open":
                if event.success:
                    self._prisma_open = True
                    self._set_badge(self.prisma_badge, "Prisma open", "ready")
                    self.status.setText("PRISMA opened in the managed browser session.")
                    controls_dirty = True
                else:
                    self._prisma_open_failed(event.error or "Unknown error")
                    terminal_reached = True
            elif event.kind == "download":
                self._handle_download_event(event)
            elif event.kind == "close":
                if event.success:
                    self._active_prisma_generation = None
                    self._prisma_open = False
                    self._prisma_closing = False
                    self._prisma_timer.stop()
                    self._set_badge(self.prisma_badge, "Prisma closed", "idle")
                    self.status.setText("PRISMA closed")
                    controls_dirty = True
                else:
                    self._prisma_close_failed(event.error or "Unknown error")
                terminal_reached = True
            else:
                self._active_prisma_generation = None
                self._prisma_open = False
                self._prisma_closing = False
                self._prisma_timer.stop()
                self._set_badge(self.prisma_badge, "Prisma closed", "idle")
                self.status.setText("PRISMA was closed manually. Open Prisma to retry.")
                controls_dirty = True
                terminal_reached = True
        if controls_dirty:
            self._update_controls()

    def _handle_download_event(self, event: PrismaLifecycleEvent) -> None:
        if not event.success:
            safe_log(
                self._logger, logging.WARNING,
                "Managed PRISMA download failed: %s", event.error,
            )
            self.status.setText(event.error or "The PRISMA CSV download failed.")
            self._show_error("PRISMA Download", event.error or "The PRISMA CSV download failed.")
            return
        result = self._manual_csv_selection.select(event.csv_path)
        if not result.accepted:
            safe_log(
                self._logger, logging.WARNING,
                "Downloaded PRISMA CSV rejected: %s", result.outcome.value,
            )
            self.status.setText(
                "The downloaded PRISMA CSV did not match the expected export format."
            )
            self._clear_mapping_display()
            self._show_error("PRISMA Download", describe_rejection(result.outcome))
            return
        self.manual_csv_label.setText(result.path.name)
        self.status.setText(f"PRISMA CSV downloaded: {result.path.name}")
        self._refresh_mapping_display(result.path)

    def _prisma_open_failed(self, exc: Exception | str) -> None:
        if self._is_closing:
            return
        self._active_prisma_generation = None
        self._prisma_open = False
        self._prisma_timer.stop()
        safe_log(self._logger, logging.ERROR, "Open Prisma failed: %s", exc)
        self._set_badge(self.prisma_badge, "Prisma error", "error")
        self._update_controls()
        self._show_error(
            "Prisma Error",
            "PRISMA could not be opened. Check Chrome or Edge and try again.",
        )
        self.status.setText("Failed to open PRISMA")

    def _prisma_close_failed(self, exc: Exception | str) -> None:
        self._active_prisma_generation = None
        self._prisma_open = False
        self._prisma_closing = False
        self._prisma_close_error = True
        self._prisma_timer.stop()
        safe_log(self._logger, logging.ERROR, "Close Prisma cleanup failed: %s", exc)
        self._set_badge(self.prisma_badge, "Prisma close error", "error")
        self._update_controls()
        self._show_error(
            "Prisma Error",
            "PRISMA could not be confirmed closed. Check Task Manager for a "
            "lingering browser process, then restart PrismaFunction.",
        )
        self.status.setText(
            "PRISMA could not be confirmed closed. Restart PrismaFunction after "
            "checking Task Manager for a lingering browser process."
        )

    def _close_prisma_session(self) -> None:
        if self._prisma_closing or self._prisma_close_error:
            return
        had_active_session = self._active_prisma_generation is not None
        self.prisma_lifecycle.close()
        if not had_active_session:
            self._prisma_open = False
            self._set_badge(self.prisma_badge, "Prisma closed", "idle")
            self.status.setText("PRISMA closed")
            self._update_controls()
            return
        self._prisma_closing = True
        self._set_badge(self.prisma_badge, "Closing Prisma…", "working")
        self.status.setText("Closing PRISMA…")
        self._update_controls()

    def start_processing(self) -> None:
        if self._processing_active:
            return
        selected, _ = QFileDialog.getOpenFileName(
            self, "Import PRISMA Export CSV", "", "CSV files (*.csv)"
        )
        if not selected:
            return
        source = Path(selected)
        self._processing_active = True
        self.status.setText("Importing PRISMA Export CSV…")
        self._update_controls()
        selected_date = self.import_date.date().toPython()
        self._processing_generation += 1
        generation = self._processing_generation
        thread = threading.Thread(
            target=self._process_worker,
            args=(source, selected_date, generation),
            daemon=False,
            name="prisma-processing",
        )
        self._processing_threads.add(thread)
        self._active_processing_thread = thread
        try:
            thread.start()
        except Exception as exc:
            self._processing_threads.discard(thread)
            self._processing_active = False
            self._update_controls()
            self._processing_finished(ProcessingOutcome(None, str(exc), generation))

    def _process_worker(self, source: Path, source_date=None, generation: int = 0) -> None:
        try:
            result = run_prisma_import_workflow(
                source,
                source_date=source_date or datetime.now().date(),
                evaluated_at=datetime.now().astimezone(),
                database_path=self._runtime_paths.database,
                state_path=self._runtime_paths.state,
                output_path=self._runtime_paths.result,
            )
            self.signals.processing_finished.emit(
                ProcessingOutcome(result, None, generation)
            )
        except Exception as exc:
            self.signals.processing_finished.emit(
                ProcessingOutcome(None, str(exc), generation)
            )

    def _processing_finished(self, outcome: ProcessingOutcome) -> None:
        if outcome.generation != self._processing_generation:
            return
        if outcome.error is not None:
            self._processing_failed(outcome.error, None)
        elif outcome.result is not None:
            self._processing_succeeded(outcome.result, None)

    def _finish_processing(self, thread: threading.Thread | None) -> bool:
        if thread is None:
            thread = self._active_processing_thread
        if thread is not None and thread is not self._active_processing_thread:
            return False
        if thread is not None and thread.is_alive():
            thread.join(timeout=0.1)
        if thread is not None and not thread.is_alive():
            self._processing_threads.discard(thread)
        self._active_processing_thread = None
        self._processing_active = False
        self._update_controls()
        return True

    def _processing_succeeded(
        self, result: PrismaWorkflowResult, thread: threading.Thread | None
    ) -> None:
        if not self._is_closing and self._finish_processing(thread):
            self.status.setText(result.summary())

    def _processing_failed(
        self, error: str, thread: threading.Thread | None
    ) -> None:
        if not self._is_closing and self._finish_processing(thread):
            safe_log(self._logger, logging.ERROR, "Processing failed: %s", error)
            self._show_error(
                "Processing Error",
                f"PRISMA import failed: {error}",
            )
            self.status.setText(f"PRISMA import failed: {error}")

    def open_result(self) -> None:
        result = self._runtime_paths.result
        if not result.exists():
            QMessageBox.information(
                self, "Result Not Found", "Process a CSV file first."
            )
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(result)))

    def _show_error(self, title: str, message: str) -> None:
        QMessageBox.critical(self, title, message)

    def closeEvent(self, event) -> None:
        if not self._shutdown_started:
            self._shutdown_started = True
            self._is_closing = True
            self._prisma_timer.stop()
            self.prisma_lifecycle.close()
            self._prisma_shutdown_deadline = (
                time.monotonic() + PRISMA_SHUTDOWN_GRACE_SECONDS
            )
        threads = list(self._processing_threads)
        if any(
            thread is not threading.current_thread() and thread.is_alive()
            for thread in threads
        ):
            self.status.setText("Closing; a background import is finishing safely.")
            event.ignore()
            QTimer.singleShot(100, self.close)
            return
        if not self.prisma_lifecycle.join(timeout=0.05):
            if time.monotonic() < self._prisma_shutdown_deadline:
                self.status.setText(
                    "Closing; the PRISMA browser session is finishing safely."
                )
            else:
                self.status.setText(
                    "Closing is taking longer than expected while the PRISMA "
                    "browser session finishes; PrismaFunction will exit as soon "
                    "as it is safe to do so."
                )
            event.ignore()
            QTimer.singleShot(100, self.close)
            return
        if self.prisma_lifecycle.state is PrismaLifecycleState.CLOSE_FAILED:
            self.status.setText(
                "PRISMA browser cleanup could not be confirmed; PrismaFunction "
                "cannot exit safely. Close the browser window manually if it is "
                "still open, then check Task Manager for a lingering process."
            )
            event.ignore()
            QTimer.singleShot(100, self.close)
            return
        self._active_prisma_generation = None
        event.accept()


def main() -> int:
    application = QApplication.instance() or QApplication(sys.argv)
    application.setApplicationName(APP_DISPLAY_NAME)
    application.setApplicationVersion(__version__)
    initialization_error = None
    paths = None
    download_directory = None
    try:
        paths = runtime_paths()
        logger, log_path = initialize_runtime_logging(paths.log)
        if log_path is None:
            raise RuntimePathError(
                "The required user-data log file could not be created. "
                "Check LOCALAPPDATA and folder permissions, then retry."
            )
        migrate_legacy_runtime_data(paths=paths, logger=logger)
        download_directory = ensure_directory_exists(default_managed_download_directory())
    except Exception as exc:
        initialization_error = str(exc)
        if any(getattr(handler, "baseFilename", None) for handler in logging.getLogger(LOGGER_NAME).handlers):
            logging.getLogger(LOGGER_NAME).exception("Runtime-data initialization failed")
    if initialization_error is not None:
        QMessageBox.critical(
            None,
            "PrismaFunction Data Error",
            "PrismaFunction could not prepare its user-data directory. "
            f"No legacy data was discarded. {initialization_error}",
        )
        return 1
    window = PrismaMonitorApp(paths, download_directory)
    window.show()
    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
