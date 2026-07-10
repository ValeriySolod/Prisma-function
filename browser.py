from __future__ import annotations

import queue
import re
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


class _LaunchCancelled(Exception):
    """Internal control flow for a user-cancelled browser launch."""


class PrismaAuctionFilter:
    """Locates and applies the Marketed Capacity filter on the PRISMA page."""

    TIMEOUT_MS = 10_000
    FIELD_NAME = re.compile(r"Marketed\s+Capacity", re.IGNORECASE)
    GREATER_OR_EQUAL = re.compile(
        r"greater\s+than\s+or\s+equal|more\s+than\s+or\s+equal|>=|≥",
        re.IGNORECASE,
    )

    def apply(self, page, cancel_event: threading.Event) -> None:
        self._check_cancelled(cancel_event)
        page.wait_for_load_state("domcontentloaded", timeout=self.TIMEOUT_MS)
        container = self._find_marketed_capacity_container(page)
        self._check_cancelled(cancel_event)
        operator = self._find_operator_dropdown(container)
        self._set_operator(page, operator, cancel_event)
        input_element = self._find_value_input(container)
        self._check_cancelled(cancel_event)
        try:
            input_element.fill("1000", timeout=self.TIMEOUT_MS)
        except Exception as exc:
            self._check_cancelled(cancel_event)
            raise RuntimeError("Не вдалося встановити значення 1000") from exc
        self._click_apply(container, cancel_event)

    def _find_marketed_capacity_container(self, page):
        return self._first_visible(
            (
                lambda: page.get_by_role("group", name=self.FIELD_NAME).first,
                lambda: page.get_by_text(self.FIELD_NAME).first.locator(
                    "xpath=ancestor::*[self::fieldset or @role='group' "
                    "or contains(@data-testid, 'filter') "
                    "or contains(@aria-label, 'Marketed Capacity')][1]"
                ),
            ),
            "Не знайдено контейнер фільтра Marketed Capacity",
        )

    def _find_operator_dropdown(self, container):
        return self._first_visible(
            (
                lambda: container.get_by_label(
                    re.compile(r"operator|condition", re.IGNORECASE)
                ).first,
                lambda: container.get_by_role("combobox").first,
                lambda: container.locator("select").first,
            ),
            "Не знайдено operator dropdown у фільтрі Marketed Capacity",
        )

    def _find_value_input(self, container):
        return self._first_visible(
            (
                lambda: container.get_by_label(self.FIELD_NAME).first,
                lambda: container.get_by_role(
                    "spinbutton", name=self.FIELD_NAME
                ).first,
                lambda: container.get_by_role("textbox", name=self.FIELD_NAME).first,
                lambda: container.locator(
                    "input[type='number'], input[inputmode='numeric']"
                ).first,
            ),
            "Не знайдено поле значення у фільтрі Marketed Capacity",
        )

    def _first_visible(self, factories, error_message: str):
        for factory in factories:
            try:
                locator = factory()
                locator.wait_for(state="visible", timeout=self.TIMEOUT_MS)
                return locator
            except Exception:
                continue
        raise RuntimeError(error_message)

    def _set_operator(self, page, operator, cancel_event: threading.Event) -> None:
        for label in (
            "Greater than or equal",
            "Greater than or equal to",
            "Is greater than or equal to",
            "More than or equal",
            ">=",
            "≥",
        ):
            try:
                operator.select_option(label=label, timeout=self.TIMEOUT_MS)
                return
            except Exception:
                self._check_cancelled(cancel_event)
                continue
        try:
            operator.click(timeout=self.TIMEOUT_MS)
            options = page.get_by_role("option", name=self.GREATER_OR_EQUAL)
            if options.count() != 1:
                raise RuntimeError("operator option is not unique")
            options.first.click(timeout=self.TIMEOUT_MS)
        except Exception as exc:
            self._check_cancelled(cancel_event)
            raise RuntimeError(
                "Не підтримується жоден варіант operator option "
                "'більше або дорівнює'"
            ) from exc

    def _click_apply(self, container, cancel_event: threading.Event) -> None:
        self._check_cancelled(cancel_event)
        try:
            button = container.get_by_role(
                "button", name=re.compile(r"apply|застосувати", re.IGNORECASE)
            ).first
            button.wait_for(state="visible", timeout=self.TIMEOUT_MS)
            button.click(timeout=self.TIMEOUT_MS)
        except Exception as exc:
            self._check_cancelled(cancel_event)
            raise RuntimeError(
                "Не знайдено або не вдалося натиснути Apply "
                "у фільтрі Marketed Capacity"
            ) from exc
        self._check_cancelled(cancel_event)

    @staticmethod
    def _check_cancelled(cancel_event: threading.Event) -> None:
        if cancel_event.is_set():
            raise _LaunchCancelled()


class BrowserController:
    """Opens PRISMA in installed Chrome or Edge and owns that session."""

    def __init__(self, page_filter: PrismaAuctionFilter | None = None) -> None:
        self._playwright = None
        self._browser = None
        self._thread: threading.Thread | None = None
        self._lock = threading.RLock()
        self._state = BrowserState.IDLE
        self._generation = 0
        self._cancel_event: threading.Event | None = None
        self._results: queue.SimpleQueue[LaunchResult] = queue.SimpleQueue()
        self.last_error: str | None = None
        self._page_filter = page_filter or PrismaAuctionFilter()

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
            try:
                self._page_filter.apply(page, cancel_event)
            except _LaunchCancelled:
                return
            except Exception as exc:
                reason = str(exc).strip() or exc.__class__.__name__
                raise RuntimeError(
                    "Не вдалося встановити фільтр "
                    f"Marketed Capacity >= 1000: {reason}"
                ) from exc

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
        except _LaunchCancelled:
            pass
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
