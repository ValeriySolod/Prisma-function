import gc
import os
import threading
import time
from datetime import date, datetime
from pathlib import Path
from unittest.mock import Mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QDate, Qt
from PySide6.QtTest import QSignalSpy
from PySide6.QtWidgets import QApplication, QLabel, QMessageBox, QPushButton, QWidget

import app
import prisma_output
import prisma_publication
from csv_contracts import PRISMA_EXPORT_COLUMNS
from date_range_selection import DateRange
from download_directory import DownloadDirectoryError
from manual_csv_selection import ManualCsvOutcome
from manual_csv_selection import describe_rejection as describe_manual_csv_rejection
from mapping_presentation import MAPPING_DISPLAY_FIELDS
from processor import PrismaImportError
from prisma_download import PrismaDownloadOutcome, describe_download_failure
from prisma_import_workflow import PrismaWorkflowResult
from prisma_lifecycle import PrismaLifecycleEvent, PrismaLifecycleState
from prisma_source_updates import SourceUpdateStatus
from version import APP_DISPLAY_NAME, __version__
from ui_components import APP_STYLE


@pytest.fixture(scope="session")
def qt_app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _build_app(monkeypatch, tmp_path):
    monkeypatch.setattr(app, "PrismaLifecycleController", Mock(return_value=Mock()))
    root = tmp_path / "runtime"
    paths = app.RuntimePaths(
        root=root, database=root / "data/test.db",
        result=root / "data/result/test.xlsx",
        state=root / "state/test.json", log=root / "logs/test.log",
    )
    download_directory = tmp_path / "Documents"
    download_directory.mkdir()
    widget = app.PrismaMonitorApp(paths, download_directory)
    return widget, None


def _close_app(widget) -> None:
    widget._is_closing = True
    for worker in widget._processing_threads:
        worker.join(timeout=2)
    widget._processing_threads.clear()
    widget.close()


@pytest.fixture
def window(qt_app, monkeypatch, tmp_path):
    widget, browser = _build_app(monkeypatch, tmp_path)
    yield widget, browser
    _close_app(widget)
    # Each PrismaMonitorApp instance holds self-referencing QTimer/slot cycles
    # (e.g. self._prisma_timer -> self._poll_prisma_lifecycle -> self); plain
    # refcounting never reclaims those, only Python's cyclic GC does. Forcing
    # collection after every test keeps unreachable Qt object graphs from
    # piling up across the whole session and being torn down in one large,
    # unordered batch at interpreter shutdown.
    del widget, browser
    gc.collect()


def accept_date_range(
    widget: app.PrismaMonitorApp, start: date = date(2026, 3, 1), end: date = date(2026, 3, 5)
) -> DateRange:
    widget.start_date_edit.setDate(QDate(start.year, start.month, start.day))
    widget.end_date_edit.setDate(QDate(end.year, end.month, end.day))
    widget._validate_date_range()
    return widget._date_range_selection.current


def test_initial_dashboard_state_and_accessibility(window):
    widget, _ = window
    assert widget.windowTitle() == f"{APP_DISPLAY_NAME} v{__version__}"
    assert widget.minimumWidth() >= 1080
    assert widget.status.text() == "Ready"
    assert widget.prisma_badge.text() == "Prisma closed"


def test_p36_2_prisma_controls_exist_and_start_in_a_closed_retryable_state(window):
    widget, _ = window
    assert widget.open_prisma_button.text() == "Open Prisma"
    assert widget.close_prisma_button.text() == "Close Prisma"
    assert not widget.open_prisma_button.isHidden()
    assert not widget.close_prisma_button.isHidden()
    assert widget.open_prisma_button.isEnabled()
    assert not widget.close_prisma_button.isEnabled()
    assert widget.prisma_badge.text() == "Prisma closed"


def test_light_workspace_widgets_use_explicit_contrast_styles(window):
    widget, _ = window
    content = widget.findChild(QWidget, "contentArea")
    subtitle = widget.findChild(QLabel, "contentSubtitle")
    section_labels = widget.findChildren(QLabel, "contentSectionLabel")

    assert content is not None
    assert subtitle is not None
    assert {label.text() for label in section_labels} == {"Mapping", "Status:"}

    required_rules = (
        "QWidget#contentArea QLabel { color: #243247; }",
        "QLabel#contentSubtitle { color: #66758a; }",
        "QLabel#contentSectionLabel { color: #314157; font-weight: 600; }",
        "QWidget#contentArea QTableView { border: none; background: white; color: #243247;",
        "QWidget#contentArea QTableView::item { color: #243247; }",
        "QWidget#contentArea QTableView::item:selected { background: #dff3f8; color: #172235; }",
    )
    for rule in required_rules:
        assert rule in APP_STYLE

    assert "QFrame#sidebar QLabel { color: #d8e1ee; }" in APP_STYLE
    assert "QLabel#browserBadge {" in APP_STYLE


def test_recent_activity_section_is_completely_removed(window):
    widget, _ = window
    assert widget.findChild(QWidget, "activityList") is None
    assert not any(
        label.text() == "Recent activity"
        for label in widget.findChildren(QLabel, "contentSectionLabel")
    )
    button_texts = {button.text() for button in widget.findChildren(QPushButton)}
    assert "Open log folder" not in button_texts
    assert "Clear" not in button_texts
    for attribute in ("activity_list", "open_logs_button", "clear_activity_button"):
        assert not hasattr(widget, attribute)
    for method_name in ("_add_activity", "clear_activity", "open_log_directory"):
        assert not hasattr(widget, method_name)


def test_mapping_panel_receives_positive_vertical_stretch(window):
    widget, _ = window
    content = widget.findChild(QWidget, "contentArea")
    main_layout = content.layout()
    mapping_panel = widget.mapping_table.parentWidget()
    index = main_layout.indexOf(mapping_panel)
    assert index >= 0
    assert main_layout.stretch(index) > 0


def test_download_directory_defaults_to_provided_documents_folder(window):
    widget, _ = window
    assert widget.download_directory_label.text() == str(widget._download_directory.current)
    assert widget.download_directory_label.text().endswith("Documents")


def test_choosing_a_valid_download_directory_updates_state_and_label(window, monkeypatch, tmp_path):
    widget, _ = window
    chosen = tmp_path / "Chosen Downloads"
    chosen.mkdir()
    monkeypatch.setattr(
        app.QFileDialog, "getExistingDirectory", Mock(return_value=str(chosen))
    )

    widget._select_download_directory()

    assert widget._download_directory.current == chosen.resolve()
    assert widget.download_directory_label.text() == str(chosen.resolve())


def test_cancelling_download_directory_dialog_preserves_current_directory(window, monkeypatch):
    widget, _ = window
    previous = widget._download_directory.current
    monkeypatch.setattr(
        app.QFileDialog, "getExistingDirectory", Mock(return_value="")
    )

    widget._select_download_directory()

    assert widget._download_directory.current == previous
    assert widget.download_directory_label.text() == str(previous)


