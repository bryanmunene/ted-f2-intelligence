from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings, load_keyword_pack, load_search_profiles
from app.ingestion.normalize import normalize_notice
from app.models import Base
from app.repositories.notices import NoticeRepository
from app.repositories.scan_runs import ScanRunRepository
from app.scoring.engine import ScoringEngine
from app.utils.time import utcnow


@pytest.fixture()
def ted_fixture_payload() -> dict:
    fixture_path = Path(__file__).parent / "fixtures" / "ted_search_response.json"
    return json.loads(fixture_path.read_text(encoding="utf-8"))


@pytest.fixture()
def db_session() -> Session:
    temp_dir = Path("tests/.tmp")
    temp_dir.mkdir(parents=True, exist_ok=True)
    db_path = temp_dir / f"test-{uuid4().hex}.db"
    engine = create_engine(
        f"sqlite+pysqlite:///{db_path}",
        connect_args={"check_same_thread": False},
        future=True,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        if db_path.exists():
            db_path.unlink()


@pytest.fixture()
def seeded_notice(db_session: Session, ted_fixture_payload: dict) -> str:
    settings = get_settings()
    keyword_pack = load_keyword_pack(settings.resolved_keyword_pack_path)
    profiles = load_search_profiles(settings.resolved_search_profiles_path)
    scorer = ScoringEngine(keyword_pack=keyword_pack, scoring_version=settings.scoring_version)
    scan_run = ScanRunRepository(db_session).create(
        started_at=utcnow(),
        profile_name="F2 Core",
        query_parameters={"seeded": True},
    )
    normalized = normalize_notice(
        ted_fixture_payload["results"][0],
        extraction_version=settings.analysis_extraction_version,
    )
    score = scorer.score(normalized, profile=profiles.by_name("F2 Core"), evaluated_at=utcnow())
    notice = NoticeRepository(db_session).upsert_notice(
        normalized_notice=normalized.repository_payload(),
        analysis_payload=score.repository_payload(),
        scan_run=scan_run,
    )
    ScanRunRepository(db_session).complete(
        scan_run,
        completed_at=utcnow(),
        total_notices_returned=1,
        total_notices_ingested=1,
        total_after_timing_filters=1,
        total_high_fit=1,
        total_conditional=0,
        total_ignored=0,
        request_count=1,
        rate_limit_events=0,
    )
    db_session.commit()
    return notice.id
