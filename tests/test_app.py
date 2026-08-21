import csv
import gc
import os
import threading
import time
from pathlib import Path
from unittest.mock import Mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel, QMessageBox, QPushButton, QWidget

import prisma_function.app as app
import prisma_function.prisma_output as prisma_output
import prisma_function.prisma_publication as prisma_publication
from prisma_function.csv_contracts import PRISMA_EXPORT_COLUMNS
from prisma_function.mapping_presentation import MAPPING_DISPLAY_FIELDS
from prisma_function.processor import PrismaImportError
from prisma_function.prisma_import_workflow import SourceUpdateStatus
from prisma_function.storage import AuctionStorage, RateResolutionRecord
from prisma_function.version import APP_DISPLAY_NAME, __version__
from prisma_function.ui_components import APP_STYLE


# Generous hang backstop for `_close_app`'s worker join — not a "settle
# quickly" budget, see that function's docstring.
_WORKER_JOIN_TIMEOUT_S = 30.0


@pytest.fixture(scope="session")
def qt_app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _build_app(monkeypatch, tmp_path):
    root = tmp_path / "runtime"
    paths = app.RuntimePaths(
        root=root, database=root / "data/test.db",
        result=root / "data/result/test.xlsx",
        state=root / "state/test.json", log=root / "logs/test.log",
    )
    publication_directory = tmp_path / "Documents"
    publication_directory.mkdir()
    widget = app.PrismaMonitorApp(paths, publication_directory)
    return widget, None


def _close_app(widget) -> None:
    """Tear down `widget`, guaranteeing every processing worker has fully
    returned first.

    Deleting the widget (and its `WorkerSignals`) while a worker thread is
    still alive races that thread's `processing_finished.emit()`/storage
    calls against the widget's own destruction, which is the Windows access
    violation this lifecycle fix addresses. A single bounded `join(timeout=
    _WORKER_JOIN_TIMEOUT_S)` call per worker blocks without holding the GIL
    and without polling `QApplication.processEvents()`, so it never contends
    with the worker thread for the GIL/CPU the way the previous busy loop
    (interleaving `processEvents()` with short `join(timeout=...)` calls) did
    on a loaded CI runner — that contention was what let the worker miss a
    tight deadline. The bound here is generous purely as a hang backstop: a
    worker that is actually still running finishes almost immediately, so
    hitting the timeout means something is genuinely stuck, and the
    subsequent `is_alive()` assertion still fails loudly with a clear message
    instead of silently proceeding into a teardown race. Only after every
    worker has actually returned do we drain the event loop once, flushing
    its now-queued `processing_finished` signal before the widget is
    destroyed.
    """
    widget._is_closing = True
    for worker in list(widget._processing_threads):
        worker.join(timeout=_WORKER_JOIN_TIMEOUT_S)
        assert not worker.is_alive(), "processing worker did not finish before test teardown"
    QApplication.processEvents()
    widget._processing_threads.clear()
    widget.close()


@pytest.fixture
def window(qt_app, monkeypatch, tmp_path):
    widget, browser = _build_app(monkeypatch, tmp_path)
    yield widget, browser
    _close_app(widget)
    # Each PrismaMonitorApp instance holds self-referencing Qt signal/slot
    # cycles; plain refcounting never reclaims those, only Python's cyclic GC
    # does. Forcing collection after every test keeps unreachable Qt object
    # graphs from piling up across the whole session and being torn down in
    # one large, unordered batch at interpreter shutdown.
    del widget, browser
    gc.collect()


@pytest.fixture(autouse=True)
def _default_critical_dialog_mock(monkeypatch):
    """Selecting an accepted CSV now always triggers real background
    processing (see `app._select_manual_csv`/`_process_selected_csv`), which
    fails closed for most of this file's fixture rows (no confirmed EUR
    rate). Settling that processing via `_settle_processing()` below would
    otherwise be free to pop a real blocking `QMessageBox.critical` dialog.
    Mocking it here by default keeps every test safe; a test that wants to
    inspect the actual dialog calls installs its own mock afterward — the
    same `monkeypatch` fixture instance lets a later `setattr` in the test
    body override this default for the rest of that test.
    """
    monkeypatch.setattr(QMessageBox, "critical", Mock())


def _settle_processing(widget, *, timeout_s: float = 5.0) -> None:
    """Pump the Qt event loop until background processing triggered by
    `_select_manual_csv()` has settled (bounded).

    A real user's separate clicks naturally allow this event-loop time to
    pass between selections; calling `_select_manual_csv()` twice
    back-to-back in a test does not. Without settling first, the still-
    "active" first selection makes `_select_manual_csv()`'s own guard treat
    a second, immediate selection as ignorable.
    """
    deadline = time.monotonic() + timeout_s
    while widget._processing_active and time.monotonic() < deadline:
        QApplication.processEvents()
        time.sleep(0.01)
    assert not widget._processing_active, "processing did not settle within the timeout"


