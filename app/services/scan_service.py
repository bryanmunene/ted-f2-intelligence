from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.api.schemas import ScanRequestPayload
from app.auth import ActorContext
from app.config import KeywordPack, SearchProfileRegistry, Settings
from app.ingestion.normalize import normalize_notice
from app.models.enums import AuditEventType, FitLabel, PriorityBucket
from app.repositories.audit import AuditRepository
from app.repositories.notices import NoticeRepository
from app.repositories.scan_runs import ScanRunRepository
from app.repositories.users import UserRepository
from app.scoring.engine import ScoringEngine
from app.services.query_builder import TedExpertQueryBuilder
from app.services.ted_client import TedApiClient, TedSearchRequest
from app.utils.time import utcnow

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ScanOutcome:
    scan_run_id: str
    total_notices_returned: int
    total_notices_ingested: int
    total_after_timing_filters: int
    total_high_fit: int
    total_conditional: int
    total_ignored: int
    request_count: int
    rate_limit_events: int


class ScanService:
    def __init__(
        self,
        *,
        session: Session,
        settings: Settings,
        ted_client: TedApiClient,
        keyword_pack: KeywordPack,
        search_profiles: SearchProfileRegistry,
        actor: ActorContext,
    ) -> None:
        self.session = session
        self.settings = settings
        self.ted_client = ted_client
        self.keyword_pack = keyword_pack
        self.search_profiles = search_profiles
        self.actor = actor
        self.query_builder = TedExpertQueryBuilder()
        self.notice_repo = NoticeRepository(session)
        self.scan_repo = ScanRunRepository(session)
        self.audit_repo = AuditRepository(session)
        self.user_repo = UserRepository(session)
        self.scoring_engine = ScoringEngine(
            keyword_pack=keyword_pack,
            scoring_version=settings.scoring_version,
        )

    def run_manual_scan(self, payload: ScanRequestPayload) -> ScanOutcome:
        profile = self.search_profiles.by_name(payload.profile_name)
        query = self.query_builder.build(payload=payload, profile=profile)
        started_at = utcnow()
        actor_user = self.user_repo.get_or_create(
            email=self.actor.email,
            display_name=self.actor.display_name,
            auth_provider=self.actor.auth_provider,
        )
        scan_run = self.scan_repo.create(
            started_at=started_at,
            profile_name=profile.name,
            query_parameters=payload.model_dump(mode="json") | {"query": query},
        )
        self.audit_repo.record(
            event_type=AuditEventType.SCAN_STARTED,
            entity_type="scan_run",
            entity_id=scan_run.id,
            payload_json={"profile_name": profile.name, "query": query},
            actor=actor_user,
        )
        self.session.commit()

        self.ted_client.reset_metrics()
        total_notices_returned = 0
        total_notices_ingested = 0
        total_after_timing_filters = 0
        total_high_fit = 0
        total_conditional = 0
        total_ignored = 0

        try:
            page_limit = min(payload.max_pages, self.settings.ted_max_pages_per_scan)
            for page_number in range(1, page_limit + 1):
                search_request = TedSearchRequest(
                    query=query,
                    page=page_number,
                    limit=min(payload.page_size, self.settings.ted_max_page_size),
                    scope=self.settings.ted_search_scope,
                )
                response = self.ted_client.search(search_request)
                if page_number == 1:
                    total_notices_returned = response.total_count
                if not response.notices:
                    break

                for raw_notice in response.notices:
                    normalized = normalize_notice(
                        raw_notice,
                        extraction_version=self.settings.analysis_extraction_version,
                    )
                    scored = self.scoring_engine.score(
                        normalized,
                        profile=profile,
                        evaluated_at=started_at,
                        exclude_old=payload.exclude_old,
                        include_soft_locks=payload.include_soft_locks,
                    )
                    self.notice_repo.upsert_notice(
                        normalized_notice=normalized.repository_payload(),
                        analysis_payload=scored.repository_payload(),
                        scan_run=scan_run,
                    )
                    total_notices_ingested += 1
                    if scored.viable_timing:
                        total_after_timing_filters += 1
                    if scored.priority_bucket == PriorityBucket.HIGH:
                        total_high_fit += 1
                    if scored.fit_label == FitLabel.CONDITIONAL:
                        total_conditional += 1
                    if scored.priority_bucket == PriorityBucket.IGNORE:
                        total_ignored += 1

                if len(response.notices) < payload.page_size:
                    break

            metrics = self.ted_client.metrics()
            self.scan_repo.complete(
                scan_run,
                completed_at=utcnow(),
                total_notices_returned=total_notices_returned,
                total_notices_ingested=total_notices_ingested,
                total_after_timing_filters=total_after_timing_filters,
                total_high_fit=total_high_fit,
                total_conditional=total_conditional,
                total_ignored=total_ignored,
                request_count=metrics.request_count,
                rate_limit_events=metrics.rate_limit_events,
                error_count=0,
            )
            self.audit_repo.record(
                event_type=AuditEventType.SCAN_COMPLETED,
                entity_type="scan_run",
                entity_id=scan_run.id,
                payload_json={
                    "total_notices_returned": total_notices_returned,
                    "total_notices_ingested": total_notices_ingested,
                    "request_count": metrics.request_count,
                    "rate_limit_events": metrics.rate_limit_events,
                },
                actor=actor_user,
            )
            self.session.commit()
            logger.info(
                "scan_completed",
                extra={
                    "scan_run_id": scan_run.id,
                    "profile_name": profile.name,
                    "total_notices_ingested": total_notices_ingested,
                },
            )
            return ScanOutcome(
                scan_run_id=scan_run.id,
                total_notices_returned=total_notices_returned,
                total_notices_ingested=total_notices_ingested,
                total_after_timing_filters=total_after_timing_filters,
                total_high_fit=total_high_fit,
                total_conditional=total_conditional,
                total_ignored=total_ignored,
                request_count=metrics.request_count,
                rate_limit_events=metrics.rate_limit_events,
            )
        except Exception as exc:
            self.session.rollback()
            self.scan_repo.fail(
                scan_run,
                completed_at=utcnow(),
                error_summary=str(exc),
                error_count=1,
            )
            self.audit_repo.record(
                event_type=AuditEventType.SCAN_FAILED,
                entity_type="scan_run",
                entity_id=scan_run.id,
                payload_json={"error": str(exc)},
                actor_email=self.actor.email,
                actor_display_name=self.actor.display_name,
            )
            self.session.commit()
            logger.exception("scan_failed", extra={"profile_name": profile.name, "scan_run_id": scan_run.id})
            raise

