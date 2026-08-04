from __future__ import annotations

import re
import time
from dataclasses import dataclass
from urllib.parse import urlsplit


class PrismaPageAdapterError(RuntimeError):
    """Base failure raised by live PRISMA page access and parsing."""


class PrismaAuthenticationRequiredError(PrismaPageAdapterError):
    """The public workflow was redirected to or replaced by authentication."""


class PrismaInvalidSessionError(PrismaPageAdapterError):
    """The browser page is not a usable public PRISMA auctions session."""


@dataclass(frozen=True)
class PrismaSessionState:
    classification: str
    location: str


class PrismaSessionValidator:
    """Validate the public page without reading or persisting browser session data."""

    TIMEOUT_MS = 10_000
    POLL_MS = 100
    PUBLIC_HOST = "app.prisma-capacity.eu"
    PUBLIC_PATH = "/reporting/auctions/short-and-long-term-auctions"
    AUTH_PATH = re.compile(r"/(login|signin|sign-in|auth|oauth)(?:/|$)", re.I)
    PUBLIC_HEADING = re.compile(r"short\s*(?:and|&)\s*long\s*term\s+auctions", re.I)
    AUTH_HEADING = re.compile(r"^(?:log|sign)\s*in|authentication|required", re.I)

    @staticmethod
    def safe_location(raw_url: str) -> str:
        try:
            if not isinstance(raw_url, str) or not raw_url.strip():
                return "unavailable"
            parsed = urlsplit(raw_url)
            host = (parsed.hostname or "unknown").lower()
            path = parsed.path or "/"
            return f"{parsed.scheme or 'unknown'}://{host}{path}"
        except Exception:
            return "unavailable"

    @classmethod
    def _parse_url(cls, raw_url):
        try:
            if not isinstance(raw_url, str) or not raw_url.strip():
                raise ValueError("missing page URL")
            parsed = urlsplit(raw_url)
            host = (parsed.hostname or "").lower()
            path = parsed.path or "/"
        except Exception as exc:
            raise PrismaInvalidSessionError(
                "The active PRISMA session location is invalid or unavailable."
            ) from exc
        return parsed, host, path, cls.safe_location(raw_url)

    @staticmethod
    def _visible(locator) -> bool:
        try:
            return locator.count() > 0 and locator.first.is_visible()
        except Exception:
            return False

    def _has_auth_dom(self, page) -> bool:
        return (
            self._visible(page.locator("input[type='password']"))
            or self._visible(page.get_by_role("heading", name=self.AUTH_HEADING))
            or self._visible(page.get_by_role("button", name=re.compile(r"^(?:log|sign)\s*in$", re.I)))
        )

    def _has_public_dom(self, page) -> bool:
        return (
            self._visible(page.get_by_role("heading", name=self.PUBLIC_HEADING))
            or self._visible(page.get_by_role("button", name=re.compile(r"^Active\s+Filter:", re.I)))
            or self._visible(page.get_by_role("table"))
        )

    def validate(self, page) -> PrismaSessionState:
        try:
            raw_url = page.url
        except Exception as exc:
            raise PrismaInvalidSessionError(
                "The active PRISMA session location is unavailable."
            ) from exc
        _parsed, host, path, location = self._parse_url(raw_url)
        if self.AUTH_PATH.search(path):
            raise PrismaAuthenticationRequiredError(
                "PRISMA authentication is required; automatic monitoring cannot continue in the public session."
            )

        deadline = time.monotonic() + self.TIMEOUT_MS / 1000
        while True:
            if self._has_auth_dom(page):
                raise PrismaAuthenticationRequiredError(
                    "PRISMA authentication is required; automatic monitoring cannot continue in the public session."
                )
            if host == self.PUBLIC_HOST and path.rstrip("/") == self.PUBLIC_PATH and self._has_public_dom(page):
                return PrismaSessionState("public-auctions", location)
            if time.monotonic() >= deadline:
                break
            try:
                page.wait_for_timeout(self.POLL_MS)
            except Exception as exc:
                raise PrismaInvalidSessionError(
                    "The active PRISMA session became unavailable during validation."
                ) from exc
        raise PrismaInvalidSessionError(
            "The active page is not a usable public PRISMA auctions session."
        )