def test_invalid_download_directory_selection_shows_generic_error_and_preserves_state(
    window, monkeypatch, tmp_path
):
    widget, _ = window
    previous = widget._download_directory.current
    missing = tmp_path / "does-not-exist"
    monkeypatch.setattr(
        app.QFileDialog, "getExistingDirectory", Mock(return_value=str(missing))
    )
    critical = Mock()
    monkeypatch.setattr(QMessageBox, "critical", critical)

    widget._select_download_directory()

    assert widget._download_directory.current == previous
    assert widget.download_directory_label.text() == str(previous)
    critical.assert_called_once()
    title, message = critical.call_args.args[1], critical.call_args.args[2]
    assert title == "Download Folder"
    assert str(missing) not in message


def _write_valid_prisma_export(path):
    path.write_bytes((";".join(PRISMA_EXPORT_COLUMNS) + "\r\n").encode("cp1252"))


_MAPPING_ROW_DEFAULTS = {
    "Auction ID": "1", "Start of Auction": "01.01.2025 09:00",
    "Marketed Capacity": "1000", "Unit Marketed Capacity": "kWh/h",
    "Product Runtime Start": "02.01.2025 00:00", "Product Runtime End": "03.01.2025 00:00",
    "Direction": "Entry", "Network Point Name Entry": "VGS Storage Hub (4290)",
    "Network Point ID Entry": "ENTRY-1", "TSO Exit": "", "TSO Entry": "GUD",
}


def _write_prisma_export_with_rows(path, rows: list[dict]) -> None:
    """Write a valid official PRISMA Export CSV with the given data rows.

    Each row is `_MAPPING_ROW_DEFAULTS` with the given overrides applied;
    unspecified contract columns are left blank.
    """
    import csv as csv_module

    with path.open("w", encoding="cp1252", newline="") as handle:
        writer = csv_module.DictWriter(
            handle, fieldnames=PRISMA_EXPORT_COLUMNS, delimiter=";", extrasaction="raise"
        )
        writer.writeheader()
        for overrides in rows:
            full_row = dict.fromkeys(PRISMA_EXPORT_COLUMNS, "")
            full_row.update(_MAPPING_ROW_DEFAULTS)
            full_row.update(overrides)
            writer.writerow(full_row)


def test_manual_csv_dialog_starts_in_current_download_directory(window, monkeypatch):
    widget, _ = window
    dialog = Mock(return_value=("", ""))
    monkeypatch.setattr(app.QFileDialog, "getOpenFileName", dialog)

    widget._select_manual_csv()

    assert dialog.call_args.args[2] == str(widget._download_directory.current)


def test_cancelling_manual_csv_dialog_is_a_no_op(window, monkeypatch):
    widget, _ = window
    monkeypatch.setattr(app.QFileDialog, "getOpenFileName", Mock(return_value=("", "")))
    critical = Mock()
    monkeypatch.setattr(QMessageBox, "critical", critical)

    widget._select_manual_csv()

    assert widget._manual_csv_selection.current is None
    assert widget.manual_csv_label.text() == "No CSV selected"
    critical.assert_not_called()


def test_cancelling_manual_csv_dialog_after_a_valid_selection_preserves_mapping_rows(
    window, monkeypatch, tmp_path
):
    widget, _ = window
    populated = tmp_path / "PRISMA_Export.csv"
    _write_prisma_export_with_rows(populated, [{"Auction ID": "1"}])
    monkeypatch.setattr(
        app.QFileDialog, "getOpenFileName", Mock(return_value=(str(populated), "CSV"))
    )
    widget._select_manual_csv()
    assert widget.mapping_table_model.rowCount() == 1

    monkeypatch.setattr(app.QFileDialog, "getOpenFileName", Mock(return_value=("", "")))
    critical = Mock()
    monkeypatch.setattr(QMessageBox, "critical", critical)

    widget._select_manual_csv()

    assert widget._manual_csv_selection.current == populated.resolve()
    assert widget.manual_csv_label.text() == "PRISMA_Export.csv"
    critical.assert_not_called()
    assert widget.mapping_table_model.rowCount() == 1
    assert not widget.mapping_table.isHidden()


def test_choosing_a_valid_manual_csv_updates_state_and_label(window, monkeypatch, tmp_path):
    widget, _ = window
    target = tmp_path / "PRISMA_Export.csv"
    _write_valid_prisma_export(target)
    monkeypatch.setattr(
        app.QFileDialog, "getOpenFileName", Mock(return_value=(str(target), "CSV"))
    )

    widget._select_manual_csv()

    assert widget._manual_csv_selection.current == target.resolve()
    assert widget.manual_csv_label.text() == "PRISMA_Export.csv"
    assert widget.status.text() == "PRISMA Export CSV selected."


def test_invalid_manual_csv_selection_shows_generic_error_and_preserves_state(
    window, monkeypatch, tmp_path
):
    widget, _ = window
    valid = tmp_path / "PRISMA_Export.csv"
    _write_valid_prisma_export(valid)
    monkeypatch.setattr(
        app.QFileDialog, "getOpenFileName", Mock(return_value=(str(valid), "CSV"))
    )
    widget._select_manual_csv()
    previous = widget._manual_csv_selection.current
    assert previous == valid.resolve()

    missing = tmp_path / "does-not-exist.csv"
    monkeypatch.setattr(
        app.QFileDialog, "getOpenFileName", Mock(return_value=(str(missing), "CSV"))
    )
    critical = Mock()
    monkeypatch.setattr(QMessageBox, "critical", critical)

    widget._select_manual_csv()

    assert widget._manual_csv_selection.current == previous
    assert widget.manual_csv_label.text() == "PRISMA_Export.csv"
    critical.assert_called_once()
    title, message = critical.call_args.args[1], critical.call_args.args[2]
    assert title == "Select CSV"
    assert str(missing) not in message


def test_rejected_manual_csv_header_mismatch_preserves_previous_selection(
    window, monkeypatch, tmp_path
):
    widget, _ = window
    valid = tmp_path / "PRISMA_Export.csv"
    _write_valid_prisma_export(valid)
    monkeypatch.setattr(
        app.QFileDialog, "getOpenFileName", Mock(return_value=(str(valid), "CSV"))
    )
    widget._select_manual_csv()

    bad = tmp_path / "wrong-header.csv"
    bad.write_bytes(b"a;b;c\r\n")
    monkeypatch.setattr(
        app.QFileDialog, "getOpenFileName", Mock(return_value=(str(bad), "CSV"))
    )
    critical = Mock()
    monkeypatch.setattr(QMessageBox, "critical", critical)

    widget._select_manual_csv()

    assert widget._manual_csv_selection.current == valid.resolve()
    critical.assert_called_once()
    _, message = critical.call_args.args[1], critical.call_args.args[2]
    assert str(bad) not in message


# --- P.36.8 mapping display ---------------------------------------------

def test_mapping_table_headers_are_exact_order_and_labels(window):
    widget, _ = window
    assert widget.mapping_table.accessibleName() == "Mapping"
    model = widget.mapping_table_model
    assert model.columnCount() == len(MAPPING_DISPLAY_FIELDS)
    headers = tuple(
        model.headerData(column, Qt.Horizontal) for column in range(model.columnCount())
    )
    assert headers == MAPPING_DISPLAY_FIELDS


