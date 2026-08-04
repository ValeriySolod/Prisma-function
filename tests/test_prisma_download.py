import threading
import time
from datetime import date
from pathlib import Path

import pytest

from browser import PRISMA_AUCTIONS_URL
from date_range_selection import DateRange
from prisma_download import (
    DEFAULT_REPORTING_URL,
    PrismaAuthenticationRequiredError,
    PrismaCookieConsentBannerError,
    PrismaDateFilterControlsNotFoundError,
    PrismaDateFilterPanelError,
    PrismaDateValueRejectedError,
    PrismaDownloadControlError,
    PrismaDownloadListenerError,
    PrismaDownloadFilesystemWaiter,
    PrismaDownloadOrchestrator,
    PrismaDownloadOutcome,
    PrismaDownloadValidationOutcome,
    PrismaDownloadWaiter,
    PrismaInvalidSessionError,
    PrismaLargeResultConfirmationError,
    build_dated_filename,
    describe_download_failure,
    describe_validation_rejection,
    reserve_unique_download_path,
    validate_download_configuration,
)

RANGE = DateRange(date(2026, 8, 1), date(2026, 8, 31))

REPO_ROOT = Path(__file__).resolve().parent.parent
_STALE_REPORTING_URL = "https://app.prisma-capacity.eu/reporting/reports/short-and-long-term-auctions"


# --- P.36.14 real-validation correction: one canonical reporting URL -------


def test_default_reporting_url_is_the_approved_auctions_url():
    assert DEFAULT_REPORTING_URL == (
        "https://app.prisma-capacity.eu/reporting/auctions/short-and-long-term-auctions"
    )


def test_default_reporting_url_is_the_same_object_as_the_canonical_browser_constant():
    # Not just equal by value: this proves prisma_download.py imports the one
    # canonical constant from browser.py rather than duplicating the literal.
    assert DEFAULT_REPORTING_URL is PRISMA_AUCTIONS_URL


def test_no_stale_reporting_url_literal_remains_in_production_code():
    production_files = [
        path
        for path in REPO_ROOT.glob("*.py")
        if path.name not in {"validate_package.py"}
    ]
    assert production_files, "expected to find production .py files at the repository root"
    offenders = [
        path.name
        for path in production_files
        if _STALE_REPORTING_URL in path.read_text(encoding="utf-8")
    ]
    assert offenders == []


# --- validate_download_configuration --------------------------------------


def test_validation_accepts_a_valid_configuration(tmp_path):
    assert (
        validate_download_configuration(RANGE, tmp_path)
        is PrismaDownloadValidationOutcome.ACCEPTED
    )


def test_validation_rejects_missing_date_range(tmp_path):
    assert (
        validate_download_configuration(None, tmp_path)
        is PrismaDownloadValidationOutcome.MISSING_DATE_RANGE
    )


def test_validation_rejects_missing_download_directory():
    assert (
        validate_download_configuration(RANGE, None)
        is PrismaDownloadValidationOutcome.MISSING_DOWNLOAD_DIRECTORY
    )


def test_validation_missing_date_range_takes_precedence_over_missing_directory():
    assert (
        validate_download_configuration(None, None)
        is PrismaDownloadValidationOutcome.MISSING_DATE_RANGE
    )


def test_validation_rejects_a_nonexistent_directory(tmp_path):
    missing = tmp_path / "does-not-exist"

    assert (
        validate_download_configuration(RANGE, missing)
        is PrismaDownloadValidationOutcome.INVALID_DOWNLOAD_DIRECTORY
    )


def test_validation_rejects_a_file_path(tmp_path):
    file_path = tmp_path / "not-a-directory.csv"
    file_path.write_text("data", encoding="utf-8")

    assert (
        validate_download_configuration(RANGE, file_path)
        is PrismaDownloadValidationOutcome.INVALID_DOWNLOAD_DIRECTORY
    )


def test_validation_rejects_a_non_writable_directory(tmp_path, monkeypatch):
    import prisma_download as prisma_download_module

    target = tmp_path / "locked"
    target.mkdir()
    monkeypatch.setattr(prisma_download_module.os, "access", lambda *a, **k: False)

    assert (
        validate_download_configuration(RANGE, target)
        is PrismaDownloadValidationOutcome.INVALID_DOWNLOAD_DIRECTORY
    )


def test_describe_validation_rejection_messages_are_distinct_and_stable():
    messages = {
        outcome: describe_validation_rejection(outcome)
        for outcome in PrismaDownloadValidationOutcome
        if outcome is not PrismaDownloadValidationOutcome.ACCEPTED
    }
    assert len(set(messages.values())) == len(messages)
    assert all(message for message in messages.values())


# --- build_dated_filename / reserve_unique_download_path ------------------


def test_build_dated_filename_appends_the_range_before_the_extension():
    assert (
        build_dated_filename("Auction_overview.csv", RANGE)
        == "Auction_overview_2026-08-01_2026-08-31.csv"
    )


def test_build_dated_filename_defaults_to_csv_when_original_has_no_suffix():
    assert (
        build_dated_filename("Auction_overview", RANGE)
        == "Auction_overview_2026-08-01_2026-08-31.csv"
    )


def test_reserve_unique_download_path_uses_the_exact_name_when_free(tmp_path):
    path = reserve_unique_download_path(tmp_path, "Auction_overview_2026-08-01_2026-08-31.csv")

    assert path == tmp_path / "Auction_overview_2026-08-01_2026-08-31.csv"
    assert path.exists()


def test_reserve_unique_download_path_appends_incrementing_suffix_on_collision(tmp_path):
    filename = "Auction_overview_2026-08-01_2026-08-31.csv"
    (tmp_path / filename).write_text("existing", encoding="utf-8")

    second = reserve_unique_download_path(tmp_path, filename)

    assert second == tmp_path / "Auction_overview_2026-08-01_2026-08-31_2.csv"
    assert (tmp_path / filename).read_text(encoding="utf-8") == "existing"


def test_reserve_unique_download_path_increments_deterministically_across_multiple_collisions(
    tmp_path,
):
    filename = "Auction_overview_2026-08-01_2026-08-31.csv"
    (tmp_path / filename).write_text("existing", encoding="utf-8")
    (tmp_path / "Auction_overview_2026-08-01_2026-08-31_2.csv").write_text(
        "existing-2", encoding="utf-8"
    )

    third = reserve_unique_download_path(tmp_path, filename)

    assert third == tmp_path / "Auction_overview_2026-08-01_2026-08-31_3.csv"


def test_reserve_unique_download_path_never_overwrites_an_existing_file(tmp_path):
    filename = "data.csv"
    original = tmp_path / filename
    original.write_text("original contents", encoding="utf-8")

    reserved = reserve_unique_download_path(tmp_path, filename)

    assert reserved != original
    assert original.read_text(encoding="utf-8") == "original contents"


# --- PrismaDownloadOrchestrator.configure() --------------------------------
#
# The fakes below model the real, live-verified DOM contract (see
# ROADMAP.md's P.36.14 real-validation record): a collapsed "Active Filter:"
# panel toggle (role=button), two masked date-time inputs reached via
# data-testid ("startOfAuctionFrom"/"startOfAuctionTo") rather than a guessed
# aria-label, and a "Filter" apply button (role=button, exact name).


class FakeFieldLocator:
    """Models one masked `startOfAuctionFrom`/`startOfAuctionTo` input.

    Real-Windows defect (2026-08-03): the real control also exposes a
    `data-test-iso-value` attribute holding the framework's own committed
    value (live DOM inspection found this is the exact value later observed
    in the real outbound PRISMA request), verified via
    `field.evaluate(...)` — which computes and returns a boolean match
    (never the browser's own local-timezone conversion; live testing found
    PRISMA always interprets typed text as fixed Europe/Berlin time
    regardless of the browser's configured timezone, see
    `_verify_committed_field_state`'s docstring) — and `_fill_field` now
    blurs the field (`field.evaluate("(el) => el.blur()")`) before
    verification. By default, `evaluate()` for the committed-value read
    returns ``True`` (matches the existing "committed correctly" default of
    every pre-existing test, since `echo_fill` already makes the plain
    text-based check pass too); `iso_committed_override` lets a test force
    ``False`` (a mismatch) or ``None`` (attribute absent), `blur_error` lets
    a test simulate `blur()` itself failing, and `committed_read_error` lets
    a test simulate the committed-value read itself failing (independently
    of `blur_error`, since both go through `evaluate()` but at different
    points in the sequence).
    """

    def __init__(
        self, *, visible=True, wait_error=None, fill_error=None,
        input_value_error=None, aria_invalid=None, echo_fill=True,
        blur_error=None, committed_read_error=None,
        iso_committed_override=True,
    ):
        self.visible = visible
        self.wait_error = wait_error
        self.fill_error = fill_error
        self.input_value_error = input_value_error
        self.aria_invalid = aria_invalid
        self.echo_fill = echo_fill
        self.blur_error = blur_error
        self.committed_read_error = committed_read_error
        self.iso_committed_override = iso_committed_override
        self.fill_calls: list[str] = []
        self.click_calls = 0
        self.action_order: list[str] = []
        self.blur_calls = 0
        self.evaluate_calls: list[str] = []
        self._value = "DD.MM.YYYY      HH:mm"

    @property
    def first(self):
        return self

    def wait_for(self, state="visible", timeout=None):
        if self.wait_error:
            raise self.wait_error
        if not self.visible:
            raise TimeoutError(f"Locator.wait_for: Timeout {timeout}ms exceeded.")

    def click(self, timeout=None):
        self.click_calls += 1
        self.action_order.append("click")

    def press(self, key, timeout=None):
        self.action_order.append(f"press:{key}")

    def fill(self, value, timeout=None):
        self.action_order.append("fill")
        if self.fill_error:
            raise self.fill_error
        self.fill_calls.append(value)
        if self.echo_fill:
            self._value = value

    def input_value(self, timeout=None):
        if self.input_value_error:
            raise self.input_value_error
        return self._value

    def get_attribute(self, name):
        if name == "aria-invalid":
            return self.aria_invalid
        return None

    def evaluate(self, script, arg=None, timeout=None):
        self.evaluate_calls.append(script)
        if "blur" in script:
            self.action_order.append("evaluate:blur")
            if self.blur_error:
                raise self.blur_error
            self.blur_calls += 1
            return None
        if self.committed_read_error:
            raise self.committed_read_error
        return self.iso_committed_override


