from __future__ import annotations

import logging
import sys
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from collections.abc import Callable

from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLayout,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from csv_contracts import CsvFormatError
from download_directory import default_download_directory, validate_download_directory
from manual_csv_selection import ManualCsvSelection, describe_rejection
from mapping_presentation import build_mapping_rows
from prisma_import_workflow import PrismaWorkflowResult, run_prisma_import_workflow
from processor import PrismaImportError, import_prisma_export
from rate_resolution import resolve_rates_for_rows
from runtime_logging import (
    LOGGER_NAME,
    initialize_runtime_logging,
    safe_log,
)
from runtime_paths import RuntimePathError, RuntimePaths, migrate_legacy_runtime_data, runtime_paths
from storage import AuctionStorage, AuctionStorageError
from ui_components import APP_STYLE, MappingTableModel
from version import APP_DISPLAY_NAME, __version__

# Sensible initial pixel widths for the Mapping table, one per
# `mapping_presentation.MAPPING_DISPLAY_FIELDS` column in the same order, wide
# enough that no header label is clipped. Interactive resize mode (see
# PrismaMonitorApp._build_ui) lets the user resize further; a horizontal
# scrollbar appears whenever the available window width is insufficient.
_MAPPING_COLUMN_WIDTHS = (130, 160, 160, 200, 150, 150, 130, 100, 110, 110)


@dataclass(frozen=True)
class ProcessingOutcome:
    result: PrismaWorkflowResult | None
    error: str | None
    generation: int


class WorkerSignals(QObject):
    processing_finished = Signal(object)


