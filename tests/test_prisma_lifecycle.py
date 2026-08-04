import sys
import threading
import time
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from browser import DefaultBrowserDetector, PRISMA_AUCTIONS_URL
from date_range_selection import DateRange
from prisma_download import (
    PrismaAuthenticationRequiredError,
    PrismaDownloadOrchestrator,
)
from prisma_lifecycle import (
    PRISMA_OFFICIAL_URL,
    PrismaLifecycleController,
    PrismaLifecycleEvent,
    PrismaLifecycleState,
)


@pytest.fixture(autouse=True)
def default_browser(monkeypatch):
    monkeypatch.setattr(
        DefaultBrowserDetector, "detect_executable",
        lambda self: Path("C:/Browsers/default.exe"),
    )


class EventEmitter:
    def __init__(self):
        self.listeners = {}
        self.removed_listeners: list[tuple[str, object]] = []

    def on(self, event, callback):
        self.listeners.setdefault(event, []).append(callback)

    def remove_listener(self, event, callback):
        self.removed_listeners.append((event, callback))
        listeners = self.listeners.get(event)
        if listeners and callback in listeners:
            listeners.remove(callback)

    def emit(self, event):
        for callback in self.listeners.get(event, [])[:]:
            callback()


class FakeContext(EventEmitter):
    """The BrowserContext owning a FakePage; only "close" is ever used."""

    def __init__(self):
        super().__init__()
        self.pages: list["FakePage"] = []


class FakeCdpSession:
    """A browser-level CDP session, modeling `Browser.new_browser_cdp_session()`.

    Only the narrow surface `prisma_lifecycle.py` actually uses is modeled:
    `send("Target.getTargets")`, `on("Target.targetCreated"/"targetDestroyed"/
    "targetInfoChanged", ...)`, and test-only helpers to mutate the tracked
    target set and fire the corresponding CDP event, mirroring real Chrome
    DevTools Protocol Target-domain notifications.
    """

    def __init__(self):
        self.listeners: dict[str, list] = {}
        self.sent: list[tuple[str, dict | None]] = []
        self._targets: dict[str, dict] = {}
        self.page_target_id: str | None = None

    def on(self, event, callback):
        self.listeners.setdefault(event, []).append(callback)

    def send(self, method, params=None):
        self.sent.append((method, params))
        if method == "Target.getTargets":
            return {
                "targetInfos": [
                    {"targetId": target_id, **info}
                    for target_id, info in self._targets.items()
                ]
            }
        return {}

    def set_page_target(self, target_id=None):
        target_id = target_id or f"page-target-{len(self._targets) + 1}"
        self._targets[target_id] = {"type": "page", "attached": True}
        return target_id

    def destroy_target(self, target_id):
        self._targets.pop(target_id, None)
        for callback in self.listeners.get("Target.targetDestroyed", [])[:]:
            callback({"targetId": target_id})

    def create_target(self, target_id, target_type="page"):
        info = {"type": target_type, "attached": True}
        self._targets[target_id] = info
        for callback in self.listeners.get("Target.targetCreated", [])[:]:
            callback({"targetId": target_id, "targetInfo": dict(info)})


class FakePage(EventEmitter):
    """Raises on any navigation-adjacent call other than goto/lifecycle hooks,
    proving no page automation beyond the approved navigation and the owned
    close-detection signals (`context`, `on("close", ...)`, `is_closed()`).
    """

    def __init__(self, navigation_error=None, context=None):
        super().__init__()
        self.navigation_error = navigation_error
        self.goto_calls = []
        self.context = context or FakeContext()
        self.context.pages.append(self)
        self._closed = False

    def goto(self, url, **kwargs):
        self.goto_calls.append((url, kwargs))
        if self.navigation_error:
            raise self.navigation_error

    def is_closed(self):
        return self._closed

    def close_silently(self):
        """Flips the owned page closed without emitting "close".

        Models a real manual window closure whose Playwright "close" event
        is not delivered, so detection must fall back to `is_closed()`
        polling rather than depending on the event alone.
        """
        self._closed = True

    def simulate_manual_close(self):
        self._closed = True
        self.emit("close")

    def __getattr__(self, name):
        raise AssertionError(f"unexpected automated page interaction: {name}")


class FakeBrowser(EventEmitter):
    def __init__(
        self, page=None, *, new_page_error=None, block_close=None,
        on_error=None, close_error=None, cdp_session_error=None,
        cdp_initial_targets=None,
    ):
        super().__init__()
        self.page = page or FakePage()
        self.new_page_error = new_page_error
        self.new_page_calls = 0
        self.new_page_options = []
        self.closed = threading.Event()
        self._block_close: threading.Event | None = block_close
        self._on_error = on_error
        self._close_error = close_error
        self._connected = True
        self._cdp_session_error = cdp_session_error
        self._cdp_initial_targets = cdp_initial_targets
        self._contexts: list[FakeContext] = []
        self.cdp_session: FakeCdpSession | None = None

    def on(self, event, callback):
        if self._on_error is not None:
            raise self._on_error
        super().on(event, callback)

    def is_connected(self):
        return self._connected

    def simulate_manual_disconnect(self):
        self._connected = False

    def new_page(self, **kwargs):
        self.new_page_calls += 1
        self.new_page_options.append(kwargs)
        if self.new_page_error:
            raise self.new_page_error
        if self.page.context not in self._contexts:
            self._contexts.append(self.page.context)
        return self.page

    @property
    def contexts(self) -> list[FakeContext]:
        return list(self._contexts)

    def new_browser_cdp_session(self) -> FakeCdpSession:
        if self._cdp_session_error is not None:
            raise self._cdp_session_error
        session = FakeCdpSession()
        if self._cdp_initial_targets is not None:
            session._targets.update(self._cdp_initial_targets)
        elif self.new_page_calls:
            session.page_target_id = session.set_page_target()
        self.cdp_session = session
        return session

    def close(self):
        if self._block_close is not None:
            assert self._block_close.wait(2)
        if self._close_error is not None:
            raise self._close_error
        self.closed.set()


class FakePlaywright:
    def __init__(self, launch, *, stop_error=None):
        self.chromium = SimpleNamespace(launch=launch)
        self.stopped = threading.Event()
        self._stop_error = stop_error

    def stop(self):
        if self._stop_error is not None:
            raise self._stop_error
        self.stopped.set()


class SignallingQueue:
    """Wraps SimpleQueue with a ready event so tests avoid polling sleeps."""

    def __init__(self):
        self._queue = __import__("queue").SimpleQueue()
        self.ready = threading.Event()

    def put(self, item):
        self._queue.put(item)
        self.ready.set()

    def get_nowait(self):
        return self._queue.get_nowait()


def install_fake_playwright(monkeypatch, launch, *, stop_error=None):
    playwright = FakePlaywright(launch, stop_error=stop_error)
    api = SimpleNamespace(
        sync_playwright=lambda: SimpleNamespace(start=lambda: playwright)
    )
    monkeypatch.setitem(sys.modules, "playwright.sync_api", api)
    return playwright


def join_worker(controller: PrismaLifecycleController) -> None:
    controller._thread.join(timeout=2)
    assert not controller._thread.is_alive()


def test_approved_url_boundary_matches_the_customer_decision():
    assert PRISMA_OFFICIAL_URL == (
        "https://app.prisma-capacity.eu/reporting/auctions/"
        "short-and-long-term-auctions"
    )
    assert PRISMA_OFFICIAL_URL == PRISMA_AUCTIONS_URL


def test_successful_open_navigates_only_to_the_approved_url(monkeypatch):
    browser = FakeBrowser()
    controller = PrismaLifecycleController()
    controller._events = SignallingQueue()
    install_fake_playwright(monkeypatch, lambda **kwargs: browser)

    generation = controller.open()
    assert controller._events.ready.wait(2)

    assert controller.state is PrismaLifecycleState.OPEN
    assert controller.is_open
    events = controller.get_events()
    assert events == [PrismaLifecycleEvent(generation, True, kind="open")]
    assert browser.page.goto_calls == [
        (PRISMA_OFFICIAL_URL, {"wait_until": "domcontentloaded"})
    ]
    assert browser.new_page_options == [{"no_viewport": True}]

    controller.close()
    join_worker(controller)
    assert controller.state is PrismaLifecycleState.IDLE
    assert browser.closed.is_set()


def test_repeated_open_while_active_is_a_safe_deterministic_no_op(monkeypatch):
    browser = FakeBrowser()
    controller = PrismaLifecycleController()
    controller._events = SignallingQueue()
    install_fake_playwright(monkeypatch, lambda **kwargs: browser)

    first_generation = controller.open()
    assert controller._events.ready.wait(2)
    second_generation = controller.open()

    assert second_generation == first_generation
    assert browser.new_page_calls == 1

    controller.close()
    join_worker(controller)


def test_open_while_opening_is_also_a_safe_no_op(monkeypatch):
    launch_entered = threading.Event()
    release_launch = threading.Event()

    def blocked_launch(**kwargs):
        launch_entered.set()
        assert release_launch.wait(2)
        return FakeBrowser()

    install_fake_playwright(monkeypatch, blocked_launch)
    controller = PrismaLifecycleController()

    first_generation = controller.open()
    assert launch_entered.wait(2)
    second_generation = controller.open()

    assert second_generation == first_generation
    assert controller.state is PrismaLifecycleState.OPENING

    controller.close()
    release_launch.set()
    join_worker(controller)


def test_close_with_no_active_session_is_idempotent():
    controller = PrismaLifecycleController()

    controller.close()
    controller.close()

    assert controller.state is PrismaLifecycleState.IDLE
    assert controller.get_events() == []