def test_initial_mapping_display_is_empty_and_hidden(window):
    widget, _ = window
    assert widget.mapping_table_model.rowCount() == 0
    assert widget.mapping_table.isHidden()
    assert not widget.mapping_empty_label.isHidden()


def test_selecting_a_csv_with_no_data_rows_leaves_mapping_display_empty(
    window, monkeypatch, tmp_path
):
    widget, _ = window
    target = tmp_path / "PRISMA_Export.csv"
    _write_valid_prisma_export(target)
    monkeypatch.setattr(
        app.QFileDialog, "getOpenFileName", Mock(return_value=(str(target), "CSV"))
    )

    widget._select_manual_csv()

    assert widget.mapping_table_model.rowCount() == 0
    assert widget.mapping_table.isHidden()
    assert not widget.mapping_empty_label.isHidden()


def test_selecting_a_valid_csv_populates_mapping_table_with_resolved_evidence(
    window, monkeypatch, tmp_path
):
    widget, _ = window
    target = tmp_path / "PRISMA_Export.csv"
    _write_prisma_export_with_rows(target, [
        {
            "Auction ID": "1", "Direction": "Entry",
            "Network Point Name Entry": "VGS Storage Hub (4290)",
            "Network Point ID Entry": "ENTRY-1", "TSO Entry": "GUD",
        },
        {
            "Auction ID": "2", "Direction": "Exit",
            "Network Point Name Exit": "VIP DK-THE (H646) (H646)",
            "Network Point ID Exit": "EXIT-1", "TSO Exit": "GTE", "TSO Entry": "",
        },
    ])
    monkeypatch.setattr(
        app.QFileDialog, "getOpenFileName", Mock(return_value=(str(target), "CSV"))
    )

    widget._select_manual_csv()

    model = widget.mapping_table_model
    assert model.rowCount() == 2
    assert not widget.mapping_table.isHidden()
    assert widget.mapping_empty_label.isHidden()

    def cell(row, column):
        return model.data(model.index(row, column))

    # Deterministic order: rows appear exactly as they were in the source CSV.
    assert (cell(0, 0), cell(0, 1), cell(0, 2), cell(0, 3), cell(0, 4)) == (
        "", "VGS Storage Hub", "VGS Storage Hub (4290)", "", "GUD",
    )
    assert (cell(1, 0), cell(1, 1), cell(1, 2), cell(1, 3), cell(1, 4)) == (
        "THE", "", "VIP DK-THE (H646) (H646)", "GTE", "",
    )


def test_filtered_and_rejected_only_csv_leaves_mapping_display_empty(
    window, monkeypatch, tmp_path
):
    widget, _ = window
    target = tmp_path / "PRISMA_Export.csv"
    _write_prisma_export_with_rows(target, [
        {"Auction ID": "1", "Marketed Capacity": "10"},  # below threshold: filtered
        {"Auction ID": "2", "Network Point Name Entry": "Unknown Point"},  # rejected
    ])
    monkeypatch.setattr(
        app.QFileDialog, "getOpenFileName", Mock(return_value=(str(target), "CSV"))
    )

    widget._select_manual_csv()

    assert widget.mapping_table_model.rowCount() == 0
    assert widget.mapping_table.isHidden()


def test_selecting_a_new_csv_replaces_previous_mapping_rows(window, monkeypatch, tmp_path):
    widget, _ = window
    first = tmp_path / "first.csv"
    _write_prisma_export_with_rows(first, [{"Auction ID": "1"}])
    monkeypatch.setattr(
        app.QFileDialog, "getOpenFileName", Mock(return_value=(str(first), "CSV"))
    )
    widget._select_manual_csv()
    assert widget.mapping_table_model.rowCount() == 1

    second = tmp_path / "second.csv"
    _write_valid_prisma_export(second)
    monkeypatch.setattr(
        app.QFileDialog, "getOpenFileName", Mock(return_value=(str(second), "CSV"))
    )
    widget._select_manual_csv()

    # The replacement CSV has zero data rows: no stale row from the first
    # selection may survive the refresh.
    assert widget.mapping_table_model.rowCount() == 0
    assert widget.mapping_table.isHidden()


def test_mapping_refresh_failure_clears_table_and_shows_safe_error(
    window, monkeypatch, tmp_path
):
    widget, _ = window
    target = tmp_path / "PRISMA_Export.csv"
    _write_prisma_export_with_rows(target, [{"Auction ID": "1"}])
    monkeypatch.setattr(
        app.QFileDialog, "getOpenFileName", Mock(return_value=(str(target), "CSV"))
    )
    widget._select_manual_csv()
    assert widget.mapping_table_model.rowCount() == 1

    second = tmp_path / "second.csv"
    _write_valid_prisma_export(second)
    monkeypatch.setattr(
        app.QFileDialog, "getOpenFileName", Mock(return_value=(str(second), "CSV"))
    )

    def _raise(path):
        raise PrismaImportError(f"internal failure reading {path}")

    monkeypatch.setattr(app, "import_prisma_export", _raise)
    critical = Mock()
    monkeypatch.setattr(QMessageBox, "critical", critical)

    widget._select_manual_csv()

    assert widget.mapping_table_model.rowCount() == 0
    assert widget.mapping_table.isHidden()
    critical.assert_called_once()
    title, message = critical.call_args.args[1], critical.call_args.args[2]
    assert title == "Mapping"
    assert str(second) not in message
    assert message == (
        "The mapping evidence for the selected PRISMA Export CSV could not be displayed."
    )


def test_downloaded_csv_populates_mapping_table(window, tmp_path):
    widget, _ = window
    csv_path = tmp_path / "Auction_overview_2026-03-01_2026-03-05.csv"
    _write_prisma_export_with_rows(csv_path, [{"Auction ID": "1"}])

    widget._handle_download_event(
        PrismaLifecycleEvent(11, True, kind="download", csv_path=csv_path)
    )

    assert widget.mapping_table_model.rowCount() == 1
    assert not widget.mapping_table.isHidden()


def test_rejected_manual_csv_replacement_clears_previous_mapping_rows(
    window, monkeypatch, tmp_path
):
    widget, _ = window
    populated = tmp_path / "PRISMA_Export.csv"
    _write_prisma_export_with_rows(populated, [{"Auction ID": "1"}])
    monkeypatch.setattr(
        app.QFileDialog, "getOpenFileName", Mock(return_value=(str(populated), "CSV"))
    )
    widget._select_manual_csv()
    assert widget.mapping_table_model.rowCount() == 1

    bad = tmp_path / "wrong-header.csv"
    bad.write_bytes(b"a;b;c\r\n")
    monkeypatch.setattr(
        app.QFileDialog, "getOpenFileName", Mock(return_value=(str(bad), "CSV"))
    )
    critical = Mock()
    monkeypatch.setattr(QMessageBox, "critical", critical)

    widget._select_manual_csv()

    critical.assert_called_once()
    assert widget.mapping_table_model.rowCount() == 0
    assert widget.mapping_table.isHidden()
    assert not widget.mapping_empty_label.isHidden()