class PrismaMonitorApp(QMainWindow):
    def __init__(self, paths: RuntimePaths, publication_directory: Path) -> None:
        super().__init__()
        self._runtime_paths = paths
        self._publication_directory = publication_directory
        self._manual_csv_selection = ManualCsvSelection()
        self.setWindowTitle(f"{APP_DISPLAY_NAME} v{__version__}")
        self.setMinimumSize(1080, 680)
        self.resize(1280, 800)
        self._logger = logging.getLogger(LOGGER_NAME)
        self._is_closing = False
        self._processing_threads: set[threading.Thread] = set()
        self._active_processing_thread: threading.Thread | None = None
        self._processing_active = False
        self._processing_generation = 0
        self._shutdown_started = False
        self.signals = WorkerSignals(self)
        self.signals.processing_finished.connect(self._processing_finished)
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
        self.choose_manual_csv_button = self._button(
            "Select CSV", self._select_manual_csv,
            tooltip=(
                "Select a local PRISMA Export CSV; it is validated, "
                "processed, and published immediately"
            ),
        )
        self.manual_csv_label = QLabel("No CSV selected")
        self.manual_csv_label.setObjectName("filename")
        self.manual_csv_label.setWordWrap(True)
        self.manual_csv_label.setAccessibleName("Selected PRISMA Export CSV")
        self._side_group(
            side, "PRISMA EXPORT CSV", self.choose_manual_csv_button, self.manual_csv_label
        )
        side.addStretch()
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
            "Select a PRISMA Export CSV to process and add it to the cumulative mapping."
        )
        content_subtitle.setObjectName("contentSubtitle")
        titles.addWidget(content_subtitle)
        header.addLayout(titles)
        header.addStretch()
        main.addLayout(header)
        mapping_panel = QFrame()
        mapping_panel.setObjectName("panel")
        mapping_layout = QVBoxLayout(mapping_panel)
        mapping_layout.setContentsMargins(16, 14, 16, 10)
        mapping_header = QHBoxLayout()
        mapping_title = QLabel("Mapping")
        mapping_title.setObjectName("contentSectionLabel")
        mapping_title.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
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
        mapping_hdr.setSectionResizeMode(QHeaderView.Interactive)
        mapping_hdr.setStretchLastSection(False)
        mapping_hdr.setMinimumSectionSize(90)
        self.mapping_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        for column, width in enumerate(_MAPPING_COLUMN_WIDTHS):
            self.mapping_table.setColumnWidth(column, width)
        mapping_layout.addWidget(self.mapping_table, 1)
        self.mapping_empty_label = QLabel(
            "No mapping evidence to display. Select a PRISMA Export CSV."
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

    def _update_controls(self) -> None:
        self.choose_manual_csv_button.setEnabled(not self._processing_active)

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

    def _refresh_mapping_display(self, path: Path) -> bool:
        """Refresh the P.36.8 mapping presentation for the current CSV selection.

        Re-runs the read-only P.36.15 import/enrichment boundary
        (`processor.import_prisma_export`, the same boundary
        `prisma_output.write_prisma_output` already uses) purely to obtain
        already-resolved mapping evidence for display; it writes no output
        file and touches no browser, network, or publication behavior. A
        failure clears the table rather than leaving stale rows from a
        previous selection.

        Returns ``True`` if the CSV could be parsed and the table refreshed,
        ``False`` if it could not (the table was already cleared and an
        error shown) — `_select_manual_csv` uses this to avoid attempting to
        process a file that could not even be read for the preview.
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
            return False
        try:
            resolutions = resolve_rates_for_rows(
                imported.rows, storage=AuctionStorage(self._runtime_paths.database),
            )
        except AuctionStorageError as exc:
            safe_log(
                self._logger, logging.ERROR,
                "Rate resolution unavailable for this Mapping refresh: %s", exc,
            )
            resolutions = {}
        self.mapping_table_model.set_rows(build_mapping_rows(imported, resolutions))
        self._update_mapping_empty_state()
        return True

    def _select_manual_csv(self) -> None:
        if self._processing_active:
            return
        selected, _ = QFileDialog.getOpenFileName(
            self, "Select PRISMA Export CSV", str(self._publication_directory), "CSV files (*.csv)"
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
        if not self._refresh_mapping_display(result.path):
            return
        self._process_selected_csv(result.path)

    def _process_selected_csv(self, source: Path) -> None:
        """Immediately process the just-selected CSV: merge its accepted rows
        into cumulative persistent storage (deduplicated) and publish the
        confirmed-EUR 12-column output. Runs on a background thread so the UI
        stays responsive; `_select_manual_csv` is the only caller and Select
        CSV is disabled (see `_update_controls`) until this finishes.
        """
        self._processing_active = True
        self.status.setText("Importing PRISMA Export CSV…")
        self._update_controls()
        self._processing_generation += 1
        generation = self._processing_generation
        thread = threading.Thread(
            target=self._process_worker,
            args=(source, generation, self._publication_directory),
            daemon=False,
            name="prisma-processing",
        )
        self._processing_threads.add(thread)
        self._active_processing_thread = thread
        try:
            thread.start()
        except Exception as exc:
            self._processing_threads.discard(thread)
            self._active_processing_thread = None
            self._processing_active = False
            self._update_controls()
            self._processing_finished(ProcessingOutcome(None, str(exc), generation))

    def _process_worker(
        self, source: Path, generation: int = 0,
        publication_directory: Path | None = None,
    ) -> None:
        try:
            result = run_prisma_import_workflow(
                source,
                source_date=datetime.now().date(),
                evaluated_at=datetime.now().astimezone(),
                database_path=self._runtime_paths.database,
                state_path=self._runtime_paths.state,
                publication_directory=publication_directory,
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
        # `_process_worker`'s signal emit is its last statement, so by the
        # time this runs (on `processing_finished`) the worker has already
        # returned or is about to; an unbounded join is the only boundary
        # that can't silently expose completion (re-enabling Select CSV,
        # letting a second import start) while storage/database work on the
        # old thread is still in flight — the prior 0.1s timeout could give
        # up and proceed anyway, which was the source of the Windows access
        # violation.
        if thread is None:
            thread = self._active_processing_thread
        if thread is not None and thread is not self._active_processing_thread:
            return False
        if thread is not None:
            thread.join()
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

    def _show_error(self, title: str, message: str) -> None:
        QMessageBox.critical(self, title, message)

    def closeEvent(self, event) -> None:
        if not self._shutdown_started:
            self._shutdown_started = True
            self._is_closing = True
        threads = list(self._processing_threads)
        if any(
            thread is not threading.current_thread() and thread.is_alive()
            for thread in threads
        ):
            self.status.setText("Closing; a background import is finishing safely.")
            event.ignore()
            QTimer.singleShot(100, self.close)
            return
        event.accept()


def main() -> int:
    application = QApplication.instance() or QApplication(sys.argv)
    application.setApplicationName(APP_DISPLAY_NAME)
    application.setApplicationVersion(__version__)
    initialization_error = None
    paths = None
    publication_directory = None
    try:
        paths = runtime_paths()
        logger, log_path = initialize_runtime_logging(paths.log)
        if log_path is None:
            raise RuntimePathError(
                "The required user-data log file could not be created. "
                "Check LOCALAPPDATA and folder permissions, then retry."
            )
        migrate_legacy_runtime_data(paths=paths, logger=logger)
        publication_directory = validate_download_directory(default_download_directory())
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
    window = PrismaMonitorApp(paths, publication_directory)
    window.show()
    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