def _seed_resolved_rate(
    widget, auction_id: str, *, currency: str = "EUR", rate_to_eur: str = "1",
    ecb_publication_date: str = "2026-08-01",
    auction_end_at: str = "2026-08-01T15:00:00+00:00",
) -> None:
    """Directly populate `AuctionStorage`'s durable per-Auction-ID rate cache.

    Per the revised specification, PrismaFunction never opens, controls, or
    downloads anything from the PRISMA website, so there is no live PRISMA
    transport left in the application to resolve an uncached Finished
    auction's rate. A previously fixed resolution is the only way a Finished
    auction's rate becomes (and stays) resolved; seeding it directly here
    mirrors that reality instead of faking a live fetch that no longer
    exists in production.
    """
    AuctionStorage(widget._runtime_paths.database).save_rate_resolution(
        RateResolutionRecord(
            auction_id=auction_id, auction_state="Finished",
            auction_end_at=auction_end_at, currency=currency,
            ecb_publication_date=ecb_publication_date, rate_to_eur=rate_to_eur,
            resolved_at_utc="2026-08-01T15:05:00+00:00", source_version="test",
        )
    )


def _seed_ecb_date_rate(
    widget, auction_date: str, currency: str, *, rate_to_eur: str = "1",
    ecb_publication_date: str | None = None,
) -> None:
    """Directly populate `AuctionStorage`'s durable P.37 `(auction_date,
    currency)` rate cache, mirroring `_seed_resolved_rate` above for the
    separate, Auction-ID-keyed Mapping-display cache. The real active
    processing call graph (`app.py` -> `run_prisma_import_workflow` ->
    `price_normalization.normalize_prices_for_output`) never injects a fake
    `ecb_source`, so a non-EUR currency with no cached rate would otherwise
    need real network access to the public ECB endpoint; seeding this cache
    directly exercises the exact same read path a previously resolved pair
    uses in production, without any network access.
    """
    from prisma_function.storage import EcbAuctionDateRateRecord

    AuctionStorage(widget._runtime_paths.database).save_ecb_auction_date_rate(
        EcbAuctionDateRateRecord(
            auction_date=auction_date, currency=currency,
            ecb_publication_date=ecb_publication_date or auction_date,
            rate_to_eur=rate_to_eur,
            resolved_at_utc="2026-08-01T15:05:00+00:00",
            source_version="test",
        )
    )


def _block_live_ecb_access(monkeypatch) -> None:
    """Patch the production ECB HTTP source so a non-EUR currency with no
    cached P.37 rate fails closed deterministically and without any real
    network access, since `app.py`'s real processing call graph never
    injects a fake `ecb_source` of its own.
    """
    from prisma_function.ecb_rates import EcbRateNotFoundError

    def fail(self, currency, *, on_or_before, timeout_seconds):
        raise EcbRateNotFoundError(f"no rate for {currency} (test double)")

    monkeypatch.setattr("prisma_function.ecb_rates.EcbSdwHttpRateSource.fetch", fail)


def test_initial_dashboard_state_and_accessibility(window):
    widget, _ = window
    assert widget.windowTitle() == f"{APP_DISPLAY_NAME} v{__version__}"
    assert widget.minimumWidth() >= 1080
    assert widget.status.text() == "Ready"


def test_light_workspace_widgets_use_explicit_contrast_styles(window):
    widget, _ = window
    content = widget.findChild(QWidget, "contentArea")
    section_labels = widget.findChildren(QLabel, "contentSectionLabel")

    assert content is not None
    assert any(label.text().startswith("Mapping") for label in section_labels)
    assert any(label.text() == "Status:" for label in section_labels)

    required_rules = (
        "QWidget#contentArea QLabel { color: #243247; }",
        "QLabel#contentSectionLabel { color: #314157; font-weight: 600; }",
        "QWidget#contentArea QTableView { border: none; background: white; color: #243247;",
        "QWidget#contentArea QTableView::item { color: #243247; }",
        "QWidget#contentArea QTableView::item:selected { background: #dff3f8; color: #172235; }",
    )
    for rule in required_rules:
        assert rule in APP_STYLE

    assert "QFrame#toolbar QLabel { color: #d8e1ee; }" in APP_STYLE


def test_left_sidebar_is_replaced_by_a_full_width_toolbar(window):
    widget, _ = window
    assert widget.findChild(QWidget, "sidebar") is None
    toolbar = widget.findChild(QWidget, "toolbar")
    assert toolbar is not None
    assert widget.choose_manual_csv_button.property("primary") is True

    company_wordmark = widget.findChild(QLabel, "companyWordmark")
    assert company_wordmark is not None
    assert company_wordmark.accessibleName() == "Trafigura company wordmark"
    assert len(widget._company_wordmark_frames) == 48
    assert all(not frame.isNull() for frame in widget._company_wordmark_frames)
    assert widget._company_wordmark_timer.isActive()
    first_frame_key = company_wordmark.pixmap().cacheKey()
    widget._advance_company_wordmark_frame()
    assert company_wordmark.pixmap().cacheKey() != first_frame_key

    toolbar_widgets = [
        toolbar.layout().itemAt(index).widget()
        for index in range(toolbar.layout().count())
        if toolbar.layout().itemAt(index).widget() is not None
    ]
    assert toolbar_widgets[0].text() == "PrismaFunction"
    assert toolbar_widgets[1] is company_wordmark
    assert toolbar_widgets[2].text() == "PRISMA Export processing"


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


