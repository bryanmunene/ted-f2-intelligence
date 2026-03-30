from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.presenters import notice_to_detail_dict, notice_to_summary_dict, scan_run_to_dict
from app.api.schemas import (
    DashboardMetricsResponse,
    NoticeDetailResponse,
    NoticeSummaryResponse,
    ScanRequestPayload,
    ScanRunResponse,
    TenderChecklistResponse,
)
from app.deps import get_db, get_scan_service
from app.repositories.notices import NoticeListFilters, NoticeRepository
from app.repositories.scan_runs import ScanRunRepository
from app.services.scan_service import ScanService
from app.services.tender_checklist import TenderChecklistService

router = APIRouter(prefix="/api/v1", tags=["api"])


@router.get("/dashboard", response_model=DashboardMetricsResponse)
def dashboard_metrics(session: Session = Depends(get_db)) -> DashboardMetricsResponse:
    payload = NoticeRepository(session).dashboard_metrics()
    return DashboardMetricsResponse.model_validate(payload)


@router.post("/scans", response_model=ScanRunResponse, status_code=status.HTTP_201_CREATED)
def run_scan(payload: ScanRequestPayload, scan_service: ScanService = Depends(get_scan_service)) -> ScanRunResponse:
    outcome = scan_service.run_manual_scan(payload)
    repository = ScanRunRepository(scan_service.session)
    scan_run = repository.get_by_id(outcome.scan_run_id)
    if scan_run is None:
        raise HTTPException(status_code=500, detail="Scan run could not be reloaded after completion.")
    return ScanRunResponse.model_validate(scan_run_to_dict(scan_run))


@router.get("/notices", response_model=list[NoticeSummaryResponse])
def list_notices(
    country: str | None = None,
    fit_label: str | None = None,
    priority_bucket: str | None = None,
    min_score: int | None = Query(default=None, ge=0, le=100),
    max_score: int | None = Query(default=None, ge=0, le=100),
    confidence_indicator: str | None = None,
    hard_lock_only: bool = False,
    publication_date_from: date | None = None,
    publication_date_to: date | None = None,
    deadline_from: date | None = None,
    deadline_to: date | None = None,
    deadline_window_days: int | None = Query(default=None, ge=1, le=365),
    include_dismissed: bool = False,
    saved_only: bool = False,
    search: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    session: Session = Depends(get_db),
) -> list[NoticeSummaryResponse]:
    repository = NoticeRepository(session)
    notices, _ = repository.list(
        NoticeListFilters(
            country=country,
            fit_label=fit_label,
            priority_bucket=priority_bucket,
            min_score=min_score,
            max_score=max_score,
            confidence_indicator=confidence_indicator,
            hard_lock_only=hard_lock_only,
            publication_date_from=publication_date_from,
            publication_date_to=publication_date_to,
            deadline_from=deadline_from,
            deadline_to=deadline_to,
            deadline_window_days=deadline_window_days,
            include_dismissed=include_dismissed,
            saved_only=saved_only,
            search=search,
        ),
        page=page,
        page_size=page_size,
    )
    return [NoticeSummaryResponse.model_validate(notice_to_summary_dict(notice)) for notice in notices]


@router.get("/notices/{notice_id}", response_model=NoticeDetailResponse)
def get_notice(notice_id: str, session: Session = Depends(get_db)) -> NoticeDetailResponse:
    notice = NoticeRepository(session).get_by_id(notice_id)
    if notice is None:
        raise HTTPException(status_code=404, detail="Notice not found.")
    return NoticeDetailResponse.model_validate(notice_to_detail_dict(notice))


@router.get("/notices/{notice_id}/checklist", response_model=TenderChecklistResponse)
def get_notice_checklist(notice_id: str, session: Session = Depends(get_db)) -> TenderChecklistResponse:
    notice = NoticeRepository(session).get_by_id(notice_id)
    if notice is None:
        raise HTTPException(status_code=404, detail="Notice not found.")
    report = TenderChecklistService.from_settings().evaluate_notice(notice_to_detail_dict(notice))
    return TenderChecklistResponse.model_validate(report)
