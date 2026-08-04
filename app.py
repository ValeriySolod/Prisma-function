from __future__ import annotations

import logging
import sys
import threading
import time
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from pathlib import Path

from collections.abc import Callable

from PySide6.QtCore import QDate, QObject, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QDateEdit,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from auction_csv import AuctionCsvRecord, CsvValidationError, load_auction_csv
from browser import BrowserController
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
from monitoring import MonitoringEngine, MonitoringResult
from monitoring_storage import MonitoringStorage, MonitoringStorageError
from notifications import StatusChangeNotification
from prisma_page import (
    LivePrismaStatusAdapter,
    PrismaAuctionNotFoundError,
    PrismaLookupTimeoutError,
    PrismaPageStructureError,
    PrismaPageUnavailableError,
)
from prisma_download import (
    PrismaDownloadValidationOutcome,
    describe_validation_rejection,
    validate_download_configuration,
)
from prisma_import_workflow import PrismaWorkflowResult, run_prisma_import_workflow
from prisma_lifecycle import PrismaLifecycleController, PrismaLifecycleEvent, PrismaLifecycleState
from runtime_logging import (
    LOGGER_NAME,
    initialize_runtime_logging,
    safe_log,
)
from runtime_paths import RuntimePathError, RuntimePaths, migrate_legacy_runtime_data, runtime_paths
from scheduler import MonitoringScheduler
from ui_components import (
    APP_STYLE,
    ArrowComboBox,
    AuctionFilterModel,
    AuctionTableModel,
    StatusDelegate,
    SummaryCard,
)
from version import APP_DISPLAY_NAME, __version__

DEFAULT_MONITORING_INTERVAL_SECONDS = 30.0
PRISMA_SHUTDOWN_GRACE_SECONDS = 5.0


def _current_local_date() -> date:
    """Return today's local calendar date, isolated so tests can inject a fixed value."""
    return date.today()


@dataclass(frozen=True)
class ProcessingOutcome:
    result: PrismaWorkflowResult | None
    error: str | None
    generation: int


class ActivityKind(Enum):
    ACTIVITY = "activity"
    STATUS_CHANGE = "status-change"