def test_rejected_download_csv_replacement_clears_previous_mapping_rows(
    window, monkeypatch, tmp_path
):
    widget, _ = window
    populated = tmp_path / "Auction_overview_2026-03-01_2026-03-05.csv"
    _write_prisma_export_with_rows(populated, [{"Auction ID": "1"}])
    widget._handle_download_event(
        PrismaLifecycleEvent(11, True, kind="download", csv_path=populated)
    )
    assert widget.mapping_table_model.rowCount() == 1

    bad = tmp_path / "bad-export.csv"
    bad.write_text("not,the,right,header\n", encoding="utf-8")
    critical = Mock()
    monkeypatch.setattr(QMessageBox, "critical", critical)

    widget._handle_download_event(
        PrismaLifecycleEvent(12, True, kind="download", csv_path=bad)
    )

    critical.assert_called_once()
    assert widget.mapping_table_model.rowCount() == 0
    assert widget.mapping_table.isHidden()
    assert not widget.mapping_empty_label.isHidden()


def test_mapping_refresh_does_not_touch_output_writing_publication_or_browser(
    window, monkeypatch, tmp_path
):
    widget, _ = window
    target = tmp_path / "PRISMA_Export.csv"
    _write_prisma_export_with_rows(target, [{"Auction ID": "1"}])
    monkeypatch.setattr(
        app.QFileDialog, "getOpenFileName", Mock(return_value=(str(target), "CSV"))
    )
    write_output = Mock(side_effect=AssertionError("write_prisma_output must not be called"))
    publish = Mock(side_effect=AssertionError("publish_cumulative_output must not be called"))
    monkeypatch.setattr(prisma_output, "write_prisma_output", write_output)
    monkeypatch.setattr(prisma_publication, "publish_cumulative_output", publish)
    lifecycle_calls_before = list(widget.prisma_lifecycle.mock_calls)

    widget._select_manual_csv()

    write_output.assert_not_called()
    publish.assert_not_called()
    assert list(widget.prisma_lifecycle.mock_calls) == lifecycle_calls_before


def test_date_range_controls_and_validate_action_are_visible(window):
    # The `window` fixture never calls show() on the top-level QMainWindow, so
    # QWidget.isVisible() is False for every widget regardless of hide()
    # state. isHidden() and window() are independent of top-level show() and
    # deterministically prove these controls are constructed, attached under
    # the same top-level window, not explicitly hidden, and usable.
    widget, _ = window

    for control in (
        widget.start_date_edit, widget.end_date_edit,
        widget.validate_date_range_button, widget.date_range_label,
    ):
        assert not control.isHidden()
        assert control.isEnabled()
        assert control.window() is widget
    assert widget.validate_date_range_button.text() == "Validate Date Range"


def test_date_range_controls_do_not_initialize_to_qts_minimum_date(window):
    # Regression test: on real Windows, both controls were observed retaining
    # values near Qt's minimum supported QDate (1752-09-25 / 1752-09-29)
    # instead of a usable application date. Neither control may ever equal
    # QDateEdit's own minimumDate() at construction time.
    widget, _ = window

    assert widget.start_date_edit.date() != widget.start_date_edit.minimumDate()
    assert widget.end_date_edit.date() != widget.end_date_edit.minimumDate()
    assert widget.start_date_edit.date().year() > 1752
    assert widget.end_date_edit.date().year() > 1752


def test_date_range_initial_state_is_deterministic_and_unset(window):
    widget, _ = window

    today = QDate.currentDate()
    assert widget.start_date_edit.date() == today
    assert widget.end_date_edit.date() == today
    assert widget._date_range_selection.current is None
    assert widget.date_range_label.text() == "No date range selected"


def test_date_range_controls_initialize_to_a_fixed_current_date(monkeypatch, tmp_path):
    fixed_today = date(2026, 3, 15)
    monkeypatch.setattr(app, "_current_local_date", lambda: fixed_today)
    widget, _ = _build_app(monkeypatch, tmp_path)
    try:
        assert widget.start_date_edit.date() == QDate(2026, 3, 15)
        assert widget.end_date_edit.date() == QDate(2026, 3, 15)
        assert widget._date_range_selection.current is None
    finally:
        _close_app(widget)


def test_validating_same_day_range_accepts_and_updates_label(window):
    widget, _ = window
    widget.start_date_edit.setDate(QDate(2026, 3, 1))
    widget.end_date_edit.setDate(QDate(2026, 3, 1))

    widget._validate_date_range()

    assert widget._date_range_selection.current == DateRange(date(2026, 3, 1), date(2026, 3, 1))
    assert widget.date_range_label.text() == "Accepted: 2026-03-01 to 2026-03-01"
    assert widget.start_date_edit.date() == QDate(2026, 3, 1)
    assert widget.end_date_edit.date() == QDate(2026, 3, 1)
    assert widget.status.text() == "Date range accepted."


def test_validating_multi_day_range_accepts_and_updates_label(window):
    widget, _ = window
    widget.start_date_edit.setDate(QDate(2026, 3, 1))
    widget.end_date_edit.setDate(QDate(2026, 3, 10))

    widget._validate_date_range()

    assert widget._date_range_selection.current == DateRange(date(2026, 3, 1), date(2026, 3, 10))
    assert widget.date_range_label.text() == "Accepted: 2026-03-01 to 2026-03-10"


def test_validating_with_missing_start_date_shows_error_and_preserves_state(window, monkeypatch):
    widget, _ = window
    # The "Not set" sentinel is represented by the control's own minimumDate();
    # explicitly select it here to simulate a genuinely missing start date,
    # since the control no longer defaults to that sentinel on construction.
    widget.start_date_edit.setDate(widget.start_date_edit.minimumDate())
    widget.end_date_edit.setDate(QDate(2026, 3, 10))
    critical = Mock()
    monkeypatch.setattr(QMessageBox, "critical", critical)

    widget._validate_date_range()

    assert widget._date_range_selection.current is None
    assert widget.date_range_label.text() == "No date range selected"
    critical.assert_called_once()
    title, message = critical.call_args.args[1], critical.call_args.args[2]
    assert title == "Date Range"
    assert message == "A start date is required."


def test_validating_with_missing_end_date_shows_error_and_preserves_state(window, monkeypatch):
    widget, _ = window
    widget.start_date_edit.setDate(QDate(2026, 3, 1))
    # See the missing-start-date test above for why the sentinel must now be
    # selected explicitly rather than relying on construction-time defaults.
    widget.end_date_edit.setDate(widget.end_date_edit.minimumDate())
    critical = Mock()
    monkeypatch.setattr(QMessageBox, "critical", critical)

    widget._validate_date_range()

    assert widget._date_range_selection.current is None
    assert widget.date_range_label.text() == "No date range selected"
    critical.assert_called_once()
    title, message = critical.call_args.args[1], critical.call_args.args[2]
    assert title == "Date Range"
    assert message == "An end date is required."


