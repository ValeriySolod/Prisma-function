"""Qt-independent P.36.14 managed-download orchestration.

Per the approved P.36.14 decision gate (see `ROADMAP.md`, corrected
2026-08-02), PrismaFunction fills the selected date range into PRISMA's own
"Start of Auction" date filter on the already-open PRISMA Auctions page,
applies the filter, then activates PRISMA's own CSV download control itself
— the user never presses anything on the PRISMA website. The single
in-application "Open Prisma"/CSV-download action drives the entire sequence:
open the managed browser, navigate, fill the dates, apply the filter, and
click the CSV control. This module recognizes the resulting Playwright
"download" event and saves the single accepted file into the selected
directory under the approved naming/collision rule.

This module is intentionally split from `prisma_lifecycle.py`:
`PrismaLifecycleController` owns the single application-managed Playwright
page/thread and drives the bounded wait loop (reusing its existing
generation/cancellation machinery); this module supplies the reusable,
independently testable business logic — configuration validation, PRISMA page
automation, and typed download outcomes — so that logic is not entangled with
UI code or with lifecycle/thread bookkeeping.

`DEFAULT_REPORTING_URL` is not a second URL: the approved PRISMA reporting
page for short-and-long-term auctions is the same page `PrismaLifecycleController`
already opens (`browser.PRISMA_AUCTIONS_URL`), so this module imports that one
canonical constant rather than defining its own literal (see `ROADMAP.md`'s
P.36.14 real-validation correction). It is exposed only as documentation of
the canonical URL; `configure()` performs no second navigation — a real-site
validation attempt proved the "reporting page" is the same page already open,
so a second `page.goto()` would only be a redundant reload.

The date-filter control contract below (the "Active Filter:" panel toggle,
`data-testid="startOfAuctionFrom"`/`"startOfAuctionTo"` masked date-time
inputs, and the "Filter" apply button) was determined by live DOM inspection
of the real, currently-active PRISMA Platform design — not guessed — and a
live fill/read-back experiment confirmed the exact fill and verification
strategy; see `ROADMAP.md`'s P.36.14 real-validation record for the full
evidence. This module does not support a second/legacy PRISMA design: the
live site was confirmed to be serving only the current design at validation
time (see `ROADMAP.md`); if a future redesign changes this contract, the
typed `PrismaDateFilterPanelError`/`PrismaDateFilterControlsNotFoundError`
failures below are the intended signal, not a silent fallback.

After "Filter" is clicked, `configure()` additionally verifies the applied
state from an independent, stronger signal than the per-field fill
verification above: live DOM inspection (2026-08-02) found PRISMA echoes the
active range back into a dedicated filter-chip element
(`data-testid="filter-startOfAuctionFrom"`, e.g. "Start of Auction 01.08.2026,
00:00 - 02.08.2026, 23:59"), which proves the results were actually
re-filtered rather than merely that the inputs accepted typed text. A visible
`role="alert"` element at that point is treated as a validation error and
fails the attempt, matching the failure mode observed on an unsupported page
state where PRISMA itself rejected the filter (see `ROADMAP.md`).

Live inspection also found PRISMA shows its own confirmation dialog
(`role="dialog"`, heading "Warning", body text matching "contains only N of M
items") when the filtered result set exceeds its export limit. This is a
normal part of the export flow, not an error: `configure()` waits briefly for
it after activating the CSV control and, if present, clicks its own
dialog-scoped "CSV" button (same accessible name as the main control, but
never confused with it since the locator is scoped to the dialog) to proceed
with the truncated export. Absence within the bounded wait is the normal case
for a sufficiently narrow date range. The download listener is registered on
the context before the main CSV control is ever clicked, so the resulting
download event — whether triggered directly or via this confirmation — can
never be missed.

**Approved production fallback (2026-08-03 customer decision).** Driving the
real installed Chrome/Edge executable was found not to reliably deliver
Playwright's `"download"` event to the controlling process, even though the
browser's own UI confirms the download completed (see `ROADMAP.md`'s P.36.14
real-Chrome download-event delivery gap). The Playwright event above remains
the primary mechanism; `PrismaDownloadFilesystemWaiter` is a bounded,
cancellable fallback that is only ever consulted once the Playwright event has
not (yet) fired. `configure()` snapshots the configured download directory
(non-recursive, top-level only) immediately before activating the CSV control;
`await_and_finalize()` then polls that snapshot for exactly one new,
non-partial file whose size has stabilized across multiple checks, is
non-empty, and can be opened for reading, and finalizes it through the same
naming/collision rule as the primary path, always with a forced `.csv`
extension. Zero, multiple, and still-partial files are never accepted as a
result.

**Real-Windows defect fix (2026-08-03): the fallback observed an empty
directory.** Live Windows evidence found that even with the fallback above in
place, `chrome://downloads` showed the PRISMA export completed under a
temporary, browser/CDP-generated (UUID-like) name, while the configured
download directory stayed empty. Root cause: `playwright.chromium.launch()`
was never given a `downloads_path`, so Chrome's CDP-driven download
interception ("allowAndName" behavior) wrote the raw artifact into a
Playwright-managed temp location that has no relationship to the directory the
user selected — the fallback above was watching the *right* directory but the
browser was writing to a *different* one. `PrismaLifecycleController._run()`
now passes `downloads_path=str(download_directory)` to `launch()` whenever a
managed download is requested, so the raw artifact (whether captured via the
Playwright event or observed only via the fallback) always lands directly in
the configured directory, never Chrome's own default Downloads folder and
never an untracked temp directory. Because that raw artifact is
browser/CDP-named (typically UUID-like, not `.csv`), `poll()` no longer
requires a `.csv` suffix to recognize a candidate — any newly appeared,
non-partial file in the configured directory is now a candidate, with
completion still decided purely by size stability and successful read, never
by name; the final `.csv` extension is always forced when the file is renamed
into place, regardless of the raw artifact's own name.
"""
from __future__ import annotations

import os
import re
import threading
import time
from dataclasses import dataclass
from datetime import date as _date
from enum import Enum
from pathlib import Path

from browser import PRISMA_AUCTIONS_URL
from date_range_selection import DateRange
from prisma_page import (
    PrismaAuthenticationRequiredError,
    PrismaInvalidSessionError,
    PrismaSessionValidator,
)

__all__ = [
    "DEFAULT_REPORTING_URL",
    "DEFAULT_DOWNLOAD_TIMEOUT_SECONDS",
    "PrismaDownloadValidationOutcome",
    "validate_download_configuration",
    "describe_validation_rejection",
    "PrismaDownloadOutcome",
    "PrismaDownloadResult",
    "describe_download_failure",
    "build_dated_filename",
    "reserve_unique_download_path",
    "PrismaDownloadWaiter",
    "PrismaDownloadFilesystemWaiter",
    "PrismaDownloadOrchestrator",
    "PrismaAuthenticationRequiredError",
    "PrismaInvalidSessionError",
    "PrismaDateFilterPanelError",
    "PrismaDateFilterControlsNotFoundError",
    "PrismaDateValueRejectedError",
    "PrismaDownloadListenerError",
    "PrismaDownloadControlError",
    "PrismaCookieConsentBannerError",
    "PrismaLargeResultConfirmationError",
]