def test_repeated_close_after_open_is_idempotent(monkeypatch):
    browser = FakeBrowser()
    controller = PrismaLifecycleController()
    controller._events = SignallingQueue()
    install_fake_playwright(monkeypatch, lambda **kwargs: browser)

    controller.open()
    assert controller._events.ready.wait(2)

    controller.close()
    join_worker(controller)
    controller.close()

    assert controller.state is PrismaLifecycleState.IDLE
    assert browser.closed.is_set()


def test_manual_browser_closure_returns_a_retryable_state(monkeypatch):
    browser = FakeBrowser()
    controller = PrismaLifecycleController()
    controller._events = SignallingQueue()
    install_fake_playwright(monkeypatch, lambda **kwargs: browser)

    controller.open()
    assert controller._events.ready.wait(2)
    controller._events = SignallingQueue()

    browser.emit("disconnected")
    join_worker(controller)

    assert controller._events.ready.wait(2)
    events = controller.get_events()
    assert events == [
        PrismaLifecycleEvent(
            1, False, "The PRISMA browser was closed manually.", kind="closed",
        )
    ]
    assert controller.state is PrismaLifecycleState.IDLE
    assert not controller.is_open


def test_retry_after_manual_closure_opens_a_new_generation(monkeypatch):
    first_browser = FakeBrowser()
    second_browser = FakeBrowser()
    browsers = iter((first_browser, second_browser))
    install_fake_playwright(monkeypatch, lambda **kwargs: next(browsers))
    controller = PrismaLifecycleController()
    controller._events = SignallingQueue()

    first_generation = controller.open()
    assert controller._events.ready.wait(2)
    first_browser.emit("disconnected")
    join_worker(controller)

    controller._events = SignallingQueue()
    second_generation = controller.open()
    assert controller._events.ready.wait(2)

    assert second_generation > first_generation
    assert controller.state is PrismaLifecycleState.OPEN
    assert second_browser.new_page_calls == 1

    controller.close()
    join_worker(controller)


def test_browser_startup_failure_is_typed_and_recovers_retry(monkeypatch):
    def fail_launch(**kwargs):
        raise RuntimeError("driver missing")

    install_fake_playwright(monkeypatch, fail_launch)
    controller = PrismaLifecycleController()

    generation = controller.open()
    join_worker(controller)

    events = controller.get_events()
    assert events == [PrismaLifecycleEvent(generation, False, "driver missing", kind="open")]
    assert controller.state is PrismaLifecycleState.IDLE


def test_close_targets_only_this_controllers_owned_browser(monkeypatch):
    owned_browser = FakeBrowser()
    unrelated_browser = FakeBrowser()
    controller = PrismaLifecycleController()
    controller._events = SignallingQueue()
    install_fake_playwright(monkeypatch, lambda **kwargs: owned_browser)

    controller.open()
    assert controller._events.ready.wait(2)

    controller.close()
    join_worker(controller)

    assert owned_browser.closed.is_set()
    assert not unrelated_browser.closed.is_set()


def test_navigation_error_reports_failure_and_closes_owned_resources(monkeypatch):
    browser = FakeBrowser(FakePage(RuntimeError("navigation failed")))
    playwright = install_fake_playwright(monkeypatch, lambda **kwargs: browser)
    controller = PrismaLifecycleController()

    generation = controller.open()
    join_worker(controller)

    events = controller.get_events()
    assert events == [
        PrismaLifecycleEvent(generation, False, "navigation failed", kind="open")
    ]
    assert browser.closed.is_set()
    assert playwright.stopped.is_set()
    assert controller.state is PrismaLifecycleState.IDLE


def test_stop_during_opening_suppresses_success_and_cleans_up(monkeypatch):
    launch_entered = threading.Event()
    release_launch = threading.Event()
    browser = FakeBrowser()

    def blocked_launch(**kwargs):
        launch_entered.set()
        assert release_launch.wait(2)
        return browser

    playwright = install_fake_playwright(monkeypatch, blocked_launch)
    controller = PrismaLifecycleController()

    generation = controller.open()
    assert launch_entered.wait(2)
    controller.close()
    assert controller.state is PrismaLifecycleState.CLOSING
    release_launch.set()
    join_worker(controller)

    assert controller.get_events() == [
        PrismaLifecycleEvent(generation, True, kind="close")
    ]
    assert controller.state is PrismaLifecycleState.IDLE
    assert browser.closed.is_set()
    assert playwright.stopped.is_set()


def test_close_stays_in_closing_state_until_cleanup_completes(monkeypatch):
    release_close = threading.Event()
    browser = FakeBrowser(block_close=release_close)
    controller = PrismaLifecycleController()
    controller._events = SignallingQueue()
    install_fake_playwright(monkeypatch, lambda **kwargs: browser)

    controller.open()
    assert controller._events.ready.wait(2)

    controller.close()
    assert controller.state is PrismaLifecycleState.CLOSING
    assert not browser.closed.is_set()

    release_close.set()
    join_worker(controller)

    assert controller.state is PrismaLifecycleState.IDLE
    assert browser.closed.is_set()


def test_open_during_closing_is_a_deterministic_no_op(monkeypatch):
    release_close = threading.Event()
    browser = FakeBrowser(block_close=release_close)
    launch_calls = []

    def launch(**kwargs):
        launch_calls.append(kwargs)
        return browser

    install_fake_playwright(monkeypatch, launch)
    controller = PrismaLifecycleController()
    controller._events = SignallingQueue()

    first_generation = controller.open()
    assert controller._events.ready.wait(2)

    controller.close()
    assert controller.state is PrismaLifecycleState.CLOSING

    second_generation = controller.open()

    assert second_generation == first_generation
    assert controller.state is PrismaLifecycleState.CLOSING
    assert len(launch_calls) == 1

    release_close.set()
    join_worker(controller)
    assert controller.state is PrismaLifecycleState.IDLE


def test_rapid_close_then_open_cannot_produce_overlapping_sessions(monkeypatch):
    release_first_close = threading.Event()
    first_browser = FakeBrowser(block_close=release_first_close)
    second_browser = FakeBrowser()
    browsers = iter((first_browser, second_browser))
    launch_calls = []

    def launch(**kwargs):
        launch_calls.append(kwargs)
        return next(browsers)

    install_fake_playwright(monkeypatch, launch)
    controller = PrismaLifecycleController()
    controller._events = SignallingQueue()

    first_generation = controller.open()
    assert controller._events.ready.wait(2)

    controller.close()
    rapid_reopen_generation = controller.open()

    assert rapid_reopen_generation == first_generation
    assert len(launch_calls) == 1
    assert second_browser.new_page_calls == 0

    release_first_close.set()
    join_worker(controller)
    assert controller.state is PrismaLifecycleState.IDLE

    controller._events = SignallingQueue()
    second_generation = controller.open()
    assert controller._events.ready.wait(2)

    assert second_generation > first_generation
    assert len(launch_calls) == 2
    assert second_browser.new_page_calls == 1

    controller.close()
    join_worker(controller)


def test_join_waits_for_the_owned_worker_thread(monkeypatch):
    controller = PrismaLifecycleController()
    assert controller.join(timeout=0.1) is True

    browser = FakeBrowser()
    controller._events = SignallingQueue()
    install_fake_playwright(monkeypatch, lambda **kwargs: browser)

    controller.open()
    assert controller._events.ready.wait(2)

    controller.close()
    assert controller.join(timeout=2) is True
    assert controller.state is PrismaLifecycleState.IDLE


def test_close_reports_failure_when_browser_close_raises(monkeypatch):
    browser = FakeBrowser(close_error=RuntimeError("cdp channel closed"))
    playwright = install_fake_playwright(monkeypatch, lambda **kwargs: browser)
    controller = PrismaLifecycleController()
    controller._events = SignallingQueue()

    generation = controller.open()
    assert controller._events.ready.wait(2)
    controller._events = SignallingQueue()

    controller.close()
    assert controller._events.ready.wait(2)
    join_worker(controller)

    assert controller.get_events() == [
        PrismaLifecycleEvent(
            generation, False,
            "The PRISMA browser could not be confirmed closed.", kind="close",
        )
    ]
    assert controller.state is PrismaLifecycleState.CLOSE_FAILED
    assert playwright.stopped.is_set()


def test_close_reports_failure_when_playwright_stop_raises(monkeypatch):
    browser = FakeBrowser()
    install_fake_playwright(
        monkeypatch, lambda **kwargs: browser,
        stop_error=RuntimeError("driver connection lost"),
    )
    controller = PrismaLifecycleController()
    controller._events = SignallingQueue()

    generation = controller.open()
    assert controller._events.ready.wait(2)
    controller._events = SignallingQueue()

    controller.close()
    assert controller._events.ready.wait(2)
    join_worker(controller)

    assert controller.get_events() == [
        PrismaLifecycleEvent(
            generation, False,
            "The PRISMA browser could not be confirmed closed.", kind="close",
        )
    ]
    assert controller.state is PrismaLifecycleState.CLOSE_FAILED
    assert browser.closed.is_set()


def test_close_reports_failure_when_both_browser_and_playwright_cleanup_raise(monkeypatch):
    browser = FakeBrowser(close_error=RuntimeError("cdp channel closed"))
    install_fake_playwright(
        monkeypatch, lambda **kwargs: browser,
        stop_error=RuntimeError("driver connection lost"),
    )
    controller = PrismaLifecycleController()
    controller._events = SignallingQueue()

    generation = controller.open()
    assert controller._events.ready.wait(2)
    controller._events = SignallingQueue()

    controller.close()
    assert controller._events.ready.wait(2)
    join_worker(controller)

    assert controller.get_events() == [
        PrismaLifecycleEvent(
            generation, False,
            "The PRISMA browser could not be confirmed closed.", kind="close",
        )
    ]
    assert controller.state is PrismaLifecycleState.CLOSE_FAILED


