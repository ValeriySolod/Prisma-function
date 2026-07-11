from types import SimpleNamespace
from unittest.mock import Mock, call

import app
from auction_csv import AuctionCsvRecord
from browser import LaunchResult


def test_key_ui_labels_and_initial_status_are_english():
    source = app.Path(app.__file__).read_text(encoding="utf-8")
    expected_texts = (
        'value="Ready"',
        'text="Browser:"',
        'text="Open PRISMA"',
        'text="CSV file:"',
        'text="Select"',
        'text="Process CSV"',
        'text="Open Result"',
        'text="Stop"',
        'text="Status:"',
        'text="Close Application"',
    )

    for expected in expected_texts:
        assert expected in source


class FakeTree:
    def __init__(self):
        self.rows = []

    def get_children(self):
        return tuple(range(len(self.rows)))

    def delete(self, *items):
        self.rows = []

    def insert(self, parent, index, values):
        self.rows.append(values)


def record(auction_id="A1", enabled=True, item_name="Item"):
    return AuctionCsvRecord(
        auction_id, "https://example.com", "L1", item_name,
        "Open", "Scheduled", 30, enabled,
    )


def make_app(browser):
    instance = app.PrismaMonitorApp.__new__(app.PrismaMonitorApp)
    instance.browser = browser
    instance.browser_name = SimpleNamespace(get=lambda: "Chrome")
    instance.csv_path = Mock()
    instance.status = Mock()
    instance.csv_table = FakeTree()
    instance.open_button = Mock()
    instance.after = Mock()
    instance.destroy = Mock()
    instance._is_closing = False
    instance._active_browser_launch = None
    return instance


def test_cancel_csv_selection_keeps_current_state(monkeypatch):
    instance = make_app(Mock())
    askopenfilename = Mock(return_value="")
    monkeypatch.setattr(app.filedialog, "askopenfilename", askopenfilename)
    load = Mock()
    monkeypatch.setattr(app, "load_auction_csv", load)

    instance.select_csv()

    askopenfilename.assert_called_once_with(
        title="Select Auction_overview.csv",
        filetypes=[("CSV files", "*.csv")],
    )
    load.assert_not_called()
    instance.csv_path.set.assert_not_called()
    instance.status.set.assert_not_called()


def test_valid_csv_updates_path_and_shows_record_count(monkeypatch):
    instance = make_app(Mock())
    selected = "C:/data/Auction_overview.csv"
    monkeypatch.setattr(app.filedialog, "askopenfilename", Mock(return_value=selected))
    monkeypatch.setattr(app, "load_auction_csv", Mock(return_value=[record(), record("A2")]))

    instance.select_csv()

    instance.csv_path.set.assert_called_once_with(selected)
    instance.status.set.assert_called_once_with(
        "Loaded Auction_overview.csv: 2 records"
    )


def test_invalid_csv_shows_error_and_preserves_previous_selection(monkeypatch):
    instance = make_app(Mock())
    monkeypatch.setattr(app.filedialog, "askopenfilename", Mock(return_value="C:/data/bad.csv"))
    monkeypatch.setattr(app, "load_auction_csv", Mock(side_effect=app.CsvValidationError("bad data")))
    showerror = Mock()
    monkeypatch.setattr(app.messagebox, "showerror", showerror)

    instance.select_csv()

    showerror.assert_called_once_with("CSV Error", "bad data")
    instance.csv_path.set.assert_not_called()
    instance.status.set.assert_not_called()


def test_csv_selection_can_be_retried_after_error(monkeypatch):
    instance = make_app(Mock())
    monkeypatch.setattr(app.filedialog, "askopenfilename", Mock(side_effect=["bad.csv", "good.csv"]))
    monkeypatch.setattr(app, "load_auction_csv", Mock(side_effect=[app.CsvValidationError("bad"), [record()]]))
    monkeypatch.setattr(app.messagebox, "showerror", Mock())

    instance.select_csv()
    instance.select_csv()

    instance.csv_path.set.assert_called_once_with("good.csv")
    assert "1" in instance.status.set.call_args.args[0]


def test_unexpected_csv_error_uses_english_fallback(monkeypatch):
    instance = make_app(Mock())
    monkeypatch.setattr(app.filedialog, "askopenfilename", Mock(return_value="bad.csv"))
    monkeypatch.setattr(app, "load_auction_csv", Mock(side_effect=RuntimeError("disk failure")))
    showerror = Mock()
    monkeypatch.setattr(app.messagebox, "showerror", showerror)

    instance.select_csv()

    showerror.assert_called_once_with(
        "CSV Error", "Failed to load CSV: disk failure"
    )
    instance.csv_path.set.assert_not_called()
    instance.status.set.assert_not_called()


def test_display_records_in_order_and_formats_enabled():
    instance = make_app(Mock())
    records = [record("A1", True, "First"), record("A2", False, "Second")]

    instance._display_csv_records(records)

    assert instance.csv_table.rows == [
        ("A1", "L1", "First", "Open", "Scheduled", 30, "Yes"),
        ("A2", "L1", "Second", "Open", "Scheduled", 30, "No"),
    ]


def test_second_successful_load_replaces_existing_rows(monkeypatch):
    instance = make_app(Mock())
    monkeypatch.setattr(app.filedialog, "askopenfilename", Mock(side_effect=["one.csv", "two.csv"]))
    monkeypatch.setattr(app, "load_auction_csv", Mock(side_effect=[[record("A1")], [record("A2", False)]]))

    instance.select_csv()
    instance.select_csv()

    assert [row[0] for row in instance.csv_table.rows] == ["A2"]