def test_managed_prisma_browser_and_download_controls_are_completely_removed(window):
    # The revised specification removes the entire managed PRISMA browser/
    # download workflow: PrismaFunction never opens, controls, or downloads
    # anything from the PRISMA website. Only local CSV selection (which
    # immediately processes the file) and the Mapping table remain.
    widget, _ = window
    button_texts = {button.text() for button in widget.findChildren(QPushButton)}
    for removed_text in (
        "Open Prisma", "Close Prisma", "Choose Download Folder",
        "Validate Date Range", "Import PRISMA Export", "Open Result",
    ):
        assert removed_text not in button_texts
    for attribute in (
        "open_prisma_button", "close_prisma_button", "prisma_badge",
        "choose_download_directory_button", "download_directory_label",
        "start_date_edit", "end_date_edit", "validate_date_range_button",
        "date_range_label", "prisma_lifecycle", "_download_directory",
        "_date_range_selection", "process_button", "open_result_button",
        "import_date", "import_date_label", "_last_output_path",
    ):
        assert not hasattr(widget, attribute)
    for method_name in (
        "_open_prisma_session", "_close_prisma_session",
        "_poll_prisma_lifecycle", "_handle_download_event",
        "_select_download_directory", "_validate_date_range",
        "start_processing", "open_result",
    ):
        assert not hasattr(widget, method_name)


def test_mapping_panel_receives_positive_vertical_stretch(window):
    widget, _ = window
    content = widget.findChild(QWidget, "contentArea")
    main_layout = content.layout()
    mapping_panel = widget.mapping_table.parentWidget()
    index = main_layout.indexOf(mapping_panel)
    assert index >= 0
    assert main_layout.stretch(index) > 0


def test_mapping_section_label_shows_cumulative_row_count(window):
    widget, _ = window
    assert widget.mapping_section_label.text() == "Mapping · 0 rows"


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


def _write_published_output(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=prisma_output.OUTPUT_CSV_COLUMNS, delimiter=";")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _output_row(**overrides: str) -> dict[str, str]:
    row = {
        "Auction Date": "01-01-2025",
        "Exit Market": "",
        "Entry Market": "VGS Storage Hub",
        "Capacity Type": "entry",
        "Network Point Name": "VGS Storage Hub (4290)",
        "Product Type": "Day",
        "Flow Start": "02-01-2025 00:00",
        "Flow End": "03-01-2025 00:00",
        "Booked Capacity": "1000.0",
        "Flow Duration Hours": "24.0",
        "Tariff Price": "0.010000",
        "Premium Price": "0.005000",
    }
    row.update(overrides)
    return row


def _mock_successful_processing(monkeypatch, widget, rows: list[dict[str, str]]):
    output_path = widget._publication_directory / prisma_publication.PUBLISHED_OUTPUT_FILENAME
    _write_published_output(output_path, rows)
    workflow_result = app.PrismaWorkflowResult(
        1, len(rows), 0, 0, 0, 0, (), output_path,
        SourceUpdateStatus.APPLIED, "Processed.",
    )
    monkeypatch.setattr(
        app, "run_prisma_import_workflow", Mock(return_value=workflow_result)
    )
    return workflow_result


# Every accepted CSV selection below immediately triggers real background
# processing (see `app._select_manual_csv`/`_process_selected_csv`): none of
# these tests mock `run_prisma_import_workflow`. This is safe and
# deterministic even though most of the fixture rows here are not eligible
# for a confirmed EUR rate (no `State: Finished`, or a never-cached Finished
# auction) and so block publication: the background thread's outcome is only
# ever observed through the queued `processing_finished` Qt signal, which
# nothing here pumps via `QApplication.processEvents()`, so a blocked or
# failed processing attempt never reaches `_processing_failed()`/
# `QMessageBox.critical` during the test itself — only the synchronous
# mapping-preview state (set before the background thread starts) is
# asserted. `window`'s teardown joins any still-running thread before the
# next test starts, so nothing leaks across tests.


def test_manual_csv_dialog_starts_in_the_publication_directory(window, monkeypatch):
    widget, _ = window
    dialog = Mock(return_value=("", ""))
    monkeypatch.setattr(app.QFileDialog, "getOpenFileName", dialog)

    widget._select_manual_csv()

    assert dialog.call_args.args[2] == str(widget._publication_directory)


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
    _mock_successful_processing(monkeypatch, widget, [_output_row()])
    monkeypatch.setattr(
        app.QFileDialog, "getOpenFileName", Mock(return_value=(str(populated), "CSV"))
    )
    widget._select_manual_csv()
    _settle_processing(widget)
    assert widget.mapping_table_model.rowCount() == 1
    _settle_processing(widget)

    monkeypatch.setattr(app.QFileDialog, "getOpenFileName", Mock(return_value=("", "")))
    critical = Mock()
    monkeypatch.setattr(QMessageBox, "critical", critical)

    widget._select_manual_csv()

    assert widget._manual_csv_selection.current == populated.resolve()
    assert widget.manual_csv_label.text() == "PRISMA_Export.csv"
    critical.assert_not_called()
    assert widget.mapping_table_model.rowCount() == 1
    assert not widget.mapping_table.isHidden()


def test_choosing_a_valid_manual_csv_selects_it_and_starts_processing(
    window, monkeypatch, tmp_path
):
    widget, _ = window
    target = tmp_path / "PRISMA_Export.csv"
    _write_valid_prisma_export(target)
    monkeypatch.setattr(
        app.QFileDialog, "getOpenFileName", Mock(return_value=(str(target), "CSV"))
    )

    widget._select_manual_csv()

    assert widget._manual_csv_selection.current == target.resolve()
    assert widget.manual_csv_label.text() == "PRISMA_Export.csv"
    # Select CSV is the single user action: selecting a valid file
    # immediately starts processing (see `app._process_selected_csv`),
    # synchronously reflected before the background thread completes.
    assert widget.status.text() == "Importing PRISMA Export CSV..."
    assert widget._processing_active
    assert not widget.choose_manual_csv_button.isEnabled()


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
    _settle_processing(widget)

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
    _settle_processing(widget)

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