class FakeButtonLocator:
    def __init__(
        self, *, visible=True, wait_error=None, click_error=None,
        hidden_after_click=True, wait_hidden_error=None,
        bounding_box=None, obstructed=False, obstructed_error=None,
        scroll_error=None,
    ):
        self.visible = visible
        self.wait_error = wait_error
        self.click_error = click_error
        self.click_calls = 0
        self.click_force_values: list[bool | None] = []
        self.hidden_after_click = hidden_after_click
        self.wait_hidden_error = wait_hidden_error
        self._bounding_box = (
            bounding_box if bounding_box is not None
            else {"x": 0.0, "y": 0.0, "width": 10.0, "height": 10.0}
        )
        self.obstructed = obstructed
        self.obstructed_error = obstructed_error
        self.evaluate_calls = 0
        self.scroll_error = scroll_error
        self.scroll_calls = 0

    def scroll_into_view_if_needed(self, timeout=None):
        self.scroll_calls += 1
        if self.scroll_error:
            raise self.scroll_error

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
        if self.wait_error:
            raise self.wait_error
        if not self.visible:
            raise TimeoutError(f"Locator.wait_for: Timeout {timeout}ms exceeded.")

    def click(self, timeout=None, force=None):
        self.click_calls += 1
        self.click_force_values.append(force)
        if self.click_error:
            raise self.click_error

    def bounding_box(self):
        return self._bounding_box

    def evaluate(self, script, arg=None):
        self.evaluate_calls += 1
        if self.obstructed_error:
            raise self.obstructed_error
        return self.obstructed


class FakeAppliedFilterChip:
    """Models the `data-testid="filter-startOfAuctionFrom"` chip PRISMA
    echoes the applied range back into once "Filter" is clicked. Defaults to
    reflecting whatever was actually filled into the two date fields, so
    every existing `configure()` test automatically exercises a matching
    chip without needing to know the specific date range in use.
    """

    def __init__(self, page, *, visible=True, wait_error=None, text_override=None):
        self._page = page
        self.visible = visible
        self.wait_error = wait_error
        self.text_override = text_override

    @property
    def first(self):
        return self

    def wait_for(self, state="visible", timeout=None):
        if self.wait_error:
            raise self.wait_error
        if not self.visible:
            raise TimeoutError(f"Locator.wait_for: Timeout {timeout}ms exceeded.")

    def inner_text(self, timeout=None):
        if self.text_override is not None:
            return self.text_override
        return (
            f"Start of Auction\n{self._page.from_field.input_value()} - "
            f"{self._page.to_field.input_value()}"
        )

    def filter(self, has_text=None):
        return FakeFilteredChipLocator(self, has_text)


class FakeFilteredChipLocator:
    """Models `chip.filter(has_text=...)`: `wait_for` only succeeds once the
    base locator's *current* text matches the pattern — re-evaluated live at
    wait_for time, mirroring Playwright's own polling semantics — rather
    than being decided once when `.filter()` is called. This is what lets
    `test_configure_verifies_the_applied_filter_chip...` exercise the real
    "the chip catches up after a short lag" behavior alongside the plain
    "never matches" rejection path.
    """

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


class FakeAlertItem:
    def __init__(self, *, visible=True, text=""):
        self._visible = visible
        self._text = text

    def is_visible(self):
        return self._visible

    def inner_text(self):
        return self._text


class FakeAlertLocator:
    """Models `page.get_by_role("alert")`: empty by default, matching "no
    visible validation error" as the normal case.
    """

    def __init__(self, alerts=None):
        self._alerts = list(alerts) if alerts else []

    def count(self):
        return len(self._alerts)

    def nth(self, index):
        return self._alerts[index]


class FakeLargeResultDialog:
    """Models PRISMA's own large-export confirmation dialog
    (`role="dialog"`, text matching "contains only N of M items")."""

    def __init__(self, *, visible=True, wait_error=None, confirm_button=None):
        self.visible = visible
        self.wait_error = wait_error
        self.confirm_button = confirm_button if confirm_button is not None else FakeButtonLocator()
        self.get_by_role_calls = []

    def wait_for(self, state="visible", timeout=None):
        if self.wait_error:
            raise self.wait_error
        if not self.visible:
            raise TimeoutError(f"Locator.wait_for: Timeout {timeout}ms exceeded.")

    def get_by_role(self, role, name=None, exact=None):
        self.get_by_role_calls.append((role, name, exact))
        if role == "button" and name == "CSV":
            return self.confirm_button
        raise AssertionError(f"unexpected dialog.get_by_role call: {role!r} {name!r}")


class FakeDialogQuery:
    """Models `page.get_by_role("dialog").filter(has_text=...)`. Absent
    (`dialog is None`) by default, matching "absence of the large-result
    modal is normal".
    """

    def __init__(self, dialog=None):
        self._dialog = dialog

    def filter(self, has_text=None):
        return self

    @property
    def first(self):
        return self._dialog if self._dialog is not None else FakeLargeResultDialog(visible=False)


class FakeBrowserContext:
    """Models `Page.context`: the real download listener target (see
    ROADMAP.md — the real PRISMA CSV export opens in a new tab, so the
    listener must be context-scoped, not page-scoped, to observe it).
    """

    def __init__(self, *, on_error=None):
        self.on_error = on_error
        self.on_calls: list[tuple[str, object]] = []
        self.removed_calls: list[tuple[str, object]] = []

    def on(self, event, callback):
        if self.on_error:
            raise self.on_error
        self.on_calls.append((event, callback))

    def remove_listener(self, event, callback):
        self.removed_calls.append((event, callback))
        self.on_calls = [
            (e, c) for (e, c) in self.on_calls if not (e == event and c == callback)
        ]


class FakeConfigurePage:
    def __init__(
        self, *,
        filter_toggle=None, filter_button=None,
        from_field=None, to_field=None, download_button=None,
        cookie_decline_button=None, cookie_accept_button=None,
        on_error=None, missing_test_ids=False,
        network_idle_error=None, context=None,
        applied_filter_chip=None, alerts=None, large_result_dialog=None,
    ):
        self.filter_toggle = filter_toggle if filter_toggle is not None else FakeButtonLocator()
        self.filter_button = filter_button if filter_button is not None else FakeButtonLocator()
        self.from_field = from_field if from_field is not None else FakeFieldLocator()
        self.to_field = to_field if to_field is not None else FakeFieldLocator()
        self.download_button = download_button if download_button is not None else FakeButtonLocator()
        # Absent by default: most tests exercise a session where the cookie
        # banner never appears, matching "absence of the banner is normal".
        self.cookie_decline_button = (
            cookie_decline_button if cookie_decline_button is not None
            else FakeButtonLocator(visible=False)
        )
        self.cookie_accept_button = (
            cookie_accept_button if cookie_accept_button is not None
            else FakeButtonLocator(visible=False)
        )
        # Default reflects whatever was actually filled, matching the real
        # applied-range chip; absent large-result dialog and empty alerts by
        # default, matching "absence is normal".
        self.applied_filter_chip = (
            applied_filter_chip if applied_filter_chip is not None
            else FakeAppliedFilterChip(self)
        )
        self.alerts = list(alerts) if alerts else []
        self.large_result_dialog = large_result_dialog
        self._missing_test_ids = missing_test_ids
        self.context = context if context is not None else FakeBrowserContext(on_error=on_error)
        self.get_by_role_calls = []
        self.get_by_test_id_calls = []
        self.network_idle_error = network_idle_error
        self.wait_for_load_state_calls = []

    def get_by_role(self, role, name=None, exact=None):
        if role == "dialog":
            self.get_by_role_calls.append((role, None, exact))
            return FakeDialogQuery(self.large_result_dialog)
        if role == "alert":
            self.get_by_role_calls.append((role, None, exact))
            return FakeAlertLocator(self.alerts)
        pattern = getattr(name, "pattern", str(name))
        self.get_by_role_calls.append((role, pattern, exact))
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
        self.get_by_test_id_calls.append(test_id)
        if test_id == "filter-startOfAuctionFrom":
            return self.applied_filter_chip
        if self._missing_test_ids:
            return FakeFieldLocator(visible=False)
        if test_id == "startOfAuctionFrom":
            return self.from_field
        if test_id == "startOfAuctionTo":
            return self.to_field
        raise AssertionError(f"unexpected get_by_test_id call: {test_id!r}")

    def wait_for_load_state(self, state=None, timeout=None):
        self.wait_for_load_state_calls.append(state)
        if self.network_idle_error:
            raise self.network_idle_error