# Single canonical source: the approved reporting page is the same page
# PrismaLifecycleController already opens. Do not redefine this as a separate
# literal or reintroduce a second navigation to it.
DEFAULT_REPORTING_URL = PRISMA_AUCTIONS_URL
DEFAULT_DOWNLOAD_TIMEOUT_SECONDS = 600.0
_POLL_INTERVAL_SECONDS = 0.1
_CONTROL_TIMEOUT_MS = 10_000

# Real, live-verified control contract (see module docstring). The "Active
# Filter:" toggle is the same collapsed-filter-panel control `PrismaAuctionFilter`
# in browser.py already opens for the unrelated Marketed Capacity field on this
# same page; the "Filter" apply button is the same pattern. The CSV download
# control is a plain `<button type="button">CSV</button>` with no test id or
# ARIA attributes (confirmed present both before and after the filter panel is
# opened, alongside an unrelated "PDF" button of the same shape) — its
# accessible name is the exact visible text "CSV", computed natively from the
# button's own text content, so an exact accessible-name role locator is the
# most stable selector available (priority 2: no test id exists for it).
_ACTIVE_FILTER_TOGGLE = re.compile(r"^Active\s+Filter:", re.IGNORECASE)
_FILTER_APPLY_BUTTON = re.compile(r"^Filter$", re.IGNORECASE)
_CSV_DOWNLOAD_BUTTON_NAME = "CSV"
_START_OF_AUCTION_FROM_TEST_ID = "startOfAuctionFrom"
_START_OF_AUCTION_TO_TEST_ID = "startOfAuctionTo"
# Live DOM inspection (2026-08-02, re-verified against the live site) found
# the applied "Start of Auction" range is echoed back into a dedicated
# filter-chip element once "Filter" is clicked, independent of the two input
# fields checked during fill.
_APPLIED_FILTER_CHIP_TEST_ID = "filter-startOfAuctionFrom"
# Bounded tolerance for the chip's own re-render lag behind the "Filter"
# click (see `_verify_filter_applied`'s docstring); longer than the other
# short detect-timeouts above because this check is required, not
# best-effort.
_FILTER_CHIP_VERIFY_TIMEOUT_MS = 5_000
# Live DOM inspection (2026-08-02) found PRISMA's own large-export
# confirmation dialog: `role="dialog"`, heading "Warning", body text "Your
# download contains only 5000 of 11667 items." (exact counts vary). The
# dialog exposes its own "CSV" confirm button with no test id or ARIA
# attribute distinguishing it from the main page control, so it is located
# via an exact accessible-name role locator scoped to the dialog itself.
_LARGE_RESULT_MODAL_TEXT_PATTERN = re.compile(
    r"contains only\s+[\d,]+\s+of\s+[\d,]+\s+items", re.IGNORECASE
)
_LARGE_RESULT_MODAL_DETECT_TIMEOUT_MS = 3_000
# Live DOM inspection (2026-08-02, headless fetch of the real public page)
# found PRISMA's fixed-bottom usability-research/cookie-consent banner has no
# test id or ARIA landmark either: its heading is "Take part in PRISMA
# usability research" and it offers two plain, unattributed <button>/<a>
# controls with these exact visible texts. Neither is guaranteed present on
# every session (Playwright launches a fresh, cookie-less browser context
# each time, so this banner is expected on effectively every managed-download
# attempt, but its absence is still treated as normal). "Decline" is tried
# first (an automated tool should not opt a human user into usability-research
# data collection on their behalf); "Accept & Close" is a fallback for a
# hypothetical banner variant that offers only a single accept-style control.
_COOKIE_BANNER_DISMISS_BUTTON_NAMES: tuple[str, ...] = ("Decline", "Accept & Close")
_COOKIE_BANNER_DETECT_TIMEOUT_MS = 3_000
# Inclusive whole-day bounds: the auction's own "Start of Auction" instant is
# a specific time of day (e.g. 06:00 for the observed default), so the
# selected calendar date range must be widened to a full-day window on both
# ends to include every auction starting anywhere within it.
_FILTER_START_TIME = "00:00"
_FILTER_END_TIME = "23:59"

# Approved production fallback (see module docstring): bounded filesystem
# observation for when the real installed Chrome/Edge executable completes a
# download without Playwright's own "download" event ever being observed.
# Chrome names an in-progress download "<final-name>.crdownload"; Edge/other
# Chromium-based browsers follow the same convention.
_FILESYSTEM_PARTIAL_SUFFIXES = (".crdownload",)
# Number of consecutive polls (at the caller's existing ~0.1s poll interval,
# the same cadence already used for the Playwright-event path) with an
# unchanged file size required before a candidate is considered stable.
_FILESYSTEM_STABILITY_CHECKS = 3
# Consecutive polls with no partial and no completed candidate, after a
# partial was previously observed, required before classifying the download
# as interrupted. This debounces the brief instant a browser's rename from
# "*.crdownload" to the final name can appear as neither file existing.
_FILESYSTEM_INTERRUPTED_GRACE_POLLS = 3


class PrismaDateFilterPanelError(RuntimeError):
    """The PRISMA "Active Filter" panel could not be opened or applied."""


class PrismaDateFilterControlsNotFoundError(RuntimeError):
    """The PRISMA "Start of Auction" date-range controls could not be located."""


class PrismaDateValueRejectedError(RuntimeError):
    """A filled date value was not accepted by the real PRISMA page."""


class PrismaDownloadListenerError(RuntimeError):
    """The Playwright download listener could not be registered."""


class PrismaDownloadControlError(RuntimeError):
    """The PRISMA CSV download control could not be located or activated."""


class PrismaCookieConsentBannerError(RuntimeError):
    """PRISMA's cookie-consent/usability-research banner blocked the CSV control
    and could not be dismissed through its own visible user control."""


class PrismaLargeResultConfirmationError(RuntimeError):
    """PRISMA's large-result confirmation dialog appeared but could not be
    confirmed through its own visible "CSV" control."""


class PrismaDownloadValidationOutcome(str, Enum):
    """Typed outcome of validating a candidate download configuration."""

    ACCEPTED = "accepted"
    MISSING_DATE_RANGE = "missing_date_range"
    MISSING_DOWNLOAD_DIRECTORY = "missing_download_directory"
    INVALID_DOWNLOAD_DIRECTORY = "invalid_download_directory"