def test_selecting_a_valid_csv_populates_mapping_table_from_cumulative_output(
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
    _mock_successful_processing(monkeypatch, widget, [
        _output_row(
            **{
                "Entry Market": "VGS Storage Hub",
                "Network Point Name": "VGS Storage Hub (4290)",
                "Flow Start": "02-01-2025 00:00",
                "Tariff Price": "0.010000",
                "Premium Price": "0.005000",
            }
        ),
        _output_row(
            **{
                "Exit Market": "THE",
                "Entry Market": "",
                "Capacity Type": "exit",
                "Network Point Name": "VIP DK-THE (H646) (H646)",
                "Flow Start": "03-01-2025 00:00",
                "Tariff Price": "0.020000",
                "Premium Price": "0.006000",
            }
        ),
    ])

    widget._select_manual_csv()
    _settle_processing(widget)

    model = widget.mapping_table_model
    assert model.rowCount() == 2
    assert not widget.mapping_table.isHidden()
    assert widget.mapping_empty_label.isHidden()

    def cell(row, column):
        return model.data(model.index(row, column))

    assert (cell(0, 1), cell(0, 2), cell(0, 3), cell(0, 4), cell(0, 6), cell(0, 10), cell(0, 11)) == (
        "THE", "", "exit", "VIP DK-THE (H646) (H646)", "03-01-2025 00:00", "0.020000", "0.006000",
    )
    assert (cell(1, 1), cell(1, 2), cell(1, 3), cell(1, 4), cell(1, 6), cell(1, 10), cell(1, 11)) == (
        "", "VGS Storage Hub", "entry", "VGS Storage Hub (4290)", "02-01-2025 00:00", "0.010000", "0.005000",
    )


def test_mapping_display_preserves_cumulative_rows_after_later_slice(
    window, monkeypatch, tmp_path
):
    widget, _ = window
    target = tmp_path / "PRISMA_Export.csv"
    _write_prisma_export_with_rows(target, [{"Auction ID": "1"}])
    monkeypatch.setattr(
        app.QFileDialog, "getOpenFileName", Mock(return_value=(str(target), "CSV"))
    )
    _mock_successful_processing(monkeypatch, widget, [
        _output_row(**{"Exit Market": "Earlier", "Flow Start": "02-01-2025 00:00"}),
        _output_row(**{"Exit Market": "Later", "Flow Start": "04-01-2025 00:00"}),
    ])

    widget._select_manual_csv()
    _settle_processing(widget)

    model = widget.mapping_table_model
    assert model.rowCount() == 2
    assert [model.data(model.index(row, 1)) for row in range(model.rowCount())] == [
        "Later", "Earlier",
    ]


def test_mapping_display_shows_cumulative_rows_published_under_legacy_date_format(
    window, monkeypatch, tmp_path
):
    # Regression: the cumulative published file is never rewritten, so it may
    # already contain rows written before the Auction Date/Flow Start/Flow
    # End format correction (legacy `YYYY-MM-DD`/`YYYY-MM-DD HH:mm`)
    # alongside rows written after it (new `DD-MM-YYYY`/`DD-MM-YYYY HH:mm`).
    # Selecting a new CSV must still display every cumulative row instead of
    # failing to parse the legacy rows and clearing the whole Mapping table.
    widget, _ = window
    target = tmp_path / "PRISMA_Export.csv"
    _write_prisma_export_with_rows(target, [{"Auction ID": "1"}])
    _mock_successful_processing(monkeypatch, widget, [
        _output_row(**{
            "Exit Market": "Legacy",
            "Auction Date": "2025-01-01",
            "Flow Start": "2025-01-02 00:00",
            "Flow End": "2025-01-03 00:00",
        }),
        _output_row(**{
            "Exit Market": "New",
            "Auction Date": "05-01-2025",
            "Flow Start": "06-01-2025 00:00",
            "Flow End": "07-01-2025 00:00",
        }),
    ])
    monkeypatch.setattr(
        app.QFileDialog, "getOpenFileName", Mock(return_value=(str(target), "CSV"))
    )

    widget._select_manual_csv()
    _settle_processing(widget)

    model = widget.mapping_table_model
    assert model.rowCount() == 2
    assert not widget.mapping_table.isHidden()
    assert [model.data(model.index(row, 1)) for row in range(model.rowCount())] == [
        "New", "Legacy",
    ]


# --- Cumulative rate-resolution cache -------------------------------------
#
# Per the revised specification, PrismaFunction never opens, controls, or
# downloads anything from the PRISMA website. A Finished auction's rate can
# only ever become resolved through `storage.AuctionStorage`'s durable
# per-Auction-ID cache (see `_seed_resolved_rate`); a never-before-seen
# Finished auction fails closed instead (see the test above). A previously
# fixed resolution is reused deterministically and requires no PRISMA access
# at all — this is what makes the cumulative Mapping display work across
# sessions without any live transport.

def test_mapping_table_has_scrollbars_for_unbounded_rows(window):
    widget, _ = window
    assert widget.mapping_table.horizontalScrollBarPolicy() == Qt.ScrollBarAsNeeded
    assert widget.mapping_table.verticalScrollBarPolicy() == Qt.ScrollBarAsNeeded


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


def test_selecting_a_new_csv_preserves_cumulative_mapping_rows(window, monkeypatch, tmp_path):
    widget, _ = window
    first = tmp_path / "first.csv"
    _write_prisma_export_with_rows(first, [{"Auction ID": "1"}])
    _mock_successful_processing(monkeypatch, widget, [_output_row()])
    monkeypatch.setattr(
        app.QFileDialog, "getOpenFileName", Mock(return_value=(str(first), "CSV"))
    )
    widget._select_manual_csv()
    _settle_processing(widget)
    assert widget.mapping_table_model.rowCount() == 1

    second = tmp_path / "second.csv"
    _write_valid_prisma_export(second)
    monkeypatch.setattr(
        app.QFileDialog, "getOpenFileName", Mock(return_value=(str(second), "CSV"))
    )
    widget._select_manual_csv()

    _settle_processing(widget)

    assert widget.mapping_table_model.rowCount() == 1
    assert not widget.mapping_table.isHidden()


def test_mapping_refresh_failure_clears_table_shows_safe_error_and_skips_processing(
    window, monkeypatch, tmp_path
):
    widget, _ = window
    target = tmp_path / "PRISMA_Export.csv"
    _write_prisma_export_with_rows(target, [{"Auction ID": "1"}])
    _mock_successful_processing(monkeypatch, widget, [_output_row()])
    monkeypatch.setattr(
        app.QFileDialog, "getOpenFileName", Mock(return_value=(str(target), "CSV"))
    )
    widget._select_manual_csv()
    _settle_processing(widget)
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
    process = Mock(side_effect=AssertionError("processing must not start when the preview fails"))
    monkeypatch.setattr(app.PrismaMonitorApp, "_process_selected_csv", process)

    widget._select_manual_csv()

    assert widget.mapping_table_model.rowCount() == 0
    assert widget.mapping_table.isHidden()
    critical.assert_called_once()
    title, message = critical.call_args.args[1], critical.call_args.args[2]
    assert title == "Mapping"
    assert str(second) not in message
    assert message == "The selected PRISMA Export CSV could not be validated for Mapping."
    process.assert_not_called()


def test_rejected_manual_csv_replacement_clears_previous_mapping_rows(
    window, monkeypatch, tmp_path
):
    widget, _ = window
    populated = tmp_path / "PRISMA_Export.csv"
    _write_prisma_export_with_rows(populated, [{"Auction ID": "1"}])
    _mock_successful_processing(monkeypatch, widget, [_output_row()])
    monkeypatch.setattr(
        app.QFileDialog, "getOpenFileName", Mock(return_value=(str(populated), "CSV"))
    )
    widget._select_manual_csv()
    _settle_processing(widget)
    assert widget.mapping_table_model.rowCount() == 1
    _settle_processing(widget)

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


def test_processing_success_preserves_full_statistics(window, monkeypatch, tmp_path):
    widget, _ = window
    target = tmp_path / "PRISMA_Export.csv"
    _write_valid_prisma_export(target)
    workflow_result = app.PrismaWorkflowResult(
        4, 1, 2, 1, 0, 0, (), Path("result.xlsx"),
        SourceUpdateStatus.APPLIED, "accepted",
    )
    monkeypatch.setattr(
        app, "run_prisma_import_workflow", Mock(return_value=workflow_result)
    )
    monkeypatch.setattr(
        app.QFileDialog, "getOpenFileName", Mock(return_value=(str(target), "CSV"))
    )

    captured: list = []
    widget.signals.processing_finished.connect(captured.append)
    widget._select_manual_csv()
    deadline = time.monotonic() + 5.0
    while not captured and time.monotonic() < deadline:
        QApplication.processEvents()
        time.sleep(0.02)
    assert captured, "processing_finished was not received within the timeout"

    outcome = captured[0]
    assert outcome.result is workflow_result
    assert outcome.error is None
    assert widget.status.text() == (
        "accepted Source rows: 4; accepted: 4; filtered: 0; rejected: 0; "
        "deduplicated: 0; inserted: 1; updated: 2; unchanged: 1; "
        "audit issues: 0. Output: result.xlsx"
    )
    assert not widget._processing_active
    assert widget._active_processing_thread is None
    assert not widget._processing_threads
    assert widget.choose_manual_csv_button.isEnabled()

    assert widget.status_counter_labels["Source"].text() == "Source: 4"
    assert widget.status_counter_labels["Accepted"].text() == "Accepted: 4"
    assert widget.status_counter_labels["Filtered"].text() == "Filtered: 0"
    assert widget.status_counter_labels["Rejected"].text() == "Rejected: 0"
    assert widget.status_counter_labels["Duplicates"].text() == "Duplicates: 0"
    assert widget.status_counter_labels["Inserted"].text() == "Inserted: 1"
    assert widget.status_badge.text() == "Success"
    assert widget.status_badge.property("state") == "success"

    # The full status text stays in the collapsed Details panel until asked for.
    assert widget.status_details_panel.isHidden()
    widget.details_button.setChecked(True)
    assert not widget.status_details_panel.isHidden()
    assert widget.details_button.text() == "Hide details"

    widget._processing_finished(app.ProcessingOutcome(workflow_result, None, widget._processing_generation))
    assert widget.status.text().startswith("accepted Source rows: 4")


def test_import_processing_success_and_error_restore_controls(window, monkeypatch, tmp_path):
    widget, _ = window
    target = tmp_path / "PRISMA_Export.csv"
    _write_valid_prisma_export(target)
    monkeypatch.setattr(QMessageBox, "critical", Mock())
    monkeypatch.setattr(
        app.QFileDialog, "getOpenFileName", Mock(return_value=(str(target), "CSV"))
    )

    class FakeThread:
        def __init__(self, **kwargs): self.kwargs = kwargs
        def start(self): pass
        def is_alive(self): return False
        def join(self, timeout=None): pass

    monkeypatch.setattr(app.threading, "Thread", FakeThread)
    widget._select_manual_csv()
    assert widget._processing_active
    assert not widget.choose_manual_csv_button.isEnabled()
    assert "Importing" in widget.status.text()
    assert widget.status_badge.property("state") == "processing"

    widget._processing_failed("Unsupported CSV format.", None)
    assert not widget._processing_active
    assert widget.choose_manual_csv_button.isEnabled()
    assert "Unsupported CSV format" in widget.status.text()
    assert widget.status_badge.property("state") == "error"
    assert widget.status_badge.text() == "Error"


def test_status_badge_shows_warning_when_a_successful_import_has_filtered_or_rejected_rows(
    window, monkeypatch, tmp_path
):
    widget, _ = window
    target = tmp_path / "PRISMA_Export.csv"
    _write_valid_prisma_export(target)
    workflow_result = app.PrismaWorkflowResult(
        5, 1, 0, 0, 2, 1, (), Path("result.xlsx"),
        SourceUpdateStatus.APPLIED, "accepted",
    )
    monkeypatch.setattr(
        app, "run_prisma_import_workflow", Mock(return_value=workflow_result)
    )
    monkeypatch.setattr(
        app.QFileDialog, "getOpenFileName", Mock(return_value=(str(target), "CSV"))
    )

    captured: list = []
    widget.signals.processing_finished.connect(captured.append)
    widget._select_manual_csv()
    deadline = time.monotonic() + 5.0
    while not captured and time.monotonic() < deadline:
        QApplication.processEvents()
        time.sleep(0.02)
    assert captured, "processing_finished was not received within the timeout"

    assert widget.status_counter_labels["Filtered"].text() == "Filtered: 2"
    assert widget.status_counter_labels["Rejected"].text() == "Rejected: 1"
    assert widget.status_badge.text() == "Warning"
    assert widget.status_badge.property("state") == "warning"


def test_select_csv_is_ignored_while_processing_is_active(window, monkeypatch, tmp_path):
    widget, _ = window
    target = tmp_path / "PRISMA_Export.csv"
    _write_valid_prisma_export(target)
    dialog = Mock(return_value=(str(target), "CSV"))
    monkeypatch.setattr(app.QFileDialog, "getOpenFileName", dialog)
    widget._processing_active = True

    widget._select_manual_csv()

    dialog.assert_not_called()


def test_close_event_accepts_immediately_when_idle(window):
    widget, _ = window
    event = Mock()

    widget.closeEvent(event)

    event.accept.assert_called_once_with()
    event.ignore.assert_not_called()


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


def test_startup_shows_generic_error_when_the_publication_directory_is_unavailable(
    tmp_path, monkeypatch
):
    application = Mock()
    paths = app.RuntimePaths(
        root=tmp_path, database=tmp_path / "data/db.sqlite",
        result=tmp_path / "data/result/result.xlsx",
        state=tmp_path / "state/state.json", log=tmp_path / "logs/app.log",
    )
    monkeypatch.setattr(app.QApplication, "instance", Mock(return_value=application))
    monkeypatch.setattr(app, "runtime_paths", Mock(return_value=paths))
    monkeypatch.setattr(
        app, "initialize_runtime_logging", Mock(return_value=(Mock(), tmp_path / "logs/app.log"))
    )
    monkeypatch.setattr(app, "migrate_legacy_runtime_data", Mock())
    monkeypatch.setattr(
        app, "default_download_directory",
        Mock(side_effect=RuntimeError("The current user's Documents directory is unavailable.")),
    )
    message = Mock()
    monkeypatch.setattr(app.QMessageBox, "critical", message)

    assert app.main() == 1

    message.assert_called_once()
    assert "Documents directory is unavailable" in message.call_args.args[2]


# --- P.36.21/P.37 correction: the real, unmocked active processing call graph
#
# These tests never mock `run_prisma_import_workflow` itself: they drive the
# real `PrismaMonitorApp._select_manual_csv()` -> `_process_selected_csv()` ->
# `_process_worker()` -> `prisma_import_workflow.run_prisma_import_workflow()`
# -> `price_normalization.normalize_prices_for_output()` ->
# `prisma_publication.publish_cumulative_output()` call graph end-to-end —
# Select CSV is the single user action that immediately processes the
# selected file and merges it into cumulative persistent storage. Under
# P.37, an EUR-unit row resolves without any cache seeding at all (no
# PRISMA/ECB transport needed for EUR identity); a non-EUR row needs either
# `_block_live_ecb_access` (deterministic failure, no network) or
# `_seed_ecb_date_rate` (`storage.AuctionStorage`'s durable
# `(auction_date, currency)` cache, populated directly, exactly as it would
# be in production for a previously resolved pair).


def _select_csv_and_wait(widget, monkeypatch, csv_path, *, timeout_s: float = 10.0):
    """Drive `_select_manual_csv()` end-to-end and return the resulting
    `ProcessingOutcome`.

    `QSignalSpy(...).wait()` proved unreliable here for a *real*, unmocked
    `run_prisma_import_workflow()` call: the worker thread's
    `processing_finished.emit()` is a genuine cross-thread queued signal, and
    only an explicit `QApplication.processEvents()` poll loop was observed to
    reliably dispatch it in this offscreen test environment. A plain Python
    slot appended to `captured` avoids depending on `QSignalSpy`'s own
    (apparently unreliable, here) internal event-loop handling.
    """
    monkeypatch.setattr(QMessageBox, "critical", Mock())
    monkeypatch.setattr(
        app.QFileDialog, "getOpenFileName", Mock(return_value=(str(csv_path), "CSV"))
    )
    captured: list = []
    widget.signals.processing_finished.connect(captured.append)
    widget._select_manual_csv()
    deadline = time.monotonic() + timeout_s
    while not captured and time.monotonic() < deadline:
        QApplication.processEvents()
        time.sleep(0.02)
    assert captured, "processing_finished was not received within the timeout"
    return captured[0]


_RESOLVABLE_EXIT_ROW = {
    "Auction ID": "1", "Direction": "Exit",
    "Network Point Name Exit": "VGS Storage Hub (4290)", "Network Point Name Entry": "",
    "Network Point ID Exit": "EXIT-1", "Network Point ID Entry": "", "State": "Finished",
    "Regulated Tariff Exit TSO": "2", "Unit Regulated Exit Capacity Tariff": "cent/kWh/h/Runtime",
}
# `_MAPPING_ROW_DEFAULTS`'s "Start of Auction" (01.01.2025 09:00) parses to
# auction_date "2025-01-01" -- the P.37 cache key `_seed_ecb_date_rate`
# below must match.
_UNRESOLVED_ENTRY_AUCTION_DATE = "2025-01-01"
_UNRESOLVED_ENTRY_ROW = {
    "Auction ID": "1", "Direction": "Entry",
    "Network Point Name Entry": "VGS Storage Hub (4290)", "Network Point ID Entry": "ENTRY-1",
    "State": "Finished",
    # A non-EUR unit (GBP) so this row genuinely requires a P.37 ECB
    # resolution, unlike `_RESOLVABLE_EXIT_ROW`'s EUR unit (identity, no
    # transport needed at all).
    "Regulated Tariff Entry TSO": "1", "Unit Regulated Entry Capacity Tariff": "pence/kWh/h/Runtime",
}


def test_active_processing_path_reaches_strict_eur_normalization_and_publishes(
    window, monkeypatch, tmp_path,
):
    widget, _ = window
    # No cache seeding needed: `_RESOLVABLE_EXIT_ROW`'s unit is EUR, which
    # `ecb_rates.resolve_rate_to_eur` resolves to the identity rate with no
    # transport at all under P.37.
    csv_path = tmp_path / "Auction_overview.csv"
    _write_prisma_export_with_rows(csv_path, [_RESOLVABLE_EXIT_ROW])

    outcome = _select_csv_and_wait(widget, monkeypatch, csv_path)

    assert outcome.error is None
    assert outcome.result is not None

    # Merged into cumulative persistent storage and published into the
    # approved Documents-directory default (`P.36.3`), never `%LOCALAPPDATA%`.
    published = widget._publication_directory / prisma_publication.PUBLISHED_OUTPUT_FILENAME
    assert published.exists()
    with published.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.reader(handle, delimiter=";"))
    header, record = rows[0], rows[1]
    assert tuple(header) == prisma_output.OUTPUT_CSV_COLUMNS
    # 2 cent/kWh/h/Runtime -> 20 EUR/MWh/h source price; VGS Storage Hub's
    # EXIT-side evidence is EUR, so the identity rate (1) applies unchanged.
    assert record[header.index("Tariff Price")] == "20.000000"


