from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.api.schemas import HistoricalBackfillRequestPayload, ScanRequestPayload
from app.config import Settings
from app.services.scan_service import ScanOutcome, ScanService


@dataclass(slots=True)
class HistoricalBackfillWindowOutcome:
    date_from: date
    date_to: date
    scan_run_id: str
    total_notices_returned: int
    total_notices_ingested: int


@dataclass(slots=True)
class HistoricalBackfillOutcome:
    date_from: date
    date_to: date
    window_months: int
    total_windows: int
    completed_windows: int
    total_notices_returned: int
    total_notices_ingested: int
    total_after_timing_filters: int
    total_high_fit: int
    total_conditional: int
    total_ignored: int
    request_count: int
    rate_limit_events: int
    windows: list[HistoricalBackfillWindowOutcome]


class HistoricalBackfillService:
    def __init__(self, *, scan_service: ScanService, settings: Settings) -> None:
        self.scan_service = scan_service
        self.settings = settings

    def run(self, payload: HistoricalBackfillRequestPayload) -> HistoricalBackfillOutcome:
        if payload.date_from > payload.date_to:
            raise ValueError("Historical backfill start date must be on or before the end date.")

        windows = self._build_windows(payload.date_from, payload.date_to, payload.window_months)
        completed_windows: list[HistoricalBackfillWindowOutcome] = []
        totals = {
            "total_notices_returned": 0,
            "total_notices_ingested": 0,
            "total_after_timing_filters": 0,
            "total_high_fit": 0,
            "total_conditional": 0,
            "total_ignored": 0,
            "request_count": 0,
            "rate_limit_events": 0,
        }

        for window_start, window_end in windows:
            scan_payload = ScanRequestPayload(
                profile_name=payload.profile_name,
                date_from=window_start,
                date_to=window_end,
                country=payload.country,
                cpv=payload.cpv,
                keyword_override=payload.keyword_override,
                include_conditional=True,
                exclude_old=False,
                include_soft_locks=True,
                page_size=self.settings.ted_default_page_size,
                max_pages=min(2, self.settings.ted_max_pages_per_scan),
            )
            outcome = self.scan_service.run_manual_scan(scan_payload)
            self._accumulate(totals, outcome)
            completed_windows.append(
                HistoricalBackfillWindowOutcome(
                    date_from=window_start,
                    date_to=window_end,
                    scan_run_id=outcome.scan_run_id,
                    total_notices_returned=outcome.total_notices_returned,
                    total_notices_ingested=outcome.total_notices_ingested,
                )
            )

        return HistoricalBackfillOutcome(
            date_from=payload.date_from,
            date_to=payload.date_to,
            window_months=payload.window_months,
            total_windows=len(windows),
            completed_windows=len(completed_windows),
            total_notices_returned=totals["total_notices_returned"],
            total_notices_ingested=totals["total_notices_ingested"],
            total_after_timing_filters=totals["total_after_timing_filters"],
            total_high_fit=totals["total_high_fit"],
            total_conditional=totals["total_conditional"],
            total_ignored=totals["total_ignored"],
            request_count=totals["request_count"],
            rate_limit_events=totals["rate_limit_events"],
            windows=completed_windows,
        )

    def _accumulate(self, totals: dict[str, int], outcome: ScanOutcome) -> None:
        totals["total_notices_returned"] += outcome.total_notices_returned
        totals["total_notices_ingested"] += outcome.total_notices_ingested
        totals["total_after_timing_filters"] += outcome.total_after_timing_filters
        totals["total_high_fit"] += outcome.total_high_fit
        totals["total_conditional"] += outcome.total_conditional
        totals["total_ignored"] += outcome.total_ignored
        totals["request_count"] += outcome.request_count
        totals["rate_limit_events"] += outcome.rate_limit_events

    def _build_windows(self, start: date, end: date, window_months: int) -> list[tuple[date, date]]:
        windows: list[tuple[date, date]] = []
        current_start = start
        while current_start <= end:
            current_end = self._subtract_one_day(self._add_months(current_start, window_months))
            if current_end > end:
                current_end = end
            windows.append((current_start, current_end))
            current_start = self._add_days(current_end, 1)
        return windows

    def _add_months(self, value: date, months: int) -> date:
        month_index = (value.month - 1) + months
        year = value.year + (month_index // 12)
        month = (month_index % 12) + 1
        day = min(value.day, self._days_in_month(year, month))
        return date(year, month, day)

    def _days_in_month(self, year: int, month: int) -> int:
        if month == 12:
            next_month = date(year + 1, 1, 1)
        else:
            next_month = date(year, month + 1, 1)
        return (next_month - date(year, month, 1)).days

    def _subtract_one_day(self, value: date) -> date:
        return date.fromordinal(value.toordinal() - 1)

    def _add_days(self, value: date, days: int) -> date:
        return date.fromordinal(value.toordinal() + days)