def test_open_after_close_failure_is_refused(monkeypatch):
    browser = FakeBrowser(close_error=RuntimeError("cdp channel closed"))
    install_fake_playwright(monkeypatch, lambda **kwargs: browser)
    controller = PrismaLifecycleController()
    controller._events = SignallingQueue()

    generation = controller.open()
    assert controller._events.ready.wait(2)
    controller.close()
    join_worker(controller)
    assert controller.state is PrismaLifecycleState.CLOSE_FAILED

    retry_generation = controller.open()

    assert retry_generation == generation
    assert controller.state is PrismaLifecycleState.CLOSE_FAILED


def test_close_after_close_failure_is_idempotent(monkeypatch):
    browser = FakeBrowser(close_error=RuntimeError("cdp channel closed"))
    install_fake_playwright(monkeypatch, lambda **kwargs: browser)
    controller = PrismaLifecycleController()
    controller._events = SignallingQueue()

    controller.open()
    assert controller._events.ready.wait(2)
    controller.close()
    join_worker(controller)
    assert controller.state is PrismaLifecycleState.CLOSE_FAILED

    controller.close()

    assert controller.state is PrismaLifecycleState.CLOSE_FAILED


def test_manual_closure_is_detected_when_disconnect_handler_registration_fails(
    monkeypatch
):
    browser = FakeBrowser(on_error=RuntimeError("listener API unavailable"))
    install_fake_playwright(monkeypatch, lambda **kwargs: browser)
    controller = PrismaLifecycleController()
    controller._events = SignallingQueue()

    generation = controller.open()
    assert controller._events.ready.wait(2)
    controller._events = SignallingQueue()

    browser.simulate_manual_disconnect()

    assert controller._events.ready.wait(2)
    join_worker(controller)

    assert controller.get_events() == [
        PrismaLifecycleEvent(
            generation, False,
            "The PRISMA browser was closed manually.", kind="closed",
        )
    ]
    assert controller.state is PrismaLifecycleState.IDLE
    assert not controller.is_open


def test_manual_closure_is_detected_by_polling_when_the_disconnected_event_never_fires(
    monkeypatch
):
    """Browser-level: registration succeeds but "disconnected" is never emitted.

    Attaching the handler without raising must not disable the
    `browser.is_connected()` polling fallback, since a successful attachment
    does not guarantee the event actually fires. Detection must rely on
    polling here, not on `browser.emit("disconnected")`. This covers loss of
    the underlying browser connection itself; see the page-level tests below
    for the confirmed real-world defect where the owned window closes while
    `browser.is_connected()` stays true.
    """
    browser = FakeBrowser()
    controller = PrismaLifecycleController()
    controller._events = SignallingQueue()
    install_fake_playwright(monkeypatch, lambda **kwargs: browser)

    generation = controller.open()
    assert controller._events.ready.wait(2)
    controller._events = SignallingQueue()

    browser.simulate_manual_disconnect()

    assert controller._events.ready.wait(2)
    join_worker(controller)

    assert controller.get_events() == [
        PrismaLifecycleEvent(
            generation, False,
            "The PRISMA browser was closed manually.", kind="closed",
        )
    ]
    assert controller.state is PrismaLifecycleState.IDLE
    assert not controller.is_open


def test_manual_closure_emits_exactly_one_event_when_both_detection_paths_fire(
    monkeypatch
):
    browser = FakeBrowser()
    controller = PrismaLifecycleController()
    controller._events = SignallingQueue()
    install_fake_playwright(monkeypatch, lambda **kwargs: browser)

    generation = controller.open()
    assert controller._events.ready.wait(2)
    controller._events = SignallingQueue()

    browser.simulate_manual_disconnect()
    browser.emit("disconnected")

    assert controller._events.ready.wait(2)
    join_worker(controller)

    assert controller.get_events() == [
        PrismaLifecycleEvent(
            generation, False,
            "The PRISMA browser was closed manually.", kind="closed",
        )
    ]
    assert controller.state is PrismaLifecycleState.IDLE


def test_retry_after_polling_detected_closure_opens_a_new_generation_without_overlap(
    monkeypatch
):
    first_browser = FakeBrowser()
    second_browser = FakeBrowser()
    browsers = iter((first_browser, second_browser))
    install_fake_playwright(monkeypatch, lambda **kwargs: next(browsers))
    controller = PrismaLifecycleController()
    controller._events = SignallingQueue()

    first_generation = controller.open()
    assert controller._events.ready.wait(2)
    first_browser.simulate_manual_disconnect()
    join_worker(controller)

    assert controller.state is PrismaLifecycleState.IDLE

    controller._events = SignallingQueue()
    second_generation = controller.open()
    assert controller._events.ready.wait(2)

    assert second_generation > first_generation
    assert controller.state is PrismaLifecycleState.OPEN
    assert second_browser.new_page_calls == 1

    controller.close()
    join_worker(controller)


def test_manual_closure_is_detected_when_the_owned_page_closes_while_browser_stays_connected(
    monkeypatch
):
    """Reproduces the confirmed real-world defect.

    Closing the visible managed window closes only the owned Playwright Page;
    the underlying Browser (e.g. a Chrome/Edge process that keeps running in
    the background after its last window closes) can remain connected.
    `browser.is_connected()` alone must therefore never be the sole signal:
    the owned page's own closed state, silently (no "close" event delivered),
    must still be detected by polling `page.is_closed()`.
    """
    browser = FakeBrowser()
    controller = PrismaLifecycleController()
    controller._events = SignallingQueue()
    install_fake_playwright(monkeypatch, lambda **kwargs: browser)

    generation = controller.open()
    assert controller._events.ready.wait(2)
    controller._events = SignallingQueue()

    browser.page.close_silently()
    assert browser.is_connected()

    assert controller._events.ready.wait(2)
    join_worker(controller)

    assert controller.get_events() == [
        PrismaLifecycleEvent(
            generation, False,
            "The PRISMA browser was closed manually.", kind="closed",
        )
    ]
    assert controller.state is PrismaLifecycleState.IDLE
    assert not controller.is_open
    assert browser.closed.is_set()


def test_manual_closure_is_detected_via_the_page_close_event_while_browser_stays_connected(
    monkeypatch
):
    browser = FakeBrowser()
    controller = PrismaLifecycleController()
    controller._events = SignallingQueue()
    install_fake_playwright(monkeypatch, lambda **kwargs: browser)

    generation = controller.open()
    assert controller._events.ready.wait(2)
    controller._events = SignallingQueue()

    browser.page.simulate_manual_close()
    assert browser.is_connected()

    assert controller._events.ready.wait(2)
    join_worker(controller)

    assert controller.get_events() == [
        PrismaLifecycleEvent(
            generation, False,
            "The PRISMA browser was closed manually.", kind="closed",
        )
    ]
    assert controller.state is PrismaLifecycleState.IDLE
    assert not controller.is_open


def test_manual_closure_emits_exactly_one_event_when_page_and_browser_both_signal_closure(
    monkeypatch
):
    browser = FakeBrowser()
    controller = PrismaLifecycleController()
    controller._events = SignallingQueue()
    install_fake_playwright(monkeypatch, lambda **kwargs: browser)

    generation = controller.open()
    assert controller._events.ready.wait(2)
    controller._events = SignallingQueue()

    browser.page.simulate_manual_close()
    browser.emit("disconnected")

    assert controller._events.ready.wait(2)
    join_worker(controller)

    assert controller.get_events() == [
        PrismaLifecycleEvent(
            generation, False,
            "The PRISMA browser was closed manually.", kind="closed",
        )
    ]
    assert controller.state is PrismaLifecycleState.IDLE


def test_retry_after_page_detected_closure_opens_a_new_generation_without_overlap(
    monkeypatch
):
    first_browser = FakeBrowser()
    second_browser = FakeBrowser()
    browsers = iter((first_browser, second_browser))
    install_fake_playwright(monkeypatch, lambda **kwargs: next(browsers))
    controller = PrismaLifecycleController()
    controller._events = SignallingQueue()

    first_generation = controller.open()
    assert controller._events.ready.wait(2)
    first_browser.page.close_silently()
    join_worker(controller)

    assert controller.state is PrismaLifecycleState.IDLE
    assert first_browser.closed.is_set()

    controller._events = SignallingQueue()
    second_generation = controller.open()
    assert controller._events.ready.wait(2)

    assert second_generation > first_generation
    assert controller.state is PrismaLifecycleState.OPEN
    assert second_browser.new_page_calls == 1

    controller.close()
    join_worker(controller)


def test_normal_close_is_not_misreported_as_manual_closure_when_page_closes_during_cleanup(
    monkeypatch
):
    """Playwright's real `browser.close()` cascades "close" to owned pages and
    contexts. A user-requested Close Prisma must not be reclassified as a
    manual closure just because that cascade fires while cleanup is already
    in progress, so `mark_manual_closure`'s CLOSING-state guard is exercised
    here with the page-close signal, not only the browser-disconnect signal.
    """
    release_close = threading.Event()
    browser = FakeBrowser(block_close=release_close)
    controller = PrismaLifecycleController()
    controller._events = SignallingQueue()
    install_fake_playwright(monkeypatch, lambda **kwargs: browser)

    generation = controller.open()
    assert controller._events.ready.wait(2)
    controller._events = SignallingQueue()

    controller.close()
    assert controller.state is PrismaLifecycleState.CLOSING
    browser.page.simulate_manual_close()
    release_close.set()
    join_worker(controller)

    assert controller.get_events() == [
        PrismaLifecycleEvent(generation, True, kind="close")
    ]
    assert controller.state is PrismaLifecycleState.IDLE