def test_unresolved_ecb_rate_produces_no_output_and_no_ui_success(window, monkeypatch, tmp_path):
    widget, _ = window
    csv_path = tmp_path / "Auction_overview.csv"
    # `_UNRESOLVED_ENTRY_ROW`'s GBP unit was never previously resolved, so
    # there is no cached rate, and `_block_live_ecb_access` makes the live
    # ECB lookup fail deterministically without real network access.
    _write_prisma_export_with_rows(csv_path, [_UNRESOLVED_ENTRY_ROW])
    _block_live_ecb_access(monkeypatch)

    outcome = _select_csv_and_wait(widget, monkeypatch, csv_path)

    assert outcome.result is None
    assert outcome.error is not None
    assert "EUR" in outcome.error
    assert not (widget._publication_directory / prisma_publication.PUBLISHED_OUTPUT_FILENAME).exists()
    assert not widget._processing_active
    assert widget.choose_manual_csv_button.isEnabled()


def test_mixed_batch_publishes_nothing_through_the_real_app_workflow(window, monkeypatch, tmp_path):
    widget, _ = window
    # Auction "1" is EUR (resolves without any transport); auction "2" is
    # GBP and was never resolved, with live ECB access blocked deterministically.
    csv_path = tmp_path / "Auction_overview.csv"
    _write_prisma_export_with_rows(csv_path, [
        _RESOLVABLE_EXIT_ROW,
        {**_UNRESOLVED_ENTRY_ROW, "Auction ID": "2", "Network Point ID Entry": "ENTRY-2"},
    ])
    _block_live_ecb_access(monkeypatch)

    outcome = _select_csv_and_wait(widget, monkeypatch, csv_path)

    assert outcome.result is None
    assert outcome.error is not None
    assert not (widget._publication_directory / prisma_publication.PUBLISHED_OUTPUT_FILENAME).exists()


