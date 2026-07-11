from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Iterable, Protocol

from auction_csv import AuctionCsvRecord


class StatusChecker(Protocol):
    """Callable contract for obtaining an auction's current status."""

    def __call__(self, record: AuctionCsvRecord) -> str: ...


@dataclass(frozen=True)
class MonitoringResult:
    auction_id: str
    checked_at: datetime
    previous_status: str
    current_status: str
    status_changed: bool
    result: str
    error_message: str


class MonitoringEngine:
    """Check auction records without owning scheduling or threading."""

    def __init__(
        self,
        status_checker: StatusChecker,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._status_checker = status_checker
        self._clock = clock or datetime.now

    def _result(
        self,
        record: AuctionCsvRecord,
        *,
        current_status: str,
        status_changed: bool,
        result: str,
        error_message: str = "",
    ) -> MonitoringResult:
        return MonitoringResult(
            auction_id=record.auction_id,
            checked_at=self._clock(),
            previous_status=record.last_known_status,
            current_status=current_status,
            status_changed=status_changed,
            result=result,
            error_message=error_message,
        )

    def check_record(self, record: AuctionCsvRecord, stop_event=None) -> MonitoringResult:
        if (stop_event is not None and stop_event.is_set()) or not record.enabled:
            return self._result(
                record,
                current_status=record.last_known_status,
                status_changed=False,
                result="Skipped",
            )

        try:
            current_status = self._status_checker(record).strip()
            if not current_status:
                raise ValueError("The status checker returned an empty status.")
        except Exception as error:
            reason = str(error).strip() or error.__class__.__name__
            return self._result(
                record,
                current_status=record.last_known_status,
                status_changed=False,
                result="Error",
                error_message=f"Unable to check auction status: {reason}",
            )

        changed = record.last_known_status.strip() != current_status
        return self._result(
            record,
            current_status=current_status,
            status_changed=changed,
            result="Changed" if changed else "Success",
        )

    def check_records(
        self, records: Iterable[AuctionCsvRecord], stop_event=None
    ) -> list[MonitoringResult]:
        return [self.check_record(record, stop_event) for record in records]
