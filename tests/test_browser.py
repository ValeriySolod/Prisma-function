import queue
import sys
import threading
from types import SimpleNamespace

import pytest

from browser import BrowserController, BrowserState


class SignallingQueue:
    def __init__(self):
        self._queue = queue.SimpleQueue()
        self.ready = threading.Event()

    def put(self, item):
        self._queue.put(item)
        self.ready.set()

    def get_nowait(self):
        return self._queue.get_nowait()


class FakePage:
    def __init__(self, navigation_error=None):
        self.navigation_error = navigation_error

    def goto(self, *args, **kwargs):
        if self.navigation_error:
            raise self.navigation_error


class FakeBrowser:
    def __init__(self, page=None):
        self.page = page or FakePage()
        self.closed = threading.Event()

    def new_page(self):
        return self.page

    def close(self):
        self.closed.set()


class FakePlaywright:
    def __init__(self, launch):
        self.chromium = SimpleNamespace(launch=launch)
        self.stopped = threading.Event()

    def stop(self):
        self.stopped.set()


def install_fake_playwright(monkeypatch, launch):
    playwright = FakePlaywright(launch)
    api = SimpleNamespace(
        sync_playwright=lambda: SimpleNamespace(start=lambda: playwright)
    )
    monkeypatch.setitem(sys.modules, "playwright.sync_api", api)
    return playwright


def join_worker(controller):
    controller._thread.join(timeout=2)
    assert not controller._thread.is_alive()


@pytest.mark.parametrize(
    ("browser_name", "expected_channel"),
    [("Chrome", "chrome"), ("Edge", "msedge")],
)
def test_successful_start_uses_expected_channel(
    monkeypatch, browser_name, expected_channel
):
    controller = BrowserController()
    controller._results = SignallingQueue()
    browser = FakeBrowser()
    launches = []
    playwright = install_fake_playwright(
        monkeypatch,
        lambda **kwargs: launches.append(kwargs) or browser,
    )

    generation = controller.open(browser_name)
    assert controller._results.ready.wait(2)

    assert controller.state is BrowserState.RUNNING
    assert controller.is_running
    result = controller.get_launch_results()[0]
    assert result.generation == generation
    assert result.success
    assert launches[0]["channel"] == expected_channel

    controller.stop()
    assert controller.state is BrowserState.STOPPING
    join_worker(controller)
    assert controller.state is BrowserState.IDLE
    assert not controller.is_running
    assert browser.closed.is_set()
    assert playwright.stopped.is_set()


def test_browser_creation_error_reports_failure_and_cleans_resources(monkeypatch):
    controller = BrowserController()

    def fail_launch(**kwargs):
        raise RuntimeError("driver missing")

    playwright = install_fake_playwright(monkeypatch, fail_launch)
    controller.open("Chrome")
    join_worker(controller)

    result = controller.get_launch_results()[0]
    assert not result.success
    assert result.error == "driver missing"
    assert controller.last_error == "driver missing"
    assert controller.state is BrowserState.IDLE
    assert not controller.is_running
    assert playwright.stopped.is_set()


def test_navigation_error_reports_failure_and_closes_all_resources(monkeypatch):
    controller = BrowserController()
    browser = FakeBrowser(FakePage(RuntimeError("navigation failed")))
    playwright = install_fake_playwright(monkeypatch, lambda **kwargs: browser)

    controller.open("Edge")
    join_worker(controller)

    result = controller.get_launch_results()[0]
    assert not result.success
    assert result.error == "navigation failed"
    assert browser.closed.is_set()
    assert playwright.stopped.is_set()
    assert controller.state is BrowserState.IDLE


def test_open_twice_is_rejected_while_starting(monkeypatch):
    controller = BrowserController()
    launch_entered = threading.Event()
    release_launch = threading.Event()

    def blocked_launch(**kwargs):
        launch_entered.set()
        assert release_launch.wait(2)
        return FakeBrowser()

    install_fake_playwright(monkeypatch, blocked_launch)
    controller.open("Chrome")
    assert launch_entered.wait(2)
    assert controller.state is BrowserState.STARTING

    with pytest.raises(RuntimeError):
        controller.open("Edge")

    controller.stop()
    release_launch.set()
    join_worker(controller)


def test_stop_during_startup_suppresses_success_and_cleans_resources(monkeypatch):
    controller = BrowserController()
    launch_entered = threading.Event()
    release_launch = threading.Event()
    browser = FakeBrowser()

    def blocked_launch(**kwargs):
        launch_entered.set()
        assert release_launch.wait(2)
        return browser

    playwright = install_fake_playwright(monkeypatch, blocked_launch)
    controller.open("Chrome")
    assert launch_entered.wait(2)

    controller.stop()
    assert controller.state is BrowserState.STOPPING
    release_launch.set()
    join_worker(controller)

    assert controller.get_launch_results() == []
    assert controller.state is BrowserState.IDLE
    assert not controller.is_running
    assert browser.closed.is_set()
    assert playwright.stopped.is_set()