class StubSessionValidator:
    """Injectable double for PrismaSessionValidator.validate()."""

    def __init__(self, *, error=None):
        self.error = error
        self.calls = []

    def validate(self, page):
        self.calls.append(page)
        if self.error:
            raise self.error


def _orchestrator_with(*, session_validator=None, timeout_seconds=60.0):
    return PrismaDownloadOrchestrator(
        timeout_seconds=timeout_seconds,
        session_validator=session_validator or StubSessionValidator(),
    )


def test_configure_opens_the_real_filter_panel_and_fills_both_dates():
    page = FakeConfigurePage()
    orchestrator = _orchestrator_with()

    waiter = orchestrator.configure(page, RANGE)

    assert page.filter_toggle.click_calls == 1
    assert page.from_field.fill_calls == ["01.08.2026 00:00"]
    assert page.to_field.fill_calls == ["31.08.2026 23:59"]
    assert page.filter_button.click_calls == 1
    assert page.context.on_calls and page.context.on_calls[0][0] == "download"
    assert page.download_button.click_calls == 1
    assert waiter.download is None
    assert not waiter.event.is_set()


def test_configure_activates_the_real_csv_download_control_by_exact_accessible_name():
    """Regression: the real PRISMA CSV control is a plain
    `<button type="button">CSV</button>` with no test id or ARIA attributes
    (see ROADMAP.md's P.36.14 contract-correction record). It is located by
    an exact accessible-name role locator, never by test id or brittle text
    matching.
    """
    page = FakeConfigurePage()
    orchestrator = _orchestrator_with()

    orchestrator.configure(page, RANGE)

    assert ("button", "CSV", True) in page.get_by_role_calls


class OrderTrackingButtonLocator(FakeButtonLocator):
    """Records whether the download listener was already registered on the
    owning page's context at the moment this control was clicked.
    """

    def __init__(self, page, **kwargs):
        super().__init__(**kwargs)
        self._page = page
        self.listener_registered_before_click = None

    def click(self, timeout=None, force=None):
        self.listener_registered_before_click = bool(self._page.context.on_calls)
        super().click(timeout=timeout, force=force)


def test_configure_registers_the_download_listener_before_activating_the_control():
    page = FakeConfigurePage()
    page.download_button = OrderTrackingButtonLocator(page)
    orchestrator = _orchestrator_with()

    orchestrator.configure(page, RANGE)

    assert page.download_button.listener_registered_before_click is True
    assert page.download_button.click_calls == 1


def test_configure_raises_when_the_download_control_cannot_be_found():
    page = FakeConfigurePage(download_button=FakeButtonLocator(visible=False))
    orchestrator = _orchestrator_with()

    with pytest.raises(PrismaDownloadControlError, match="could not be found"):
        orchestrator.configure(page, RANGE)

    # The listener must not be left registered if the control was never found.
    assert page.context.on_calls == []


def test_configure_raises_when_the_download_control_cannot_be_activated():
    page = FakeConfigurePage(
        download_button=FakeButtonLocator(click_error=RuntimeError("element intercepted"))
    )
    orchestrator = _orchestrator_with()

    with pytest.raises(PrismaDownloadControlError, match="could not be activated"):
        orchestrator.configure(page, RANGE)

    # The listener registration must have already happened before the failed click.
    assert page.context.on_calls and page.context.on_calls[0][0] == "download"
    # Never force=True: the requirements forbid bypassing an overlay by force.
    assert True not in page.download_button.click_force_values


def test_configure_tolerates_a_slow_or_unsupported_network_idle_wait():
    """The post-filter readiness wait is best-effort and bounded: it must
    never fail the whole attempt, whether the fake page raises (simulating an
    API the real page doesn't settle into) or simply doesn't implement it.
    """
    page = FakeConfigurePage(network_idle_error=RuntimeError("Timeout 10000ms exceeded"))
    orchestrator = _orchestrator_with()

    orchestrator.configure(page, RANGE)  # must not raise

    assert page.download_button.click_calls == 1


def test_configure_clears_each_field_before_filling_it():
    """Regression: live validation found that filling a masked date-time
    input that already holds a value (the "from" field starts pre-populated
    with PRISMA's own default filter) without first clearing it only updates
    the date segment and leaves the time segment stuck at its placeholder,
    which then fails verification. Both fields must be cleared first,
    including the "to" field, which starts empty but must behave uniformly.
    """
    page = FakeConfigurePage()
    orchestrator = _orchestrator_with()

    orchestrator.configure(page, RANGE)

    for field in (page.from_field, page.to_field):
        assert field.action_order == [
            "click", "press:Control+A", "press:Delete", "fill", "evaluate:blur",
        ]


def test_configure_verifies_the_real_start_of_auction_test_ids_are_used():
    page = FakeConfigurePage()
    orchestrator = _orchestrator_with()

    orchestrator.configure(page, RANGE)

    assert page.get_by_test_id_calls == [
        "startOfAuctionFrom", "startOfAuctionTo", "filter-startOfAuctionFrom",
    ]


def test_configure_waits_for_the_filter_toggle_before_clicking_it():
    toggle = FakeButtonLocator(visible=False)
    page = FakeConfigurePage(filter_toggle=toggle)
    orchestrator = _orchestrator_with()

    with pytest.raises(PrismaDateFilterPanelError, match="could not be found"):
        orchestrator.configure(page, RANGE)

    assert toggle.click_calls == 0


def test_configure_raises_when_authentication_is_required():
    validator = StubSessionValidator(
        error=PrismaAuthenticationRequiredError("PRISMA authentication is required.")
    )
    page = FakeConfigurePage()
    orchestrator = _orchestrator_with(session_validator=validator)

    with pytest.raises(PrismaAuthenticationRequiredError):
        orchestrator.configure(page, RANGE)

    assert page.filter_toggle.click_calls == 0


def test_configure_raises_when_the_report_page_is_not_a_usable_session():
    validator = StubSessionValidator(
        error=PrismaInvalidSessionError("The active page is not a usable public session.")
    )
    page = FakeConfigurePage()
    orchestrator = _orchestrator_with(session_validator=validator)

    with pytest.raises(PrismaInvalidSessionError):
        orchestrator.configure(page, RANGE)


def test_configure_raises_when_the_filter_panel_cannot_be_opened():
    toggle = FakeButtonLocator(click_error=RuntimeError("element intercepted"))
    page = FakeConfigurePage(filter_toggle=toggle)
    orchestrator = _orchestrator_with()

    with pytest.raises(PrismaDateFilterPanelError, match="could not be opened"):
        orchestrator.configure(page, RANGE)


def test_configure_raises_when_date_controls_cannot_be_located():
    page = FakeConfigurePage(missing_test_ids=True)
    orchestrator = _orchestrator_with()

    with pytest.raises(PrismaDateFilterControlsNotFoundError):
        orchestrator.configure(page, RANGE)


def test_configure_raises_when_a_date_value_is_rejected_by_fill():
    from_field = FakeFieldLocator(fill_error=RuntimeError("input disabled"))
    page = FakeConfigurePage(from_field=from_field)
    orchestrator = _orchestrator_with()

    with pytest.raises(PrismaDateValueRejectedError, match="start date field"):
        orchestrator.configure(page, RANGE)


def test_configure_raises_when_the_filled_value_does_not_verify():
    # Simulates a masked input silently ignoring the fill (echo_fill=False
    # leaves it at the placeholder), so the post-fill read-back must catch it.
    from_field = FakeFieldLocator(echo_fill=False)
    page = FakeConfigurePage(from_field=from_field)
    orchestrator = _orchestrator_with()

    with pytest.raises(PrismaDateValueRejectedError, match="was not accepted"):
        orchestrator.configure(page, RANGE)


def test_configure_raises_when_prisma_marks_the_value_aria_invalid():
    to_field = FakeFieldLocator(aria_invalid="true")
    page = FakeConfigurePage(to_field=to_field)
    orchestrator = _orchestrator_with()

    with pytest.raises(PrismaDateValueRejectedError, match="rejected the end date"):
        orchestrator.configure(page, RANGE)


# --- Real-Windows defect (2026-08-03): dates not actually applied ---------
#
# Root cause: this masked, framework-managed date field only guarantees its
# own committed value (the one the real reporting/export request uses,
# exposed as `data-test-iso-value` per live DOM inspection) is up to date
# after a blur; nothing previously forced that, and verification only ever
# checked the *date* portion of the visible masked text, never the
# time-of-day segment `_fill_field` sets to widen the selection to a full
# calendar day. Both gaps are fixed and covered below.