_VALIDATION_MESSAGES: dict[PrismaDownloadValidationOutcome, str] = {
    PrismaDownloadValidationOutcome.MISSING_DATE_RANGE: (
        "Select and validate a date range before opening PRISMA."
    ),
    PrismaDownloadValidationOutcome.MISSING_DOWNLOAD_DIRECTORY: (
        "Choose a download folder before opening PRISMA."
    ),
    PrismaDownloadValidationOutcome.INVALID_DOWNLOAD_DIRECTORY: (
        "The selected download folder is not valid. Choose an existing, "
        "writable folder."
    ),
}


def describe_validation_rejection(outcome: PrismaDownloadValidationOutcome) -> str:
    """Return a stable, English message for a rejected configuration."""
    return _VALIDATION_MESSAGES.get(
        outcome, "PRISMA could not be opened with the current configuration."
    )


def validate_download_configuration(
    date_range: DateRange | None, download_directory: str | Path | None
) -> PrismaDownloadValidationOutcome:
    """Validate the two preconditions Open Prisma requires (P.36.14).

    Checks run in a fixed order — missing date range, then missing directory,
    then directory validity — so a candidate missing both deterministically
    reports `MISSING_DATE_RANGE`. Performs no browser, Playwright, or
    filesystem-write operation; only a read-only existence/writability check.
    """
    if date_range is None:
        return PrismaDownloadValidationOutcome.MISSING_DATE_RANGE
    if download_directory is None:
        return PrismaDownloadValidationOutcome.MISSING_DOWNLOAD_DIRECTORY
    path = Path(download_directory)
    if not path.is_dir() or not os.access(path, os.W_OK):
        return PrismaDownloadValidationOutcome.INVALID_DOWNLOAD_DIRECTORY
    return PrismaDownloadValidationOutcome.ACCEPTED


class PrismaDownloadOutcome(str, Enum):
    """Typed outcome of one managed PRISMA CSV download attempt.

    Only covers the post-`configure()` download-detection phase (steps 9-13:
    the browser is already correctly configured and under user control).
    Pre-configuration failures (session/authentication, filter panel, date
    controls, rejected date values, listener registration, download-control
    activation) are raised as specific exceptions from `configure()` instead
    — see `PrismaAuthenticationRequiredError`, `PrismaInvalidSessionError`,
    `PrismaDateFilterPanelError`, `PrismaDateFilterControlsNotFoundError`,
    `PrismaDateValueRejectedError`, `PrismaDownloadListenerError`, and
    `PrismaDownloadControlError` — since that phase has a natural caller to
    propagate to, unlike the polled download-wait phase below, which needs a
    typed result object.
    """

    SUCCESS = "success"
    DOWNLOAD_TIMEOUT = "download_timeout"
    DOWNLOAD_CANCELLED = "download_cancelled"
    DOWNLOAD_INTERRUPTED = "download_interrupted"
    NOT_CSV = "not_csv"
    SAVE_FAILED = "save_failed"
    MULTIPLE_DOWNLOADS = "multiple_downloads"


_FAILURE_MESSAGES: dict[PrismaDownloadOutcome, str] = {
    PrismaDownloadOutcome.DOWNLOAD_TIMEOUT: (
        "PRISMA did not deliver the requested CSV download in time. Try again."
    ),
    PrismaDownloadOutcome.DOWNLOAD_CANCELLED: (
        "The PRISMA CSV download was cancelled."
    ),
    PrismaDownloadOutcome.DOWNLOAD_INTERRUPTED: (
        "The PRISMA CSV download was interrupted before it completed."
    ),
    PrismaDownloadOutcome.NOT_CSV: (
        "PRISMA did not offer a CSV file for download."
    ),
    PrismaDownloadOutcome.SAVE_FAILED: (
        "The downloaded PRISMA CSV could not be saved to the selected folder."
    ),
    PrismaDownloadOutcome.MULTIPLE_DOWNLOADS: (
        "PRISMA started more than one CSV download. Only one download is "
        "accepted; try again."
    ),
}


def describe_download_failure(outcome: PrismaDownloadOutcome) -> str:
    """Return a stable, English, path-free message for a failed outcome."""
    return _FAILURE_MESSAGES.get(outcome, "The PRISMA CSV download failed.")


@dataclass(frozen=True)
class PrismaDownloadResult:
    """Immutable typed outcome of one managed PRISMA CSV download attempt."""

    outcome: PrismaDownloadOutcome
    csv_path: Path | None = None
    error: str | None = None

    @property
    def succeeded(self) -> bool:
        return self.outcome is PrismaDownloadOutcome.SUCCESS


def build_dated_filename(original_filename: str, date_range: DateRange) -> str:
    """Apply the approved P.36.14 naming rule: ``<stem>_<start>_<end><suffix>``."""
    original = Path(original_filename)
    suffix = original.suffix or ".csv"
    return (
        f"{original.stem}_{date_range.start.isoformat()}_"
        f"{date_range.end.isoformat()}{suffix}"
    )


