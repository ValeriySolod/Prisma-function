from __future__ import annotations

import logging
import sys
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from collections.abc import Callable

from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from prisma_function.csv_contracts import CsvFormatError
from prisma_function.download_directory import default_download_directory, validate_download_directory
from prisma_function.manual_csv_selection import ManualCsvSelection, describe_rejection
from prisma_function.mapping_presentation import load_mapping_rows_from_output_csv
from prisma_function.prisma_import_workflow import PrismaWorkflowResult, run_prisma_import_workflow
from prisma_function.processor import PrismaImportError, import_prisma_export
from prisma_function.runtime_logging import (
    LOGGER_NAME,
    initialize_runtime_logging,
    safe_log,
)
from prisma_function.runtime_paths import RuntimePathError, RuntimePaths, migrate_legacy_runtime_data, runtime_paths
from prisma_function.ui_components import APP_STYLE, MappingTableModel
from prisma_function.version import APP_DISPLAY_NAME, __version__

# Sensible initial pixel widths for the Mapping table, one per
# `mapping_presentation.MAPPING_DISPLAY_FIELDS` column in the same order, wide
# enough that no header label is clipped. Interactive resize mode (see
# PrismaMonitorApp._build_ui) lets the user resize further; a horizontal
# scrollbar appears whenever the available window width is insufficient.
_MAPPING_COLUMN_WIDTHS = (130, 160, 160, 130, 200, 130, 150, 150, 130, 150, 120, 120)
_COMPANY_WORDMARK_PATH = Path(__file__).resolve().parent / "resources" / "company_wordmark.png"


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
        tooltip: str = "",
    ) -> QPushButton:
        button = QPushButton(text)
        button.clicked.connect(handler)
        button.setProperty("primary", primary)
        button.setToolTip(tooltip)
        button.setAccessibleName(text)
        return button

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("workspace")
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        outer.addWidget(self._build_toolbar())

        content = QWidget()
        content.setObjectName("contentArea")
        main = QVBoxLayout(content)
        main.setContentsMargins(20, 16, 20, 0)
        main.setSpacing(0)
        main.addWidget(self._build_mapping_panel(), 1)
        outer.addWidget(content, 1)

        outer.addWidget(self._build_status_bar())

        self.setCentralWidget(root)
        self.setStyleSheet(APP_STYLE)
        self._update_mapping_empty_state()
        self._set_status_badge("ready", "Ready")

    def _build_toolbar(self) -> QFrame:
        toolbar = QFrame()
        toolbar.setObjectName("toolbar")
        bar = QHBoxLayout(toolbar)
        bar.setContentsMargins(20, 10, 20, 10)
        bar.setSpacing(14)
        brand = QLabel("PrismaFunction")
        brand.setObjectName("brand")
        company_wordmark = QLabel()
        company_wordmark.setObjectName("companyWordmark")
        company_wordmark.setAccessibleName("Trafigura company wordmark")
        company_wordmark.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        company_wordmark.setPixmap(
            QPixmap(str(_COMPANY_WORDMARK_PATH)).scaledToHeight(
                34, Qt.SmoothTransformation
            )
        )
        subtitle = QLabel("PRISMA Export processing")
        subtitle.setObjectName("subtitle")
        bar.addWidget(brand)
        bar.addWidget(company_wordmark)
        bar.addWidget(subtitle)
        bar.addStretch()
        self.manual_csv_label = QLabel("No CSV selected")
        self.manual_csv_label.setObjectName("filename")
        self.manual_csv_label.setAccessibleName("Selected PRISMA Export CSV")
        bar.addWidget(self.manual_csv_label)
        self.choose_manual_csv_button = self._button(
            "Select CSV", self._select_manual_csv, primary=True,
            tooltip=(
                "Select a local PRISMA Export CSV; it is validated, "
                "processed, and published immediately"
            ),
        )
        bar.addWidget(self.choose_manual_csv_button)
        version = QLabel(f"Version {__version__}")
        version.setObjectName("subtitle")
        bar.addWidget(version)
        return toolbar

    def _build_mapping_panel(self) -> QFrame:
        mapping_panel = QFrame()
        mapping_panel.setObjectName("panel")
        mapping_layout = QVBoxLayout(mapping_panel)
        mapping_layout.setContentsMargins(16, 14, 16, 10)
        mapping_header = QHBoxLayout()
        self.mapping_section_label = QLabel("Mapping")
        self.mapping_section_label.setObjectName("contentSectionLabel")
        self.mapping_section_label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        mapping_header.addWidget(self.mapping_section_label)
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
        self.mapping_table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        for column, width in enumerate(_MAPPING_COLUMN_WIDTHS):
            self.mapping_table.setColumnWidth(column, width)
        mapping_layout.addWidget(self.mapping_table, 1)
        self.mapping_empty_label = QLabel(
            "No mapping evidence to display. Select a PRISMA Export CSV."
        )
        self.mapping_empty_label.setAlignment(Qt.AlignCenter)
        self.mapping_empty_label.setStyleSheet("color:#718096; padding:18px")
        mapping_layout.addWidget(self.mapping_empty_label)
        return mapping_panel

    def _build_status_bar(self) -> QFrame:
        status_bar = QFrame()
        status_bar.setObjectName("statusBar")
        status_outer = QVBoxLayout(status_bar)
        status_outer.setContentsMargins(20, 8, 20, 8)
        status_outer.setSpacing(6)

        counters_row = QHBoxLayout()
        counters_row.setSpacing(18)
        self.status_badge = QLabel("Ready")
        self.status_badge.setObjectName("statusBadge")
        counters_row.addWidget(self.status_badge)
        self.status_counter_labels: dict[str, QLabel] = {}
        for name in ("Source", "Accepted", "Filtered", "Rejected", "Duplicates", "Inserted"):
            label = QLabel(f"{name}: –")
            label.setObjectName("statusCounter")
            self.status_counter_labels[name] = label
            counters_row.addWidget(label)
        counters_row.addStretch()
        self.details_button = QPushButton("Details")
        self.details_button.setObjectName("detailsButton")
        self.details_button.setCheckable(True)
        self.details_button.setAccessibleName("Details")
        self.details_button.toggled.connect(self._toggle_status_details)
        counters_row.addWidget(self.details_button)
        status_outer.addLayout(counters_row)

        self.status_details_panel = QFrame()
        self.status_details_panel.setObjectName("statusDetails")
        details_layout = QHBoxLayout(self.status_details_panel)
        details_layout.setContentsMargins(0, 6, 0, 0)
        details_caption = QLabel("Status:")
        details_caption.setObjectName("contentSectionLabel")
        details_layout.addWidget(details_caption)
        self.status = QLabel("Ready")
        self.status.setObjectName("primaryStatus")
        self.status.setWordWrap(True)
        details_layout.addWidget(self.status, 1)
        self.status_details_panel.setVisible(False)
        status_outer.addWidget(self.status_details_panel)

        return status_bar

    def _toggle_status_details(self, checked: bool) -> None:
        self.status_details_panel.setVisible(checked)
        self.details_button.setText("Hide details" if checked else "Details")

    def _set_status_badge(self, state: str, text: str) -> None:
        self.status_badge.setText(text)
        self.status_badge.setProperty("state", state)
        self.status_badge.style().unpolish(self.status_badge)
        self.status_badge.style().polish(self.status_badge)

    def _update_status_counters(self, result: PrismaWorkflowResult) -> None:
        source_rows = result.total_source_rows if result.total_source_rows is not None else result.processed
        accepted = result.accepted if result.accepted is not None else result.processed
        deduplicated = result.deduplicated if result.deduplicated is not None else 0
        values = {
            "Source": source_rows, "Accepted": accepted, "Filtered": result.filtered,
            "Rejected": result.rejected, "Duplicates": deduplicated, "Inserted": result.inserted,
        }
        for name, value in values.items():
            text = "–" if value is None else str(value)
            self.status_counter_labels[name].setText(f"{name}: {text}")
        has_issues = any(value not in (None, 0) for value in (result.filtered, result.rejected, deduplicated))
        self._set_status_badge(
            "warning" if has_issues else "success", "Warning" if has_issues else "Success"
        )

    def _update_controls(self) -> None:
        self.choose_manual_csv_button.setEnabled(not self._processing_active)

    def _update_mapping_empty_state(self) -> None:
        count = self.mapping_table_model.rowCount()
        has_rows = count > 0
        self.mapping_table.setVisible(has_rows)
        self.mapping_empty_label.setVisible(not has_rows)
        self.mapping_section_label.setText(f"Mapping · {count} row" + ("" if count == 1 else "s"))

    def _clear_mapping_display(self) -> None:
        """Discard any displayed mapping rows and show the empty state.

        Used whenever a CSV replacement attempt does not end in a freshly
        refreshed mapping display, so a rejected candidate can never leave a
        previous selection's rows visible.
        """
        self.mapping_table_model.set_rows(())
        self._update_mapping_empty_state()

    def _validate_mapping_source(self, path: Path) -> bool:
        """Validate the selected CSV before the processing thread starts."""
        try:
            import_prisma_export(path)
        except (PrismaImportError, CsvFormatError, OSError) as exc:
            safe_log(self._logger, logging.ERROR, "Mapping source validation failed: %s", exc)
            self._clear_mapping_display()
            self._show_error(
                "Mapping",
                "The selected PRISMA Export CSV could not be validated for Mapping.",
            )
            return False
        return True

    def _refresh_mapping_display_from_output(self, path: Path) -> None:
        try:
            self.mapping_table_model.set_rows(load_mapping_rows_from_output_csv(path))
        except (OSError, ValueError) as exc:
            safe_log(self._logger, logging.ERROR, "Mapping output refresh failed: %s", exc)
            self._clear_mapping_display()
            self._show_error(
                "Mapping",
                "The published Mapping output could not be displayed.",
            )
            return
        self._update_mapping_empty_state()

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
        if not self._validate_mapping_source(result.path):
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
        self.status.setText("Importing PRISMA Export CSV...")
        self._set_status_badge("processing", "Processing")
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
        # old thread is still in flight вЂ” the prior 0.1s timeout could give
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
            self._refresh_mapping_display_from_output(result.output_path)
            self.status.setText(result.summary())
            self._update_status_counters(result)

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
            self._set_status_badge("error", "Error")

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