def test_manual_closure_is_detected_via_cdp_target_destroyed_when_page_and_browser_signals_stay_silent(
    monkeypatch
):
    """Models the confirmed real-world mystery from the second failed fix:
    real X-button validation showed the browser closing while Playwright's
    own Page, BrowserContext, and Browser objects all kept reporting "alive"
    (`browser.on("disconnected")`, `browser.is_connected()`, `page.on("close")`,
    `page.is_closed()`, and `context.on("close")` all failed to fire/change).

    The CDP `Target.targetDestroyed` event for the owned page's target is a
    lower-level, independent ground-truth signal layered on top of those
    Playwright-level objects. This test only proves the wiring reacts
    correctly to that CDP event while every higher-level signal stays silent;
    it cannot prove real Windows window-manager/Chrome behavior actually
    fires this CDP event either — that requires another real X-button test.
    """
    browser = FakeBrowser()
    controller = PrismaLifecycleController()
    controller._events = SignallingQueue()
    install_fake_playwright(monkeypatch, lambda **kwargs: browser)

    generation = controller.open()
    assert controller._events.ready.wait(2)
    controller._events = SignallingQueue()

    assert browser.cdp_session is not None
    owned_target_id = browser.cdp_session.page_target_id
    assert owned_target_id is not None
    assert browser.page.is_closed() is False
    assert browser.is_connected() is True

    browser.cdp_session.destroy_target(owned_target_id)

    assert controller._events.ready.wait(2)
    join_worker(controller)

    assert controller.get_events() == [
        PrismaLifecycleEvent(
            generation, False,
            "The PRISMA browser was closed manually.", kind="closed",
        )
    ]
    assert controller.state is PrismaLifecycleState.IDLE
    assert not controller.is_open
    assert browser.closed.is_set()


def test_manual_closure_is_still_detected_when_cdp_session_creation_fails(monkeypatch):
    browser = FakeBrowser(cdp_session_error=RuntimeError("browser CDP session refused"))
    controller = PrismaLifecycleController()
    controller._events = SignallingQueue()
    install_fake_playwright(monkeypatch, lambda **kwargs: browser)

    generation = controller.open()
    assert controller._events.ready.wait(2)
    controller._events = SignallingQueue()

    assert browser.cdp_session is None

    browser.page.close_silently()

    assert controller._events.ready.wait(2)
    join_worker(controller)

    assert controller.get_events() == [
        PrismaLifecycleEvent(
            generation, False,
            "The PRISMA browser was closed manually.", kind="closed",
        )
    ]
    assert controller.state is PrismaLifecycleState.IDLE


def test_ambiguous_cdp_target_baseline_falls_back_to_page_level_detection(monkeypatch):
    """When more than one page-type target already exists at open time, the
    owned target cannot be uniquely identified from CDP alone; detection must
    still work through the existing page-level signal instead of guessing.
    """
    browser = FakeBrowser(cdp_initial_targets={
        "target-a": {"type": "page", "attached": True},
        "target-b": {"type": "page", "attached": True},
    })
    controller = PrismaLifecycleController()
    controller._events = SignallingQueue()
    install_fake_playwright(monkeypatch, lambda **kwargs: browser)

    generation = controller.open()
    assert controller._events.ready.wait(2)
    controller._events = SignallingQueue()

    assert browser.cdp_session is not None
    assert browser.cdp_session.page_target_id is None

    browser.page.close_silently()

    assert controller._events.ready.wait(2)
    join_worker(controller)

    assert controller.get_events() == [
        PrismaLifecycleEvent(
            generation, False,
            "The PRISMA browser was closed manually.", kind="closed",
        )
    ]
    assert controller.state is PrismaLifecycleState.IDLE


def test_manual_closure_emits_exactly_one_event_when_cdp_and_page_signals_both_fire(
    monkeypatch
):
    browser = FakeBrowser()
    controller = PrismaLifecycleController()
    controller._events = SignallingQueue()
    install_fake_playwright(monkeypatch, lambda **kwargs: browser)

    generation = controller.open()
    assert controller._events.ready.wait(2)
    controller._events = SignallingQueue()

    owned_target_id = browser.cdp_session.page_target_id
    browser.cdp_session.destroy_target(owned_target_id)
    browser.page.simulate_manual_close()

    assert controller._events.ready.wait(2)
    join_worker(controller)

    assert controller.get_events() == [
        PrismaLifecycleEvent(
            generation, False,
            "The PRISMA browser was closed manually.", kind="closed",
        )
    ]
    assert controller.state is PrismaLifecycleState.IDLE


def test_retry_after_cdp_target_detected_closure_opens_a_new_generation_without_overlap(
    monkeypatch
):
    first_browser = FakeBrowser()
    second_browser = FakeBrowser()
    browsers = iter((first_browser, second_browser))
    install_fake_playwright(monkeypatch, lambda **kwargs: next(browsers))
    controller = PrismaLifecycleController()
    controller._events = SignallingQueue()

    first_generation = controller.open()
    assert controller._events.ready.wait(2)
    first_browser.cdp_session.destroy_target(first_browser.cdp_session.page_target_id)
    join_worker(controller)

    assert controller.state is PrismaLifecycleState.IDLE
    assert first_browser.closed.is_set()

    controller._events = SignallingQueue()
    second_generation = controller.open()
    assert controller._events.ready.wait(2)

    assert second_generation > first_generation
    assert controller.state is PrismaLifecycleState.OPEN
    assert second_browser.new_page_calls == 1

    controller.close()
    join_worker(controller)


def test_normal_close_is_not_misreported_when_cdp_target_destroyed_fires_during_cleanup(
    monkeypatch
):
    """A real `browser.close()` would also tear down its owned CDP target, so
    the same CLOSING-state guard that protects against a cascading page
    "close" event during cleanup must also protect against a cascading
    `Target.targetDestroyed` for the owned target.
    """
    release_close = threading.Event()
    browser = FakeBrowser(block_close=release_close)
    controller = PrismaLifecycleController()
    controller._events = SignallingQueue()
    install_fake_playwright(monkeypatch, lambda **kwargs: browser)

    generation = controller.open()
    assert controller._events.ready.wait(2)
    controller._events = SignallingQueue()

    controller.close()
    assert controller.state is PrismaLifecycleState.CLOSING
    owned_target_id = browser.cdp_session.page_target_id
    browser.cdp_session.destroy_target(owned_target_id)
    release_close.set()
    join_worker(controller)

    assert controller.get_events() == [
        PrismaLifecycleEvent(generation, True, kind="close")
    ]
    assert controller.state is PrismaLifecycleState.IDLE


# --- P.36.14: managed PRISMA CSV download ---------------------------------
#
# These fakes model the real, live-verified DOM contract (Active Filter
# panel toggle, startOfAuctionFrom/To masked inputs, Filter apply button —
# see ROADMAP.md's P.36.14 real-validation record). Session validation
# (authentication/session-usability) is exercised at the unit level in
# tests/test_prisma_download.py; here a StubSessionValidator is injected via
# a custom PrismaDownloadOrchestrator so these tests stay focused on
# PrismaLifecycleController's own wiring (event emission, cancellation,
# backward compatibility) rather than re-verifying DOM-contract details.


class StubSessionValidator:
    def __init__(self, *, error=None):
        self.error = error

    def validate(self, page):
        if self.error:
            raise self.error


class FakeDateFieldLocator:
    """Real-Windows defect (2026-08-03): the real field also exposes a
    `data-test-iso-value` attribute mirroring the framework's own committed
    value, verified via `field.evaluate(...)` — which computes and returns a
    boolean match, never the browser's own local-timezone conversion (see
    `prisma_download._verify_committed_field_state`'s docstring) — and
    `_fill_field` now blurs the field before verification. `evaluate()`
    returns ``True`` by default (matches "committed correctly"), so existing
    lifecycle-level tests exercise that path without change;
    `iso_committed_override=False` simulates a mismatch and ``None``
    simulates an absent attribute.
    """

    def __init__(
        self, *, visible=True, fill_error=None, echo_fill=True, aria_invalid=None,
        iso_committed_override=True,
    ):
        self.visible = visible
        self.fill_error = fill_error
        self.echo_fill = echo_fill
        self.aria_invalid = aria_invalid
        self.iso_committed_override = iso_committed_override
        self.fill_calls: list[str] = []
        self.blur_calls = 0
        self._value = "DD.MM.YYYY      HH:mm"

    @property
    def first(self):
        return self

    def wait_for(self, state="visible", timeout=None):
        if not self.visible:
            raise TimeoutError(f"Locator.wait_for: Timeout {timeout}ms exceeded.")

    def click(self, timeout=None):
        pass

    def press(self, key, timeout=None):
        pass

    def fill(self, value, timeout=None):
        if self.fill_error:
            raise self.fill_error
        self.fill_calls.append(value)
        if self.echo_fill:
            self._value = value

    def input_value(self, timeout=None):
        return self._value

    def get_attribute(self, name):
        return self.aria_invalid if name == "aria-invalid" else None

    def evaluate(self, script, arg=None, timeout=None):
        if "blur" in script:
            self.blur_calls += 1
            return None
        return self.iso_committed_override