def test_configure_fills_both_fields_with_the_exact_requested_date_and_time():
    """Both application-selected dates must reach the page automation with
    the exact PRISMA-required `DD.MM.YYYY HH:mm` text and the full-day
    00:00/23:59 widening, not just the bare date.
    """
    page = FakeConfigurePage()
    orchestrator = _orchestrator_with()

    orchestrator.configure(page, RANGE)

    assert page.from_field.fill_calls == ["01.08.2026 00:00"]
    assert page.to_field.fill_calls == ["31.08.2026 23:59"]


def test_configure_blurs_each_date_field_after_filling_it_before_verifying():
    """The exact required event sequence for this framework-managed field:
    click, clear, fill, then blur — in that order — before the value is
    treated as verified, so any commit-on-blur logic in the page's own
    component runs deterministically instead of relying on an incidental
    later blur from focusing the next control.
    """
    page = FakeConfigurePage()
    orchestrator = _orchestrator_with()

    orchestrator.configure(page, RANGE)

    for field in (page.from_field, page.to_field):
        assert field.action_order == [
            "click", "press:Control+A", "press:Delete", "fill", "evaluate:blur",
        ]
        assert field.blur_calls == 1


def test_configure_raises_when_blurring_the_field_fails():
    from_field = FakeFieldLocator(blur_error=RuntimeError("detached"))
    page = FakeConfigurePage(from_field=from_field)
    orchestrator = _orchestrator_with()

    with pytest.raises(PrismaDateValueRejectedError, match="start date field"):
        orchestrator.configure(page, RANGE)


def test_configure_raises_when_the_filled_time_of_day_does_not_verify():
    """Regression: a value that looked accepted only because the *date*
    substring was present previously passed even with the wrong time — e.g.
    the masked input's time segment silently staying at PRISMA's own
    pre-populated default instead of the requested 00:00/23:59 full-day
    widening. This is exactly the failure mode `_fill_field`'s own docstring
    documents for an unclear field; verification must now catch it even when
    only the time (not the date) is wrong.
    """
    from_field = FakeFieldLocator()
    # A field that echoes the correct date but a wrong, unrequested time —
    # the masked input's own default, not the one requested.
    from_field.fill = lambda value, timeout=None: setattr(
        from_field, "_value", "01.08.2026 06:00"
    )
    page = FakeConfigurePage(from_field=from_field)
    orchestrator = _orchestrator_with()

    with pytest.raises(PrismaDateValueRejectedError, match="start time value was not accepted"):
        orchestrator.configure(page, RANGE)


def test_configure_raises_when_the_committed_value_does_not_match_the_visible_text():
    """Root-cause regression: the visible masked text can look correct
    (Playwright's `fill()` always sets it synchronously) while the page's
    own framework-tracked committed value — the one actually used for the
    real PRISMA reporting/export request — has not caught up. This is
    exactly the reported real-Windows defect: dates that appear selected in
    the control are not actually applied to the official PRISMA reporting
    page. Verification must fail rather than continue with a potentially
    wrong range.
    """
    from_field = FakeFieldLocator(iso_committed_override=False)
    page = FakeConfigurePage(from_field=from_field)
    orchestrator = _orchestrator_with()

    with pytest.raises(
        PrismaDateValueRejectedError, match="start date value was not committed"
    ):
        orchestrator.configure(page, RANGE)


def test_configure_tolerates_a_field_without_the_committed_value_attribute():
    """A PRISMA build that never exposes `data-test-iso-value` (the
    committed-value signal did not exist before this fix's live discovery)
    must not be treated as a failure: the text-based date+time check above
    already ran and is the fallback signal in that case.
    """
    from_field = FakeFieldLocator(iso_committed_override=None)
    page = FakeConfigurePage(from_field=from_field)
    orchestrator = _orchestrator_with()

    orchestrator.configure(page, RANGE)  # must not raise


def test_configure_raises_when_reading_the_committed_value_itself_fails():
    # Blur succeeds (it's a distinct evaluate() call from the later
    # committed-value read); only the committed-value read itself fails.
    to_field = FakeFieldLocator(committed_read_error=RuntimeError("context destroyed"))
    page = FakeConfigurePage(to_field=to_field)
    orchestrator = _orchestrator_with()

    with pytest.raises(
        PrismaDateValueRejectedError, match="end date value could not be confirmed as committed"
    ):
        orchestrator.configure(page, RANGE)
    assert to_field.blur_calls == 1


def test_verify_filter_applied_requires_the_time_of_day_not_only_the_dates():
    """Regression at the filter-chip layer: previously only the two dates
    were required in the applied-filter chip, so a chip showing the right
    dates but a wrong/unset time (e.g. reverted to PRISMA's own pre-populated
    default) incorrectly passed, even though the actually-applied range would
    exclude part of the requested day.
    """
    chip = FakeAppliedFilterChip(
        page=None, text_override="Start of Auction\n01.08.2026, 06:00 - 31.08.2026, 23:59",
    )
    page = FakeConfigurePage(applied_filter_chip=chip)
    orchestrator = _orchestrator_with()

    with pytest.raises(
        PrismaDateValueRejectedError, match="does not match the selected range"
    ):
        orchestrator.configure(page, RANGE)


def test_verify_filter_applied_accepts_the_chip_when_both_dates_and_times_match():
    chip = FakeAppliedFilterChip(
        page=None,
        text_override="Start of Auction\n01.08.2026, 00:00 - 31.08.2026, 23:59",
    )
    page = FakeConfigurePage(applied_filter_chip=chip)
    orchestrator = _orchestrator_with()

    orchestrator.configure(page, RANGE)  # must not raise


def test_configure_raises_when_the_filter_apply_button_is_unavailable():
    page = FakeConfigurePage(filter_button=FakeButtonLocator(visible=False))
    orchestrator = _orchestrator_with()

    with pytest.raises(PrismaDateFilterPanelError, match="could not be applied"):
        orchestrator.configure(page, RANGE)


def test_configure_raises_when_download_listener_registration_fails():
    page = FakeConfigurePage(on_error=RuntimeError("listener API unavailable"))
    orchestrator = _orchestrator_with()

    with pytest.raises(PrismaDownloadListenerError):
        orchestrator.configure(page, RANGE)


def test_configure_never_uses_the_old_guessed_from_date_label_locator():
    """Regression: P.36.14's first real-validation attempt used a guessed
    `get_by_label(/from\\s*date/i)` locator that never matched the real page
    (see ROADMAP.md). `FakeConfigurePage` has no `get_by_label` method at
    all, so any reintroduction of that call fails immediately with
    AttributeError rather than silently passing.
    """
    page = FakeConfigurePage()
    assert not hasattr(page, "get_by_label")

    orchestrator = _orchestrator_with()
    orchestrator.configure(page, RANGE)  # must not raise AttributeError


# --- Cookie-consent banner handling -----------------------------------------
#
# Live inspection of the real public PRISMA page (2026-08-02) found a fixed
# bottom banner ("Take part in PRISMA usability research") with no test id or
# ARIA landmark, offering two plain, unattributed controls with exact visible
# text "Decline" and "Accept & Close" (see ROADMAP.md/module docstring). Both
# are absent from `FakeConfigurePage` by default, so every test above already
# proves the "banner absent" path works without special-casing.


def test_configure_proceeds_when_the_cookie_banner_is_absent():
    page = FakeConfigurePage()
    orchestrator = _orchestrator_with()

    orchestrator.configure(page, RANGE)  # must not raise

    assert page.download_button.click_calls == 1


def test_configure_dismisses_the_cookie_banner_via_decline_when_present():
    decline = FakeButtonLocator()
    page = FakeConfigurePage(cookie_decline_button=decline)
    orchestrator = _orchestrator_with()

    orchestrator.configure(page, RANGE)

    assert decline.click_calls == 1
    assert page.cookie_accept_button.click_calls == 0
    assert page.download_button.click_calls == 1


def test_configure_dismisses_the_cookie_banner_via_accept_when_decline_is_not_offered():
    """A banner variant offering only a single accept-style control is still
    handled: "Decline" is tried first and, when absent, "Accept & Close" is
    used instead (see requirement: prefer accepting OR dismissing).
    """
    accept = FakeButtonLocator()
    page = FakeConfigurePage(cookie_accept_button=accept)
    orchestrator = _orchestrator_with()

    orchestrator.configure(page, RANGE)

    assert accept.click_calls == 1
    assert page.download_button.click_calls == 1


def test_configure_raises_when_the_cookie_banner_cannot_be_clicked():
    decline = FakeButtonLocator(click_error=RuntimeError("element intercepted"))
    page = FakeConfigurePage(cookie_decline_button=decline)
    orchestrator = _orchestrator_with()

    with pytest.raises(PrismaCookieConsentBannerError, match="could not be dismissed"):
        orchestrator.configure(page, RANGE)

    # The CSV control must never be activated if the banner could not be
    # dismissed.
    assert page.download_button.click_calls == 0


