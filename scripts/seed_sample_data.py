from __future__ import annotations

import json
from pathlib import Path

from app.config import get_settings, load_keyword_pack, load_search_profiles
from app.database import get_session_factory
from app.ingestion.normalize import normalize_notice
from app.models.enums import AuditEventType
from app.repositories.audit import AuditRepository
from app.repositories.notices import NoticeRepository
from app.repositories.scan_runs import ScanRunRepository
from app.repositories.users import UserRepository
from app.scoring.engine import ScoringEngine
from app.utils.time import utcnow


def main() -> None:
    settings = get_settings()
    keyword_pack = load_keyword_pack(settings.resolved_keyword_pack_path)
    profiles = load_search_profiles(settings.resolved_search_profiles_path)
    profile = profiles.by_name("F2 Core")

    fixture_path = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "ted_search_response.json"
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))

    session = get_session_factory()()
    try:
        user = UserRepository(session).get_or_create(
            email=settings.default_user_email,
            display_name=settings.default_user_name,
            auth_provider="seed-script",
        )
        scan_run = ScanRunRepository(session).create(
            started_at=utcnow(),
            profile_name=profile.name,
            query_parameters={"source": "fixture", "fixture": str(fixture_path.name)},
        )
        scorer = ScoringEngine(keyword_pack=keyword_pack, scoring_version=settings.scoring_version)
        notice_repo = NoticeRepository(session)

        for raw_notice in payload["results"]:
            normalized = normalize_notice(raw_notice, extraction_version=settings.analysis_extraction_version)
            score = scorer.score(normalized, profile=profile, evaluated_at=utcnow())
            notice_repo.upsert_notice(
                normalized_notice=normalized.repository_payload(),
                analysis_payload=score.repository_payload(),
                scan_run=scan_run,
            )

        AuditRepository(session).record(
            event_type=AuditEventType.SCAN_COMPLETED,
            entity_type="scan_run",
            entity_id=scan_run.id,
            payload_json={"seeded": True},
            actor=user,
        )
        session.commit()
        print(f"Seeded sample TED notices into database using scan run {scan_run.id}")
    finally:
        session.close()


if __name__ == "__main__":
    main()

