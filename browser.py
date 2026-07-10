from __future__ import annotations

import queue
import threading
from dataclasses import dataclass
from enum import Enum

PRISMA_AUCTIONS_URL = (
    "https://app.prisma-capacity.eu/reporting/auctions/"
    "short-and-long-term-auctions"
)


class BrowserState(str, Enum):
    IDLE = "idle"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"


@dataclass(frozen=True)
class LaunchResult:
    generation: int
    success: bool
    error: str | None = None


class BrowserController:
    """Opens PRISMA in installed Chrome or Edge and owns that session."""

    def __init__(self) -> None:
        self._playwright = None
        self._browser = None
        self._thread: threading.Thread | None = None
        self._lock = threading.RLock()
        self._state = BrowserState.IDLE
        self._generation = 0
        self._cancel_event: threading.Event | None = None
        self._results: queue.SimpleQueue[LaunchResult] = queue.SimpleQueue()
        self.last_error: str | None = None

    @property
    def state(self) -> BrowserState:
        with self._lock:
            return self._state

    @property
    def is_running(self) -> bool:
        return self.state is BrowserState.RUNNING

    def open(self, browser_name: str) -> int:
        with self._lock:
            if self._state is not BrowserState.IDLE:
                raise RuntimeError("Браузерна сесія вже запущена або зупиняється.")

            self._generation += 1
            generation = self._generation
            cancel_event = threading.Event()
            self._cancel_event = cancel_event
            self.last_error = None
            self._state = BrowserState.STARTING
            thread = threading.Thread(
                target=self._run,
                args=(browser_name, generation, cancel_event),
                daemon=True,
            )
            self._thread = thread
            thread.start()
            return generation

    def get_launch_results(self) -> list[LaunchResult]:
        results = []
        while True:
            try:
                results.append(self._results.get_nowait())
            except queue.Empty:
                return results

    def _is_current(self, generation: int) -> bool:
        return generation == self._generation

    def _run(
        self,
        browser_name: str,
        generation: int,
        cancel_event: threading.Event,
    ) -> None:
        playwright = None
        browser = None
        launch_error: str | None = None
        announced_success = False

        try:
            from playwright.sync_api import sync_playwright

            channels = {"Chrome": "chrome", "Edge": "msedge"}
            channel = channels[browser_name]
            playwright = sync_playwright().start()
            if cancel_event.is_set():
                return

            browser = playwright.chromium.launch(channel=channel, headless=False)
            with self._lock:
                if self._is_current(generation):
                    self._playwright = playwright
                    self._browser = browser
            if cancel_event.is_set():
                return

            page = browser.new_page()
            page.goto(PRISMA_AUCTIONS_URL, wait_until="domcontentloaded")

            with self._lock:
                if (
                    self._is_current(generation)
                    and self._state is BrowserState.STARTING
                    and not cancel_event.is_set()
                ):
                    self._state = BrowserState.RUNNING
                    announced_success = True
                    self._results.put(LaunchResult(generation, True))

            if not announced_success:
                return

            cancel_event.wait()
        except Exception as exc:
            launch_error = str(exc).strip() or exc.__class__.__name__
        finally:
            if browser is not None:
                try:
                    browser.close()
                except Exception:
                    pass
            if playwright is not None:
                try:
                    playwright.stop()
                except Exception:
                    pass

            with self._lock:
                is_current = self._is_current(generation)
                was_cancelled = cancel_event.is_set() or (
                    is_current and self._state is BrowserState.STOPPING
                )
                if is_current:
                    self._browser = None
                    self._playwright = None
                    self._cancel_event = None
                    self._state = BrowserState.IDLE
                    if launch_error and not was_cancelled and not announced_success:
                        self.last_error = launch_error
                        self._results.put(
                            LaunchResult(generation, False, launch_error)
                        )

    def stop(self) -> None:
        with self._lock:
            if self._state is BrowserState.IDLE:
                return
            self._state = BrowserState.STOPPING
            if self._cancel_event is not None:
                self._cancel_event.set()