def test_configure_raises_when_the_cookie_banner_does_not_close_after_being_dismissed():
    decline = FakeButtonLocator(hidden_after_click=False)
    page = FakeConfigurePage(cookie_decline_button=decline)
    orchestrator = _orchestrator_with()

    with pytest.raises(PrismaCookieConsentBannerError, match="did not close"):
        orchestrator.configure(page, RANGE)

    assert page.download_button.click_calls == 0


def test_configure_raises_when_the_csv_control_remains_obstructed_after_banner_handling():
    """Requirement: verify the CSV control is no longer obstructed before
    clicking it. Even after the banner claims to have closed, an
    `elementFromPoint` check catching a leftover overlay must still block
    the click rather than force it through.
    """
    page = FakeConfigurePage(
        cookie_decline_button=FakeButtonLocator(),
        download_button=FakeButtonLocator(obstructed=True),
    )
    orchestrator = _orchestrator_with()

    with pytest.raises(PrismaCookieConsentBannerError, match="obstructed"):
        orchestrator.configure(page, RANGE)

    assert page.download_button.click_calls == 0


def test_configure_never_uses_force_to_click_the_cookie_banner_or_csv_control():
    decline = FakeButtonLocator()
    page = FakeConfigurePage(cookie_decline_button=decline)
    orchestrator = _orchestrator_with()

    orchestrator.configure(page, RANGE)

    assert True not in decline.click_force_values
    assert True not in page.download_button.click_force_values


def test_configure_scrolls_the_csv_control_into_view_before_checking_obstruction():
    """Regression: live validation on the real, long PRISMA results page found
    the CSV control is very often below the fold, and `elementFromPoint` on
    unscrolled coordinates always misses an out-of-viewport point — which
    would misreport every off-screen control as obstructed unless it is
    scrolled into view first, mirroring Playwright's own click() behavior.
    """
    page = FakeConfigurePage()
    orchestrator = _orchestrator_with()

    orchestrator.configure(page, RANGE)

    assert page.download_button.scroll_calls == 1


def test_configure_tolerates_the_scroll_into_view_step_failing():
    page = FakeConfigurePage(
        download_button=FakeButtonLocator(scroll_error=RuntimeError("no scrollable ancestor"))
    )
    orchestrator = _orchestrator_with()

    orchestrator.configure(page, RANGE)  # must not raise

    assert page.download_button.click_calls == 1


def test_configure_tolerates_the_obstruction_check_itself_failing():
    """The elementFromPoint verification is best-effort, like the networkidle
    wait: if it cannot run at all (e.g. an unsupported API), it must not
    block the whole attempt — the normal click (with its own actionability
    retries) still gets a chance to succeed or fail on its own terms.
    """
    page = FakeConfigurePage(
        download_button=FakeButtonLocator(obstructed_error=RuntimeError("no CDP"))
    )
    orchestrator = _orchestrator_with()

    orchestrator.configure(page, RANGE)  # must not raise

    assert page.download_button.click_calls == 1


def test_configure_registers_the_download_listener_on_the_context_not_the_page():
    page = FakeConfigurePage()
    orchestrator = _orchestrator_with()

    waiter = orchestrator.configure(page, RANGE)

    assert page.context.on_calls == [("download", waiter.on_download)]
    assert not hasattr(page, "on")


# --- Applied-filter verification (P.36.14 live-site date-filter fix) -------
#
# Live DOM inspection (2026-08-02, re-verified against the live site) found
# the applied "Start of Auction" range is echoed back into a dedicated
# filter-chip element (data-testid="filter-startOfAuctionFrom") once
# "Filter" is clicked. `FakeConfigurePage`'s chip defaults to reflecting
# whatever was actually filled, so every prior configure() test above
# already exercises the "verification succeeds" path; the tests below cover
# its failure modes explicitly.


def test_configure_verifies_the_applied_filter_chip_before_locating_the_download_control():
    page = FakeConfigurePage()
    orchestrator = _orchestrator_with()

    orchestrator.configure(page, RANGE)

    # The chip is checked (after both date fields are located) before the
    # download control is even located.
    assert page.get_by_test_id_calls == [
        "startOfAuctionFrom", "startOfAuctionTo", "filter-startOfAuctionFrom",
    ]
    assert page.download_button.click_calls == 1


def test_configure_raises_when_the_applied_filter_chip_cannot_be_found():
    page = FakeConfigurePage(
        applied_filter_chip=FakeAppliedFilterChip(None, visible=False)
    )
    orchestrator = _orchestrator_with()

    with pytest.raises(PrismaDateFilterPanelError, match="could not be confirmed as applied"):
        orchestrator.configure(page, RANGE)

    assert page.download_button.click_calls == 0


def test_configure_raises_when_the_applied_filter_chip_does_not_match_the_selected_range():
    page = FakeConfigurePage(
        applied_filter_chip=FakeAppliedFilterChip(
            None, text_override="Start of Auction\n01.01.2020 00:00 - 02.01.2020 23:59"
        )
    )
    orchestrator = _orchestrator_with()

    with pytest.raises(PrismaDateValueRejectedError, match="does not match the selected range"):
        orchestrator.configure(page, RANGE)

    assert page.download_button.click_calls == 0


def test_configure_raises_when_a_visible_validation_error_remains_after_applying_the_filter():
    page = FakeConfigurePage(alerts=[FakeAlertItem(visible=True, text="Invalid date range.")])
    orchestrator = _orchestrator_with()

    with pytest.raises(PrismaDateValueRejectedError, match="validation error"):
        orchestrator.configure(page, RANGE)

    assert page.download_button.click_calls == 0


def test_configure_ignores_a_present_but_not_visible_validation_alert():
    page = FakeConfigurePage(alerts=[FakeAlertItem(visible=False, text="Stale alert.")])
    orchestrator = _orchestrator_with()

    orchestrator.configure(page, RANGE)  # must not raise

    assert page.download_button.click_calls == 1


# --- Large-result confirmation modal (P.36.14 large-export flow) ----------
#
# Live DOM inspection (2026-08-02) found PRISMA's own confirmation dialog
# (role="dialog", heading "Warning", text "Your download contains only N of
# M items.") for filtered result sets exceeding its export limit. It exposes
# its own "CSV" confirm button — same accessible name as the main page
# control, but scoped to the dialog so it is never confused with it.


def test_configure_treats_absence_of_the_large_result_modal_as_normal():
    page = FakeConfigurePage()  # large_result_dialog is None (absent) by default
    orchestrator = _orchestrator_with()

    orchestrator.configure(page, RANGE)  # must not raise

    assert page.download_button.click_calls == 1


def test_configure_confirms_the_large_result_modal_when_present():
    confirm = FakeButtonLocator()
    dialog = FakeLargeResultDialog(confirm_button=confirm)
    page = FakeConfigurePage(large_result_dialog=dialog)
    orchestrator = _orchestrator_with()

    orchestrator.configure(page, RANGE)

    # The main page CSV control is activated first, then the dialog's own
    # scoped confirm control — never confused with each other.
    assert page.download_button.click_calls == 1
    assert confirm.click_calls == 1
    assert ("button", "CSV", True) in dialog.get_by_role_calls


def test_configure_raises_when_the_large_result_modal_confirm_control_cannot_be_found():
    dialog = FakeLargeResultDialog(confirm_button=FakeButtonLocator(visible=False))
    page = FakeConfigurePage(large_result_dialog=dialog)
    orchestrator = _orchestrator_with()

    with pytest.raises(PrismaLargeResultConfirmationError):
        orchestrator.configure(page, RANGE)

    assert page.download_button.click_calls == 1


def test_configure_raises_when_the_large_result_modal_confirm_control_cannot_be_activated():
    dialog = FakeLargeResultDialog(
        confirm_button=FakeButtonLocator(click_error=RuntimeError("element intercepted"))
    )
    page = FakeConfigurePage(large_result_dialog=dialog)
    orchestrator = _orchestrator_with()

    with pytest.raises(PrismaLargeResultConfirmationError):
        orchestrator.configure(page, RANGE)


def test_configure_never_alters_the_date_range_to_avoid_the_large_result_modal():
    dialog = FakeLargeResultDialog()
    page = FakeConfigurePage(large_result_dialog=dialog)
    orchestrator = _orchestrator_with()

    orchestrator.configure(page, RANGE)

    assert page.from_field.fill_calls == ["01.08.2026 00:00"]
    assert page.to_field.fill_calls == ["31.08.2026 23:59"]


def test_download_captured_after_large_result_modal_confirmation(tmp_path):
    """End-to-end: the download listener registered before the main CSV
    click is still what observes the download after the modal's own confirm
    control is clicked — no second listener registration is needed.
    """
    dialog = FakeLargeResultDialog()
    page = FakeConfigurePage(large_result_dialog=dialog)
    orchestrator = _orchestrator_with()

    waiter = orchestrator.configure(page, RANGE)
    event, callback = page.context.on_calls[0]
    assert event == "download"
    download = FakeDownload("Auction_overview.csv")
    callback(download)

    cancel_event = threading.Event()
    result = orchestrator.await_and_finalize(
        waiter, RANGE, tmp_path, cancel_event, deadline=time.monotonic() + 60.0,
    )

    assert result.outcome is PrismaDownloadOutcome.SUCCESS
    assert result.csv_path == tmp_path / "Auction_overview_2026-08-01_2026-08-31.csv"


