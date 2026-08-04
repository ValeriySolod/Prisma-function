import pytest

from prisma_page import (
    PrismaAuthenticationRequiredError, PrismaInvalidSessionError,
    PrismaSessionValidator,
)


class SessionLocator:
    def __init__(self, visible=False):
        self.first = self
        self.visible = visible

    def count(self):
        return int(self.visible)

    def is_visible(self):
        return self.visible


class SessionPage:
    def __init__(self, url, *, public=False, auth=False, ready_after=0, consent=False):
        self.url = url
        self.public = public
        self.auth = auth
        self.ready_after = ready_after
        self.polls = 0
        self.consent = consent

    def locator(self, selector):
        assert selector == "input[type='password']"
        return SessionLocator(self.auth)

    def get_by_role(self, role, name=None):
        pattern = getattr(name, "pattern", "")
        if role == "heading" and "authentication" in pattern:
            return SessionLocator(self.auth)
        if role == "button" and "in$" in pattern:
            return SessionLocator(self.auth)
        if role in ("heading", "button", "table"):
            return SessionLocator(self.public and self.polls >= self.ready_after)
        raise AssertionError(role)

    def wait_for_timeout(self, milliseconds):
        self.polls += 1


PUBLIC_URL = (
    "https://app.prisma-capacity.eu/reporting/auctions/"
    "short-and-long-term-auctions"
)


def validator():
    item = PrismaSessionValidator()
    item.TIMEOUT_MS = 20
    item.POLL_MS = 1
    return item


def test_public_auctions_page_and_harmless_consent_are_accepted():
    state = validator().validate(SessionPage(PUBLIC_URL, public=True, consent=True))
    assert state.classification == "public-auctions"


def test_delayed_public_readiness_is_not_authentication_failure():
    state = validator().validate(SessionPage(PUBLIC_URL, public=True, ready_after=2))
    assert state.classification == "public-auctions"


def test_login_redirect_is_typed_authentication_required():
    with pytest.raises(PrismaAuthenticationRequiredError):
        validator().validate(SessionPage("https://app.prisma-capacity.eu/login?token=secret"))


def test_login_dom_is_detected_when_url_looks_public():
    with pytest.raises(PrismaAuthenticationRequiredError):
        validator().validate(SessionPage(PUBLIC_URL, auth=True))


def test_unexpected_page_is_typed_invalid_session():
    with pytest.raises(PrismaInvalidSessionError):
        validator().validate(SessionPage("https://example.com/error?password=secret"))


@pytest.mark.parametrize("raw_url", [
    None,
    123,
    "",
    "   ",
    "https://[invalid-host/path?token=representative",
])
def test_malformed_or_non_string_page_url_is_typed_invalid_session(raw_url):
    with pytest.raises(
        PrismaInvalidSessionError,
        match="session location is invalid or unavailable",
    ) as error:
        validator().validate(SessionPage(raw_url))

    assert "representative" not in str(error.value)


def test_safe_location_removes_queries_fragments_and_user_information():
    location = PrismaSessionValidator.safe_location(
        "https://user:password@app.prisma-capacity.eu/login?token=secret#cookie=value"
    )
    assert location == "https://app.prisma-capacity.eu/login"
    assert all(value not in location for value in ("user", "password", "token", "secret", "cookie"))