class WorkerSignals(QObject):
    processing_finished = Signal(object)
    monitoring_results = Signal(object)
    monitoring_finished = Signal(object)


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
        self.browser = BrowserController()
        self.prisma_lifecycle = PrismaLifecycleController()
        self._logger = logging.getLogger(LOGGER_NAME)
        self._is_closing = False
        self._browser_ready = False
        self._active_browser_launch: int | None = None
        self._active_prisma_generation: int | None = None
        self._prisma_open = False
        self._prisma_closing = False
        self._prisma_close_error = False
        self._prisma_shutdown_deadline: float | None = None
        self._auction_records: list[AuctionCsvRecord] = []
        self._monitoring_thread: threading.Thread | None = None
        self._monitoring_stop_event: threading.Event | None = None
        self._processing_threads: set[threading.Thread] = set()
        self._active_processing_thread: threading.Thread | None = None
        self._processing_active = False
        self._processing_generation = 0
        self._shutdown_started = False
        self.signals = WorkerSignals(self)
        self.signals.processing_finished.connect(self._processing_finished)
        self.signals.monitoring_results.connect(self._monitoring_results)
        self.signals.monitoring_finished.connect(self._monitoring_finished)
        self._browser_timer = QTimer(self)
        self._browser_timer.setInterval(50)
        self._browser_timer.timeout.connect(self._poll_browser_launch)
        self._prisma_timer = QTimer(self)
        self._prisma_timer.setInterval(50)
        self._prisma_timer.timeout.connect(self._poll_prisma_lifecycle)
        self._build_ui()
        self._update_controls()
        self._add_activity("Application ready")

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
        subtitle = QLabel("PRISMA auction monitoring")
        subtitle.setObjectName("subtitle")
        side.addWidget(brand)
        side.addWidget(subtitle)
        side.addSpacing(20)
        self.open_button = self._button("Open Browser", self.open_prisma, primary=True,
            tooltip="Open a PrismaFunction-managed PRISMA browser session")
        self.stop_browser_button = self._button("Stop Browser", self.stop_work)
        browser_heading = self._side_group(side, "BROWSER", self.open_button, self.stop_browser_button)
        self.load_csv_button = self._button("Load Monitoring CSV", self.select_csv, primary=True)
        self.csv_filename = QLabel("No CSV selected")
        self.csv_filename.setObjectName("filename")
        self.csv_count = QLabel("0 records loaded")
        data_source_heading = self._side_group(
            side, "DATA SOURCE", self.load_csv_button, self.csv_filename, self.csv_count
        )
        self.start_monitoring_button = self._button("Start Monitoring", self.start_monitoring, primary=True)
        self.stop_monitoring_button = self._button("Stop Monitoring", self.stop_monitoring)
        monitoring_heading = self._side_group(
            side, "MONITORING", self.start_monitoring_button, self.stop_monitoring_button
        )
        # P.36.2: the manual CSV workflow replaces the live monitoring dashboard,
        # scheduler, and automated monitoring workflow (see ROADMAP.md). These
        # controls stay in the codebase for now (full removal is P.36.10) but are
        # hidden so they cannot be triggered through the UI and do not appear as
        # an active product workflow alongside the new PRISMA lifecycle controls.
        for widget in (
            browser_heading, self.open_button, self.stop_browser_button,
            data_source_heading, self.load_csv_button, self.csv_filename, self.csv_count,
            monitoring_heading, self.start_monitoring_button, self.stop_monitoring_button,
        ):
            widget.hide()
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
        title = QLabel("Monitoring dashboard")
        title.setStyleSheet("font-size: 19pt; font-weight: 700; color: #152033")
        titles.addWidget(title)
        dashboard_subtitle = QLabel(
            "Track PRISMA auction states from your validated CSV data."
        )
        dashboard_subtitle.setObjectName("dashboardSubtitle")
        titles.addWidget(dashboard_subtitle)
        header.addLayout(titles)
        header.addStretch()
        self.browser_badge = QLabel("Disconnected")
        self.browser_badge.setObjectName("browserBadge")
        self.monitor_badge = QLabel("Monitoring idle")
        self.monitor_badge.setObjectName("monitorBadge")
        self.browser_badge.hide()
        self.monitor_badge.hide()
        self.prisma_badge = QLabel("Prisma closed")
        self.prisma_badge.setObjectName("browserBadge")
        header.addWidget(self.browser_badge)
        header.addWidget(self.monitor_badge)
        header.addWidget(self.prisma_badge)
        main.addLayout(header)
        cards = QHBoxLayout()
        self.summary_cards: dict[str, SummaryCard] = {}
        for key, caption in (("total", "Total"), ("active", "Pending / active"),
                             ("completed", "Completed"), ("errors", "Errors")):
            card = SummaryCard(caption)
            self.summary_cards[key] = card
            cards.addWidget(card)
        main.addLayout(cards)
        panel = QFrame()
        panel.setObjectName("panel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(16, 14, 16, 10)
        tools = QHBoxLayout()
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search Auction ID, lot, or market…")
        self.search_box.setClearButtonEnabled(True)
        self.search_box.setAccessibleName("Search auctions")
        self.status_filter = ArrowComboBox()
        self.status_filter.setProperty("arrowImplementation", "custom-paint")
        self.status_filter.addItems(
            ["All statuses", "Pending", "Scheduled", "Open", "In Progress", "Completed", "Cancelled", "Error", "Disabled"])
        self.status_filter.setAccessibleName("Filter by status")
        tools.addWidget(self.search_box, 1)
        tools.addWidget(self.status_filter)
        panel_layout.addLayout(tools)
        self.table_model = AuctionTableModel(self)
        self.proxy_model = AuctionFilterModel(self)
        self.proxy_model.setSourceModel(self.table_model)
        self.csv_table = QTableView()
        self.csv_table.setModel(self.proxy_model)
        self.csv_table.setAlternatingRowColors(True)
        self.csv_table.setSortingEnabled(True)
        self.csv_table.setSelectionBehavior(QTableView.SelectRows)
        self.csv_table.setAccessibleName("Auctions")
        self.csv_table.verticalHeader().hide()
        self.csv_table.setItemDelegateForColumn(4, StatusDelegate(self.csv_table))
        self.csv_table.setItemDelegateForColumn(5, StatusDelegate(self.csv_table))
        hdr = self.csv_table.horizontalHeader()
        hdr.setSectionResizeMode(QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(2, QHeaderView.Stretch)
        panel_layout.addWidget(self.csv_table, 1)
        self.empty_label = QLabel("Load a CSV file to begin monitoring auctions.")
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setStyleSheet("color:#718096; padding:18px")
        panel_layout.addWidget(self.empty_label)
        main.addWidget(panel, 1)
        activity_panel = QFrame()
        activity_panel.setObjectName("panel")
        activity_layout = QVBoxLayout(activity_panel)
        activity_header = QHBoxLayout()
        activity_title = QLabel("Recent activity")
        activity_title.setObjectName("contentSectionLabel")
        activity_header.addWidget(activity_title)
        activity_header.addStretch()
        self.open_logs_button = self._button("Open log folder", self.open_log_directory, sidebar=False)
        self.clear_activity_button = self._button("Clear", self.clear_activity, sidebar=False)
        activity_header.addWidget(self.open_logs_button)
        activity_header.addWidget(self.clear_activity_button)
        self.activity_list = QListWidget()
        self.activity_list.setObjectName("activityList")
        self.activity_list.setMaximumHeight(105)
        activity_layout.addLayout(activity_header)
        activity_layout.addWidget(self.activity_list)
        main.addWidget(activity_panel)
        status_row = QHBoxLayout()
        status_caption = QLabel("Status:")
        status_caption.setObjectName("contentSectionLabel")
        status_row.addWidget(status_caption)
        self.status = QLabel("Ready")
        self.status.setObjectName("primaryStatus")
        self.status.setWordWrap(True)
        status_row.addWidget(self.status, 1)
        main.addLayout(status_row)
        self.csv_path = QLineEdit()
        self.csv_path.hide()  # compatibility/state holder, not user-editable
        outer.addWidget(sidebar)
        outer.addWidget(content, 1)
        self.setCentralWidget(root)
        self.setStyleSheet(APP_STYLE)
        self.search_box.textChanged.connect(self.proxy_model.set_search)
        self.status_filter.currentTextChanged.connect(self.proxy_model.set_status)
        self._set_badge(self.browser_badge, "Disconnected", "idle")
        self._set_badge(self.monitor_badge, "Monitoring idle", "idle")
        self._set_badge(self.prisma_badge, "Prisma closed", "idle")

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

    def _add_activity(
        self, message: str, kind: ActivityKind = ActivityKind.ACTIVITY
    ) -> None:
        label = "Status change — " if kind is ActivityKind.STATUS_CHANGE else ""
        item = QListWidgetItem(f"{datetime.now():%H:%M:%S}  {label}{message}")
        item.setData(Qt.UserRole, kind.value)
        if kind is ActivityKind.STATUS_CHANGE:
            font = item.font()
            font.setBold(True)
            item.setFont(font)
            item.setForeground(QColor("#075985"))
            item.setData(
                Qt.AccessibleDescriptionRole,
                f"Status change notification. {message}",
            )
        self.activity_list.insertItem(0, item)
        while self.activity_list.count() > 50:
            self.activity_list.takeItem(self.activity_list.count() - 1)

    def clear_activity(self) -> None:
        self.activity_list.clear()

    def _update_controls(self) -> None:
        launching = self._active_browser_launch is not None and not self._browser_ready
        monitoring = self._monitoring_thread is not None
        has_records = any(record.enabled for record in self._auction_records)
        self.open_button.setEnabled(not launching and not self._browser_ready)
        self.stop_browser_button.setEnabled(launching or self._browser_ready)
        self.load_csv_button.setEnabled(not monitoring)
        self.start_monitoring_button.setEnabled(self._browser_ready and has_records and not monitoring)
        self.stop_monitoring_button.setEnabled(monitoring)
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
        self._add_activity("Download folder changed")

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
            self._show_error("Select CSV", describe_rejection(result.outcome))
            return
        self.manual_csv_label.setText(result.path.name)
        self.status.setText("PRISMA Export CSV selected.")
        self._add_activity("PRISMA Export CSV selected")

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
        self._add_activity("Date range accepted")

    def select_csv(self) -> None:
        selected, _ = QFileDialog.getOpenFileName(self, "Load Monitoring CSV", "", "CSV files (*.csv)")
        if not selected:
            return
        try:
            records = load_auction_csv(selected)
        except CsvValidationError as exc:
            self._show_error("CSV Error", str(exc))
            return
        except Exception as exc:
            safe_log(self._logger, logging.ERROR, "CSV load failed: %s", exc)
            self._show_error(
                "CSV Error",
                "The CSV file could not be loaded. Check the file and try again.",
            )
            return
        self._auction_records = records
        self.csv_path.setText(selected)
        self.table_model.set_records(records)
        self.csv_filename.setText(Path(selected).name)
        self.csv_count.setText(f"{len(records)} records loaded")
        self.empty_label.hide()
        self._update_summary()
        self._update_controls()
        self.status.setText(f"Loaded {Path(selected).name}: {len(records)} records")
        self._add_activity(f"CSV loaded: {Path(selected).name} ({len(records)} records)")

    def _display_csv_records(self, records: list[AuctionCsvRecord]) -> None:
        self.table_model.set_records(records)
        self.empty_label.setVisible(not records)
        self._update_summary()

    def _update_summary(self) -> None:
        for key, count in self.table_model.counts().items():
            self.summary_cards[key].value.setText(str(count))

    def open_prisma(self) -> None:
        if self._active_browser_launch is not None or self._browser_ready:
            return
        try:
            self.status.setText("Opening the managed PRISMA browser…")
            self._set_badge(self.browser_badge, "Opening", "working")
            self._active_browser_launch = self.browser.open()
            self._browser_timer.start()
            self._update_controls()
        except Exception as exc:
            self._browser_start_failed(exc)

    def _poll_browser_launch(self) -> None:
        if self._is_closing or self._active_browser_launch is None:
            self._browser_timer.stop()
            return
        for result in self.browser.get_launch_results():
            if result.generation != self._active_browser_launch:
                continue
            if result.success:
                self._browser_ready = True
                self._set_badge(self.browser_badge, "Ready", "ready")
                self.status.setText("PRISMA browser session is ready")
                self._add_activity("Browser opened")
            elif result.kind == "launch":
                self._browser_start_failed(result.error or "Unknown error")
                return
            else:
                self._active_browser_launch = None
                self._browser_ready = False
                self._browser_timer.stop()
                if self._monitoring_stop_event is not None: self._monitoring_stop_event.set()
                self._set_badge(self.browser_badge, "Disconnected", "error")
                self.status.setText("The managed PRISMA page or browser was closed. Open it again to retry.")
                self._add_activity("Browser session closed")
            self._update_controls()
            return

    def _browser_start_failed(self, exc: Exception | str) -> None:
        if self._is_closing:
            return
        self._active_browser_launch = None
        self._browser_ready = False
        self._browser_timer.stop()
        safe_log(self._logger, logging.ERROR, "Browser launch failed: %s", exc)
        self._set_badge(self.browser_badge, "Error", "error")
        self._update_controls()
        self._show_error(
            "Browser Error",
            "The browser could not be opened. Check Chrome or Edge and try again.",
        )
        self.status.setText("Failed to open the browser")
        self._add_activity("Browser error")

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
                    self._add_activity("Prisma opened")
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
                    self._add_activity("Prisma closed")
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
                self._add_activity("Prisma closed manually")
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
            self._add_activity("PRISMA CSV download failed")
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
            self._show_error("PRISMA Download", describe_rejection(result.outcome))
            self._add_activity("PRISMA CSV download validation failed")
            return
        self.manual_csv_label.setText(result.path.name)
        self.status.setText(f"PRISMA CSV downloaded: {result.path.name}")
        self._add_activity(f"PRISMA CSV downloaded: {result.path.name}")

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
        self._add_activity("Prisma error")

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
        self._add_activity("Prisma close error")

    def _close_prisma_session(self) -> None:
        if self._prisma_closing or self._prisma_close_error:
            return
        had_active_session = self._active_prisma_generation is not None
        self.prisma_lifecycle.close()
        if not had_active_session:
            self._prisma_open = False
            self._set_badge(self.prisma_badge, "Prisma closed", "idle")
            self.status.setText("PRISMA closed")
            self._add_activity("Prisma closed")
            self._update_controls()
            return
        self._prisma_closing = True
        self._set_badge(self.prisma_badge, "Closing Prisma…", "working")
        self.status.setText("Closing PRISMA…")
        self._add_activity("Prisma closing")
        self._update_controls()

    def create_monitoring_engine(self) -> MonitoringEngine:
        return MonitoringEngine(
            LivePrismaStatusAdapter(self.browser),
            persistence=MonitoringStorage(self._runtime_paths.database),
        )

    def create_monitoring_scheduler(
        self, records: list[AuctionCsvRecord]
    ) -> MonitoringScheduler:
        return MonitoringScheduler(self.create_monitoring_engine(), lambda: records)

    def start_monitoring(self) -> None:
        if self._monitoring_thread is not None:
            return
        records = [record for record in self._auction_records if record.enabled]
        if not records or not self._browser_ready:
            self._show_error(
                "Monitoring Error",
                "Open the browser and load a CSV with enabled auctions first.",
            )
            return
        stop_event = threading.Event()
        scheduler = self.create_monitoring_scheduler(records)
        thread = threading.Thread(
            target=self._monitoring_worker,
            args=(scheduler, stop_event),
            daemon=False,
            name="prisma-monitoring",
        )
        self._monitoring_stop_event, self._monitoring_thread = stop_event, thread
        self._set_badge(self.monitor_badge, "Monitoring active", "ready")
        self.status.setText("Monitoring started")
        self._add_activity("Monitoring started")
        self._update_controls()
        try:
            thread.start()
        except Exception as exc:
            self._set_monitoring_idle()
            safe_log(
                self._logger, logging.ERROR, "Monitoring start failed: %s", exc
            )
            self._show_error(
                "Monitoring Error", "Monitoring could not be started. Please try again."
            )

    def stop_monitoring(self) -> None:
        if self._monitoring_stop_event is not None:
            self._monitoring_stop_event.set()
            self.status.setText("Stopping monitoring…")
            self._set_badge(self.monitor_badge, "Stopping", "working")

    def _monitoring_worker(
        self, scheduler: MonitoringScheduler, stop_event: threading.Event
    ) -> None:
        error = None
        try:
            scheduler.run_forever(
                stop_event,
                DEFAULT_MONITORING_INTERVAL_SECONDS,
                self.signals.monitoring_results.emit,
            )
        except Exception as exc:
            error = exc
        self.signals.monitoring_finished.emit(error)

    def _monitoring_results(self, results: list[MonitoringResult]) -> None:
        changed = errors = 0
        notifications: list[StatusChangeNotification] = []
        for result in results:
            self.table_model.apply_result(result)
            changed += bool(result.status_changed)
            errors += result.result == "Error"
            notification = StatusChangeNotification.from_result(result)
            if notification is not None:
                notifications.append(notification)
        self._update_summary()
        # The list is newest-first. Reverse insertion preserves the scheduler's
        # deterministic result order directly below the cycle summary.
        for notification in reversed(notifications):
            self._add_activity(
                notification.message(), ActivityKind.STATUS_CHANGE
            )
        self._add_activity(
            f"Statuses updated: {len(results)} checked, "
            f"{changed} changed, {errors} errors"
        )

    @staticmethod
    def _monitoring_failure_message(error: object) -> str:
        if isinstance(error, PrismaLookupTimeoutError):
            return (
                "The live PRISMA status lookup timed out. "
                "Reopen the browser and retry."
            )
        if isinstance(error, PrismaPageUnavailableError):
            return (
                "The PRISMA page is unavailable or closed. "
                "Reopen the browser and retry."
            )
        if isinstance(error, PrismaPageStructureError):
            return (
                "The PRISMA page structure could not be read. "
                "Reopen the browser or retry."
            )
        if isinstance(error, PrismaAuctionNotFoundError):
            return str(error)
        if isinstance(error, MonitoringStorageError):
            return "Monitoring history could not be saved. Please retry."
        return "Monitoring stopped because of an unexpected error. Please retry."

    def _monitoring_finished(self, error: object = None) -> None:
        if self._is_closing:
            return
        self._set_monitoring_idle()
        if error is not None:
            message = self._monitoring_failure_message(error)
            safe_log(
                self._logger, logging.WARNING, "Monitoring terminated: %s", error
            )
            self.status.setText(message)
            self._show_error("Monitoring Error", message)
            self._add_activity("Monitoring error")
        else:
            self.status.setText("Monitoring stopped")
            self._add_activity("Monitoring stopped")

    def _set_monitoring_idle(self) -> None:
        self._monitoring_thread = None
        self._monitoring_stop_event = None
        self._set_badge(self.monitor_badge, "Monitoring idle", "idle")
        self._update_controls()

    def stop_work(self) -> None:
        if self._monitoring_thread is not None:
            answer = QMessageBox.question(
                self,
                "Stop Browser",
                "Monitoring is active. Stop monitoring and close the managed browser?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                return
            self.stop_monitoring()
        self.browser.stop()
        self._active_browser_launch = None
        self._browser_ready = False
        self._browser_timer.stop()
        self._set_badge(self.browser_badge, "Disconnected", "idle")
        self._update_controls()
        self.status.setText("Managed browser closed")
        self._add_activity("Browser stopped")

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
        self._add_activity(f"PRISMA import started: {source.name}")
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
            self._add_activity(
                f"PRISMA import completed: {result.processed} processed, "
                f"{len(result.issues)} audit issues"
            )
            for issue in result.issues[:5]:
                self._add_activity(
                    f"Row {issue.source_row_number}: {issue.status.value} — {issue.message}"
                )

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

    def open_log_directory(self) -> None:
        path = self._runtime_paths.log.parent
        path.mkdir(parents=True, exist_ok=True)
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(path))):
            self._show_error("Log Folder", "The log folder could not be opened.")

    def _show_error(self, title: str, message: str) -> None:
        QMessageBox.critical(self, title, message)

    def closeEvent(self, event) -> None:
        if not self._shutdown_started and self._monitoring_thread is not None:
            answer = QMessageBox.question(
                self,
                "Close PrismaFunction",
                "Monitoring is active. Stop monitoring and close PrismaFunction?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                event.ignore()
                return
        if not self._shutdown_started:
            self._shutdown_started = True
            self._is_closing = True
            self._browser_timer.stop()
            self._active_browser_launch = None
            if self._monitoring_stop_event is not None:
                self._monitoring_stop_event.set()
            self.browser.stop()
            self._prisma_timer.stop()
            self.prisma_lifecycle.close()
            self._prisma_shutdown_deadline = (
                time.monotonic() + PRISMA_SHUTDOWN_GRACE_SECONDS
            )
        threads = (
            [self._monitoring_thread] if self._monitoring_thread else []
        ) + list(self._processing_threads)
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