def test_validating_reversed_range_shows_error_and_preserves_previous_accepted_range(
    window, monkeypatch
):
    widget, _ = window
    widget.start_date_edit.setDate(QDate(2026, 3, 1))
    widget.end_date_edit.setDate(QDate(2026, 3, 5))
    widget._validate_date_range()
    previous = widget._date_range_selection.current
    assert previous == DateRange(date(2026, 3, 1), date(2026, 3, 5))

    widget.start_date_edit.setDate(QDate(2026, 3, 9))
    widget.end_date_edit.setDate(QDate(2026, 3, 1))
    critical = Mock()
    monkeypatch.setattr(QMessageBox, "critical", critical)

    widget._validate_date_range()

    assert widget._date_range_selection.current == previous
    assert widget.date_range_label.text() == "Accepted: 2026-03-01 to 2026-03-05"
    critical.assert_called_once()
    title, message = critical.call_args.args[1], critical.call_args.args[2]
    assert title == "Date Range"
    assert message == "The end date must not be earlier than the start date."


def test_date_range_controls_remain_enabled_and_retryable_after_error(window, monkeypatch):
    widget, _ = window
    widget.start_date_edit.setDate(QDate(2026, 3, 9))
    widget.end_date_edit.setDate(QDate(2026, 3, 1))
    monkeypatch.setattr(QMessageBox, "critical", Mock())

    widget._validate_date_range()

    assert widget._date_range_selection.current is None
    assert widget.start_date_edit.isEnabled()
    assert widget.end_date_edit.isEnabled()
    assert widget.validate_date_range_button.isEnabled()


def test_date_range_successful_retry_after_correction(window, monkeypatch):
    widget, _ = window
    widget.start_date_edit.setDate(QDate(2026, 3, 9))
    widget.end_date_edit.setDate(QDate(2026, 3, 1))
    monkeypatch.setattr(QMessageBox, "critical", Mock())
    widget._validate_date_range()
    assert widget._date_range_selection.current is None

    widget.start_date_edit.setDate(QDate(2026, 3, 1))
    widget.end_date_edit.setDate(QDate(2026, 3, 9))

    widget._validate_date_range()

    assert widget._date_range_selection.current == DateRange(date(2026, 3, 1), date(2026, 3, 9))
    assert widget.date_range_label.text() == "Accepted: 2026-03-01 to 2026-03-09"


def test_date_range_validation_triggers_no_browser_lifecycle_file_or_processing_operation(
    window, monkeypatch
):
    widget, _ = window
    monkeypatch.setattr(app.QFileDialog, "getOpenFileName", Mock())
    monkeypatch.setattr(app.QFileDialog, "getExistingDirectory", Mock())
    thread_start = Mock()
    monkeypatch.setattr(threading.Thread, "start", thread_start)
    # The second _validate_date_range() call below uses a reversed (invalid)
    # range, which reaches _show_error() -> QMessageBox.critical(). Without
    # mocking it, that call opens a real blocking modal Qt event loop that
    # never returns under the offscreen platform, hanging the test.
    monkeypatch.setattr(QMessageBox, "critical", Mock())
    previous_download_directory = widget._download_directory.current
    widget.start_date_edit.setDate(QDate(2026, 3, 1))
    widget.end_date_edit.setDate(QDate(2026, 3, 5))

    widget._validate_date_range()
    widget.start_date_edit.setDate(QDate(2026, 3, 9))
    widget.end_date_edit.setDate(QDate(2026, 3, 1))
    widget._validate_date_range()

    widget.prisma_lifecycle.open.assert_not_called()
    widget.prisma_lifecycle.close.assert_not_called()
    app.QFileDialog.getOpenFileName.assert_not_called()
    app.QFileDialog.getExistingDirectory.assert_not_called()
    thread_start.assert_not_called()
    assert widget._download_directory.current == previous_download_directory
    assert widget._manual_csv_selection.current is None


def test_open_prisma_session_success_updates_badge_and_status(window, monkeypatch):
    widget, _ = window
    date_range = accept_date_range(widget)
    widget.prisma_lifecycle.open.return_value = 11
    widget.prisma_lifecycle.get_events.return_value = [
        PrismaLifecycleEvent(11, True, kind="open")
    ]
    monkeypatch.setattr(widget._prisma_timer, "start", Mock())
    monkeypatch.setattr(widget._prisma_timer, "stop", Mock())

    widget._open_prisma_session()
    widget._poll_prisma_lifecycle()

    widget.prisma_lifecycle.open.assert_called_once_with(
        date_range=date_range, download_directory=widget._download_directory.current,
    )
    assert widget._prisma_open
    assert widget.prisma_badge.text() == "Prisma open"
    assert "PRISMA opened" in widget.status.text()
    assert not widget.open_prisma_button.isEnabled()
    assert widget.close_prisma_button.isEnabled()


def test_open_prisma_rejects_without_an_accepted_date_range(window, monkeypatch):
    widget, _ = window
    critical = Mock()
    monkeypatch.setattr(QMessageBox, "critical", critical)

    widget._open_prisma_session()

    widget.prisma_lifecycle.open.assert_not_called()
    assert widget._active_prisma_generation is None
    critical.assert_called_once()
    title, message = critical.call_args.args[1], critical.call_args.args[2]
    assert title == "Open Prisma"
    assert message == "Select and validate a date range before opening PRISMA."


def test_open_prisma_rejects_when_the_download_directory_is_no_longer_valid(
    window, monkeypatch
):
    widget, _ = window
    accept_date_range(widget)
    widget._download_directory.current.rmdir()
    critical = Mock()
    monkeypatch.setattr(QMessageBox, "critical", critical)

    widget._open_prisma_session()

    widget.prisma_lifecycle.open.assert_not_called()
    assert widget._active_prisma_generation is None
    critical.assert_called_once()
    title, message = critical.call_args.args[1], critical.call_args.args[2]
    assert title == "Open Prisma"
    assert message == (
        "The selected download folder is not valid. Choose an existing, writable folder."
    )


def test_download_event_success_selects_the_csv_and_updates_labels(window, tmp_path):
    widget, _ = window
    csv_path = tmp_path / "Auction_overview_2026-03-01_2026-03-05.csv"
    header = ";".join(PRISMA_EXPORT_COLUMNS)
    csv_path.write_bytes((header + "\r\n").encode("cp1252"))

    widget._handle_download_event(
        PrismaLifecycleEvent(11, True, kind="download", csv_path=csv_path)
    )

    assert widget._manual_csv_selection.current == csv_path.resolve()
    assert widget.manual_csv_label.text() == csv_path.name
    assert "PRISMA CSV downloaded" in widget.status.text()


def test_download_event_failure_shows_the_stable_error_and_does_not_touch_csv_selection(
    window, monkeypatch
):
    widget, _ = window
    critical = Mock()
    monkeypatch.setattr(QMessageBox, "critical", critical)
    message_text = describe_download_failure(PrismaDownloadOutcome.DOWNLOAD_TIMEOUT)

    widget._handle_download_event(
        PrismaLifecycleEvent(11, False, message_text, kind="download")
    )

    assert widget._manual_csv_selection.current is None
    assert widget.status.text() == message_text
    critical.assert_called_once()
    title, message = critical.call_args.args[1], critical.call_args.args[2]
    assert title == "PRISMA Download"
    assert message == message_text