def reserve_unique_download_path(directory: str | Path, filename: str) -> Path:
    """Atomically reserve a non-colliding path for ``filename`` in ``directory``.

    Per the approved P.36.14 decision gate, a name collision is resolved with
    an incrementing numeric suffix (``_2``, ``_3``, ...) and an existing file
    is never overwritten. Reservation uses exclusive file creation
    (`os.O_CREAT | os.O_EXCL`) so the chosen name cannot be silently claimed
    by a concurrent writer between the existence check and the reservation;
    the returned path is a zero-byte placeholder this call created, which the
    caller (`PrismaDownloadOrchestrator`) then overwrites with the actual
    download.
    """
    base = Path(directory)
    stem = Path(filename).stem
    suffix = Path(filename).suffix
    candidate = base / filename
    attempt = 1
    while True:
        try:
            handle = os.open(str(candidate), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            attempt += 1
            candidate = base / f"{stem}_{attempt}{suffix}"
            continue
        os.close(handle)
        return candidate


def _safe_cancel_download(download) -> None:
    cancel = getattr(download, "cancel", None)
    if callable(cancel):
        try:
            cancel()
        except Exception:
            pass


class PrismaDownloadWaiter:
    """Captures at most one Playwright "download" event, registered on the
    owned BrowserContext (not a single page) so downloads originating from a
    newly opened page/tab within the same context are observed too (see
    module docstring: the real PRISMA CSV export was found to open its
    download in a new browser tab, not the originating page).

    A second (or later) download event is rejected explicitly rather than
    silently ignored: it is best-effort cancelled immediately and recorded
    via `multiple`, which `PrismaDownloadOrchestrator._finalize()` checks
    before reporting success, so at most one download is ever accepted.
    """

    def __init__(self) -> None:
        self.event = threading.Event()
        self.download = None
        self.multiple = False
        self._lock = threading.Lock()
        self._context = None
        self._detached = False
        # Set by `PrismaDownloadOrchestrator.configure()` when a download
        # directory is supplied; stays `None` (fallback disabled) otherwise,
        # matching pre-fallback behavior exactly.
        self.filesystem_fallback: "PrismaDownloadFilesystemWaiter | None" = None

    def attach(self, context) -> None:
        """Record the BrowserContext this waiter's listener is registered on,
        so `detach()` can remove it deterministically later."""
        self._context = context

    def on_download(self, download) -> None:
        with self._lock:
            if self.download is None:
                self.download = download
                self.event.set()
                return
            self.multiple = True
        _safe_cancel_download(download)

    def detach(self) -> None:
        """Idempotently remove this waiter's context-level "download" listener.

        Safe to call multiple times and from any outcome path (success,
        timeout, cancellation, browser close, error): only the first call
        does anything.
        """
        with self._lock:
            if self._detached:
                return
            self._detached = True
            context = self._context
        if context is None:
            return
        remove = getattr(context, "remove_listener", None)
        if callable(remove):
            try:
                remove("download", self.on_download)
            except Exception:
                pass


class _FilesystemPollOutcome(str, Enum):
    """Internal, per-poll outcome of `PrismaDownloadFilesystemWaiter.poll()`."""

    NOT_READY = "not_ready"
    READY = "ready"
    MULTIPLE = "multiple"
    INTERRUPTED = "interrupted"


@dataclass(frozen=True)
class _FilesystemPollResult:
    outcome: _FilesystemPollOutcome
    path: Path | None = None


class PrismaDownloadFilesystemWaiter:
    """Bounded, cancellable filesystem-observation fallback for the approved
    production gap where the real installed Chrome/Edge executable completes
    a CSV download but no Playwright `"download"` event is ever observed by
    the controlling process (see module docstring's "Approved production
    fallback" section and `ROADMAP.md`'s P.36.14 real-Chrome download-event
    delivery gap).

    This is a fallback only: the Playwright `"download"` event remains the
    primary mechanism and `PrismaDownloadOrchestrator.await_and_finalize()`
    always checks it first. This waiter never scans outside the single
    configured download directory (non-recursive, top-level `iterdir()`
    only) and only ever considers files created strictly after `snapshot()`
    was taken — a pre-existing file is never a candidate.
    """

    def __init__(self, directory: Path, existing_names: frozenset[str]) -> None:
        self._directory = directory
        self._existing_names = existing_names
        self._candidate: Path | None = None
        self._last_size: int | None = None
        self._stable_count = 0
        self._activity_seen = False
        self._missing_after_partial_count = 0

    @classmethod
    def snapshot(
        cls, directory: str | Path
    ) -> "PrismaDownloadFilesystemWaiter":
        """Record the directory's current contents before the CSV download
        control is activated, so later polls can identify strictly new
        files. A directory that cannot be listed yields an empty snapshot
        (every subsequently found file is then treated as new) rather than
        raising, since this is a best-effort fallback layered on top of the
        primary Playwright-event mechanism.
        """
        directory_path = Path(directory)
        try:
            existing = frozenset(entry.name for entry in directory_path.iterdir())
        except OSError:
            existing = frozenset()
        return cls(directory_path, existing)

    def poll(self) -> _FilesystemPollResult:
        """Non-blocking: inspect the configured directory's current state and
        return one poll's outcome. Never sleeps or waits; the caller is
        expected to call this repeatedly at its own existing poll cadence.

        Real-Windows defect (2026-08-03): a candidate was previously only
        recognized by a literal ``.csv`` suffix. Live evidence found real
        Chrome/CDP download interception ("allowAndName" behavior) writes the
        raw artifact under a framework-generated, UUID-like name with no
        reliable extension — never necessarily ``.csv`` — so a genuine
        completed download could sit in the configured directory forever,
        unrecognized by name. Any newly appeared, non-partial file is now a
        candidate; genuine completion is still decided the same way as
        before — size stability across `_FILESYSTEM_STABILITY_CHECKS` polls
        plus a successful open-for-read — never by name alone. The final
        `.csv` extension is guaranteed later, in `_finalize_from_filesystem`,
        regardless of what this raw artifact happens to be named.
        """
        try:
            entries = list(self._directory.iterdir())
        except OSError:
            return _FilesystemPollResult(_FilesystemPollOutcome.NOT_READY)

        new_files = [
            entry for entry in entries
            if entry.name not in self._existing_names and entry.is_file()
        ]
        partials = [
            entry for entry in new_files
            if entry.name.lower().endswith(_FILESYSTEM_PARTIAL_SUFFIXES)
        ]
        candidates = [entry for entry in new_files if entry not in partials]

        if partials or candidates:
            self._activity_seen = True

        if len(candidates) > 1:
            return _FilesystemPollResult(_FilesystemPollOutcome.MULTIPLE)
        if len(candidates) == 1:
            self._missing_after_partial_count = 0
            return self._poll_candidate(candidates[0])

        self._candidate = None
        self._last_size = None
        self._stable_count = 0
        if self._activity_seen and not partials:
            self._missing_after_partial_count += 1
            if self._missing_after_partial_count >= _FILESYSTEM_INTERRUPTED_GRACE_POLLS:
                return _FilesystemPollResult(_FilesystemPollOutcome.INTERRUPTED)
        else:
            self._missing_after_partial_count = 0
        return _FilesystemPollResult(_FilesystemPollOutcome.NOT_READY)

    def _poll_candidate(self, entry: Path) -> _FilesystemPollResult:
        if self._candidate != entry:
            self._candidate = entry
            self._last_size = None
            self._stable_count = 0
        try:
            size = entry.stat().st_size
        except OSError:
            self._stable_count = 0
            return _FilesystemPollResult(_FilesystemPollOutcome.NOT_READY)
        if self._last_size is not None and size == self._last_size:
            self._stable_count += 1
        else:
            self._stable_count = 1
        self._last_size = size
        if self._stable_count < _FILESYSTEM_STABILITY_CHECKS:
            return _FilesystemPollResult(_FilesystemPollOutcome.NOT_READY)
        try:
            with open(entry, "rb"):
                pass
        except OSError:
            self._stable_count = 0
            return _FilesystemPollResult(_FilesystemPollOutcome.NOT_READY)
        if size == 0:
            # A stable, readable, but empty artifact never received any
            # content: the download did not actually complete, even though
            # the file itself stopped changing. Never accepted as a result.
            return _FilesystemPollResult(_FilesystemPollOutcome.INTERRUPTED)
        return _FilesystemPollResult(_FilesystemPollOutcome.READY, path=entry)


class PrismaDownloadOrchestrator:
    """Prepares the PRISMA reporting page and triggers one application-initiated download.

    `configure()` and `await_and_finalize()` are the two synchronous,
    independently testable steps; the bounded wait between them (steps 9-12 of
    the P.36.14 workflow: the browser stays open while the already-activated
    PRISMA download is delivered) is driven by the caller
    (`PrismaLifecycleController`) so it can share the same cancellation and
    manual-closure polling loop already used for the rest of the owned
    session, instead of a second competing wait mechanism.
    """

    def __init__(
        self,
        *,
        timeout_seconds: float = DEFAULT_DOWNLOAD_TIMEOUT_SECONDS,
        session_validator: PrismaSessionValidator | None = None,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self._session_validator = session_validator or PrismaSessionValidator()

    def configure(
        self,
        page,
        date_range: DateRange,
        download_directory: str | Path | None = None,
    ) -> PrismaDownloadWaiter:
        """Verify the session, open the real Active Filter panel, fill and
        verify the Start of Auction date range, apply it, then register the
        download listener and activate PRISMA's own CSV download control.

        No navigation happens here: the already-open PRISMA Auctions page
        *is* the reporting page (see module docstring). The download listener
        is registered on the owned BrowserContext (not the page) strictly
        before the cookie-consent banner is handled and the CSV control is
        clicked, so the resulting Playwright "download" event — including one
        delivered on a newly opened tab, since the real CSV export was found
        to open in a new tab rather than the originating page — can never be
        missed. Each failure mode raises a specific, precise exception (never
        a raw Playwright timeout); the caller treats any of them identically
        to a navigation failure (the whole Open Prisma attempt fails) per the
        P.36.14 validation contract, while the distinct type/message remains
        available for logging and tests.

        When ``download_directory`` is supplied, the approved production
        fallback (see module docstring) snapshots that directory's current
        contents immediately before the CSV control is activated, strictly
        after the Playwright listener is registered, so `await_and_finalize()`
        can later recognize a genuinely new file even if it never observes a
        listener callback. Omitting ``download_directory`` (the default)
        leaves the fallback disabled, matching pre-fallback behavior exactly.
        """
        self._session_validator.validate(page)
        self._open_filter_panel(page)
        from_field, to_field = self._locate_date_fields(page)
        self._fill_field(from_field, date_range.start, _FILTER_START_TIME, "start")
        self._fill_field(to_field, date_range.end, _FILTER_END_TIME, "end")
        self._apply_filter(page)
        self._verify_filter_applied(page, date_range)
        download_button = self._locate_download_control(page)
        self._dismiss_cookie_consent_banner(page)
        self._ensure_control_not_obstructed(download_button)
        context = page.context
        waiter = PrismaDownloadWaiter()
        waiter.attach(context)
        try:
            context.on("download", waiter.on_download)
        except Exception as exc:
            raise PrismaDownloadListenerError(
                "The PRISMA download listener could not be registered."
            ) from exc
        if download_directory is not None:
            waiter.filesystem_fallback = PrismaDownloadFilesystemWaiter.snapshot(
                download_directory
            )
        self._activate_download_control(download_button)
        self._confirm_large_result_modal_if_present(page)
        return waiter

    def _open_filter_panel(self, page) -> None:
        toggle = page.get_by_role("button", name=_ACTIVE_FILTER_TOGGLE).first
        try:
            toggle.wait_for(state="visible", timeout=_CONTROL_TIMEOUT_MS)
        except Exception as exc:
            raise PrismaDateFilterPanelError(
                "The PRISMA Active Filter panel could not be found."
            ) from exc
        try:
            toggle.click(timeout=_CONTROL_TIMEOUT_MS)
        except Exception as exc:
            raise PrismaDateFilterPanelError(
                "The PRISMA Active Filter panel could not be opened."
            ) from exc

    def _locate_date_fields(self, page):
        from_field = page.get_by_test_id(_START_OF_AUCTION_FROM_TEST_ID)
        to_field = page.get_by_test_id(_START_OF_AUCTION_TO_TEST_ID)
        try:
            from_field.wait_for(state="visible", timeout=_CONTROL_TIMEOUT_MS)
            to_field.wait_for(state="visible", timeout=_CONTROL_TIMEOUT_MS)
        except Exception as exc:
            raise PrismaDateFilterControlsNotFoundError(
                "The PRISMA Start of Auction date-range controls could not be located."
            ) from exc
        return from_field, to_field

    @staticmethod
    def _format_filter_datetime(value: _date, time_of_day: str) -> str:
        return f"{value:%d.%m.%Y} {time_of_day}"

    def _fill_field(self, field, value: _date, time_of_day: str, label: str) -> None:
        text = self._format_filter_datetime(value, time_of_day)
        try:
            field.click(timeout=_CONTROL_TIMEOUT_MS)
            # The "Start of Auction from" field is pre-populated with a
            # default value by PRISMA itself; filling a masked date-time
            # input that already holds a value without first clearing it was
            # live-verified to only update the date segment and leave the
            # time segment stuck at its placeholder ("HH:mm"), which then
            # fails verification. Clearing first makes the fill uniformly
            # reliable whether the field started empty (the "to" field) or
            # pre-populated (the "from" field).
            field.press("Control+A", timeout=_CONTROL_TIMEOUT_MS)
            field.press("Delete", timeout=_CONTROL_TIMEOUT_MS)
            field.fill(text, timeout=_CONTROL_TIMEOUT_MS)
            # Real-Windows defect (2026-08-03): this field is framework-managed
            # (React) rather than a plain uncontrolled `<input>`; Playwright's
            # `fill()` only dispatches an `input` event. Some of this page's
            # controls only commit a typed value into the framework's own
            # state — the state actually serialized into the PRISMA
            # reporting/export request — on blur, matching how a real user
            # commits a field by tabbing or clicking away. Previously nothing
            # forced this before the next field/control was touched, so the
            # masked *display* text could look correct while the framework's
            # committed value silently lagged behind. `el.blur()` performs
            # that same supported interaction deterministically, before
            # verification runs, instead of relying on an incidental later
            # blur from focusing the next control.
            field.evaluate("(el) => el.blur()", timeout=_CONTROL_TIMEOUT_MS)
        except Exception as exc:
            raise PrismaDateValueRejectedError(
                f"The PRISMA {label} date field rejected the selected value."
            ) from exc
        self._verify_field_value(field, value, time_of_day, label)

    @staticmethod
    def _verify_field_value(
        field, expected_date: _date, time_of_day: str, label: str
    ) -> None:
        """Verify both the visible masked text and the page's own
        framework-tracked committed value.

        Real-Windows defect (2026-08-03): this previously checked only that
        the formatted *date* substring appeared in the masked display text —
        never the time-of-day segment `_fill_field` explicitly sets to widen
        the selection to a full calendar day (`00:00`/`23:59`). Since this
        exact masked input has a documented failure mode where the time
        segment can silently stay unset while the date segment updates (see
        `_fill_field`'s docstring), a value that *looked* accepted could still
        carry the wrong time — and hence the wrong effective range — without
        being caught. Both segments are now required independently (not as
        one combined string, since the real control pads the display text
        with extra internal whitespace that a single formatted substring
        would not match).
        """
        try:
            actual = field.input_value(timeout=_CONTROL_TIMEOUT_MS)
        except Exception as exc:
            raise PrismaDateValueRejectedError(
                f"The PRISMA {label} date value could not be verified."
            ) from exc
        actual_text = actual or ""
        expected_date_text = f"{expected_date:%d.%m.%Y}"
        if expected_date_text not in actual_text:
            raise PrismaDateValueRejectedError(
                f"The PRISMA {label} date value was not accepted."
            )
        if time_of_day not in actual_text:
            raise PrismaDateValueRejectedError(
                f"The PRISMA {label} time value was not accepted."
            )
        try:
            invalid = field.get_attribute("aria-invalid")
        except Exception:
            invalid = None
        if invalid and invalid.strip().lower() == "true":
            raise PrismaDateValueRejectedError(
                f"PRISMA rejected the {label} date value."
            )
        PrismaDownloadOrchestrator._verify_committed_field_state(
            field, expected_date, time_of_day, label
        )

    @staticmethod
    def _verify_committed_field_state(
        field, expected_date: _date, time_of_day: str, label: str
    ) -> None:
        """Verify the field's own framework-tracked committed value, not only
        the visible masked text.

        Live DOM inspection (2026-08-03) of the real PRISMA page found this
        field exposes `data-test-iso-value`, an ISO-8601 UTC instant that is
        the exact same value later observed in the real outbound PRISMA
        reporting/export request's query string — i.e. this is not merely
        display text, it is the framework's actual committed state. Checking
        it directly is what closes the gap the reported defect exposed: the
        masked display text can look correct (Playwright's `fill()` always
        sets the raw DOM value synchronously) while this framework-tracked
        value has not actually been committed, silently sending PRISMA a
        different range than the one shown on screen.

        Live testing (2026-08-03) found the committed instant must **not** be
        interpreted using the browser's own local timezone: launching the
        same fill against the real page under four different browser
        timezones (`Europe/Berlin`, `America/New_York`, `Asia/Tokyo`, `UTC`)
        produced the *exact same* `data-test-iso-value` every time — proving
        PRISMA always interprets the typed local text as fixed Europe/Berlin
        time, regardless of the machine's own configured timezone (sensible
        for a EU energy-market platform, but it means naively converting the
        committed instant back to the *browser's* local wall-clock time, as
        an earlier version of this check did, produced false rejections on
        any machine not already set to Europe/Berlin — exactly the kind of
        machine-dependent defect this fix must not introduce). The check
        below instead computes, inside the browser via `Intl.DateTimeFormat`
        with an explicit `timeZone: 'Europe/Berlin'`, the UTC instant that
        corresponds to the requested wall-clock date/time in that fixed
        zone (correctly handling the CET/CEST DST boundary, live-verified
        against both an August/CEST and a January/CET date), and compares
        that to the committed instant directly — never the machine's own
        local timezone.

        A future PRISMA build without this attribute is tolerated (returns
        without raising): the text-based check above already ran and is the
        fallback signal in that case, so a page that never exposed this
        attribute cannot report a false failure here.
        """
        hour_text, _, minute_text = time_of_day.partition(":")
        try:
            matches = field.evaluate(
                """
                (el, [day, month, year, hour, minute]) => {
                    const iso = el.getAttribute('data-test-iso-value');
                    if (!iso) { return null; }
                    const actual = new Date(iso).getTime();
                    if (Number.isNaN(actual)) { return null; }
                    const utcGuess = Date.UTC(year, month - 1, day, hour, minute);
                    const formatter = new Intl.DateTimeFormat('en-US', {
                        timeZone: 'Europe/Berlin', hour12: false,
                        year: 'numeric', month: '2-digit', day: '2-digit',
                        hour: '2-digit', minute: '2-digit',
                    });
                    const parts = {};
                    for (const part of formatter.formatToParts(new Date(utcGuess))) {
                        parts[part.type] = part.value;
                    }
                    const hour24 = Number(parts.hour) === 24 ? 0 : Number(parts.hour);
                    const asIfUtc = Date.UTC(
                        Number(parts.year), Number(parts.month) - 1, Number(parts.day),
                        hour24, Number(parts.minute),
                    );
                    const expected = utcGuess - (asIfUtc - utcGuess);
                    return Math.abs(expected - actual) < 60000;
                }
                """,
                [
                    expected_date.day, expected_date.month, expected_date.year,
                    int(hour_text), int(minute_text),
                ],
                timeout=_CONTROL_TIMEOUT_MS,
            )
        except Exception as exc:
            raise PrismaDateValueRejectedError(
                f"The PRISMA {label} date value could not be confirmed as committed."
            ) from exc
        if matches is None:
            return
        if not matches:
            raise PrismaDateValueRejectedError(
                f"The PRISMA {label} date value was not committed by the page."
            )

    def _apply_filter(self, page) -> None:
        button = page.get_by_role("button", name=_FILTER_APPLY_BUTTON).first
        try:
            button.wait_for(state="visible", timeout=_CONTROL_TIMEOUT_MS)
            button.click(timeout=_CONTROL_TIMEOUT_MS)
        except Exception as exc:
            raise PrismaDateFilterPanelError(
                "The PRISMA date filter could not be applied."
            ) from exc
        # Best-effort readiness wait: applying the filter triggers PRISMA's
        # own asynchronous refresh of the results the CSV control exports.
        # This is bounded and non-fatal (a slow/absent "networkidle" signal
        # must not block or fail the whole attempt) rather than an arbitrary
        # sleep, since the download-control click below must not race a
        # still-in-flight filtered-results fetch.
        try:
            page.wait_for_load_state("networkidle", timeout=_CONTROL_TIMEOUT_MS)
        except Exception:
            pass

    def _verify_filter_applied(self, page, date_range: DateRange) -> None:
        """Confirm the applied "Start of Auction" filter chip reflects the
        exact selected range and no visible validation error remains, before
        the download control is ever located. This is a stronger signal than
        `_fill_field`'s per-field verification: it proves PRISMA's own
        results were actually re-filtered, not just that an input accepted
        typed text.

        Live validation (2026-08-02, real PRISMA site, real Chrome) found the
        chip's own re-render can lag slightly behind the "Filter" click — the
        best-effort `networkidle` wait in `_apply_filter` only waits for the
        network, not PRISMA's own React re-render, so a single immediate read
        can still observe the pre-filter chip content and be misreported as a
        rejected date. The content check below therefore uses Playwright's
        own polling `wait_for` (bounded, re-evaluated against the live DOM)
        instead of reading the chip exactly once.

        Real-Windows defect (2026-08-03): this previously required only the
        two formatted *dates* to appear in the chip, never the `00:00`/
        `23:59` time-of-day `_fill_field` sets to widen the selection to a
        full calendar day. A chip showing the right dates but a wrong or
        unset time (e.g. reverted to PRISMA's own pre-populated default)
        previously passed this check even though the actually-applied range
        would exclude part of the requested day. Each of the four
        substrings is required independently (not one combined string),
        since the exact separator between date and time in the chip's own
        text is not part of the contract being verified here.
        """
        chip = page.get_by_test_id(_APPLIED_FILTER_CHIP_TEST_ID).first
        try:
            chip.wait_for(state="visible", timeout=_CONTROL_TIMEOUT_MS)
        except Exception as exc:
            raise PrismaDateFilterPanelError(
                "The PRISMA date filter could not be confirmed as applied."
            ) from exc
        start_text = f"{date_range.start:%d.%m.%Y}"
        end_text = f"{date_range.end:%d.%m.%Y}"
        expected_text = re.compile(
            rf"(?=.*{re.escape(start_text)})(?=.*{re.escape(end_text)})"
            rf"(?=.*{re.escape(_FILTER_START_TIME)})(?=.*{re.escape(_FILTER_END_TIME)})",
            re.DOTALL,
        )
        matching_chip = chip.filter(has_text=expected_text)
        try:
            matching_chip.wait_for(
                state="visible", timeout=_FILTER_CHIP_VERIFY_TIMEOUT_MS
            )
        except Exception as exc:
            raise PrismaDateValueRejectedError(
                "The applied PRISMA date filter does not match the selected range."
            ) from exc
        self._ensure_no_visible_validation_error(page)

    @staticmethod
    def _ensure_no_visible_validation_error(page) -> None:
        try:
            alerts = page.get_by_role("alert")
            count = alerts.count()
        except Exception:
            return
        for index in range(count):
            alert = alerts.nth(index)
            try:
                visible = alert.is_visible()
            except Exception:
                continue
            if not visible:
                continue
            try:
                text = (alert.inner_text() or "").strip()
            except Exception:
                text = ""
            raise PrismaDateValueRejectedError(
                "PRISMA reported a validation error after applying the date "
                f"filter: {text}" if text else
                "PRISMA reported a validation error after applying the date filter."
            )

    def _locate_download_control(self, page):
        button = page.get_by_role(
            "button", name=_CSV_DOWNLOAD_BUTTON_NAME, exact=True
        ).first
        try:
            button.wait_for(state="visible", timeout=_CONTROL_TIMEOUT_MS)
        except Exception as exc:
            raise PrismaDownloadControlError(
                "The PRISMA CSV download control could not be found."
            ) from exc
        return button

    def _dismiss_cookie_consent_banner(self, page) -> None:
        """Dismiss PRISMA's fixed cookie-consent/usability-research banner if
        present, before the CSV control is activated (see module docstring
        for the live-verified banner contract).

        A short bounded wait treats absence of the banner as the normal case
        rather than an error. Each of the two known controls is tried through
        its own visible, accessible-name locator — never a raw CSS selector —
        and clicked without `force=True`, so an unrelated obstruction is
        never silently bypassed. No DOM element is ever removed through
        JavaScript: a supported user control is always tried first, and if
        none is found or usable, a typed error is raised instead of falling
        back to forced removal.
        """
        control = self._find_cookie_banner_control(page)
        if control is None:
            return
        try:
            control.click(timeout=_CONTROL_TIMEOUT_MS)
        except Exception as exc:
            raise PrismaCookieConsentBannerError(
                "The PRISMA cookie-consent banner could not be dismissed."
            ) from exc
        try:
            control.wait_for(state="hidden", timeout=_CONTROL_TIMEOUT_MS)
        except Exception as exc:
            raise PrismaCookieConsentBannerError(
                "The PRISMA cookie-consent banner did not close after being "
                "dismissed."
            ) from exc

    @staticmethod
    def _find_cookie_banner_control(page):
        for name in _COOKIE_BANNER_DISMISS_BUTTON_NAMES:
            control = page.get_by_role("button", name=name, exact=True).first
            try:
                control.wait_for(
                    state="visible", timeout=_COOKIE_BANNER_DETECT_TIMEOUT_MS
                )
            except Exception:
                continue
            return control
        return None

    @staticmethod
    def _ensure_control_not_obstructed(control) -> None:
        """Verify the CSV control actually receives pointer events at its own
        location before it is clicked, instead of relying on `force=True` to
        push the click through a possible leftover overlay.

        The control is scrolled into view first (live validation on the real,
        long PRISMA results page found the control is very often below the
        fold): without this, `document.elementFromPoint` on its unscrolled
        coordinates always misses (a point outside the viewport resolves to
        no element), which would misreport every off-screen control as
        obstructed. This mirrors the scroll-into-view step Playwright's own
        `click()` actionability checks already perform internally.
        """
        try:
            control.scroll_into_view_if_needed(timeout=_CONTROL_TIMEOUT_MS)
        except Exception:
            # Best-effort: if the control cannot even be scrolled to, the
            # normal click below will surface its own PrismaDownloadControlError.
            return
        try:
            box = control.bounding_box()
        except Exception:
            return
        if box is None:
            return
        x = box["x"] + box["width"] / 2
        y = box["y"] + box["height"] / 2
        try:
            obstructed = control.evaluate(
                """(el, [x, y]) => {
                    const top = document.elementFromPoint(x, y);
                    return !(top && (top === el || el.contains(top)));
                }""",
                [x, y],
            )
        except Exception:
            return
        if obstructed:
            raise PrismaCookieConsentBannerError(
                "The PRISMA CSV download control remained obstructed by an "
                "overlay after the cookie-consent banner was handled."
            )

    @staticmethod
    def _activate_download_control(button) -> None:
        try:
            # Never force=True: an obstructed control must fail with a typed
            # error (see _ensure_control_not_obstructed above and
            # PrismaDownloadControlError below), not be clicked through
            # whatever is covering it.
            button.click(timeout=_CONTROL_TIMEOUT_MS)
        except Exception as exc:
            raise PrismaDownloadControlError(
                "The PRISMA CSV download control could not be activated."
            ) from exc

    def _confirm_large_result_modal_if_present(self, page) -> None:
        """Confirm PRISMA's own large-export warning dialog if it appears
        after the CSV control is activated (see module docstring). Absence
        within the short bounded wait below is the normal case (a
        sufficiently narrow date range never triggers this dialog) and is
        never treated as an error. The dialog's own "CSV" button — scoped to
        the dialog so it is never confused with the main page control that
        shares the same accessible name — proceeds with the truncated
        export; the dialog's close/dismiss controls are never used, since
        that would cancel the download instead of confirming it. The date
        range itself is never altered to avoid this dialog.
        """
        dialog = page.get_by_role("dialog").filter(
            has_text=_LARGE_RESULT_MODAL_TEXT_PATTERN
        ).first
        try:
            dialog.wait_for(
                state="visible", timeout=_LARGE_RESULT_MODAL_DETECT_TIMEOUT_MS
            )
        except Exception:
            return
        confirm = dialog.get_by_role(
            "button", name=_CSV_DOWNLOAD_BUTTON_NAME, exact=True
        ).first
        try:
            confirm.wait_for(state="visible", timeout=_CONTROL_TIMEOUT_MS)
            confirm.click(timeout=_CONTROL_TIMEOUT_MS)
        except Exception as exc:
            raise PrismaLargeResultConfirmationError(
                "PRISMA's large-result confirmation could not be confirmed."
            ) from exc

    def await_and_finalize(
        self,
        waiter: PrismaDownloadWaiter,
        date_range: DateRange,
        download_directory: str | Path,
        cancel_event: threading.Event,
        *,
        deadline: float | None = None,
    ) -> PrismaDownloadResult | None:
        """Poll ``waiter`` for exactly one download, honoring ``cancel_event``.

        Returns ``None`` (not yet resolved, keep polling) if neither the
        download event, the filesystem fallback (see module docstring; only
        consulted when `waiter.filesystem_fallback` was set by `configure()`),
        nor the timeout deadline has resolved, so the caller can interleave
        this with its own closure-detection polling instead of blocking
        exclusively on this wait. This method itself never sleeps or blocks,
        so it remains as cancellable as the primary path: the caller's own
        poll loop observes `cancel_event` between calls.
        """
        if waiter.event.is_set():
            return self._finalize(waiter, date_range, download_directory)
        if cancel_event.is_set():
            return None
        if waiter.filesystem_fallback is not None:
            poll_result = waiter.filesystem_fallback.poll()
            if poll_result.outcome is _FilesystemPollOutcome.READY:
                # The Playwright event is the primary mechanism and may have
                # arrived between the check above and here; prefer it if so.
                if waiter.event.is_set():
                    return self._finalize(waiter, date_range, download_directory)
                return self._finalize_from_filesystem(
                    poll_result.path, date_range, download_directory
                )
            if poll_result.outcome is _FilesystemPollOutcome.MULTIPLE:
                return PrismaDownloadResult(PrismaDownloadOutcome.MULTIPLE_DOWNLOADS)
            if poll_result.outcome is _FilesystemPollOutcome.INTERRUPTED:
                return PrismaDownloadResult(PrismaDownloadOutcome.DOWNLOAD_INTERRUPTED)
        if deadline is not None and time.monotonic() >= deadline:
            return PrismaDownloadResult(PrismaDownloadOutcome.DOWNLOAD_TIMEOUT)
        return None

    def _finalize_from_filesystem(
        self,
        path: Path,
        date_range: DateRange,
        download_directory: str | Path,
    ) -> PrismaDownloadResult:
        """Finalize a download recognized only through the filesystem
        fallback: apply the same naming/collision rule as the primary path,
        then atomically rename the already-downloaded file into place (there
        is no `Download` object to call `save_as()` on).

        Unlike the primary path, there is no `suggested_filename` here: the
        raw artifact's own name is a browser/CDP-generated identifier (often
        UUID-like, see `PrismaDownloadFilesystemWaiter.poll()`), never a
        trustworthy source of the final extension. The ``.csv`` extension is
        therefore forced explicitly here, regardless of the raw artifact's own
        name, rather than deferring to `build_dated_filename`'s
        suffix-preserving default.
        """
        filename = build_dated_filename(f"{path.stem}.csv", date_range)
        try:
            target = reserve_unique_download_path(download_directory, filename)
        except OSError as exc:
            return PrismaDownloadResult(PrismaDownloadOutcome.SAVE_FAILED, error=str(exc))
        try:
            os.replace(str(path), str(target))
        except OSError as exc:
            return PrismaDownloadResult(PrismaDownloadOutcome.SAVE_FAILED, error=str(exc))
        return PrismaDownloadResult(PrismaDownloadOutcome.SUCCESS, csv_path=target)

    def _finalize(
        self,
        waiter: PrismaDownloadWaiter,
        date_range: DateRange,
        download_directory: str | Path,
    ) -> PrismaDownloadResult:
        download = waiter.download
        suggested = getattr(download, "suggested_filename", "") or ""
        if not suggested.lower().endswith(".csv"):
            _safe_cancel_download(download)
            return PrismaDownloadResult(
                PrismaDownloadOutcome.NOT_CSV,
                error=f"suggested_filename={suggested!r}",
            )
        failure = self._safe_failure(download)
        if failure:
            return PrismaDownloadResult(self._classify_failure(failure), error=failure)
        # Requirement: reject multiple download events explicitly rather than
        # silently keeping only the first. `waiter.on_download` already
        # best-effort cancels every extra download as it arrives; this check
        # covers the race where a second event lands between listener
        # registration and this point.
        if waiter.multiple:
            _safe_cancel_download(download)
            return PrismaDownloadResult(PrismaDownloadOutcome.MULTIPLE_DOWNLOADS)

        filename = build_dated_filename(suggested, date_range)
        try:
            target = reserve_unique_download_path(download_directory, filename)
        except OSError as exc:
            return PrismaDownloadResult(PrismaDownloadOutcome.SAVE_FAILED, error=str(exc))

        try:
            download.save_as(str(target))
        except Exception as exc:
            return PrismaDownloadResult(PrismaDownloadOutcome.SAVE_FAILED, error=str(exc))

        failure_after_save = self._safe_failure(download)
        if failure_after_save:
            return PrismaDownloadResult(
                self._classify_failure(failure_after_save), error=failure_after_save
            )
        if waiter.multiple:
            # A second download arrived while the first was being saved:
            # discard the saved artifact rather than reporting a success that
            # silently dropped the extra download.
            try:
                target.unlink(missing_ok=True)
            except OSError:
                pass
            return PrismaDownloadResult(PrismaDownloadOutcome.MULTIPLE_DOWNLOADS)
        try:
            saved_size = target.stat().st_size
        except OSError as exc:
            return PrismaDownloadResult(PrismaDownloadOutcome.SAVE_FAILED, error=str(exc))
        if saved_size == 0:
            # A download that reports success but saved zero bytes never
            # actually completed; never accepted as a result (see the
            # matching filesystem-fallback check in `_poll_candidate`).
            try:
                target.unlink(missing_ok=True)
            except OSError:
                pass
            return PrismaDownloadResult(PrismaDownloadOutcome.DOWNLOAD_INTERRUPTED)
        return PrismaDownloadResult(PrismaDownloadOutcome.SUCCESS, csv_path=target)

    @staticmethod
    def _classify_failure(failure: str) -> PrismaDownloadOutcome:
        return (
            PrismaDownloadOutcome.DOWNLOAD_CANCELLED
            if "cancel" in failure.lower()
            else PrismaDownloadOutcome.DOWNLOAD_INTERRUPTED
        )

    @staticmethod
    def _safe_failure(download) -> str | None:
        try:
            return download.failure()
        except Exception:
            return None
