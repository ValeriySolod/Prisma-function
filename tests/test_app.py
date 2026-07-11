from types import SimpleNamespace
from unittest.mock import Mock, call

import app
from browser import LaunchResult


def make_app(browser):
    instance = app.PrismaMonitorApp.__new__(app.PrismaMonitorApp)
    instance.browser = browser
    instance.browser_name = SimpleNamespace(get=lambda: "Chrome")
    instance.status = Mock()
    instance.open_button = Mock()
    instance.after = Mock()
    instance.destroy = Mock()
    instance._is_closing = False
    instance._active_browser_launch = None
    return instance


def test_success_result_is_handled_only_when_main_loop_polls():
    browser = Mock()
    browser.open.return_value = 7
    browser.get_launch_results.return_value = [LaunchResult(7, True)]
    instance = make_app(browser)

    instance.open_prisma()

    assert instance.status.set.call_args_list == [call("Запуск PRISMA у Chrome...")]
    assert instance.open_button.config.call_args == call(state="disabled")
    instance._poll_browser_launch()
    assert instance.status.set.call_args == call("PRISMA відкрито у Chrome")
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
    assert "PRISMA відкрито у Chrome" not in statuses
    assert statuses[-1] == "Не вдалося відкрити браузер"
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


def test_stale_result_is_ignored_and_polling_continues():
    browser = Mock()
    browser.open.return_value = 9
    browser.get_launch_results.return_value = [LaunchResult(8, True)]
    instance = make_app(browser)

    instance.open_prisma()
    instance._poll_browser_launch()

    statuses = [item.args[0] for item in instance.status.set.call_args_list]
    assert "PRISMA відкрито у Chrome" not in statuses
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
