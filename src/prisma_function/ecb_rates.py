"""Focused, UI- and PRISMA-independent official ECB reference-rate resolution.

P.36.19 uses this module only to resolve the historical exchange rate to EUR
for one finished auction's authoritative end date, for Mapping display. It
never touches the 12-column output contract, the CSV input contract, the UI,
or PRISMA browser/session code.

Quotation direction. The ECB Statistical Data Warehouse `EXR` dataflow
publishes `D.<CCY>.EUR.SP00.A` as the number of `<CCY>` units per 1 EUR (for
example `USD 1.0921` means 1 EUR = 1.0921 USD). `resolve_rate_to_eur()`
always inverts this into an unambiguous "rate to EUR" domain value — the
number of EUR equal to 1 unit of `<CCY>` — using exact `decimal.Decimal`
arithmetic (never binary floating point), so `rate_to_eur * published_value`
is always 1 up to the fixed rounding applied.

Fallback rule. The ECB does not publish rates on weekends or ECB holidays.
The production source queries `endPeriod=<on_or_before>&lastNObservations=1`,
so the authoritative ECB source itself enforces "the newest publication on or
before the requested date, never a later one"; `resolve_rate_to_eur()`
additionally rejects any observation whose publication date is after
`on_or_before` as defense in depth against a malformed/untrusted source.

EUR identity. `resolve_rate_to_eur("EUR", on_or_before)` returns rate `1`
with `publication_date == on_or_before` and performs no network access at
all — EUR requires no ECB lookup, and its "publication date" is a clearly
documented identity date, not a fabricated ECB publication.
"""
from __future__ import annotations

import csv
import io
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, DecimalException, ROUND_HALF_UP
from typing import Protocol

__all__ = [
    "EUR",
    "DEFAULT_TIMEOUT_SECONDS",
    "EcbRateError",
    "EcbRateSourceError",
    "EcbRateNotFoundError",
    "EcbRateObservation",
    "EcbRateResult",
    "EcbRateSource",
    "EcbSdwHttpRateSource",
    "resolve_rate_to_eur",
]

_ISO_4217_PATTERN = re.compile(r"^[A-Z]{3}\Z")
_RATE_QUANTUM = Decimal("1.0000000000")  # 10 decimal places
EUR = "EUR"
DEFAULT_TIMEOUT_SECONDS = 10.0
_ECB_SDW_URL_TEMPLATE = (
    "https://data-api.ecb.europa.eu/service/data/EXR/D.{currency}.EUR.SP00.A"
    "?endPeriod={on_or_before}&lastNObservations=1&format=csvdata"
)


class EcbRateError(RuntimeError):
    """Base failure raised by ECB reference-rate resolution."""


class EcbRateSourceError(EcbRateError):
    """The ECB data source could not be reached or returned malformed data."""


class EcbRateNotFoundError(EcbRateError):
    """No eligible historical ECB rate exists on or before the requested date."""


@dataclass(frozen=True)
class EcbRateObservation:
    """One raw ECB publication: `published_value` units of currency per 1 EUR."""

    publication_date: date
    published_value: Decimal


@dataclass(frozen=True)
class EcbRateResult:
    """An unambiguous, already-inverted "rate to EUR" domain value."""

    currency: str
    rate_to_eur: Decimal
    publication_date: date


class EcbRateSource(Protocol):
    def fetch(
        self, currency: str, *, on_or_before: date, timeout_seconds: float
    ) -> EcbRateObservation | None:
        """Return the latest published observation on or before `on_or_before`,
        or `None` when no eligible observation exists. Implementations must
        never return an observation published after `on_or_before`."""
        ...