# --- PrismaDownloadOrchestrator.await_and_finalize() -----------------------


class FakeDownload:
    def __init__(self, suggested_filename, *, failure=None):
        self.suggested_filename = suggested_filename
        self._failure = failure
        self.save_as_calls = []
        self.cancel_calls = 0

    def failure(self):
        return self._failure

    def save_as(self, path):
        self.save_as_calls.append(path)
        Path(path).write_bytes(b"a,b,c\n1,2,3\n")

    def cancel(self):
        self.cancel_calls += 1


def _orchestrator():
    return PrismaDownloadOrchestrator(timeout_seconds=60.0)


def test_await_and_finalize_returns_none_while_nothing_has_happened_yet(tmp_path):
    orchestrator = _orchestrator()
    waiter = PrismaDownloadWaiter()
    cancel_event = threading.Event()

    result = orchestrator.await_and_finalize(
        waiter, RANGE, tmp_path, cancel_event,
        deadline=time.monotonic() + 60.0,
    )

    assert result is None


def test_await_and_finalize_times_out_after_the_deadline(tmp_path):
    orchestrator = _orchestrator()
    waiter = PrismaDownloadWaiter()
    cancel_event = threading.Event()

    result = orchestrator.await_and_finalize(
        waiter, RANGE, tmp_path, cancel_event,
        deadline=time.monotonic() - 1.0,
    )

    assert result.outcome is PrismaDownloadOutcome.DOWNLOAD_TIMEOUT
    assert result.csv_path is None


def test_await_and_finalize_returns_none_on_cancellation_before_any_download(tmp_path):
    orchestrator = _orchestrator()
    waiter = PrismaDownloadWaiter()
    cancel_event = threading.Event()
    cancel_event.set()

    result = orchestrator.await_and_finalize(
        waiter, RANGE, tmp_path, cancel_event,
        deadline=time.monotonic() + 60.0,
    )

    assert result is None


def test_await_and_finalize_saves_a_successful_csv_download_with_the_dated_name(tmp_path):
    orchestrator = _orchestrator()
    waiter = PrismaDownloadWaiter()
    download = FakeDownload("Auction_overview.csv")
    waiter.on_download(download)
    cancel_event = threading.Event()

    result = orchestrator.await_and_finalize(
        waiter, RANGE, tmp_path, cancel_event,
        deadline=time.monotonic() + 60.0,
    )

    assert result.outcome is PrismaDownloadOutcome.SUCCESS
    assert result.csv_path == tmp_path / "Auction_overview_2026-08-01_2026-08-31.csv"
    assert result.csv_path.exists()
    assert download.save_as_calls == [str(result.csv_path)]


def test_finalize_avoids_overwriting_an_existing_file_with_the_same_dated_name(tmp_path):
    existing = tmp_path / "Auction_overview_2026-08-01_2026-08-31.csv"
    existing.write_text("previous run", encoding="utf-8")
    orchestrator = _orchestrator()
    waiter = PrismaDownloadWaiter()
    download = FakeDownload("Auction_overview.csv")
    waiter.on_download(download)
    cancel_event = threading.Event()

    result = orchestrator.await_and_finalize(
        waiter, RANGE, tmp_path, cancel_event,
        deadline=time.monotonic() + 60.0,
    )

    assert result.outcome is PrismaDownloadOutcome.SUCCESS
    assert result.csv_path == tmp_path / "Auction_overview_2026-08-01_2026-08-31_2.csv"
    assert existing.read_text(encoding="utf-8") == "previous run"


def test_finalize_rejects_a_non_csv_suggested_filename_without_saving(tmp_path):
    orchestrator = _orchestrator()
    waiter = PrismaDownloadWaiter()
    download = FakeDownload("Auction_overview.xlsx")
    waiter.on_download(download)
    cancel_event = threading.Event()

    result = orchestrator.await_and_finalize(
        waiter, RANGE, tmp_path, cancel_event,
        deadline=time.monotonic() + 60.0,
    )

    assert result.outcome is PrismaDownloadOutcome.NOT_CSV
    assert result.csv_path is None
    assert download.save_as_calls == []
    assert download.cancel_calls == 1
    assert list(tmp_path.iterdir()) == []


def test_finalize_classifies_a_cancelled_download(tmp_path):
    orchestrator = _orchestrator()
    waiter = PrismaDownloadWaiter()
    download = FakeDownload("Auction_overview.csv", failure="canceled")
    waiter.on_download(download)
    cancel_event = threading.Event()

    result = orchestrator.await_and_finalize(
        waiter, RANGE, tmp_path, cancel_event,
        deadline=time.monotonic() + 60.0,
    )

    assert result.outcome is PrismaDownloadOutcome.DOWNLOAD_CANCELLED
    assert result.csv_path is None
    assert download.save_as_calls == []


def test_finalize_classifies_an_interrupted_download(tmp_path):
    orchestrator = _orchestrator()
    waiter = PrismaDownloadWaiter()
    download = FakeDownload("Auction_overview.csv", failure="net::ERR_CONNECTION_RESET")
    waiter.on_download(download)
    cancel_event = threading.Event()

    result = orchestrator.await_and_finalize(
        waiter, RANGE, tmp_path, cancel_event,
        deadline=time.monotonic() + 60.0,
    )

    assert result.outcome is PrismaDownloadOutcome.DOWNLOAD_INTERRUPTED
    assert result.csv_path is None


def test_finalize_reports_save_failure_without_crashing(tmp_path):
    orchestrator = _orchestrator()
    waiter = PrismaDownloadWaiter()
    download = FakeDownload("Auction_overview.csv")

    def fail_save(path):
        raise RuntimeError("disk full")

    download.save_as = fail_save
    waiter.on_download(download)
    cancel_event = threading.Event()

    result = orchestrator.await_and_finalize(
        waiter, RANGE, tmp_path, cancel_event,
        deadline=time.monotonic() + 60.0,
    )

    assert result.outcome is PrismaDownloadOutcome.SAVE_FAILED


def test_finalize_detects_failure_reported_only_after_save_as(tmp_path):
    orchestrator = _orchestrator()
    waiter = PrismaDownloadWaiter()
    download = FakeDownload("Auction_overview.csv")
    calls = {"count": 0}

    def failure_after_save():
        calls["count"] += 1
        return "canceled" if calls["count"] > 1 else None

    download.failure = failure_after_save
    waiter.on_download(download)
    cancel_event = threading.Event()

    result = orchestrator.await_and_finalize(
        waiter, RANGE, tmp_path, cancel_event,
        deadline=time.monotonic() + 60.0,
    )

    assert result.outcome is PrismaDownloadOutcome.DOWNLOAD_CANCELLED


def test_finalize_rejects_a_zero_byte_saved_download(tmp_path):
    """A download that reports success but saved zero bytes never actually
    completed; it must never be reported as SUCCESS, and the empty artifact
    must not be left behind in the configured directory.
    """
    orchestrator = _orchestrator()
    waiter = PrismaDownloadWaiter()
    download = FakeDownload("Auction_overview.csv")

    def save_empty(path):
        download.save_as_calls.append(path)
        Path(path).write_bytes(b"")

    download.save_as = save_empty
    waiter.on_download(download)
    cancel_event = threading.Event()

    result = orchestrator.await_and_finalize(
        waiter, RANGE, tmp_path, cancel_event,
        deadline=time.monotonic() + 60.0,
    )

    assert result.outcome is PrismaDownloadOutcome.DOWNLOAD_INTERRUPTED
    assert list(tmp_path.iterdir()) == []


def test_finalize_sanitizes_a_path_traversal_suggested_filename_to_stay_inside_the_directory(
    tmp_path,
):
    """`suggested_filename` is untrusted, PRISMA/browser-supplied input.
    Final output must never escape the configured download directory
    regardless of what it contains.
    """
    orchestrator = _orchestrator()
    waiter = PrismaDownloadWaiter()
    download = FakeDownload("../../evil.csv")
    waiter.on_download(download)
    cancel_event = threading.Event()

    result = orchestrator.await_and_finalize(
        waiter, RANGE, tmp_path, cancel_event,
        deadline=time.monotonic() + 60.0,
    )

    assert result.outcome is PrismaDownloadOutcome.SUCCESS
    assert result.csv_path.parent == tmp_path
    assert result.csv_path.name == "evil_2026-08-01_2026-08-31.csv"
    # The naive, unsafe approach this guards against would treat the whole
    # untrusted string as a relative path and resolve it two levels above
    # the configured directory; confirm nothing was ever written there.
    escaped_path = tmp_path / "../../evil_2026-08-01_2026-08-31.csv"
    assert not escaped_path.exists()


# --- Multiple-download rejection and context-level observation ------------