class FakeFilterButtonLocator:
    def __init__(
        self, *, visible=True, click_error=None,
        hidden_after_click=True, wait_hidden_error=None,
        obstructed=False,
    ):
        self.visible = visible
        self.click_error = click_error
        self.click_calls = 0
        self.click_force_values: list[bool | None] = []
        self.hidden_after_click = hidden_after_click
        self.wait_hidden_error = wait_hidden_error
        self.obstructed = obstructed

    @property
    def first(self):
        return self

    def wait_for(self, state="visible", timeout=None):
        if state == "hidden":
            if self.wait_hidden_error:
                raise self.wait_hidden_error
            if not self.hidden_after_click:
                raise TimeoutError(f"Locator.wait_for: Timeout {timeout}ms exceeded.")
            return
        if not self.visible:
            raise TimeoutError(f"Locator.wait_for: Timeout {timeout}ms exceeded.")

    def click(self, timeout=None, force=None):
        self.click_calls += 1
        self.click_force_values.append(force)
        if self.click_error:
            raise self.click_error

    def bounding_box(self):
        return {"x": 0.0, "y": 0.0, "width": 10.0, "height": 10.0}

    def evaluate(self, script, arg=None):
        return self.obstructed

    def scroll_into_view_if_needed(self, timeout=None):
        pass


class FakeAppliedFilterChip:
    """Models the `data-testid="filter-startOfAuctionFrom"` chip PRISMA
    echoes the applied range back into once "Filter" is clicked. Defaults to
    reflecting whatever was actually filled into the two date fields (see
    tests/test_prisma_download.py for the unit-level coverage of its own
    failure modes).
    """

    def __init__(self, page, *, visible=True):
        self._page = page
        self.visible = visible

    @property
    def first(self):
        return self

    def wait_for(self, state="visible", timeout=None):
        if not self.visible:
            raise TimeoutError(f"Locator.wait_for: Timeout {timeout}ms exceeded.")

    def inner_text(self, timeout=None):
        return (
            f"Start of Auction\n{self._page.from_field.input_value()} - "
            f"{self._page.to_field.input_value()}"
        )

    def filter(self, has_text=None):
        return FakeFilteredChipLocator(self, has_text)


class FakeFilteredChipLocator:
    """Models `chip.filter(has_text=...)` (see tests/test_prisma_download.py
    for the unit-level coverage of its lag-tolerant polling behavior)."""

    def __init__(self, base, has_text):
        self._base = base
        self._has_text = has_text

    def wait_for(self, state="visible", timeout=None):
        self._base.wait_for(state=state, timeout=timeout)
        text = self._base.inner_text()
        pattern = self._has_text
        matches = (
            bool(pattern.search(text)) if hasattr(pattern, "search")
            else (str(pattern) in text)
        )
        if not matches:
            raise TimeoutError(f"Locator.wait_for: Timeout {timeout}ms exceeded.")


class FakeAlertLocator:
    """Models `page.get_by_role("alert")`: empty by default."""

    def count(self):
        return 0

    def nth(self, index):
        raise AssertionError("no alerts registered")


class FakeLargeResultDialog:
    """Models PRISMA's own large-export confirmation dialog."""

    def __init__(self, *, visible=True, confirm_button=None):
        self.visible = visible
        self.confirm_button = confirm_button if confirm_button is not None else FakeFilterButtonLocator()

    def wait_for(self, state="visible", timeout=None):
        if not self.visible:
            raise TimeoutError(f"Locator.wait_for: Timeout {timeout}ms exceeded.")

    def get_by_role(self, role, name=None, exact=None):
        if role == "button" and name == "CSV":
            return self.confirm_button
        raise AssertionError(f"unexpected dialog.get_by_role call: {role!r} {name!r}")


class FakeDialogQuery:
    """Models `page.get_by_role("dialog").filter(has_text=...)`. Absent by
    default, matching "absence of the large-result modal is normal".
    """

    def __init__(self, dialog=None):
        self._dialog = dialog

    def filter(self, has_text=None):
        return self

    @property
    def first(self):
        return self._dialog if self._dialog is not None else FakeLargeResultDialog(visible=False)