def _parse_csv_observation(payload: str) -> EcbRateObservation | None:
    reader = csv.DictReader(io.StringIO(payload))
    rows = list(reader)
    if not rows:
        return None
    fieldnames = reader.fieldnames or ()
    if "TIME_PERIOD" not in fieldnames or "OBS_VALUE" not in fieldnames:
        raise EcbRateSourceError(
            "ECB data source response is missing the required TIME_PERIOD/OBS_VALUE columns."
        )
    last = rows[-1]
    time_period = (last.get("TIME_PERIOD") or "").strip()
    obs_value = (last.get("OBS_VALUE") or "").strip()
    try:
        publication_date = date.fromisoformat(time_period)
    except ValueError as exc:
        raise EcbRateSourceError(
            f"ECB data source returned an invalid publication date: {time_period!r}."
        ) from exc
    try:
        published_value = Decimal(obs_value)
    except (DecimalException, ValueError) as exc:
        raise EcbRateSourceError(
            f"ECB data source returned a non-numeric rate: {obs_value!r}."
        ) from exc
    return EcbRateObservation(publication_date, published_value)


class EcbSdwHttpRateSource:
    """Production ECB Statistical Data Warehouse REST source (stdlib-only).

    Queries the official ECB SDW `EXR` dataflow for exactly one currency with
    `lastNObservations=1`, bounded by `endPeriod=<on_or_before>`, so the
    fallback-to-the-most-recent-earlier-publication rule (weekends, ECB
    holidays) is enforced server-side by the authoritative source itself: a
    later publication can never be returned, since the query's own upper
    bound is the requested date. Uses only the standard library, with an
    explicit read/connect timeout on every request.
    """

    def fetch(
        self,
        currency: str,
        *,
        on_or_before: date,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> EcbRateObservation | None:
        url = _ECB_SDW_URL_TEMPLATE.format(
            currency=currency, on_or_before=on_or_before.isoformat()
        )
        try:
            with urllib.request.urlopen(url, timeout=timeout_seconds) as response:
                status = getattr(response, "status", 200)
                if status != 200:
                    raise EcbRateSourceError(f"ECB data source returned HTTP {status}.")
                payload = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return None
            raise EcbRateSourceError(f"ECB data source returned HTTP {exc.code}.") from exc
        except (urllib.error.URLError, OSError, ValueError) as exc:
            raise EcbRateSourceError("The ECB data source could not be reached.") from exc
        return _parse_csv_observation(payload)


def resolve_rate_to_eur(
    currency: str,
    on_or_before: date,
    *,
    source: EcbRateSource | None = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> EcbRateResult:
    """Resolve the historical rate-to-EUR fixed for `on_or_before`.

    `currency == "EUR"` short-circuits to the identity result with no network
    access. Any other currency is validated as an exact three-letter
    uppercase ISO 4217 code, then resolved through `source` (an
    `EcbSdwHttpRateSource` by default; tests inject a fake so no unit test
    ever performs real network access). Raises `EcbRateNotFoundError` when no
    eligible historical publication exists, and `EcbRateSourceError` when the
    source itself is unreachable or returns malformed/contradictory data
    (including a publication dated after `on_or_before`, which is rejected as
    defense in depth even though the production source's own `endPeriod`
    bound already prevents it).
    """
    if not isinstance(currency, str) or not _ISO_4217_PATTERN.match(currency):
        raise EcbRateError(
            f"Currency must be an exact three-letter uppercase ISO 4217 code: {currency!r}."
        )
    if not isinstance(on_or_before, date):
        raise EcbRateError("on_or_before must be a date.")
    if currency == EUR:
        return EcbRateResult(EUR, Decimal(1), on_or_before)

    active_source = source if source is not None else EcbSdwHttpRateSource()
    observation = active_source.fetch(
        currency, on_or_before=on_or_before, timeout_seconds=timeout_seconds
    )
    if observation is None:
        raise EcbRateNotFoundError(
            f"No ECB reference rate is published for {currency} on or before "
            f"{on_or_before.isoformat()}."
        )
    if observation.publication_date > on_or_before:
        raise EcbRateSourceError(
            "ECB data source returned a publication date later than the "
            "requested date; rejected."
        )
    if not observation.published_value.is_finite() or observation.published_value <= 0:
        raise EcbRateSourceError(
            "ECB data source returned a non-positive or non-finite rate: "
            f"{observation.published_value}."
        )
    rate_to_eur = (Decimal(1) / observation.published_value).quantize(
        _RATE_QUANTUM, rounding=ROUND_HALF_UP
    )
    return EcbRateResult(currency, rate_to_eur, observation.publication_date)
