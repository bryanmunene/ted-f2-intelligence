from __future__ import annotations

import builtins
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Any

from sqlalchemy import Select, case, func, or_, select
from sqlalchemy.orm import Session, contains_eager, selectinload

from app.models import AnalystNote, Notice, NoticeAnalysis, ScanRun
from app.models.enums import ConfidenceIndicator, FitLabel, PriorityBucket
from app.utils.countries import ted_country_code_variants


@dataclass(slots=True)
class NoticeListFilters:
    country: str | list[str] | None = None
    fit_label: str | None = None
    priority_bucket: str | None = None
    min_score: int | None = None
    max_score: int | None = None
    confidence_indicator: str | None = None
    relevant_only: bool = False
    min_days_remaining: int | None = 0
    hard_lock_only: bool = False
    publication_date_from: date | None = None
    publication_date_to: date | None = None
    deadline_from: date | None = None
    deadline_to: date | None = None
    deadline_window_days: int | None = None
    include_dismissed: bool = False
    saved_only: bool = False
    search: str | None = None


AWARDED_NOTICE_PATTERNS = (
    "contract award",
    "award notice",
    "award of contract",
    "awarded contract",
    "has already been awarded",
    "already been awarded",
    "result of the procurement procedure",
    "concession award",
)


def looks_like_awarded_notice(*values: str | None) -> bool:
    text = " ".join(value.strip().lower() for value in values if isinstance(value, str) and value.strip())
    return any(pattern in text for pattern in AWARDED_NOTICE_PATTERNS)


def _non_awarded_notice_clause():
    searchable_fields = (
        func.lower(func.coalesce(Notice.notice_type, "")),
        func.lower(func.coalesce(Notice.title, "")),
        func.lower(func.coalesce(Notice.summary, "")),
    )
    award_matches = [field.like(f"%{pattern}%") for field in searchable_fields for pattern in AWARDED_NOTICE_PATTERNS]
    return ~or_(*award_matches)


class NoticeRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def upsert_notice(
        self,
        *,
        normalized_notice: dict[str, Any],
        analysis_payload: dict[str, Any],
        scan_run: ScanRun | None = None,
    ) -> Notice:
        publication_number = normalized_notice["publication_number"]
        notice = self.session.scalar(
            select(Notice)
            .options(selectinload(Notice.analysis))
            .where(Notice.publication_number == publication_number)
        )
        if notice is None:
            notice = Notice(**normalized_notice, last_scan_run_id=scan_run.id if scan_run else None)
            self.session.add(notice)
            self.session.flush()
        else:
            preserved_saved = notice.saved
            preserved_dismissed = notice.dismissed
            for key, value in normalized_notice.items():
                setattr(notice, key, value)
            notice.last_scan_run_id = scan_run.id if scan_run else notice.last_scan_run_id
            notice.saved = preserved_saved
            notice.dismissed = preserved_dismissed

        if notice.analysis is None:
            notice.analysis = NoticeAnalysis(notice_id=notice.id, **analysis_payload)
        else:
            for key, value in analysis_payload.items():
                setattr(notice.analysis, key, value)
        self.session.flush()
        return notice

    def list(self, filters: NoticeListFilters, *, page: int = 1, page_size: int = 25) -> tuple[list[Notice], int]:
        priority_rank = case(
            (NoticeAnalysis.priority_bucket == PriorityBucket.HIGH, 0),
            (NoticeAnalysis.priority_bucket == PriorityBucket.GOOD, 1),
            (NoticeAnalysis.priority_bucket == PriorityBucket.WATCHLIST, 2),
            (NoticeAnalysis.priority_bucket == PriorityBucket.IGNORE, 3),
            else_=4,
        )
        fit_rank = case(
            (NoticeAnalysis.fit_label == FitLabel.YES, 0),
            (NoticeAnalysis.fit_label == FitLabel.CONDITIONAL, 1),
            (NoticeAnalysis.fit_label == FitLabel.NO, 2),
            else_=3,
        )
        stmt = (
            select(Notice)
            .join(Notice.analysis)
            .options(contains_eager(Notice.analysis), selectinload(Notice.notes))
            .order_by(
                priority_rank,
                fit_rank,
                NoticeAnalysis.score.desc(),
                Notice.deadline.asc().nullslast(),
                Notice.updated_at.desc(),
            )
        )
        stmt = self._apply_filters(stmt, filters)

        total = self.session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        paged = stmt.offset((page - 1) * page_size).limit(page_size)
        return list(self.session.scalars(paged).unique().all()), int(total)

    def get_by_id(self, notice_id: str) -> Notice | None:
        stmt = (
            select(Notice)
            .outerjoin(Notice.analysis)
            .options(
                contains_eager(Notice.analysis),
                selectinload(Notice.notes).selectinload(AnalystNote.user),
            )
            .where(Notice.id == notice_id)
        )
        return self.session.scalar(stmt)

    def predictive_history(self, *, limit: int = 500) -> builtins.list[Notice]:
        stmt = (
            select(Notice)
            .join(Notice.analysis)
            .options(contains_eager(Notice.analysis))
            .where(_non_awarded_notice_clause())
            .order_by(Notice.publication_date.desc().nullslast(), Notice.updated_at.desc())
            .limit(limit)
        )
        return list(self.session.scalars(stmt).unique().all())

    def set_triage(self, notice_id: str, *, saved: bool | None = None, dismissed: bool | None = None) -> Notice:
        notice = self.get_by_id(notice_id)
        if notice is None:
            raise KeyError(f"Notice not found: {notice_id}")
        if saved is not None:
            notice.saved = saved
            if saved:
                notice.dismissed = False
        if dismissed is not None:
            notice.dismissed = dismissed
            if dismissed:
                notice.saved = False
        self.session.flush()
        return notice

    def add_note(self, *, notice_id: str, user_id: str | None, note_text: str) -> AnalystNote:
        note = AnalystNote(notice_id=notice_id, user_id=user_id, note_text=note_text)
        self.session.add(note)
        self.session.flush()
        return note

    def dashboard_metrics(self) -> dict[str, Any]:
        now = datetime.now(tz=UTC)
        soon = now + timedelta(days=7)
        reviewable_notice_filter = _non_awarded_notice_clause()

        total_notices = self.session.scalar(
            select(func.count()).select_from(Notice).where(reviewable_notice_filter)
        ) or 0
        high_fit = self.session.scalar(
            select(func.count())
            .select_from(NoticeAnalysis)
            .join(Notice, Notice.id == NoticeAnalysis.notice_id)
            .where(NoticeAnalysis.priority_bucket == PriorityBucket.HIGH, reviewable_notice_filter)
        ) or 0
        conditional = self.session.scalar(
            select(func.count())
            .select_from(NoticeAnalysis)
            .join(Notice, Notice.id == NoticeAnalysis.notice_id)
            .where(NoticeAnalysis.fit_label == FitLabel.CONDITIONAL, reviewable_notice_filter)
        ) or 0
        expiring_soon = self.session.scalar(
            select(func.count())
            .select_from(Notice)
            .where(reviewable_notice_filter, Notice.deadline.is_not(None), Notice.deadline <= soon, Notice.deadline >= now)
        ) or 0
        hard_lock = self.session.scalar(
            select(func.count())
            .select_from(NoticeAnalysis)
            .join(Notice, Notice.id == NoticeAnalysis.notice_id)
            .where(NoticeAnalysis.hard_lock_detected.is_(True), reviewable_notice_filter)
        ) or 0
        freshest_scan = self.session.scalar(select(func.max(ScanRun.completed_at)))

        return {
            "total_notices": int(total_notices),
            "high_fit": int(high_fit),
            "conditional": int(conditional),
            "expiring_soon": int(expiring_soon),
            "hard_lock": int(hard_lock),
            "scan_freshness": freshest_scan,
        }

    def _apply_filters(self, stmt: Select[tuple[Notice]], filters: NoticeListFilters) -> Select[tuple[Notice]]:
        stmt = stmt.where(_non_awarded_notice_clause())
        if filters.relevant_only:
            stmt = stmt.where(NoticeAnalysis.fit_label.in_([FitLabel.YES, FitLabel.CONDITIONAL]))
        if filters.country:
            country_variants = self._country_variants(filters.country)
            if country_variants:
                stmt = stmt.where(Notice.buyer_country.in_(country_variants))
        if filters.fit_label:
            stmt = stmt.where(NoticeAnalysis.fit_label == FitLabel(filters.fit_label))
        if filters.priority_bucket:
            stmt = stmt.where(NoticeAnalysis.priority_bucket == PriorityBucket(filters.priority_bucket))
        if filters.confidence_indicator:
            stmt = stmt.where(NoticeAnalysis.confidence_indicator == ConfidenceIndicator(filters.confidence_indicator))
        if filters.min_score is not None:
            stmt = stmt.where(NoticeAnalysis.score >= filters.min_score)
        if filters.max_score is not None:
            stmt = stmt.where(NoticeAnalysis.score <= filters.max_score)
        if filters.min_days_remaining is not None:
            now = datetime.now(tz=UTC)
            minimum_deadline = now + timedelta(days=filters.min_days_remaining)
            stale_publication_cutoff = now.date() - timedelta(days=90)
            if filters.min_days_remaining == 0:
                stmt = stmt.where(
                    (Notice.deadline.is_not(None) & (Notice.deadline >= minimum_deadline))
                    | (
                        Notice.deadline.is_(None)
                        & (
                            Notice.publication_date.is_(None)
                            | (Notice.publication_date >= stale_publication_cutoff)
                        )
                    )
                )
            else:
                stmt = stmt.where(Notice.deadline.is_not(None), Notice.deadline >= minimum_deadline)
        if filters.hard_lock_only:
            stmt = stmt.where(NoticeAnalysis.hard_lock_detected.is_(True))
        if filters.publication_date_from is not None:
            stmt = stmt.where(Notice.publication_date.is_not(None), Notice.publication_date >= filters.publication_date_from)
        if filters.publication_date_to is not None:
            stmt = stmt.where(Notice.publication_date.is_not(None), Notice.publication_date <= filters.publication_date_to)
        if filters.deadline_from is not None:
            deadline_lower_bound = datetime.combine(filters.deadline_from, time.min, tzinfo=UTC)
            stmt = stmt.where(Notice.deadline.is_not(None), Notice.deadline >= deadline_lower_bound)
        if filters.deadline_to is not None:
            deadline_upper_bound = datetime.combine(filters.deadline_to, time.max, tzinfo=UTC)
            stmt = stmt.where(Notice.deadline.is_not(None), Notice.deadline <= deadline_upper_bound)
        if filters.deadline_window_days is not None:
            upper_bound = datetime.now(tz=UTC) + timedelta(days=filters.deadline_window_days)
            stmt = stmt.where(Notice.deadline.is_not(None), Notice.deadline <= upper_bound)
        if not filters.include_dismissed:
            stmt = stmt.where(Notice.dismissed.is_(False))
        if filters.saved_only:
            stmt = stmt.where(Notice.saved.is_(True))
        if filters.search:
            pattern = f"%{filters.search.lower()}%"
            stmt = stmt.where(
                func.lower(Notice.title).like(pattern)
                | func.lower(func.coalesce(Notice.buyer, "")).like(pattern)
                | func.lower(func.coalesce(Notice.summary, "")).like(pattern)
            )
        return stmt

    def _country_variants(self, value: str | builtins.list[str] | None) -> builtins.list[str]:
        if value is None:
            return []

        raw_values: list[str]
        if isinstance(value, str):
            raw_values = [part.strip() for part in value.split(",") if part.strip()]
        else:
            raw_values = [part.strip() for part in value if isinstance(part, str) and part.strip()]

        variants: list[str] = []
        seen: set[str] = set()
        for raw in raw_values:
            for variant in ted_country_code_variants(raw):
                if variant not in seen:
                    seen.add(variant)
                    variants.append(variant)
        return variants
