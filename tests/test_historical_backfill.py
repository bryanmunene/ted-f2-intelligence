from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.api.schemas import HistoricalBackfillRequestPayload
from app.config import get_settings
from app.services.historical_backfill import HistoricalBackfillService
from app.services.scan_service import ScanOutcome


@dataclass
class _FakeScanService:
    payloads: list

    def run_manual_scan(self, payload):
        self.payloads.append(payload)
        return ScanOutcome(
            scan_run_id=f"scan-{len(self.payloads)}",
            total_notices_returned=5,
            total_notices_ingested=3,
            total_after_timing_filters=2,
            total_high_fit=1,
            total_conditional=1,
            total_ignored=1,
            request_count=2,
            rate_limit_events=0,
        )


def test_historical_backfill_splits_range_into_monthly_windows() -> None:
    fake_scan_service = _FakeScanService(payloads=[])
    service = HistoricalBackfillService(scan_service=fake_scan_service, settings=get_settings())

    outcome = service.run(
        HistoricalBackfillRequestPayload(
            profile_name="F2 Core",
            date_from=date(2025, 1, 1),
            date_to=date(2025, 3, 15),
            country="DK",
        )
    )

    assert outcome.total_windows == 3
    assert outcome.completed_windows == 3
    assert outcome.total_notices_ingested == 9
    assert outcome.request_count == 6
    assert fake_scan_service.payloads[0].date_from == date(2025, 1, 1)
    assert fake_scan_service.payloads[0].date_to == date(2025, 1, 31)
    assert fake_scan_service.payloads[1].date_from == date(2025, 2, 1)
    assert fake_scan_service.payloads[1].date_to == date(2025, 2, 28)
    assert fake_scan_service.payloads[2].date_from == date(2025, 3, 1)
    assert fake_scan_service.payloads[2].date_to == date(2025, 3, 15)
    assert fake_scan_service.payloads[0].exclude_old is False
