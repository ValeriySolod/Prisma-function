import sys
import threading
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from browser import DefaultBrowserDetector, PRISMA_AUCTIONS_URL
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

    def on(self, event, callback):
        self.listeners.setdefault(event, []).append(callback)

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