def test_download_event_with_an_invalid_csv_contract_is_rejected(window, monkeypatch, tmp_path):
    widget, _ = window
    csv_path = tmp_path / "bad-export.csv"
    csv_path.write_text("not,the,right,header\n", encoding="utf-8")
    critical = Mock()
    monkeypatch.setattr(QMessageBox, "critical", critical)

    widget._handle_download_event(
        PrismaLifecycleEvent(11, True, kind="download", csv_path=csv_path)
    )

    assert widget._manual_csv_selection.current is None
    critical.assert_called_once()
    title, message = critical.call_args.args[1], critical.call_args.args[2]
    assert title == "PRISMA Download"
    assert message == describe_manual_csv_rejection(ManualCsvOutcome.DELIMITER)
    assert widget.status.text() == (
        "The downloaded PRISMA CSV did not match the expected export format."
    )


def test_poll_prisma_lifecycle_routes_a_download_event_without_closing_the_session(
    window, tmp_path
):
    widget, _ = window
    csv_path = tmp_path / "Auction_overview_2026-03-01_2026-03-05.csv"
    header = ";".join(PRISMA_EXPORT_COLUMNS)
    csv_path.write_bytes((header + "\r\n").encode("cp1252"))
    widget._active_prisma_generation = 11
    widget._prisma_open = True
    widget.prisma_lifecycle.get_events.return_value = [
        PrismaLifecycleEvent(11, True, kind="download", csv_path=csv_path)
    ]

    widget._poll_prisma_lifecycle()

    assert widget.manual_csv_label.text() == csv_path.name
    assert widget._prisma_open
    assert widget._active_prisma_generation == 11


def test_repeated_open_prisma_click_is_a_safe_no_op_while_active(window):
    widget, _ = window
    widget.prisma_lifecycle.open.return_value = 11
    widget._active_prisma_generation = 11
    widget._prisma_open = True

    widget._open_prisma_session()

    widget.prisma_lifecycle.open.assert_not_called()


def test_close_prisma_with_no_active_session_is_idempotent(window):
    widget, _ = window

    widget._close_prisma_session()
    widget._close_prisma_session()

    assert widget.prisma_lifecycle.close.call_count == 2
    assert not widget._prisma_open
    assert widget._active_prisma_generation is None
    assert widget.prisma_badge.text() == "Prisma closed"
    assert widget.status.text() == "PRISMA closed"


def test_close_prisma_session_enters_a_stable_closing_state(window):
    widget, _ = window
    widget._active_prisma_generation = 11
    widget._prisma_open = True
    widget._update_controls()

    widget._close_prisma_session()

    widget.prisma_lifecycle.close.assert_called_once_with()
    assert widget._prisma_closing
    assert widget._active_prisma_generation == 11
    assert widget.prisma_badge.text() == "Closing Prisma…"
    assert widget.status.text() == "Closing PRISMA…"
    assert not widget.open_prisma_button.isEnabled()
    assert not widget.close_prisma_button.isEnabled()


def test_repeated_close_click_while_closing_does_not_resignal(window):
    widget, _ = window
    widget._active_prisma_generation = 11
    widget._prisma_open = True
    widget._update_controls()
    widget._close_prisma_session()

    widget._close_prisma_session()

    widget.prisma_lifecycle.close.assert_called_once_with()


def test_close_completed_event_restores_idle_controls_only_after_cleanup(window):
    widget, _ = window
    widget._active_prisma_generation = 11
    widget._prisma_open = True
    widget._update_controls()
    widget._close_prisma_session()
    assert not widget.open_prisma_button.isEnabled()
    assert not widget.close_prisma_button.isEnabled()

    widget.prisma_lifecycle.get_events.return_value = []
    widget._poll_prisma_lifecycle()
    assert widget._prisma_closing
    assert not widget.open_prisma_button.isEnabled()
    assert widget.prisma_badge.text() == "Closing Prisma…"

    widget.prisma_lifecycle.get_events.return_value = [
        PrismaLifecycleEvent(11, True, kind="close")
    ]
    widget._poll_prisma_lifecycle()

    assert not widget._prisma_closing
    assert not widget._prisma_open
    assert widget._active_prisma_generation is None
    assert widget.prisma_badge.text() == "Prisma closed"
    assert widget.status.text() == "PRISMA closed"
    assert widget.open_prisma_button.isEnabled()
    assert not widget.close_prisma_button.isEnabled()


def test_open_prisma_click_during_closing_is_a_deterministic_no_op(window):
    widget, _ = window
    widget._active_prisma_generation = 11
    widget._prisma_open = True
    widget._update_controls()
    widget._close_prisma_session()
    widget.prisma_lifecycle.open.reset_mock()

    widget._open_prisma_session()

    widget.prisma_lifecycle.open.assert_not_called()
    assert widget._active_prisma_generation == 11
    assert not widget.open_prisma_button.isEnabled()


def test_rapid_close_then_open_cannot_produce_overlapping_sessions(window):
    widget, _ = window
    date_range = accept_date_range(widget)
    widget.prisma_lifecycle.open.return_value = 11
    widget.prisma_lifecycle.get_events.return_value = [
        PrismaLifecycleEvent(11, True, kind="open")
    ]
    widget._open_prisma_session()
    widget._poll_prisma_lifecycle()
    assert widget._prisma_open
    widget.prisma_lifecycle.open.reset_mock()

    widget._close_prisma_session()
    widget._open_prisma_session()

    widget.prisma_lifecycle.open.assert_not_called()

    widget.prisma_lifecycle.get_events.return_value = [
        PrismaLifecycleEvent(11, True, kind="close")
    ]
    widget._poll_prisma_lifecycle()
    assert widget.open_prisma_button.isEnabled()

    widget.prisma_lifecycle.open.return_value = 12
    widget.prisma_lifecycle.get_events.return_value = [
        PrismaLifecycleEvent(12, True, kind="open")
    ]
    widget._open_prisma_session()
    widget._poll_prisma_lifecycle()

    widget.prisma_lifecycle.open.assert_called_once_with(
        date_range=date_range, download_directory=widget._download_directory.current,
    )
    assert widget._prisma_open
    assert widget._active_prisma_generation == 12


def test_manual_prisma_closure_returns_a_retryable_state(window):
    widget, _ = window
    widget._active_prisma_generation = 11
    widget._prisma_open = True
    widget._update_controls()
    widget.prisma_lifecycle.get_events.return_value = [
        PrismaLifecycleEvent(
            11, False, "The PRISMA browser was closed manually.", kind="closed"
        )
    ]

    widget._poll_prisma_lifecycle()

    assert not widget._prisma_open
    assert widget._active_prisma_generation is None
    assert widget.prisma_badge.text() == "Prisma closed"
    assert "Open Prisma to retry" in widget.status.text()
    assert widget.open_prisma_button.isEnabled()
    assert not widget.close_prisma_button.isEnabled()


