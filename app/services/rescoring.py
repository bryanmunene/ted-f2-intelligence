from __future__ import annotations

from functools import lru_cache

from sqlalchemy import select
from sqlalchemy.orm import Session, contains_eager, selectinload

from app.config import SearchProfile, get_settings
from app.deps import get_keyword_pack_cached, get_search_profiles_cached
from app.ingestion.models import NormalizedNotice
from app.models import Notice, NoticeAnalysis
from app.repositories.notices import NoticeRepository
from app.scoring.engine import ScoringEngine
from app.utils.time import ensure_utc, utcnow


@lru_cache(maxsize=1)
def _rescoring_bundle() -> tuple[ScoringEngine, SearchProfile]:
    settings = get_settings()
    profiles = get_search_profiles_cached()
    try:
        profile = profiles.by_name("f2-all-opportunities")
    except KeyError:
        profile = profiles.profiles[0]
    engine = ScoringEngine(
        keyword_pack=get_keyword_pack_cached(),
        scoring_version=settings.scoring_version,
    )
    return engine, profile


def normalized_notice_from_record(notice: Notice) -> NormalizedNotice:
    return NormalizedNotice(
        ted_notice_id=notice.ted_notice_id,
        publication_number=notice.publication_number,
        title=notice.title,
        title_translated_optional=notice.title_translated_optional,
        buyer=notice.buyer,
        buyer_country=notice.buyer_country,
        place_of_performance=notice.place_of_performance,
        notice_type=notice.notice_type,
        procedure_type=notice.procedure_type,
        cpv_codes=list(notice.cpv_codes or []),
        publication_date=notice.publication_date,
        deadline=ensure_utc(notice.deadline) if notice.deadline else None,
        contract_duration=notice.contract_duration,
        source_url=notice.source_url,
        html_url=notice.html_url,
        pdf_url=notice.pdf_url,
        xml_url=notice.xml_url,
        summary=notice.summary,
        raw_payload_json=dict(notice.raw_payload_json or {}),
        extraction_version=notice.extraction_version,
    )


def rescore_outdated_notices(session: Session, *, limit: int = 250) -> int:
    settings = get_settings()
    engine, profile = _rescoring_bundle()

    stmt = (
        select(Notice)
        .outerjoin(Notice.analysis)
        .options(contains_eager(Notice.analysis), selectinload(Notice.notes))
        .where((NoticeAnalysis.id.is_(None)) | (NoticeAnalysis.scoring_version != settings.scoring_version))
        .order_by(Notice.updated_at.desc())
        .limit(limit)
    )
    notices = list(session.scalars(stmt).unique().all())
    if not notices:
        return 0

    repo = NoticeRepository(session)
    evaluated_at = utcnow()
    rescored = 0
    for notice in notices:
        normalized = normalized_notice_from_record(notice)
        scored = engine.score(
            normalized,
            profile=profile,
            evaluated_at=evaluated_at,
            exclude_old=False,
            include_soft_locks=True,
        )
        repo.upsert_notice(
            normalized_notice=normalized.repository_payload(),
            analysis_payload=scored.repository_payload(),
            scan_run=None,
        )
        rescored += 1

    session.commit()
    return rescored