def test_blocked_processing_does_not_finalize_source_operation_as_accepted(window, monkeypatch, tmp_path):
    widget, _ = window
    csv_path = tmp_path / "Auction_overview.csv"
    _write_prisma_export_with_rows(csv_path, [_UNRESOLVED_ENTRY_ROW])
    _block_live_ecb_access(monkeypatch)

    outcome = _select_csv_and_wait(widget, monkeypatch, csv_path)
    assert outcome.result is None

    storage = AuctionStorage(widget._runtime_paths.database)
    assert all(row["status"] != "accepted" for row in storage.operations())


def test_retry_after_an_ecb_rate_becomes_available_succeeds(window, monkeypatch, tmp_path):
    widget, _ = window
    csv_path = tmp_path / "Auction_overview.csv"
    _write_prisma_export_with_rows(csv_path, [_UNRESOLVED_ENTRY_ROW])

    # First selection: this GBP-unit row has never been resolved before, and
    # live ECB access is blocked deterministically, so there is no rate.
    _block_live_ecb_access(monkeypatch)
    first = _select_csv_and_wait(widget, monkeypatch, csv_path)
    assert first.result is None
    assert not (widget._publication_directory / prisma_publication.PUBLISHED_OUTPUT_FILENAME).exists()

    # Second selection of the same source: the rate has since become
    # available (e.g. resolved separately and cached).
    _seed_ecb_date_rate(widget, _UNRESOLVED_ENTRY_AUCTION_DATE, "GBP", rate_to_eur="0.5")
    second = _select_csv_and_wait(widget, monkeypatch, csv_path)
    assert second.result is not None
    published = widget._publication_directory / prisma_publication.PUBLISHED_OUTPUT_FILENAME
    assert published.exists()