def test_finalize_rejects_a_second_download_event_and_cancels_it(tmp_path):
    orchestrator = _orchestrator()
    waiter = PrismaDownloadWaiter()
    first = FakeDownload("Auction_overview.csv")
    second = FakeDownload("Auction_overview.csv")
    waiter.on_download(first)
    waiter.on_download(second)
    cancel_event = threading.Event()

    result = orchestrator.await_and_finalize(
        waiter, RANGE, tmp_path, cancel_event,
        deadline=time.monotonic() + 60.0,
    )

    assert result.outcome is PrismaDownloadOutcome.MULTIPLE_DOWNLOADS
    assert result.csv_path is None
    # The second (extra) download is cancelled the moment it arrives.
    assert second.cancel_calls == 1
    # The first is cancelled too once finalize() detects the collision.
    assert first.cancel_calls == 1
    assert first.save_as_calls == []
    assert list(tmp_path.iterdir()) == []


def test_finalize_discards_a_saved_file_when_a_second_download_arrives_during_save(
    tmp_path,
):
    """Models the race where the second download event lands between the
    not-CSV/failure checks and `save_as()` finishing: the saved artifact must
    be discarded rather than silently reported as a successful single
    download.
    """
    orchestrator = _orchestrator()
    waiter = PrismaDownloadWaiter()
    first = FakeDownload("Auction_overview.csv")

    def save_and_race(path):
        FakeDownload.save_as(first, path)
        waiter.on_download(FakeDownload("Auction_overview.csv"))

    first.save_as = save_and_race
    waiter.on_download(first)
    cancel_event = threading.Event()

    result = orchestrator.await_and_finalize(
        waiter, RANGE, tmp_path, cancel_event,
        deadline=time.monotonic() + 60.0,
    )

    assert result.outcome is PrismaDownloadOutcome.MULTIPLE_DOWNLOADS
    assert result.csv_path is None
    assert list(tmp_path.iterdir()) == []


def test_waiter_on_download_accepts_exactly_one_download_from_the_originating_page():
    waiter = PrismaDownloadWaiter()
    download = FakeDownload("Auction_overview.csv")

    waiter.on_download(download)

    assert waiter.download is download
    assert waiter.multiple is False
    assert waiter.event.is_set()


def test_waiter_on_download_captures_a_download_triggered_by_a_newly_opened_page():
    """The real PRISMA CSV export opens in a new tab (see ROADMAP.md); since
    the listener is context-scoped, the waiter must accept a download that
    reports a different originating page just like one from the original
    page — it must never assume `download.page` is the page it was configured
    against.
    """
    new_tab = object()
    waiter = PrismaDownloadWaiter()
    download = FakeDownload("Auction_overview.csv")
    download.page = new_tab

    waiter.on_download(download)

    assert waiter.download is download
    assert waiter.multiple is False


def test_context_level_download_registration_observes_downloads_dispatched_through_it():
    """End-to-end through `configure()`: firing the exact callback registered
    on `page.context` (not `page`) must reach the waiter, proving observation
    is genuinely context-scoped rather than merely page-scoped.
    """
    page = FakeConfigurePage()
    orchestrator = _orchestrator_with()
    waiter = orchestrator.configure(page, RANGE)
    download = FakeDownload("Auction_overview.csv")

    event, callback = page.context.on_calls[0]
    assert event == "download"
    callback(download)

    assert waiter.download is download
    assert waiter.event.is_set()


# --- Approved production fallback: bounded filesystem observation ---------
#
# Real installed Chrome/Edge was found not to reliably deliver Playwright's
# "download" event to the controlling process even though the download
# completes (see ROADMAP.md's P.36.14 real-Chrome download-event delivery
# gap). `PrismaDownloadFilesystemWaiter` is the approved, bounded, cancellable
# fallback; the Playwright event above remains primary and is always checked
# first by `await_and_finalize()`.


def test_configure_snapshot_excludes_a_pre_existing_file_from_the_fallback(tmp_path):
    (tmp_path / "already-there.csv").write_text("old", encoding="utf-8")
    page = FakeConfigurePage()
    orchestrator = _orchestrator_with()

    waiter = orchestrator.configure(page, RANGE, tmp_path)

    assert waiter.filesystem_fallback is not None
    result = waiter.filesystem_fallback.poll()
    assert result.outcome.value == "not_ready"


def test_configure_without_a_download_directory_leaves_the_fallback_disabled():
    page = FakeConfigurePage()
    orchestrator = _orchestrator_with()

    waiter = orchestrator.configure(page, RANGE)

    assert waiter.filesystem_fallback is None


def test_filesystem_fallback_ignores_partial_crdownload_files(tmp_path):
    fallback = PrismaDownloadFilesystemWaiter.snapshot(tmp_path)
    (tmp_path / "Auction_overview.csv.crdownload").write_bytes(b"partial-data")

    result = fallback.poll()

    assert result.outcome.value == "not_ready"
    assert result.path is None


def test_filesystem_fallback_waits_for_size_stability_before_accepting(tmp_path):
    fallback = PrismaDownloadFilesystemWaiter.snapshot(tmp_path)
    target = tmp_path / "Auction_overview.csv"
    target.write_bytes(b"a")

    assert fallback.poll().outcome.value == "not_ready"  # size 1, first reading

    target.write_bytes(b"ab")  # size changes to 2: stability count resets
    assert fallback.poll().outcome.value == "not_ready"  # size 2, first reading
    assert fallback.poll().outcome.value == "not_ready"  # size 2, second reading

    final = fallback.poll()  # size 2, third consecutive matching reading

    assert final.outcome.value == "ready"
    assert final.path == target


def test_filesystem_fallback_rejects_multiple_new_csv_files(tmp_path):
    fallback = PrismaDownloadFilesystemWaiter.snapshot(tmp_path)
    (tmp_path / "a.csv").write_bytes(b"1")
    (tmp_path / "b.csv").write_bytes(b"2")

    result = fallback.poll()

    assert result.outcome.value == "multiple"
    assert result.path is None


def test_filesystem_fallback_accepts_a_uuid_named_artifact_without_a_csv_suffix(tmp_path):
    """Real-Windows defect (2026-08-03): Chrome/CDP's own download
    interception ("allowAndName" behavior) writes the raw artifact under a
    framework-generated, UUID-like name with no reliable extension. A
    candidate must be recognized by size stability alone, never by a
    required ``.csv`` suffix, or a genuinely completed download would sit
    in the configured directory forever, unrecognized.
    """
    fallback = PrismaDownloadFilesystemWaiter.snapshot(tmp_path)
    target = tmp_path / "3fa85f64-5717-4562-b3fc-2c963f66afa6"
    target.write_bytes(b"a,b,c\n1,2,3\n")

    assert fallback.poll().outcome.value == "not_ready"  # first stable reading
    assert fallback.poll().outcome.value == "not_ready"  # second stable reading
    final = fallback.poll()  # third consecutive matching reading

    assert final.outcome.value == "ready"
    assert final.path == target


def test_filesystem_fallback_rejects_multiple_new_files_regardless_of_extension(tmp_path):
    """The broadened, suffix-independent candidate recognition above must
    still refuse ambiguity: two new non-partial files, extension or not, are
    never silently narrowed down to one.
    """
    fallback = PrismaDownloadFilesystemWaiter.snapshot(tmp_path)
    (tmp_path / "3fa85f64-5717-4562-b3fc-2c963f66afa6").write_bytes(b"1")
    (tmp_path / "b.csv").write_bytes(b"2")

    result = fallback.poll()

    assert result.outcome.value == "multiple"
    assert result.path is None


def test_filesystem_fallback_rejects_a_stable_empty_file(tmp_path):
    """A file that stops changing size at zero bytes never actually received
    any content: it must never be accepted as a completed result, even
    though it is otherwise "stable" and readable.
    """
    fallback = PrismaDownloadFilesystemWaiter.snapshot(tmp_path)
    (tmp_path / "Auction_overview.csv").write_bytes(b"")

    assert fallback.poll().outcome.value == "not_ready"
    assert fallback.poll().outcome.value == "not_ready"
    final = fallback.poll()

    assert final.outcome.value == "interrupted"
    assert final.path is None


def test_filesystem_fallback_never_scans_outside_the_configured_directory(tmp_path):
    outside = tmp_path.parent / f"{tmp_path.name}-sibling-outside.csv"
    outside.write_bytes(b"unrelated")
    try:
        fallback = PrismaDownloadFilesystemWaiter.snapshot(tmp_path)

        result = fallback.poll()

        assert result.outcome.value == "not_ready"
    finally:
        outside.unlink(missing_ok=True)


def test_await_and_finalize_falls_back_to_filesystem_observation(tmp_path):
    orchestrator = _orchestrator()
    waiter = PrismaDownloadWaiter()
    waiter.filesystem_fallback = PrismaDownloadFilesystemWaiter.snapshot(tmp_path)
    cancel_event = threading.Event()
    downloaded = tmp_path / "Auction_overview.csv"
    downloaded.write_bytes(b"a,b,c\n1,2,3\n")

    result = None
    for _ in range(5):
        result = orchestrator.await_and_finalize(
            waiter, RANGE, tmp_path, cancel_event,
            deadline=time.monotonic() + 60.0,
        )
        if result is not None:
            break

    assert result is not None
    assert result.outcome is PrismaDownloadOutcome.SUCCESS
    assert result.csv_path == tmp_path / "Auction_overview_2026-08-01_2026-08-31.csv"
    assert result.csv_path.exists()
    assert not downloaded.exists()  # moved into place, not copied