class FakeManagedPage(FakePage):
    """Extends FakePage with the real Active-Filter-panel automation P.36.14
    performs only when a managed download is requested. Kept separate from
    the base FakePage (whose `__getattr__` proves no extra automation occurs
    for the plain Open Prisma path) so that proof stays intact.
    """

    def __init__(
        self, *args,
        filter_toggle=None, filter_button=None,
        from_field=None, to_field=None, download_button=None,
        cookie_decline_button=None, cookie_accept_button=None,
        large_result_dialog=None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.filter_toggle = filter_toggle if filter_toggle is not None else FakeFilterButtonLocator()
        self.filter_button = filter_button if filter_button is not None else FakeFilterButtonLocator()
        self.from_field = from_field if from_field is not None else FakeDateFieldLocator()
        self.to_field = to_field if to_field is not None else FakeDateFieldLocator()
        self.download_button = download_button if download_button is not None else FakeFilterButtonLocator()
        # Absent by default, matching "banner absence is normal"; the DOM
        # contract itself is unit-tested in tests/test_prisma_download.py, so
        # here it is only exercised where a lifecycle-level test needs it.
        self.cookie_decline_button = (
            cookie_decline_button if cookie_decline_button is not None
            else FakeFilterButtonLocator(visible=False)
        )
        self.cookie_accept_button = (
            cookie_accept_button if cookie_accept_button is not None
            else FakeFilterButtonLocator(visible=False)
        )
        self.applied_filter_chip = FakeAppliedFilterChip(self)
        self.large_result_dialog = large_result_dialog

    def get_by_role(self, role, name=None, exact=None):
        if role == "dialog":
            return FakeDialogQuery(self.large_result_dialog)
        if role == "alert":
            return FakeAlertLocator()
        pattern = getattr(name, "pattern", str(name))
        if role == "button" and "active" in pattern.lower():
            return self.filter_toggle
        if role == "button" and pattern == r"^Filter$":
            return self.filter_button
        if role == "button" and pattern == "CSV":
            return self.download_button
        if role == "button" and pattern == "Decline":
            return self.cookie_decline_button
        if role == "button" and pattern == "Accept & Close":
            return self.cookie_accept_button
        raise AssertionError(f"unexpected get_by_role call: {role!r} {pattern!r}")

    def get_by_test_id(self, test_id):
        if test_id == "filter-startOfAuctionFrom":
            return self.applied_filter_chip
        if test_id == "startOfAuctionFrom":
            return self.from_field
        if test_id == "startOfAuctionTo":
            return self.to_field
        raise AssertionError(f"unexpected get_by_test_id call: {test_id!r}")

    def wait_for_load_state(self, state=None, timeout=None):
        pass


def _managed_download_controller(**orchestrator_kwargs):
    orchestrator_kwargs.setdefault("session_validator", StubSessionValidator())
    orchestrator = PrismaDownloadOrchestrator(**orchestrator_kwargs)
    return PrismaLifecycleController(download_orchestrator=orchestrator)


class FakeDownload:
    def __init__(self, suggested_filename, *, failure=None):
        self.suggested_filename = suggested_filename
        self._failure = failure
        self.save_as_calls = []

    def failure(self):
        return self._failure

    def save_as(self, path):
        self.save_as_calls.append(path)
        Path(path).write_bytes(b"a,b,c\n1,2,3\n")

    def cancel(self):
        pass


DATE_RANGE = DateRange(date(2026, 8, 1), date(2026, 8, 31))


def _fire_download(page: FakeManagedPage, download: FakeDownload) -> None:
    """Fires the download callback registered on the page's context (not the
    page itself): the real CSV export was found to open in a new tab, so
    P.36.14's listener is context-scoped (see prisma_download.py).
    """
    listeners = page.context.listeners.get("download", [])
    assert len(listeners) == 1
    listeners[0](download)


def test_open_without_download_arguments_performs_no_managed_download_automation(
    monkeypatch,
):
    """Backward compatibility: omitting date_range/download_directory keeps
    the pre-P.36.14 behavior exactly, proven by FakePage's __getattr__ guard.
    """
    browser = FakeBrowser()
    controller = PrismaLifecycleController()
    controller._events = SignallingQueue()
    install_fake_playwright(monkeypatch, lambda **kwargs: browser)

    controller.open()
    assert controller._events.ready.wait(2)

    assert browser.page.goto_calls == [
        (PRISMA_OFFICIAL_URL, {"wait_until": "domcontentloaded"})
    ]
    controller.close()
    join_worker(controller)


def test_open_without_download_arguments_never_sets_a_downloads_path(monkeypatch):
    """Backward compatibility: the pre-P.36.14 no-managed-download path must
    not start passing `downloads_path` to `launch()` either.
    """
    browser = FakeBrowser()
    launch_calls = []

    def capturing_launch(**kwargs):
        launch_calls.append(kwargs)
        return browser

    controller = PrismaLifecycleController()
    controller._events = SignallingQueue()
    install_fake_playwright(monkeypatch, capturing_launch)

    controller.open()
    assert controller._events.ready.wait(2)

    assert len(launch_calls) == 1
    assert "downloads_path" not in launch_calls[0]
    controller.close()
    join_worker(controller)


def test_managed_download_launches_the_browser_with_downloads_path_set_to_the_configured_directory(
    monkeypatch, tmp_path,
):
    """Real-Windows defect fix (2026-08-03): without `downloads_path` set,
    Chrome/CDP's download interception writes the raw artifact into a
    Playwright-managed temp location that has no relationship to the folder
    Prisma Function configured, so it is never found there — matching the
    confirmed defect where Chrome showed a completed download under a
    temporary name while the configured directory stayed empty.
    """
    page = FakeManagedPage()
    browser = FakeBrowser(page)
    launch_calls = []

    def capturing_launch(**kwargs):
        launch_calls.append(kwargs)
        return browser

    controller = _managed_download_controller()
    controller._events = SignallingQueue()
    install_fake_playwright(monkeypatch, capturing_launch)

    controller.open(date_range=DATE_RANGE, download_directory=tmp_path)
    assert controller._events.ready.wait(2)

    assert len(launch_calls) == 1
    assert launch_calls[0]["downloads_path"] == str(tmp_path)
    controller.close()
    join_worker(controller)


def test_managed_download_opens_the_real_filter_panel_and_fills_both_dates(
    monkeypatch, tmp_path,
):
    page = FakeManagedPage()
    browser = FakeBrowser(page)
    controller = _managed_download_controller()
    controller._events = SignallingQueue()
    install_fake_playwright(monkeypatch, lambda **kwargs: browser)

    controller.open(date_range=DATE_RANGE, download_directory=tmp_path)
    assert controller._events.ready.wait(2)

    assert controller.get_events() == [PrismaLifecycleEvent(1, True, kind="open")]
    # Exactly one navigation (the approved URL P.36.2 already opens); no
    # second "reporting page" navigation is performed (see ROADMAP.md's
    # P.36.14 real-validation correction — the reporting page is the same
    # page, so a second goto() would only be a redundant reload).
    assert page.goto_calls == [
        (PRISMA_OFFICIAL_URL, {"wait_until": "domcontentloaded"})
    ]
    assert page.filter_toggle.click_calls == 1
    assert page.from_field.fill_calls == ["01.08.2026 00:00"]
    assert page.to_field.fill_calls == ["31.08.2026 23:59"]
    assert page.filter_button.click_calls == 1
    # Registered on the context, not the page (see _fire_download docstring).
    assert len(page.context.listeners.get("download", [])) == 1
    # P.36.14 contract correction: PrismaFunction itself activates PRISMA's
    # CSV download control; the user never presses anything on the website.
    assert page.download_button.click_calls == 1

    controller.close()
    join_worker(controller)


def test_managed_download_reports_as_an_open_failure_when_a_date_is_not_actually_committed(
    monkeypatch, tmp_path,
):
    """Full-trace regression for the reported real-Windows defect: the UI's
    selected start/end dates travel through `PrismaLifecycleController.open()`
    into `PrismaDownloadOrchestrator.configure()`'s page automation, which
    fills the field and the field's own framework-tracked committed value
    (the one the real reporting/export request actually uses) never catches
    up. This must fail the whole Open Prisma attempt through the existing
    typed open-failure path rather than silently proceeding with PRISMA still
    using a different date than the one selected in Prisma Function.
    """
    page = FakeManagedPage(
        from_field=FakeDateFieldLocator(iso_committed_override=False),
    )
    browser = FakeBrowser(page)
    controller = _managed_download_controller()
    controller._events = SignallingQueue()
    install_fake_playwright(monkeypatch, lambda **kwargs: browser)

    controller.open(date_range=DATE_RANGE, download_directory=tmp_path)
    assert controller._events.ready.wait(2)

    events = controller.get_events()
    assert len(events) == 1
    assert events[0].kind == "open"
    assert events[0].success is False
    assert "start date value was not committed" in events[0].error
    # The download control must never be activated with an unverified range.
    assert page.download_button.click_calls == 0
    join_worker(controller)


def test_managed_download_configuration_failure_reports_as_an_open_failure(
    monkeypatch, tmp_path,
):
    page = FakeManagedPage(from_field=FakeDateFieldLocator(fill_error=RuntimeError("locator not found")))
    browser = FakeBrowser(page)
    install_fake_playwright(monkeypatch, lambda **kwargs: browser)
    controller = _managed_download_controller()

    generation = controller.open(date_range=DATE_RANGE, download_directory=tmp_path)
    join_worker(controller)

    events = controller.get_events()
    assert len(events) == 1
    assert events[0].generation == generation
    assert events[0].success is False
    assert events[0].kind == "open"
    assert "start date field rejected" in events[0].error
    assert browser.closed.is_set()
    assert controller.state is PrismaLifecycleState.IDLE


def test_managed_download_authentication_required_reports_as_an_open_failure(
    monkeypatch, tmp_path,
):
    page = FakeManagedPage()
    browser = FakeBrowser(page)
    install_fake_playwright(monkeypatch, lambda **kwargs: browser)
    controller = _managed_download_controller(
        session_validator=StubSessionValidator(
            error=PrismaAuthenticationRequiredError(
                "PRISMA authentication is required; the public session cannot continue."
            )
        ),
    )

    generation = controller.open(date_range=DATE_RANGE, download_directory=tmp_path)
    join_worker(controller)

    events = controller.get_events()
    assert len(events) == 1
    assert events[0].generation == generation
    assert events[0].success is False
    assert events[0].kind == "open"
    assert "authentication is required" in events[0].error
    # Authentication failure is detected before any filter-panel automation.
    assert page.filter_toggle.click_calls == 0
    assert controller.state is PrismaLifecycleState.IDLE


def test_managed_download_missing_filter_controls_reports_as_an_open_failure(
    monkeypatch, tmp_path,
):
    page = FakeManagedPage(from_field=FakeDateFieldLocator(visible=False))
    browser = FakeBrowser(page)
    install_fake_playwright(monkeypatch, lambda **kwargs: browser)
    controller = _managed_download_controller()

    generation = controller.open(date_range=DATE_RANGE, download_directory=tmp_path)
    join_worker(controller)

    events = controller.get_events()
    assert len(events) == 1
    assert events[0].generation == generation
    assert events[0].success is False
    assert "date-range controls could not be located" in events[0].error


def test_managed_download_control_not_found_reports_as_an_open_failure(
    monkeypatch, tmp_path,
):
    page = FakeManagedPage(download_button=FakeFilterButtonLocator(visible=False))
    browser = FakeBrowser(page)
    install_fake_playwright(monkeypatch, lambda **kwargs: browser)
    controller = _managed_download_controller()

    generation = controller.open(date_range=DATE_RANGE, download_directory=tmp_path)
    join_worker(controller)

    events = controller.get_events()
    assert len(events) == 1
    assert events[0].generation == generation
    assert events[0].success is False
    assert events[0].kind == "open"
    assert "download control could not be found" in events[0].error
    # The filter itself must have been applied before the (failed) attempt
    # to locate the download control.
    assert page.filter_button.click_calls == 1
    # No listener is left registered when the control was never found.
    assert page.context.listeners.get("download", []) == []


def test_managed_download_control_activation_failure_reports_as_an_open_failure(
    monkeypatch, tmp_path,
):
    page = FakeManagedPage(
        download_button=FakeFilterButtonLocator(click_error=RuntimeError("element intercepted"))
    )
    browser = FakeBrowser(page)
    install_fake_playwright(monkeypatch, lambda **kwargs: browser)
    controller = _managed_download_controller()

    generation = controller.open(date_range=DATE_RANGE, download_directory=tmp_path)
    join_worker(controller)

    events = controller.get_events()
    assert len(events) == 1
    assert events[0].generation == generation
    assert events[0].success is False
    assert "download control could not be activated" in events[0].error
    # The listener must already be registered before the failed click.
    assert len(page.context.listeners.get("download", [])) == 1


def test_managed_download_filter_verification_failure_reports_as_an_open_failure(
    monkeypatch, tmp_path,
):
    """Regression: if PRISMA's applied-filter chip does not confirm the
    requested range (see prisma_download.py's `_verify_filter_applied`),
    Open Prisma must fail like any other configure() failure, never proceed
    to click the download control with an unconfirmed filter state.
    """
    page = FakeManagedPage()
    page.applied_filter_chip = FakeAppliedFilterChip(page, visible=False)
    browser = FakeBrowser(page)
    install_fake_playwright(monkeypatch, lambda **kwargs: browser)
    controller = _managed_download_controller()

    generation = controller.open(date_range=DATE_RANGE, download_directory=tmp_path)
    join_worker(controller)

    events = controller.get_events()
    assert len(events) == 1
    assert events[0].generation == generation
    assert events[0].success is False
    assert events[0].kind == "open"
    assert "could not be confirmed as applied" in events[0].error
    assert page.download_button.click_calls == 0


def test_managed_download_confirms_the_large_result_modal_when_present(
    monkeypatch, tmp_path,
):
    """Regression: PRISMA's own large-export confirmation dialog (see
    prisma_download.py's `_confirm_large_result_modal_if_present`) must be
    confirmed automatically so the managed download still completes with no
    manual browser interaction.
    """
    confirm = FakeFilterButtonLocator()
    dialog = FakeLargeResultDialog(confirm_button=confirm)
    page = FakeManagedPage(large_result_dialog=dialog)
    browser = FakeBrowser(page)
    controller = _managed_download_controller()
    controller._events = SignallingQueue()
    install_fake_playwright(monkeypatch, lambda **kwargs: browser)

    controller.open(date_range=DATE_RANGE, download_directory=tmp_path)
    assert controller._events.ready.wait(2)

    assert controller.get_events() == [PrismaLifecycleEvent(1, True, kind="open")]
    assert page.download_button.click_calls == 1
    assert confirm.click_calls == 1

    controller.close()
    join_worker(controller)


def test_managed_download_large_result_modal_that_cannot_be_confirmed_reports_as_an_open_failure(
    monkeypatch, tmp_path,
):
    dialog = FakeLargeResultDialog(
        confirm_button=FakeFilterButtonLocator(click_error=RuntimeError("element intercepted"))
    )
    page = FakeManagedPage(large_result_dialog=dialog)
    browser = FakeBrowser(page)
    install_fake_playwright(monkeypatch, lambda **kwargs: browser)
    controller = _managed_download_controller()

    generation = controller.open(date_range=DATE_RANGE, download_directory=tmp_path)
    join_worker(controller)

    events = controller.get_events()
    assert len(events) == 1
    assert events[0].generation == generation
    assert events[0].success is False
    assert events[0].kind == "open"
    assert "large-result confirmation could not be confirmed" in events[0].error


def test_managed_download_absent_large_result_modal_is_treated_as_normal(
    monkeypatch, tmp_path,
):
    page = FakeManagedPage()  # large_result_dialog is None (absent) by default
    browser = FakeBrowser(page)
    controller = _managed_download_controller()
    controller._events = SignallingQueue()
    install_fake_playwright(monkeypatch, lambda **kwargs: browser)

    controller.open(date_range=DATE_RANGE, download_directory=tmp_path)
    assert controller._events.ready.wait(2)

    assert controller.get_events() == [PrismaLifecycleEvent(1, True, kind="open")]
    assert page.download_button.click_calls == 1

    controller.close()
    join_worker(controller)


def test_managed_download_captures_the_csv_after_large_result_modal_confirmation(
    monkeypatch, tmp_path,
):
    """The download is still captured end-to-end (name, collision-safe save)
    when it followed a large-result modal confirmation.
    """
    dialog = FakeLargeResultDialog()
    page = FakeManagedPage(large_result_dialog=dialog)
    browser = FakeBrowser(page)
    controller = _managed_download_controller()
    controller._events = SignallingQueue()
    install_fake_playwright(monkeypatch, lambda **kwargs: browser)

    controller.open(date_range=DATE_RANGE, download_directory=tmp_path)
    assert controller._events.ready.wait(2)
    controller.get_events()
    controller._events = SignallingQueue()

    _fire_download(page, FakeDownload("Auction_overview.csv"))

    assert controller._events.ready.wait(2)
    events = controller.get_events()
    assert len(events) == 1
    assert events[0].kind == "download"
    assert events[0].success is True
    assert events[0].csv_path == tmp_path / "Auction_overview_2026-08-01_2026-08-31.csv"
    assert events[0].csv_path.exists()

    controller.close()
    join_worker(controller)


def test_managed_download_success_emits_a_download_event_with_the_saved_csv_path(
    monkeypatch, tmp_path,
):
    page = FakeManagedPage()
    browser = FakeBrowser(page)
    controller = _managed_download_controller()
    controller._events = SignallingQueue()
    install_fake_playwright(monkeypatch, lambda **kwargs: browser)

    controller.open(date_range=DATE_RANGE, download_directory=tmp_path)
    assert controller._events.ready.wait(2)
    controller.get_events()
    controller._events = SignallingQueue()

    download = FakeDownload("Auction_overview.csv")
    _fire_download(page, download)

    assert controller._events.ready.wait(2)
    events = controller.get_events()
    assert len(events) == 1
    event = events[0]
    assert event.kind == "download"
    assert event.success is True
    assert event.csv_path == tmp_path / "Auction_overview_2026-08-01_2026-08-31.csv"
    assert event.csv_path.exists()

    controller.close()
    join_worker(controller)


def test_managed_download_dismisses_the_cookie_banner_before_activating_the_csv_control(
    monkeypatch, tmp_path,
):
    """Live acceptance found the fixed cookie-consent banner sometimes
    intercepts the CSV control's pointer events (see ROADMAP.md P.36.14 live
    corrections). With the banner present, Open Prisma must still dismiss it
    and complete the managed download.
    """
    decline = FakeFilterButtonLocator()
    page = FakeManagedPage(cookie_decline_button=decline)
    browser = FakeBrowser(page)
    controller = _managed_download_controller()
    controller._events = SignallingQueue()
    install_fake_playwright(monkeypatch, lambda **kwargs: browser)

    controller.open(date_range=DATE_RANGE, download_directory=tmp_path)
    assert controller._events.ready.wait(2)

    assert controller.get_events() == [PrismaLifecycleEvent(1, True, kind="open")]
    assert decline.click_calls == 1
    assert page.download_button.click_calls == 1

    controller.close()
    join_worker(controller)


def test_managed_download_cookie_banner_that_cannot_be_dismissed_reports_as_an_open_failure(
    monkeypatch, tmp_path,
):
    decline = FakeFilterButtonLocator(click_error=RuntimeError("element intercepted"))
    page = FakeManagedPage(cookie_decline_button=decline)
    browser = FakeBrowser(page)
    install_fake_playwright(monkeypatch, lambda **kwargs: browser)
    controller = _managed_download_controller()

    generation = controller.open(date_range=DATE_RANGE, download_directory=tmp_path)
    join_worker(controller)

    events = controller.get_events()
    assert len(events) == 1
    assert events[0].generation == generation
    assert events[0].success is False
    assert events[0].kind == "open"
    assert "cookie-consent banner could not be dismissed" in events[0].error
    # The CSV control must never be clicked if the banner blocked it.
    assert page.download_button.click_calls == 0


def test_managed_download_captures_a_download_triggered_by_a_newly_opened_page(
    monkeypatch, tmp_path,
):
    """The real PRISMA CSV export was found to open in a new tab rather than
    the originating page (see ROADMAP.md). Since the listener is registered
    on the shared BrowserContext, a download reported by any page sharing
    that context — not just the originating `page` — must still be accepted.
    """
    page = FakeManagedPage()
    browser = FakeBrowser(page)
    controller = _managed_download_controller()
    controller._events = SignallingQueue()
    install_fake_playwright(monkeypatch, lambda **kwargs: browser)

    controller.open(date_range=DATE_RANGE, download_directory=tmp_path)
    assert controller._events.ready.wait(2)
    controller.get_events()
    controller._events = SignallingQueue()

    new_tab = FakePage(context=page.context)  # shares the same BrowserContext
    download = FakeDownload("Auction_overview.csv")
    _fire_download(new_tab, download)

    assert controller._events.ready.wait(2)
    events = controller.get_events()
    assert len(events) == 1
    assert events[0].kind == "download"
    assert events[0].success is True
    assert events[0].csv_path == tmp_path / "Auction_overview_2026-08-01_2026-08-31.csv"

    controller.close()
    join_worker(controller)


def test_managed_download_rejects_a_second_download_event(monkeypatch, tmp_path):
    page = FakeManagedPage()
    browser = FakeBrowser(page)
    controller = _managed_download_controller()
    controller._events = SignallingQueue()
    install_fake_playwright(monkeypatch, lambda **kwargs: browser)

    controller.open(date_range=DATE_RANGE, download_directory=tmp_path)
    assert controller._events.ready.wait(2)
    controller.get_events()
    controller._events = SignallingQueue()

    listeners = page.context.listeners.get("download", [])
    assert len(listeners) == 1
    listeners[0](FakeDownload("Auction_overview.csv"))
    listeners[0](FakeDownload("Auction_overview.csv"))

    assert controller._events.ready.wait(2)
    events = controller.get_events()
    assert len(events) == 1
    assert events[0].kind == "download"
    assert events[0].success is False
    assert events[0].csv_path is None
    assert list(tmp_path.iterdir()) == []

    controller.close()
    join_worker(controller)


def test_managed_download_success_removes_the_context_listener(monkeypatch, tmp_path):
    page = FakeManagedPage()
    browser = FakeBrowser(page)
    controller = _managed_download_controller()
    controller._events = SignallingQueue()
    install_fake_playwright(monkeypatch, lambda **kwargs: browser)

    controller.open(date_range=DATE_RANGE, download_directory=tmp_path)
    assert controller._events.ready.wait(2)
    controller.get_events()
    controller._events = SignallingQueue()

    _fire_download(page, FakeDownload("Auction_overview.csv"))
    assert controller._events.ready.wait(2)

    assert page.context.listeners.get("download", []) == []
    assert len(page.context.removed_listeners) == 1
    assert page.context.removed_listeners[0][0] == "download"

    controller.close()
    join_worker(controller)


def test_managed_download_timeout_removes_the_context_listener(monkeypatch, tmp_path):
    page = FakeManagedPage()
    browser = FakeBrowser(page)
    controller = _managed_download_controller(timeout_seconds=0.05)
    controller._events = SignallingQueue()
    install_fake_playwright(monkeypatch, lambda **kwargs: browser)

    controller.open(date_range=DATE_RANGE, download_directory=tmp_path)
    assert controller._events.ready.wait(2)
    controller.get_events()
    controller._events = SignallingQueue()

    assert controller._events.ready.wait(2)
    controller.get_events()

    assert page.context.listeners.get("download", []) == []
    assert len(page.context.removed_listeners) == 1

    controller.close()
    join_worker(controller)


def test_managed_download_cancellation_before_resolution_removes_the_context_listener(
    monkeypatch, tmp_path,
):
    page = FakeManagedPage()
    browser = FakeBrowser(page)
    controller = _managed_download_controller()
    controller._events = SignallingQueue()
    install_fake_playwright(monkeypatch, lambda **kwargs: browser)

    controller.open(date_range=DATE_RANGE, download_directory=tmp_path)
    assert controller._events.ready.wait(2)
    controller.get_events()

    # Close Prisma while the download is still unresolved (no _fire_download).
    controller.close()
    join_worker(controller)

    assert page.context.listeners.get("download", []) == []
    assert len(page.context.removed_listeners) == 1


def test_managed_download_not_csv_emits_a_typed_failure_event(monkeypatch, tmp_path):
    page = FakeManagedPage()
    browser = FakeBrowser(page)
    controller = _managed_download_controller()
    controller._events = SignallingQueue()
    install_fake_playwright(monkeypatch, lambda **kwargs: browser)

    controller.open(date_range=DATE_RANGE, download_directory=tmp_path)
    assert controller._events.ready.wait(2)
    controller.get_events()
    controller._events = SignallingQueue()

    _fire_download(page, FakeDownload("Auction_overview.xlsx"))

    assert controller._events.ready.wait(2)
    events = controller.get_events()
    assert len(events) == 1
    assert events[0].kind == "download"
    assert events[0].success is False
    assert events[0].csv_path is None
    assert list(tmp_path.iterdir()) == []

    controller.close()
    join_worker(controller)


def test_managed_download_cancelled_emits_a_typed_failure_event(monkeypatch, tmp_path):
    page = FakeManagedPage()
    browser = FakeBrowser(page)
    controller = _managed_download_controller()
    controller._events = SignallingQueue()
    install_fake_playwright(monkeypatch, lambda **kwargs: browser)

    controller.open(date_range=DATE_RANGE, download_directory=tmp_path)
    assert controller._events.ready.wait(2)
    controller.get_events()
    controller._events = SignallingQueue()

    _fire_download(page, FakeDownload("Auction_overview.csv", failure="canceled"))

    assert controller._events.ready.wait(2)
    events = controller.get_events()
    assert events[0].kind == "download"
    assert events[0].success is False

    controller.close()
    join_worker(controller)


def test_managed_download_interrupted_emits_a_typed_failure_event(monkeypatch, tmp_path):
    page = FakeManagedPage()
    browser = FakeBrowser(page)
    controller = _managed_download_controller()
    controller._events = SignallingQueue()
    install_fake_playwright(monkeypatch, lambda **kwargs: browser)

    controller.open(date_range=DATE_RANGE, download_directory=tmp_path)
    assert controller._events.ready.wait(2)
    controller.get_events()
    controller._events = SignallingQueue()

    _fire_download(
        page, FakeDownload("Auction_overview.csv", failure="net::ERR_CONNECTION_RESET")
    )

    assert controller._events.ready.wait(2)
    events = controller.get_events()
    assert events[0].kind == "download"
    assert events[0].success is False

    controller.close()
    join_worker(controller)


def test_managed_download_times_out_when_no_download_is_ever_triggered(
    monkeypatch, tmp_path,
):
    page = FakeManagedPage()
    browser = FakeBrowser(page)
    controller = _managed_download_controller(timeout_seconds=0.05)
    controller._events = SignallingQueue()
    install_fake_playwright(monkeypatch, lambda **kwargs: browser)

    controller.open(date_range=DATE_RANGE, download_directory=tmp_path)
    assert controller._events.ready.wait(2)
    controller.get_events()
    controller._events = SignallingQueue()

    assert controller._events.ready.wait(2)
    events = controller.get_events()
    assert len(events) == 1
    assert events[0].kind == "download"
    assert events[0].success is False

    controller.close()
    join_worker(controller)


def test_managed_download_wait_does_not_block_manual_closure_detection(
    monkeypatch, tmp_path,
):
    page = FakeManagedPage()
    browser = FakeBrowser(page)
    controller = _managed_download_controller()
    controller._events = SignallingQueue()
    install_fake_playwright(monkeypatch, lambda **kwargs: browser)

    controller.open(date_range=DATE_RANGE, download_directory=tmp_path)
    assert controller._events.ready.wait(2)
    controller.get_events()
    controller._events = SignallingQueue()

    browser.emit("disconnected")

    assert controller._events.ready.wait(2)
    events = controller.get_events()
    assert events == [
        PrismaLifecycleEvent(
            1, False, "The PRISMA browser was closed manually.", kind="closed",
        )
    ]
    join_worker(controller)


def test_managed_download_succeeds_via_filesystem_fallback_when_no_playwright_event_arrives(
    monkeypatch, tmp_path,
):
    """Approved production fallback (see prisma_download.py's
    `PrismaDownloadFilesystemWaiter`): if the real installed Chrome completes
    the download but no Playwright "download" event is ever observed, a
    completed CSV file simply appearing in the configured directory must
    still be recognized, named, and reported as a successful download.
    """
    page = FakeManagedPage()
    browser = FakeBrowser(page)
    controller = _managed_download_controller(timeout_seconds=5.0)
    controller._events = SignallingQueue()
    install_fake_playwright(monkeypatch, lambda **kwargs: browser)

    controller.open(date_range=DATE_RANGE, download_directory=tmp_path)
    assert controller._events.ready.wait(2)
    controller.get_events()
    controller._events = SignallingQueue()

    # No Playwright "download" event is ever fired here: the file simply
    # appears, exactly as it would if the real Chrome executable's own
    # download manager bypassed Playwright's CDP-based interception.
    (tmp_path / "Auction_overview.csv").write_bytes(b"a,b,c\n1,2,3\n")

    assert controller._events.ready.wait(2)
    events = controller.get_events()
    assert len(events) == 1
    assert events[0].kind == "download"
    assert events[0].success is True
    assert events[0].csv_path == tmp_path / "Auction_overview_2026-08-01_2026-08-31.csv"
    assert events[0].csv_path.exists()

    controller.close()
    join_worker(controller)


def test_managed_download_succeeds_via_filesystem_fallback_with_a_uuid_named_artifact(
    monkeypatch, tmp_path,
):
    """Real-Windows defect fix (2026-08-03): the raw artifact Chrome/CDP
    writes into the now-correctly-configured `downloads_path` is named by
    the browser/CDP itself (typically UUID-like), never necessarily
    ``.csv``. The fallback must still recognize, finalize (forcing a
    ``.csv`` extension), and report it as a successful download.
    """
    page = FakeManagedPage()
    browser = FakeBrowser(page)
    controller = _managed_download_controller(timeout_seconds=5.0)
    controller._events = SignallingQueue()
    install_fake_playwright(monkeypatch, lambda **kwargs: browser)

    controller.open(date_range=DATE_RANGE, download_directory=tmp_path)
    assert controller._events.ready.wait(2)
    controller.get_events()
    controller._events = SignallingQueue()

    (tmp_path / "3fa85f64-5717-4562-b3fc-2c963f66afa6").write_bytes(b"a,b,c\n1,2,3\n")

    assert controller._events.ready.wait(2)
    events = controller.get_events()
    assert len(events) == 1
    assert events[0].kind == "download"
    assert events[0].success is True
    assert events[0].csv_path.suffix == ".csv"
    assert events[0].csv_path.name.endswith("_2026-08-01_2026-08-31.csv")
    assert events[0].csv_path.parent == tmp_path
    assert events[0].csv_path.exists()

    controller.close()
    join_worker(controller)


def test_managed_download_reports_exactly_one_success_when_the_event_and_fallback_observe_the_same_download(
    monkeypatch, tmp_path,
):
    """No duplicate final file (and no duplicate "download" event) is
    produced when the Playwright event and the filesystem fallback both
    observe the same underlying download: only one `kind="download"` event
    is ever emitted, and exactly one dated CSV exists afterward.
    """
    page = FakeManagedPage()
    browser = FakeBrowser(page)
    controller = _managed_download_controller(timeout_seconds=5.0)
    controller._events = SignallingQueue()
    install_fake_playwright(monkeypatch, lambda **kwargs: browser)

    controller.open(date_range=DATE_RANGE, download_directory=tmp_path)
    assert controller._events.ready.wait(2)
    controller.get_events()
    controller._events = SignallingQueue()

    # The raw artifact appears on disk (as it now genuinely would, since
    # `downloads_path` points at the configured directory) before the
    # Playwright "download" event is delivered.
    (tmp_path / "3fa85f64-5717-4562-b3fc-2c963f66afa6").write_bytes(b"a,b,c\n1,2,3\n")
    download = FakeDownload("Auction_overview.csv")
    _fire_download(page, download)

    assert controller._events.ready.wait(2)
    events = controller.get_events()
    download_events = [event for event in events if event.kind == "download"]
    assert len(download_events) == 1
    assert download_events[0].success is True
    dated_outputs = list(tmp_path.glob("*_2026-08-01_2026-08-31.csv"))
    assert dated_outputs == [download_events[0].csv_path]

    controller.close()
    join_worker(controller)


def test_managed_download_wait_with_active_filesystem_fallback_does_not_block_manual_closure_detection(
    monkeypatch, tmp_path,
):
    """Approved production fallback (see prisma_download.py's
    `PrismaDownloadFilesystemWaiter`): `configure()` now always receives
    `download_directory`, so the real orchestrator's bounded filesystem
    polling runs on every iteration of the same idle loop that also detects
    manual closure. This must not make that loop any less responsive: a
    browser "disconnected" event must still be detected promptly even while
    the filesystem fallback is actively polling an empty directory for a
    download that never arrives.
    """
    page = FakeManagedPage()
    browser = FakeBrowser(page)
    controller = _managed_download_controller()
    controller._events = SignallingQueue()
    install_fake_playwright(monkeypatch, lambda **kwargs: browser)

    controller.open(date_range=DATE_RANGE, download_directory=tmp_path)
    assert controller._events.ready.wait(2)
    controller.get_events()
    controller._events = SignallingQueue()

    browser.emit("disconnected")

    assert controller._events.ready.wait(2)
    events = controller.get_events()
    assert events == [
        PrismaLifecycleEvent(
            1, False, "The PRISMA browser was closed manually.", kind="closed",
        )
    ]
    join_worker(controller)


def test_windowed_runtime_supplies_output_handles_before_playwright_start(monkeypatch):
    browser = FakeBrowser()
    streams_at_start = []
    playwright = FakePlaywright(lambda **kwargs: browser)

    def start():
        streams_at_start.append((sys.stdout, sys.stderr))
        return playwright

    monkeypatch.setitem(
        sys.modules, "playwright.sync_api",
        SimpleNamespace(sync_playwright=lambda: SimpleNamespace(start=start)),
    )
    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)
    controller = PrismaLifecycleController()

    controller.open()
    while controller.state is PrismaLifecycleState.OPENING:
        threading.Event().wait(0.01)

    assert len(streams_at_start) == 1
    assert all(stream is not None for stream in streams_at_start[0])

    controller.close()
    join_worker(controller)