def test_legacy_excel_export_is_never_invoked_by_the_active_workflow(window, monkeypatch, tmp_path):
    widget, _ = window
    monkeypatch.setattr(
        AuctionStorage, "export_excel",
        lambda *_a, **_k: pytest.fail(
            "The dormant legacy Excel pipeline must not be invoked by the active workflow."
        ),
    )
    csv_path = tmp_path / "Auction_overview.csv"
    _write_prisma_export_with_rows(csv_path, [_RESOLVABLE_EXIT_ROW])

    outcome = _select_csv_and_wait(widget, monkeypatch, csv_path)
    assert outcome.result is not None


def test_legacy_published_csv_is_never_touched_by_the_active_workflow(window, monkeypatch, tmp_path):
    widget, _ = window
    legacy_path = (
        widget._publication_directory / prisma_publication.LEGACY_PUBLISHED_OUTPUT_FILENAME
    )
    legacy_path.parent.mkdir(parents=True, exist_ok=True)
    legacy_content = b"pre-P.36.21 rows; unconverted; never proven EUR\n"
    legacy_path.write_bytes(legacy_content)
    csv_path = tmp_path / "Auction_overview.csv"
    _write_prisma_export_with_rows(csv_path, [_RESOLVABLE_EXIT_ROW])

    outcome = _select_csv_and_wait(widget, monkeypatch, csv_path)

    assert outcome.result is not None
    assert legacy_path.read_bytes() == legacy_content
    published = widget._publication_directory / prisma_publication.PUBLISHED_OUTPUT_FILENAME
    assert published != legacy_path
    assert published.exists()


