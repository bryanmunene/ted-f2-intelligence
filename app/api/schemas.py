from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.enums import ConfidenceIndicator, FitLabel, PriorityBucket


class ScanRequestPayload(BaseModel):
    profile_name: str = "F2 Core"
    date_from: date | None = None
    date_to: date | None = None
    country: str | None = None
    cpv: str | None = None
    keyword_override: str | None = None
    include_conditional: bool = True
    exclude_old: bool = True
    include_soft_locks: bool = True
    page_size: int = Field(default=50, ge=1, le=250)
    max_pages: int = Field(default=2, ge=1, le=20)

    def keyword_override_terms(self) -> list[str]:
        if not self.keyword_override:
            return []
        terms: list[str] = []
        for raw in self.keyword_override.replace(";", ",").split(","):
            cleaned = raw.strip()
            if cleaned:
                terms.append(cleaned)
        return terms

    @property
    def request_budget_preview(self) -> int:
        return self.max_pages


class NoticeSummaryResponse(BaseModel):
    id: str
    publication_number: str
    title: str
    buyer: str | None
    buyer_country: str | None
    publication_date: date | None
    deadline: datetime | None
    score: int
    fit_label: FitLabel
    priority_bucket: PriorityBucket
    confidence_indicator: ConfidenceIndicator
    hard_lock_detected: bool
    viable_timing: bool
    keyword_hits: list[dict[str, Any]]
    saved: bool
    dismissed: bool


class NoticeDetailResponse(NoticeSummaryResponse):
    ted_notice_id: str | None
    place_of_performance: str | None
    notice_type: str | None
    procedure_type: str | None
    cpv_codes: list[str]
    source_url: str | None
    html_url: str | None
    pdf_url: str | None
    xml_url: str | None
    summary: str | None
    reasoning: str
    qualification_questions: list[str]
    score_breakdown: list[dict[str, Any]]
    positive_signals: list[dict[str, Any]]
    negative_signals: list[dict[str, Any]]
    platform_lock_signals: list[dict[str, Any]]
    timing_flags: list[dict[str, Any]]
    raw_payload_json: dict[str, Any]
    notes: list[dict[str, Any]]


class ScanRunResponse(BaseModel):
    id: str
    status: str
    started_at: datetime
    completed_at: datetime | None
    total_notices_returned: int
    total_notices_ingested: int
    total_after_timing_filters: int
    total_high_fit: int
    total_conditional: int
    total_ignored: int
    request_count: int
    rate_limit_events: int
    error_count: int


class DashboardMetricsResponse(BaseModel):
    total_notices: int
    high_fit: int
    conditional: int
    expiring_soon: int
    hard_lock: int
    scan_freshness: datetime | None