def test_stale_prisma_event_does_not_change_dashboard(window):
    widget, _ = window
    widget._active_prisma_generation = 11
    widget.prisma_lifecycle.get_events.return_value = [
        PrismaLifecycleEvent(10, True, kind="open")
    ]

    widget._poll_prisma_lifecycle()

    assert not widget._prisma_open
    assert widget.prisma_badge.text() == "Prisma closed"


def test_single_drain_with_open_then_manual_closed_loses_no_event(window):
    widget, _ = window
    widget._active_prisma_generation = 11
    widget.prisma_lifecycle.get_events.return_value = [
        PrismaLifecycleEvent(11, True, kind="open"),
        PrismaLifecycleEvent(
            11, False, "The PRISMA browser was closed manually.", kind="closed"
        ),
    ]
    status_spy = Mock(wraps=widget.status.setText)
    widget.status.setText = status_spy

    widget._poll_prisma_lifecycle()

    assert not widget._prisma_open
    assert widget._active_prisma_generation is None
    assert widget.prisma_badge.text() == "Prisma closed"
    assert "Open Prisma to retry" in widget.status.text()
    assert widget.open_prisma_button.isEnabled()
    assert not widget.close_prisma_button.isEnabled()
    status_texts = [call.args[0] for call in status_spy.call_args_list]
    assert status_texts.count("PRISMA opened in the managed browser session.") == 1
    assert status_texts.count("PRISMA was closed manually. Open Prisma to retry.") == 1


def test_single_drain_with_open_then_close_completed_loses_no_event(window):
    widget, _ = window
    widget._active_prisma_generation = 11
    widget._prisma_closing = True
    widget.prisma_lifecycle.get_events.return_value = [
        PrismaLifecycleEvent(11, True, kind="open"),
        PrismaLifecycleEvent(11, True, kind="close"),
    ]

    widget._poll_prisma_lifecycle()

    assert not widget._prisma_open
    assert not widget._prisma_closing
    assert widget._active_prisma_generation is None
    assert widget.prisma_badge.text() == "Prisma closed"
    assert widget.status.text() == "PRISMA closed"
    assert widget.open_prisma_button.isEnabled()
    assert not widget.close_prisma_button.isEnabled()


def test_close_failure_event_locks_controls_with_a_stable_error(window, monkeypatch):
    widget, _ = window
    widget._active_prisma_generation = 11
    widget._prisma_closing = True
    critical = Mock()
    monkeypatch.setattr(QMessageBox, "critical", critical)
    widget.prisma_lifecycle.get_events.return_value = [
        PrismaLifecycleEvent(
            11, False,
            "The PRISMA browser could not be confirmed closed.", kind="close",
        )
    ]

    widget._poll_prisma_lifecycle()

    assert not widget._prisma_open
    assert not widget._prisma_closing
    assert widget._prisma_close_error
    assert widget.prisma_badge.text() == "Prisma close error"
    assert not widget.open_prisma_button.isEnabled()
    assert not widget.close_prisma_button.isEnabled()
    critical.assert_called_once()

    widget.prisma_lifecycle.open.reset_mock()
    widget._open_prisma_session()
    widget.prisma_lifecycle.open.assert_not_called()

    widget.prisma_lifecycle.close.reset_mock()
    widget._close_prisma_session()
    widget.prisma_lifecycle.close.assert_not_called()


def test_single_drain_skips_stale_generation_events_mixed_with_active_ones(window):
    widget, _ = window
    widget._active_prisma_generation = 12
    widget.prisma_lifecycle.get_events.return_value = [
        PrismaLifecycleEvent(11, True, kind="open"),
        PrismaLifecycleEvent(
            11, False, "The PRISMA browser was closed manually.", kind="closed"
        ),
        PrismaLifecycleEvent(12, True, kind="open"),
    ]

    widget._poll_prisma_lifecycle()

    assert widget._prisma_open
    assert widget._active_prisma_generation == 12
    assert widget.prisma_badge.text() == "Prisma open"


def test_open_prisma_startup_failure_shows_stable_english_error(window, monkeypatch):
    widget, _ = window
    accept_date_range(widget)
    widget.prisma_lifecycle.open.return_value = 11
    widget.prisma_lifecycle.get_events.return_value = [
        PrismaLifecycleEvent(11, False, "diagnostic detail", kind="open")
    ]
    monkeypatch.setattr(widget._prisma_timer, "start", Mock())
    critical = Mock()
    monkeypatch.setattr(QMessageBox, "critical", critical)

    widget._open_prisma_session()
    widget._poll_prisma_lifecycle()

    assert widget.open_prisma_button.isEnabled()
    assert not widget.close_prisma_button.isEnabled()
    assert widget.prisma_badge.text() == "Prisma error"
    critical.assert_called_once()
    assert "diagnostic detail" not in critical.call_args.args[2]


def test_single_drain_stops_after_a_terminal_open_failure_avoiding_duplicate_dialogs(
    window, monkeypatch
):
    widget, _ = window
    widget._active_prisma_generation = 11
    critical = Mock()
    monkeypatch.setattr(QMessageBox, "critical", critical)
    widget.prisma_lifecycle.get_events.return_value = [
        PrismaLifecycleEvent(11, False, "diagnostic detail", kind="open"),
        PrismaLifecycleEvent(
            11, False, "The PRISMA browser was closed manually.", kind="closed"
        ),
    ]

    widget._poll_prisma_lifecycle()

    critical.assert_called_once()
    assert widget.prisma_badge.text() == "Prisma error"


def test_open_prisma_session_raising_synchronously_is_handled(window, monkeypatch):
    widget, _ = window
    accept_date_range(widget)
    widget.prisma_lifecycle.open.side_effect = RuntimeError("driver missing")
    monkeypatch.setattr(QMessageBox, "critical", Mock())

    widget._open_prisma_session()

    assert not widget._prisma_open
    assert widget._active_prisma_generation is None
    assert widget.prisma_badge.text() == "Prisma error"


def test_shutdown_closes_only_the_owned_prisma_session(window):
    widget, _ = window

    widget.closeEvent(Mock())

    widget.prisma_lifecycle.close.assert_called_once_with()


def test_shutdown_waits_boundedly_for_prisma_lifecycle_cleanup(window, monkeypatch):
    widget, _ = window
    widget.prisma_lifecycle.join.return_value = False
    monkeypatch.setattr(app.QTimer, "singleShot", Mock())
    close_event = Mock()

    widget.closeEvent(close_event)

    widget.prisma_lifecycle.close.assert_called_once_with()
    widget.prisma_lifecycle.join.assert_called_once_with(timeout=0.05)
    close_event.ignore.assert_called_once_with()
    close_event.accept.assert_not_called()
    assert "PRISMA browser session is finishing safely" in widget.status.text()

    widget.prisma_lifecycle.join.return_value = True
    finished_event = Mock()
    widget.closeEvent(finished_event)

    finished_event.accept.assert_called_once_with()