def test_reselecting_the_same_csv_does_not_duplicate_cumulative_rows(window, monkeypatch, tmp_path):
    # "merge it into cumulative persistent storage without duplicates":
    # selecting and processing the exact same accepted source a second time
    # must be an idempotent exact retry, never a second set of rows.
    widget, _ = window
    csv_path = tmp_path / "Auction_overview.csv"
    _write_prisma_export_with_rows(csv_path, [_RESOLVABLE_EXIT_ROW])

    first = _select_csv_and_wait(widget, monkeypatch, csv_path)
    assert first.result is not None
    published = widget._publication_directory / prisma_publication.PUBLISHED_OUTPUT_FILENAME
    first_content = published.read_bytes()

    second = _select_csv_and_wait(widget, monkeypatch, csv_path)

    assert second.result is not None
    assert published.read_bytes() == first_content
    storage = AuctionStorage(widget._runtime_paths.database)
    accepted = [row for row in storage.operations() if row["status"] == "accepted"]
    assert len(accepted) == 1


def test_active_modules_are_reachable_from_apps_own_import_graph():
    """This file already imports `app` at module load, so if `app.py` ->
    `prisma_import_workflow.py` -> `prisma_publication.py`/
    `price_normalization.py` (which in turn imports `prisma_output.py`) is a
    real, live import chain, every one of these names is already in
    `sys.modules` by the time this test runs, proving the import graph
    starting at `app.py` really reaches each of them."""
    import sys

    for name in ("prisma_import_workflow", "prisma_publication", "price_normalization", "prisma_output"):
        assert f"prisma_function.{name}" in sys.modules, f"{name} is not reachable from app.py's import graph"
    assert app.run_prisma_import_workflow.__module__ == "prisma_function.prisma_import_workflow"
