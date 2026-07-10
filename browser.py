from __future__ import annotations

import threading

PRISMA_AUCTIONS_URL = (
    "https://app.prisma-capacity.eu/reporting/auctions/"
    "short-and-long-term-auctions"
)


class BrowserController:
    """Opens PRISMA in installed Chrome or Edge and closes only this session."""

    def __init__(self) -> None:
        self._playwright = None
        self._browser = None
        self._thread: threading.Thread | None = None

    def open(self, browser_name: str) -> None:
        if self._thread and self._thread.is_alive():
            raise RuntimeError("Браузерна сесія вже запущена.")

        self._thread = threading.Thread(
            target=self._run,
            args=(browser_name,),
            daemon=True,
        )
        self._thread.start()

    def _run(self, browser_name: str) -> None:
        try:
            from playwright.sync_api import sync_playwright

            channel = "chrome" if browser_name == "Chrome" else "msedge"
            self._playwright = sync_playwright().start()
            self._browser = self._playwright.chromium.launch(
                channel=channel,
                headless=False,
            )
            page = self._browser.new_page()
            page.goto(PRISMA_AUCTIONS_URL, wait_until="domcontentloaded")
            page.wait_for_timeout(24 * 60 * 60 * 1000)
        except Exception:
            self.stop()

    def stop(self) -> None:
        try:
            if self._browser:
                self._browser.close()
        finally:
            self._browser = None
            if self._playwright:
                try:
                    self._playwright.stop()
                except Exception:
                    pass
            self._playwright = None
