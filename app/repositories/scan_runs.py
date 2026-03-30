from __future__ import annotations

from datetime import datetime

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models import ScanRun
from app.models.enums import ScanStatus


class ScanRunRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(self, scan_run_id: str) -> ScanRun | None:
        return self.session.scalar(select(ScanRun).where(ScanRun.id == scan_run_id))

    def create(self, *, started_at: datetime, profile_name: str, query_parameters: dict) -> ScanRun:
        record = ScanRun(
            started_at=started_at,
            profile_name=profile_name,
            query_parameters=query_parameters,
            status=ScanStatus.STARTED,
        )
        self.session.add(record)
        self.session.flush()
        return record

    def complete(
        self,
        scan_run: ScanRun,
        *,
        completed_at: datetime,
        total_notices_returned: int,
        total_notices_ingested: int,
        total_after_timing_filters: int,
        total_high_fit: int,
        total_conditional: int,
        total_ignored: int,
        request_count: int,
        rate_limit_events: int,
        error_count: int = 0,
    ) -> ScanRun:
        scan_run.completed_at = completed_at
        scan_run.status = ScanStatus.COMPLETED
        scan_run.total_notices_returned = total_notices_returned
        scan_run.total_notices_ingested = total_notices_ingested
        scan_run.total_after_timing_filters = total_after_timing_filters
        scan_run.total_high_fit = total_high_fit
        scan_run.total_conditional = total_conditional
        scan_run.total_ignored = total_ignored
        scan_run.request_count = request_count
        scan_run.rate_limit_events = rate_limit_events
        scan_run.error_count = error_count
        self.session.flush()
        return scan_run

    def fail(self, scan_run: ScanRun, *, completed_at: datetime, error_summary: str, error_count: int) -> ScanRun:
        scan_run.completed_at = completed_at
        scan_run.status = ScanStatus.FAILED
        scan_run.error_summary = error_summary
        scan_run.error_count = error_count
        self.session.flush()
        return scan_run

    def recent(self, limit: int = 10) -> list[ScanRun]:
        stmt = select(ScanRun).order_by(desc(ScanRun.started_at)).limit(limit)
        return list(self.session.scalars(stmt).all())