def test_cancel_and_load_errors_preserve_complete_valid_state(monkeypatch):
    instance = make_app(Mock())
    instance.csv_table.rows = [("existing",)]
    monkeypatch.setattr(app.filedialog, "askopenfilename", Mock(side_effect=["", "bad.csv", "broken.csv"]))
    monkeypatch.setattr(
        app, "load_auction_csv",
        Mock(side_effect=[app.CsvValidationError("bad"), RuntimeError("disk")]),
    )
    monkeypatch.setattr(app.messagebox, "showerror", Mock())

    instance.select_csv()
    instance.select_csv()
    instance.select_csv()

    assert instance.csv_table.rows == [("existing",)]
    instance.csv_path.set.assert_not_called()
    instance.status.set.assert_not_called()


def test_ui_creates_table_with_expected_columns(monkeypatch):
    created = {}

    class Widget:
        def __init__(self, *args, **kwargs):
            self.kwargs = kwargs
        def grid(self, *args, **kwargs): pass
        def pack(self, *args, **kwargs): pass
        def columnconfigure(self, *args, **kwargs): pass
        def rowconfigure(self, *args, **kwargs): pass
        def heading(self, *args, **kwargs): pass
        def column(self, *args, **kwargs): pass
        def configure(self, *args, **kwargs): pass
        def yview(self, *args, **kwargs): pass
        def set(self, *args, **kwargs): pass

    class Tree(Widget):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            created["tree"] = self

    for name in ("Frame", "Label", "Combobox", "Button", "Entry", "Separator", "Scrollbar"):
        monkeypatch.setattr(app.ttk, name, Widget)
    monkeypatch.setattr(app.ttk, "Treeview", Tree)
    instance = make_app(Mock())
    instance.protocol = Mock()

    instance._build_ui()

    assert created["tree"].kwargs["columns"] == (
        "auction_id", "lot_number", "item_name", "expected_status",
        "last_known_status", "check_interval_seconds", "enabled",
    )


def test_success_result_is_handled_only_when_main_loop_polls():
    browser = Mock()
    browser.open.return_value = 7
    browser.get_launch_results.return_value = [LaunchResult(7, True)]
    instance = make_app(browser)

    instance.open_prisma()

    assert instance.status.set.call_args_list == [call("Starting PRISMA in Chrome...")]
    assert instance.open_button.config.call_args == call(state="disabled")
    instance._poll_browser_launch()
    assert instance.status.set.call_args == call("PRISMA opened in Chrome")
    assert instance.open_button.config.call_args == call(state="normal")


def test_failure_restores_button_without_false_success(monkeypatch):
    browser = Mock()
    browser.open.return_value = 8
    browser.get_launch_results.return_value = [
        LaunchResult(8, False, "driver missing")
    ]
    instance = make_app(browser)
    showerror = Mock()
    monkeypatch.setattr(app.messagebox, "showerror", showerror)

    instance.open_prisma()
    instance._poll_browser_launch()

    statuses = [item.args[0] for item in instance.status.set.call_args_list]
    assert "PRISMA opened in Chrome" not in statuses
    assert statuses[-1] == "Failed to open the browser"
    assert instance.open_button.config.call_args == call(state="normal")
    assert "driver missing" in showerror.call_args.args[1]


def test_ui_allows_retry_after_failed_launch(monkeypatch):
    browser = Mock()
    browser.open.side_effect = [11, 12]
    browser.get_launch_results.side_effect = [
        [LaunchResult(11, False, "driver missing")],
        [LaunchResult(12, True)],
    ]
    instance = make_app(browser)
    monkeypatch.setattr(app.messagebox, "showerror", Mock())

    instance.open_prisma()
    instance._poll_browser_launch()
    assert instance._active_browser_launch is None
    assert instance.open_button.config.call_args == call(state="normal")

    instance.open_prisma()
    assert instance._active_browser_launch == 12
    assert instance.open_button.config.call_args == call(state="disabled")
    instance._poll_browser_launch()

    assert instance._active_browser_launch is None
    final_status = instance.status.set.call_args.args[0]
    assert final_status.startswith("PRISMA ")
    assert final_status.endswith(" Chrome")
    assert browser.open.call_count == 2


def test_synchronous_open_error_restores_ui_and_allows_retry(monkeypatch):
    browser = Mock()
    browser.open.side_effect = [RuntimeError("sync launch failed"), 14]
    instance = make_app(browser)
    showerror = Mock()
    monkeypatch.setattr(app.messagebox, "showerror", showerror)

    instance.open_prisma()

    assert instance._active_browser_launch is None
    assert instance.open_button.config.call_args == call(state="normal")
    assert "sync launch failed" in showerror.call_args.args[1]
    assert instance.status.set.call_count == 2
    instance.after.assert_not_called()

    instance.open_prisma()

    assert browser.open.call_count == 2
    assert instance._active_browser_launch == 14
    assert instance.open_button.config.call_args == call(state="disabled")
    instance.after.assert_called_once_with(50, instance._poll_browser_launch)


def test_stale_result_is_ignored_and_polling_continues():
    browser = Mock()
    browser.open.return_value = 9
    browser.get_launch_results.return_value = [LaunchResult(8, True)]
    instance = make_app(browser)

    instance.open_prisma()
    instance._poll_browser_launch()

    statuses = [item.args[0] for item in instance.status.set.call_args_list]
    assert "PRISMA opened in Chrome" not in statuses
    assert instance._active_browser_launch == 9
    assert instance.after.call_count == 2


def test_result_after_shutdown_is_ignored_without_tk_calls():
    browser = Mock()
    instance = make_app(browser)
    instance._active_browser_launch = 10

    instance.close_app()
    instance._poll_browser_launch()

    browser.stop.assert_called_once()
    browser.get_launch_results.assert_not_called()
    instance.open_button.config.assert_not_called()
    instance.status.set.assert_not_called()
    instance.destroy.assert_called_once()
