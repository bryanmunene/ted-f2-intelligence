from __future__ import annotations

from datetime import UTC, datetime

from app.config import get_settings, load_keyword_pack, load_search_profiles
from app.ingestion.normalize import normalize_notice
from app.repositories.notices import NoticeRepository
from app.scoring.engine import ScoringEngine
from app.services.rescoring import rescore_outdated_notices


def test_rescore_outdated_notices_refreshes_old_analysis(db_session, ted_fixture_payload: dict) -> None:
    settings = get_settings()
    keyword_pack = load_keyword_pack(settings.resolved_keyword_pack_path)
    profiles = load_search_profiles(settings.resolved_search_profiles_path)
    profile = profiles.by_name("F2 Core")

    notice = normalize_notice(
        ted_fixture_payload["results"][0],
        extraction_version=settings.analysis_extraction_version,
    )
    old_scorer = ScoringEngine(keyword_pack=keyword_pack, scoring_version="2026.04.2")
    old_score = old_scorer.score(notice, profile=profile, evaluated_at=datetime(2026, 3, 30, tzinfo=UTC))

    repo = NoticeRepository(db_session)
    stored = repo.upsert_notice(
        normalized_notice=notice.repository_payload(),
        analysis_payload=old_score.repository_payload(),
        scan_run=None,
    )
    stored.analysis.score = 0
    stored.analysis.scoring_version = "2026.04.2"
    db_session.commit()

    updated_count = rescore_outdated_notices(db_session)
    db_session.refresh(stored)
    db_session.refresh(stored.analysis)

    assert updated_count >= 1
    assert stored.analysis.scoring_version == settings.scoring_version
    assert stored.analysis.score > 0