def test_shutdown_never_accepts_while_the_lifecycle_worker_is_still_alive(window, monkeypatch):
    widget, _ = window
    widget.prisma_lifecycle.join.return_value = False
    monkeypatch.setattr(app.QTimer, "singleShot", Mock())
    widget.closeEvent(Mock())
    widget._prisma_shutdown_deadline = time.monotonic() - 1

    still_alive_event = Mock()
    widget.closeEvent(still_alive_event)

    still_alive_event.accept.assert_not_called()
    still_alive_event.ignore.assert_called_once_with()
    assert "longer than expected" in widget.status.text()

    another_event = Mock()
    widget.closeEvent(another_event)

    another_event.accept.assert_not_called()
    another_event.ignore.assert_called_once_with()

    widget.prisma_lifecycle.join.return_value = True
    finished_event = Mock()
    widget.closeEvent(finished_event)

    finished_event.accept.assert_called_once_with()


def test_shutdown_never_accepts_when_close_cleanup_could_not_be_confirmed(
    window, monkeypatch
):
    widget, _ = window
    widget.prisma_lifecycle.join.return_value = True
    widget.prisma_lifecycle.state = PrismaLifecycleState.CLOSE_FAILED
    monkeypatch.setattr(app.QTimer, "singleShot", Mock())

    first_event = Mock()
    widget.closeEvent(first_event)

    first_event.accept.assert_not_called()
    first_event.ignore.assert_called_once_with()
    assert "cannot exit safely" in widget.status.text()

    second_event = Mock()
    widget.closeEvent(second_event)

    second_event.accept.assert_not_called()
    second_event.ignore.assert_called_once_with()

    widget.prisma_lifecycle.state = PrismaLifecycleState.IDLE
    finished_event = Mock()
    widget.closeEvent(finished_event)

    finished_event.accept.assert_called_once_with()


def test_processing_success_preserves_full_statistics(window, monkeypatch):
    widget, _ = window
    workflow_result = PrismaWorkflowResult(
        4, 1, 2, 1, 0, 0, (), Path("result.xlsx"),
        SourceUpdateStatus.APPLIED, "accepted",
    )
    monkeypatch.setattr(
        app, "run_prisma_import_workflow", Mock(return_value=workflow_result)
    )
    monkeypatch.setattr(
        app.QFileDialog, "getOpenFileName", Mock(return_value=("input.csv", "CSV"))
    )

    finished = QSignalSpy(widget.signals.processing_finished)
    widget.start_processing()
    assert finished.count() == 1 or finished.wait(2000)
    QApplication.processEvents()

    assert finished.count() == 1
    outcome = finished.at(0)[0]
    assert outcome.result is workflow_result
    assert outcome.error is None
    assert widget.status.text() == (
        "accepted Processed: 4; inserted: 1; updated: 2; unchanged: 1; "
        "filtered: 0; rejected: 0; audit issues: 0. Output: result.xlsx"
    )
    assert not widget._processing_active
    assert widget._active_processing_thread is None
    assert not widget._processing_threads
    assert widget.process_button.isEnabled()

    widget._processing_finished(app.ProcessingOutcome(workflow_result, None, 0))
    assert widget.status.text().startswith("accepted Processed: 4")


def test_import_processing_success_and_error_restore_controls(window, monkeypatch):
    widget, _ = window
    monkeypatch.setattr(QMessageBox, "critical", Mock())
    monkeypatch.setattr(
        app.QFileDialog, "getOpenFileName", Mock(return_value=("export.csv", "CSV"))
    )

    class FakeThread:
        def __init__(self, **kwargs): self.kwargs = kwargs
        def start(self): pass
        def is_alive(self): return False

    monkeypatch.setattr(app.threading, "Thread", FakeThread)
    widget.start_processing()
    assert widget._processing_active
    assert not widget.process_button.isEnabled()
    assert "Importing" in widget.status.text()

    widget._processing_failed("Unsupported CSV format.", None)
    assert not widget._processing_active
    assert widget.process_button.isEnabled()
    assert "Unsupported CSV format" in widget.status.text()


def test_close_defers_without_blocking_until_live_workers_finish(window, monkeypatch):
    widget, _ = window
    widget._is_closing = True
    processing_worker = Mock()
    processing_worker.is_alive.return_value = True
    widget._processing_threads = {processing_worker}
    close_event = Mock()
    retry_close = Mock()
    monkeypatch.setattr(app.QTimer, "singleShot", Mock(side_effect=lambda _, callback: retry_close(callback)))

    widget.closeEvent(close_event)

    processing_worker.join.assert_not_called()
    assert widget.status.text() == "Closing; a background import is finishing safely."
    close_event.ignore.assert_called_once_with()
    assert retry_close.call_count == 1

    processing_worker.is_alive.return_value = False
    finished_event = Mock()
    widget.closeEvent(finished_event)
    finished_event.accept.assert_called_once_with()


def test_close_does_not_block_on_a_genuinely_running_import(window, monkeypatch):
    widget, _ = window
    release = threading.Event()
    worker = threading.Thread(target=release.wait, name="blocked-import")
    worker.start()
    widget._processing_threads = {worker}
    widget._active_processing_thread = worker
    widget._processing_active = True
    monkeypatch.setattr(app.QTimer, "singleShot", Mock())
    event = Mock()
    try:
        started = time.monotonic()
        widget.closeEvent(event)
        assert time.monotonic() - started < 0.5
        event.ignore.assert_called_once_with()
        assert widget.status.text() == "Closing; a background import is finishing safely."
    finally:
        release.set()
        worker.join(timeout=2)
    final_event = Mock()
    widget.closeEvent(final_event)
    final_event.accept.assert_called_once_with()


def test_startup_shows_path_error_after_qapplication_exists(monkeypatch):
    application = Mock()
    monkeypatch.setattr(app.QApplication, "instance", Mock(return_value=application))
    monkeypatch.setattr(app, "runtime_paths", Mock(side_effect=app.RuntimePathError("LOCALAPPDATA must be absolute")))
    logging_init = Mock()
    migration = Mock()
    message = Mock()
    monkeypatch.setattr(app, "initialize_runtime_logging", logging_init)
    monkeypatch.setattr(app, "migrate_legacy_runtime_data", migration)
    monkeypatch.setattr(app.QMessageBox, "critical", message)

    assert app.main() == 1

    logging_init.assert_not_called()
    migration.assert_not_called()
    message.assert_called_once()
    assert "LOCALAPPDATA must be absolute" in message.call_args.args[2]


def test_startup_does_not_migrate_when_required_logging_fails(tmp_path, monkeypatch):
    application = Mock()
    paths = app.RuntimePaths(
        root=tmp_path, database=tmp_path / "data/db.sqlite",
        result=tmp_path / "data/result/result.xlsx",
        state=tmp_path / "state/state.json", log=tmp_path / "logs/app.log",
    )
    monkeypatch.setattr(app.QApplication, "instance", Mock(return_value=application))
    monkeypatch.setattr(app, "runtime_paths", Mock(return_value=paths))
    monkeypatch.setattr(app, "initialize_runtime_logging", Mock(return_value=(Mock(), None)))
    migration = Mock()
    message = Mock()
    monkeypatch.setattr(app, "migrate_legacy_runtime_data", migration)
    monkeypatch.setattr(app.QMessageBox, "critical", message)

    assert app.main() == 1

    migration.assert_not_called()
    assert "required user-data log file could not be created" in message.call_args.args[2]