def test_await_and_finalize_prefers_a_late_playwright_event_over_the_fallback(tmp_path):
    """If the Playwright "download" event arrives between one poll and the
    next (after the fallback already found a stable, readable file), the
    primary mechanism still wins, since it carries the real `Download` object.
    """
    orchestrator = _orchestrator()
    waiter = PrismaDownloadWaiter()
    waiter.filesystem_fallback = PrismaDownloadFilesystemWaiter.snapshot(tmp_path)
    cancel_event = threading.Event()
    stray = tmp_path / "Auction_overview.csv"
    stray.write_bytes(b"a,b,c\n1,2,3\n")
    for _ in range(2):
        assert orchestrator.await_and_finalize(
            waiter, RANGE, tmp_path, cancel_event,
            deadline=time.monotonic() + 60.0,
        ) is None

    download = FakeDownload("Auction_overview.csv")
    waiter.on_download(download)

    result = orchestrator.await_and_finalize(
        waiter, RANGE, tmp_path, cancel_event,
        deadline=time.monotonic() + 60.0,
    )

    assert result.outcome is PrismaDownloadOutcome.SUCCESS
    assert download.save_as_calls == [str(result.csv_path)]


def test_await_and_finalize_produces_exactly_one_dated_output_when_the_event_wins_the_race(
    tmp_path,
):
    """No duplicate final file is produced when the event and fallback both
    observe the same underlying download: the primary path must win and the
    fallback must never also finalize the same artifact.
    """
    orchestrator = _orchestrator()
    waiter = PrismaDownloadWaiter()
    waiter.filesystem_fallback = PrismaDownloadFilesystemWaiter.snapshot(tmp_path)
    cancel_event = threading.Event()
    raw_artifact = tmp_path / "3fa85f64-5717-4562-b3fc-2c963f66afa6"
    raw_artifact.write_bytes(b"a,b,c\n1,2,3\n")
    for _ in range(2):
        assert orchestrator.await_and_finalize(
            waiter, RANGE, tmp_path, cancel_event,
            deadline=time.monotonic() + 60.0,
        ) is None

    download = FakeDownload("Auction_overview.csv")
    waiter.on_download(download)

    result = orchestrator.await_and_finalize(
        waiter, RANGE, tmp_path, cancel_event,
        deadline=time.monotonic() + 60.0,
    )

    assert result.outcome is PrismaDownloadOutcome.SUCCESS
    dated_outputs = list(tmp_path.glob("*2026-08-01_2026-08-31*"))
    assert dated_outputs == [result.csv_path]


def test_await_and_finalize_from_filesystem_forces_a_csv_extension_for_a_suffixless_artifact(
    tmp_path,
):
    orchestrator = _orchestrator()
    waiter = PrismaDownloadWaiter()
    waiter.filesystem_fallback = PrismaDownloadFilesystemWaiter.snapshot(tmp_path)
    cancel_event = threading.Event()
    (tmp_path / "3fa85f64-5717-4562-b3fc-2c963f66afa6").write_bytes(b"a,b,c\n1,2,3\n")

    result = None
    for _ in range(5):
        result = orchestrator.await_and_finalize(
            waiter, RANGE, tmp_path, cancel_event,
            deadline=time.monotonic() + 60.0,
        )
        if result is not None:
            break

    assert result is not None
    assert result.outcome is PrismaDownloadOutcome.SUCCESS
    assert result.csv_path.suffix == ".csv"
    assert result.csv_path.name.endswith("_2026-08-01_2026-08-31.csv")
    assert result.csv_path.parent == tmp_path
    assert result.csv_path.exists()
    assert result.csv_path.read_bytes() == b"a,b,c\n1,2,3\n"


def test_filesystem_fallback_finalize_never_overwrites_an_existing_file(tmp_path):
    existing = tmp_path / "Auction_overview_2026-08-01_2026-08-31.csv"
    existing.write_text("previous run", encoding="utf-8")
    orchestrator = _orchestrator()
    waiter = PrismaDownloadWaiter()
    waiter.filesystem_fallback = PrismaDownloadFilesystemWaiter.snapshot(tmp_path)
    cancel_event = threading.Event()
    downloaded = tmp_path / "Auction_overview.csv"
    downloaded.write_bytes(b"a,b,c\n1,2,3\n")

    result = None
    for _ in range(5):
        result = orchestrator.await_and_finalize(
            waiter, RANGE, tmp_path, cancel_event,
            deadline=time.monotonic() + 60.0,
        )
        if result is not None:
            break

    assert result is not None
    assert result.outcome is PrismaDownloadOutcome.SUCCESS
    assert result.csv_path == tmp_path / "Auction_overview_2026-08-01_2026-08-31_2.csv"
    assert existing.read_text(encoding="utf-8") == "previous run"


def test_await_and_finalize_rejects_multiple_csv_files_found_via_the_fallback(tmp_path):
    orchestrator = _orchestrator()
    waiter = PrismaDownloadWaiter()
    waiter.filesystem_fallback = PrismaDownloadFilesystemWaiter.snapshot(tmp_path)
    cancel_event = threading.Event()
    (tmp_path / "a.csv").write_bytes(b"1")
    (tmp_path / "b.csv").write_bytes(b"2")

    result = orchestrator.await_and_finalize(
        waiter, RANGE, tmp_path, cancel_event,
        deadline=time.monotonic() + 60.0,
    )

    assert result.outcome is PrismaDownloadOutcome.MULTIPLE_DOWNLOADS
    assert result.csv_path is None


def test_await_and_finalize_times_out_when_the_fallback_never_finds_a_file(tmp_path):
    orchestrator = _orchestrator()
    waiter = PrismaDownloadWaiter()
    waiter.filesystem_fallback = PrismaDownloadFilesystemWaiter.snapshot(tmp_path)
    cancel_event = threading.Event()

    result = orchestrator.await_and_finalize(
        waiter, RANGE, tmp_path, cancel_event,
        deadline=time.monotonic() - 1.0,
    )

    assert result.outcome is PrismaDownloadOutcome.DOWNLOAD_TIMEOUT
    assert result.csv_path is None


def test_await_and_finalize_returns_none_on_cancellation_with_the_fallback_pending(
    tmp_path,
):
    orchestrator = _orchestrator()
    waiter = PrismaDownloadWaiter()
    waiter.filesystem_fallback = PrismaDownloadFilesystemWaiter.snapshot(tmp_path)
    cancel_event = threading.Event()
    cancel_event.set()
    (tmp_path / "Auction_overview.csv").write_bytes(b"a,b,c\n1,2,3\n")

    result = orchestrator.await_and_finalize(
        waiter, RANGE, tmp_path, cancel_event,
        deadline=time.monotonic() + 60.0,
    )

    assert result is None


# --- PrismaDownloadWaiter.detach() ------------------------------------------


def test_waiter_detach_removes_the_registered_listener_from_the_context():
    context = FakeBrowserContext()
    waiter = PrismaDownloadWaiter()
    waiter.attach(context)
    context.on("download", waiter.on_download)

    waiter.detach()

    assert context.removed_calls == [("download", waiter.on_download)]
    assert context.on_calls == []


def test_waiter_detach_is_idempotent():
    context = FakeBrowserContext()
    waiter = PrismaDownloadWaiter()
    waiter.attach(context)
    context.on("download", waiter.on_download)

    waiter.detach()
    waiter.detach()

    assert len(context.removed_calls) == 1


def test_waiter_detach_without_attach_is_a_safe_no_op():
    waiter = PrismaDownloadWaiter()

    waiter.detach()  # must not raise


def test_waiter_detach_tolerates_remove_listener_raising():
    class RaisingContext(FakeBrowserContext):
        def remove_listener(self, event, callback):
            raise RuntimeError("context already torn down")

    context = RaisingContext()
    waiter = PrismaDownloadWaiter()
    waiter.attach(context)

    waiter.detach()  # must not raise


def test_describe_download_failure_messages_are_distinct_and_stable():
    outcomes = [o for o in PrismaDownloadOutcome if o is not PrismaDownloadOutcome.SUCCESS]
    messages = {outcome: describe_download_failure(outcome) for outcome in outcomes}
    assert len(set(messages.values())) == len(messages)
    assert all(message for message in messages.values())


def test_download_timeout_message_does_not_ask_the_user_to_press_anything():
    """Regression: the P.36.14 contract correction made PrismaFunction itself
    activate the PRISMA CSV control; the timeout message must not imply the
    user needs to press anything on the PRISMA website.
    """
    message = describe_download_failure(PrismaDownloadOutcome.DOWNLOAD_TIMEOUT).lower()
    assert "press" not in message
    assert "button" not in message
