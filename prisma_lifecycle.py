from __future__ import annotations

import logging
import queue
import threading
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from browser import PRISMA_AUCTIONS_URL as PRISMA_OFFICIAL_URL
from browser import DefaultBrowserDetector, _ensure_subprocess_output_streams
from date_range_selection import DateRange
from prisma_download import (
    PrismaDownloadOrchestrator,
    describe_download_failure,
)
from runtime_logging import LOGGER_NAME, safe_log

__all__ = [
    "PRISMA_OFFICIAL_URL",
    "PrismaLifecycleState",
    "PrismaLifecycleEvent",
    "PrismaLifecycleController",
]


class PrismaLifecycleState(str, Enum):
    IDLE = "idle"
    OPENING = "opening"
    OPEN = "open"
    CLOSING = "closing"
    CLOSE_FAILED = "close_failed"


@dataclass(frozen=True)
class PrismaLifecycleEvent:
    generation: int
    success: bool
    error: str | None = None
    kind: str = "open"
    csv_path: Path | None = None


class PrismaLifecycleController:
    """Owns exactly one application-managed PRISMA browser session.

    Opening always navigates to the approved official PRISMA URL first. No
    login is ever automated. When a date range and download directory are
    supplied (P.36.14, corrected 2026-08-02), opening additionally fills
    PRISMA's own date filter, applies it, and activates PRISMA's own CSV
    download control itself — the user never presses anything on the PRISMA
    website; pressing the single in-application action is the entire user
    interaction. Without those arguments, behavior is unchanged: no
    navigation, filtering, date selection, download, monitoring, or polling
    beyond the approved URL and closure detection is automated. Closing
    releases only browser resources owned by this controller; it never
    targets unrelated browser windows, profiles, sessions, or processes.
    """

    def __init__(self, detector=None, logger=None, download_orchestrator=None) -> None:
        self._detector = detector or DefaultBrowserDetector()
        self._logger = logger or logging.getLogger(LOGGER_NAME)
        self._download_orchestrator = download_orchestrator or PrismaDownloadOrchestrator()
        self._lock = threading.RLock()
        self._state = PrismaLifecycleState.IDLE
        self._generation = 0
        self._cancel_event: threading.Event | None = None
        self._playwright = None
        self._browser = None
        self._thread: threading.Thread | None = None
        self._events: queue.SimpleQueue[PrismaLifecycleEvent] = queue.SimpleQueue()

    def _log(self, level: int, message: str, *args, **kwargs) -> None:
        safe_log(self._logger, level, message, *args, **kwargs)

    @property
    def state(self) -> PrismaLifecycleState:
        with self._lock:
            return self._state

    @property
    def is_open(self) -> bool:
        return self.state is PrismaLifecycleState.OPEN

    def _is_current(self, generation: int) -> bool:
        return generation == self._generation

    def open(
        self,
        *,
        date_range: DateRange | None = None,
        download_directory: Path | None = None,
    ) -> int:
        """Open the approved PRISMA URL in an application-owned browser.

        Repeating this call while a session is already opening, open, still
        closing, or stuck in CLOSE_FAILED (cleanup could not be confirmed) is
        a deterministic no-op: it returns the existing generation and never
        starts a second browser session. A session must reach IDLE (cleanup
        fully complete) before a new one can start.

        When both ``date_range`` and ``download_directory`` are supplied
        (P.36.14, corrected 2026-08-02), after the approved PRISMA URL loads
        the session fills the date filter, applies it, and activates PRISMA's
        own CSV download control itself, then waits (bounded, without
        blocking manual-closure detection) for exactly one resulting CSV
        download, reported as a separate ``kind="download"`` event.
        Precondition validation (missing/invalid date range or directory) is
        the caller's responsibility (`prisma_download.validate_download_configuration`)
        so it can be reported before any browser is launched. Omitting either
        argument preserves the pre-P.36.14 behavior: open the browser with no
        managed download.
        """
        with self._lock:
            if self._state in (
                PrismaLifecycleState.OPENING,
                PrismaLifecycleState.OPEN,
                PrismaLifecycleState.CLOSING,
                PrismaLifecycleState.CLOSE_FAILED,
            ):
                self._log(
                    logging.INFO,
                    "Open Prisma ignored: generation=%s state=%s reason=already-active",
                    self._generation, self._state.value,
                )
                return self._generation
            self._generation += 1
            generation = self._generation
            cancel_event = threading.Event()
            self._cancel_event = cancel_event
            self._state = PrismaLifecycleState.OPENING
        self._log(logging.INFO, "Open Prisma requested: generation=%s", generation)
        thread = threading.Thread(
            target=self._run,
            args=(generation, cancel_event, date_range, download_directory),
            daemon=True, name="prisma-lifecycle",
        )
        self._thread = thread
        thread.start()
        return generation

    def get_events(self) -> list[PrismaLifecycleEvent]:
        events = []
        while True:
            try:
                events.append(self._events.get_nowait())
            except queue.Empty:
                return events

    def close(self) -> None:
        """Signal cancellation of the owned PRISMA session.

        Idempotent when nothing is open, a close is already in progress, or
        a prior close's cleanup could not be confirmed (CLOSE_FAILED).
        Returning from this call does not mean cleanup has finished: the
        state stays CLOSING while the owned browser/Playwright resources are
        released on the background worker thread. It reaches IDLE only if
        that release is confirmed (both `browser.close()` and
        `playwright.stop()` succeed), publishing a typed close-completed
        event (`kind="close"`, `success=True`). If either fails, the owned
        handles are kept (never nulled) and the state moves to CLOSE_FAILED
        instead of IDLE — the failure is never reported as a successful
        closure, and no new session can be opened until this is resolved.
        Call `join()` to wait for the worker deterministically.
        """
        with self._lock:
            if self._state in (
                PrismaLifecycleState.IDLE,
                PrismaLifecycleState.CLOSING,
                PrismaLifecycleState.CLOSE_FAILED,
            ):
                self._log(
                    logging.INFO,
                    "Close Prisma ignored: generation=%s state=%s reason=no-effect",
                    self._generation, self._state.value,
                )
                return
            previous_state = self._state
            self._state = PrismaLifecycleState.CLOSING
            cancel_event = self._cancel_event
        self._log(
            logging.INFO,
            "Close Prisma requested: generation=%s state_before=%s",
            self._generation, previous_state.value,
        )
        if cancel_event is not None:
            cancel_event.set()

    def join(self, timeout: float | None = None) -> bool:
        """Wait for the owned lifecycle worker thread to finish.

        Only ever waits on this controller's own background thread, never
        on unrelated threads or processes. Returns True once the worker has
        finished (or if none was ever started); False if `timeout` elapsed
        first.
        """
        thread = self._thread
        if thread is None:
            return True
        thread.join(timeout=timeout)
        return not thread.is_alive()

    def _run(
        self,
        generation: int,
        cancel_event: threading.Event,
        date_range: DateRange | None = None,
        download_directory: Path | None = None,
    ) -> None:
        playwright = None
        browser = None
        page = None
        context = None
        cdp_session = None
        owned_target_id: str | None = None
        launch_error: str | None = None
        announced_success = False
        cleanup_reason = "user-requested shutdown"
        download_waiter = None
        download_deadline: float | None = None
        download_finalized = False
        managed_download = date_range is not None and download_directory is not None

        def mark_manual_closure(source: str) -> None:
            nonlocal cleanup_reason
            with self._lock:
                if not self._is_current(generation):
                    return
                if self._state is PrismaLifecycleState.CLOSING:
                    return
            cleanup_reason = "manual-closure"
            self._log(
                logging.INFO,
                "Prisma manual closure detected: generation=%s source=%s",
                generation, source,
            )
            cancel_event.set()

        def on_browser_disconnected(*_args) -> None:
            mark_manual_closure("browser-disconnected-event")

        def on_page_closed(*_args) -> None:
            mark_manual_closure("page-closed-event")

        def on_context_closed(*_args) -> None:
            mark_manual_closure("context-closed-event")

        def on_target_destroyed(params) -> None:
            target_id = (params or {}).get("targetId")
            if target_id is not None and target_id == owned_target_id:
                mark_manual_closure("owned-target-destroyed-cdp")

        def emit_download_result(result) -> None:
            nonlocal download_finalized
            download_finalized = True
            if download_waiter is not None:
                download_waiter.detach()
            self._log(
                logging.INFO if result.succeeded else logging.WARNING,
                "Managed PRISMA download resolved: generation=%s outcome=%s detail=%s",
                generation, result.outcome.value, result.error,
            )
            self._events.put(PrismaLifecycleEvent(
                generation, result.succeeded,
                None if result.succeeded else describe_download_failure(result.outcome),
                kind="download",
                csv_path=result.csv_path,
            ))

        try:
            _ensure_subprocess_output_streams()
            from playwright.sync_api import sync_playwright

            executable = self._detector.detect_executable()
            self._log(
                logging.INFO,
                "Open Prisma: default browser detected: generation=%s executable=%s",
                generation, executable,
            )
            playwright = sync_playwright().start()
            if cancel_event.is_set():
                return

            launch_kwargs = {
                "executable_path": str(executable), "headless": False,
                "args": ["--start-maximized"],
            }
            if managed_download:
                # Real-Windows defect (2026-08-03): without this, Chrome/CDP's
                # download interception writes the raw artifact into a
                # Playwright-managed temp location under a generated name,
                # never into the folder Prisma Function configured — so the
                # configured directory stayed empty even though Chrome itself
                # showed the download as completed. Setting `downloads_path`
                # forces both the primary Playwright "download" event's
                # backing file and the raw browser-level artifact (observed by
                # `PrismaDownloadFilesystemWaiter` when the event itself is not
                # reliably delivered, see prisma_download.py) into the exact
                # directory the user selected — never Chrome's own default
                # Downloads folder, never an untracked temp directory.
                launch_kwargs["downloads_path"] = str(download_directory)
            browser = playwright.chromium.launch(**launch_kwargs)
            self._log(logging.INFO, "Prisma browser created: generation=%s", generation)
            try:
                browser.on("disconnected", on_browser_disconnected)
            except Exception:
                self._log(
                    logging.WARNING,
                    "Could not attach Prisma browser disconnect handler: generation=%s",
                    generation, exc_info=True,
                )
            with self._lock:
                if not self._is_current(generation):
                    return
                self._playwright = playwright
                self._browser = browser
            if cancel_event.is_set():
                return

            page = browser.new_page(no_viewport=True)
            context = page.context
            try:
                page.on("close", on_page_closed)
            except Exception:
                self._log(
                    logging.WARNING,
                    "Could not attach Prisma page close handler: generation=%s",
                    generation, exc_info=True,
                )
            try:
                context.on("close", on_context_closed)
            except Exception:
                self._log(
                    logging.WARNING,
                    "Could not attach Prisma context close handler: generation=%s",
                    generation, exc_info=True,
                )
            # The CDP Target.targetDestroyed event for the owned page's target
            # is an independent, lower-level ground-truth signal, layered on
            # top of the Playwright-level page/context/browser signals above:
            # real Windows X-button validation showed those alone were not
            # always sufficient (see workflow_p.md P.36.2 real-runtime
            # evidence log).
            try:
                cdp_session = browser.new_browser_cdp_session()
                cdp_session.send("Target.setDiscoverTargets", {"discover": True})
                cdp_session.on("Target.targetDestroyed", on_target_destroyed)
                targets = cdp_session.send("Target.getTargets") or {}
                page_target_ids = [
                    info.get("targetId")
                    for info in targets.get("targetInfos", [])
                    if info.get("type") == "page" and info.get("targetId")
                ]
                if len(page_target_ids) == 1:
                    owned_target_id = page_target_ids[0]
                else:
                    self._log(
                        logging.WARNING,
                        "Prisma CDP target correlation ambiguous: generation=%s "
                        "page_target_count=%s",
                        generation, len(page_target_ids),
                    )
            except Exception:
                cdp_session = None
                self._log(
                    logging.WARNING,
                    "Could not attach Prisma CDP target session: generation=%s",
                    generation, exc_info=True,
                )
            page.goto(PRISMA_OFFICIAL_URL, wait_until="domcontentloaded")
            self._log(
                logging.INFO,
                "Open Prisma: navigation completed: generation=%s url=%s",
                generation, PRISMA_OFFICIAL_URL,
            )

            if managed_download:
                if cancel_event.is_set():
                    return
                download_waiter = self._download_orchestrator.configure(
                    page, date_range, download_directory,
                )
                download_deadline = (
                    time.monotonic() + self._download_orchestrator.timeout_seconds
                )
                self._log(
                    logging.INFO,
                    "Open Prisma: managed download configured: generation=%s",
                    generation,
                )

            with self._lock:
                if (
                    self._is_current(generation)
                    and self._state is PrismaLifecycleState.OPENING
                    and not cancel_event.is_set()
                ):
                    self._state = PrismaLifecycleState.OPEN
                    announced_success = True
                    self._events.put(PrismaLifecycleEvent(generation, True, kind="open"))

            if not announced_success:
                return

            while not cancel_event.wait(0.1):
                if managed_download and not download_finalized:
                    result = self._download_orchestrator.await_and_finalize(
                        download_waiter, date_range, download_directory,
                        cancel_event, deadline=download_deadline,
                    )
                    if result is not None:
                        emit_download_result(result)
                try:
                    page_closed = page.is_closed()
                except Exception:
                    page_closed = True
                if page_closed:
                    mark_manual_closure("page-closed-poll")
                    break
                try:
                    browser_connected = browser.is_connected()
                except Exception:
                    browser_connected = False
                if not browser_connected:
                    mark_manual_closure("browser-disconnected-poll")
                    break
        except Exception as exc:
            launch_error = str(exc).strip() or exc.__class__.__name__
            self._log(
                logging.ERROR, "Open Prisma failed: generation=%s", generation,
                exc_info=True,
            )
        finally:
            # Catch-all listener cleanup: emit_download_result() above already
            # detaches on a resolved outcome (success/timeout/typed failure);
            # this covers every other exit path (cancellation or browser
            # close before the download ever resolved, and configure()/
            # navigation errors). detach() is idempotent, so calling it here
            # unconditionally is always safe.
            if download_waiter is not None:
                download_waiter.detach()
            cleanup_failed = False
            if browser is not None:
                try:
                    browser.close()
                except Exception:
                    cleanup_failed = True
                    self._log(
                        logging.WARNING, "Prisma browser cleanup failed: generation=%s",
                        generation, exc_info=True,
                    )
            if playwright is not None:
                try:
                    playwright.stop()
                except Exception:
                    cleanup_failed = True
                    self._log(
                        logging.WARNING,
                        "Prisma playwright cleanup failed: generation=%s",
                        generation, exc_info=True,
                    )
            with self._lock:
                if self._is_current(generation):
                    if launch_error and not announced_success:
                        self._browser = None
                        self._playwright = None
                        self._cancel_event = None
                        self._state = PrismaLifecycleState.IDLE
                        self._events.put(
                            PrismaLifecycleEvent(generation, False, launch_error, kind="open")
                        )
                    elif cleanup_reason == "manual-closure":
                        self._browser = None
                        self._playwright = None
                        self._cancel_event = None
                        self._state = PrismaLifecycleState.IDLE
                        self._events.put(PrismaLifecycleEvent(
                            generation, False,
                            "The PRISMA browser was closed manually.", kind="closed",
                        ))
                    elif cleanup_failed:
                        # Ownership is not relinquished: browser.close() or
                        # playwright.stop() failed, so the owned browser may
                        # still be alive. Keep the handles and stay out of
                        # IDLE so no new session can start and shutdown
                        # cannot silently proceed while this is unresolved.
                        self._cancel_event = None
                        self._state = PrismaLifecycleState.CLOSE_FAILED
                        self._events.put(PrismaLifecycleEvent(
                            generation, False,
                            "The PRISMA browser could not be confirmed closed.",
                            kind="close",
                        ))
                    else:
                        self._browser = None
                        self._playwright = None
                        self._cancel_event = None
                        self._state = PrismaLifecycleState.IDLE
                        self._events.put(
                            PrismaLifecycleEvent(generation, True, kind="close")
                        )
            self._log(
                logging.INFO,
                "Prisma cleanup completed: generation=%s state=%s classification=%s "
                "cleanup_failed=%s",
                generation, self.state.value, cleanup_reason, cleanup_failed,
            )
