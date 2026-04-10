from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.config import get_settings, load_keyword_pack, load_search_profiles
from app.ingestion.normalize import normalize_notice
from app.repositories.notices import NoticeListFilters, NoticeRepository
from app.scoring.engine import ScoringEngine


def _store_scored_notice(db_session, payload: dict) -> str:
    settings = get_settings()
    keyword_pack = load_keyword_pack(settings.resolved_keyword_pack_path)
    profiles = load_search_profiles(settings.resolved_search_profiles_path)
    scorer = ScoringEngine(keyword_pack=keyword_pack, scoring_version=settings.scoring_version)
    normalized = normalize_notice(payload, extraction_version="test-version")
    score = scorer.score(
        normalized,
        profile=profiles.by_name("F2 Core"),
        evaluated_at=datetime(2026, 3, 30, tzinfo=UTC),
    )
    notice = NoticeRepository(db_session).upsert_notice(
        normalized_notice=normalized.repository_payload(),
        analysis_payload=score.repository_payload(),
    )
    db_session.commit()
    return notice.id


def test_notice_repository_lists_seeded_notice(db_session, seeded_notice: str) -> None:
    repository = NoticeRepository(db_session)
    notices, total = repository.list(NoticeListFilters(), page=1, page_size=25)

    assert total == 1
    assert len(notices) == 1
    assert notices[0].id == seeded_notice


def test_dashboard_metrics_reflect_seeded_notice(db_session, seeded_notice: str) -> None:
    metrics = NoticeRepository(db_session).dashboard_metrics()

    assert metrics["total_notices"] == 1
    assert metrics["scan_freshness"] is not None


def test_notice_repository_country_filter_accepts_iso2_or_ted_code(db_session, seeded_notice: str) -> None:
    repository = NoticeRepository(db_session)

    notices_alpha2, total_alpha2 = repository.list(NoticeListFilters(country="DK"), page=1, page_size=25)
    notices_alpha3, total_alpha3 = repository.list(NoticeListFilters(country="DNK"), page=1, page_size=25)

    assert total_alpha2 == 1
    assert total_alpha3 == 1
    assert notices_alpha2[0].id == seeded_notice
    assert notices_alpha3[0].id == seeded_notice


def test_notice_repository_country_filter_accepts_multiple_countries(db_session, seeded_notice: str) -> None:
    repository = NoticeRepository(db_session)
    swe_notice_id = _store_scored_notice(
        db_session,
        {
            "publication-number": "77701-2026",
            "notice-title": "Records management platform",
            "buyer-name": "Municipal Archives Authority",
            "buyer-country": "SE",
            "publication-date": "2026-03-28",
            "deadline": "2026-06-20T10:00:00Z",
            "additional-information": "Records management, workflow automation and archiving.",
        },
    )

    notices_list, total_list = repository.list(NoticeListFilters(country=["DK", "SE"]), page=1, page_size=25)
    notices_csv, total_csv = repository.list(NoticeListFilters(country="DK,SE"), page=1, page_size=25)

    assert total_list == 2
    assert total_csv == 2
    assert {notice.id for notice in notices_list} == {seeded_notice, swe_notice_id}
    assert {notice.id for notice in notices_csv} == {seeded_notice, swe_notice_id}


def test_notice_repository_default_review_queue_is_broader_but_can_be_narrowed(
    db_session,
    seeded_notice: str,
) -> None:
    repository = NoticeRepository(db_session)
    soon_deadline = (datetime.now(tz=UTC) + timedelta(hours=12)).isoformat().replace("+00:00", "Z")

    soon_notice_id = _store_scored_notice(
        db_session,
        {
            "publication-number": "55555-2026",
            "notice-title": "Case management platform for regional permit workflow",
            "buyer-name": "Regional Permits Authority",
            "buyer-country": "DK",
            "publication-date": "2026-03-29",
            "deadline": soon_deadline,
            "additional-information": "Case management, workflow automation, records handling, and citizen services.",
        },
    )
    irrelevant_notice_id = _store_scored_notice(
        db_session,
        {
            "publication-number": "66666-2026",
            "notice-title": "Supply of firewalls, switches and antivirus software",
            "buyer-name": "Regional IT Operations",
            "buyer-country": "DK",
            "publication-date": "2026-03-29",
            "deadline": "2026-05-15T10:00:00Z",
            "additional-information": "Pure hardware and security tooling procurement with no case handling or records platform scope.",
        },
    )

    broad_notices, broad_total = repository.list(NoticeListFilters(), page=1, page_size=25)
    broad_ids = {notice.id for notice in broad_notices}

    assert broad_total == 3
    assert broad_ids == {seeded_notice, soon_notice_id, irrelevant_notice_id}

    strict_notices, strict_total = repository.list(
        NoticeListFilters(relevant_only=True, min_days_remaining=1),
        page=1,
        page_size=25,
    )
    strict_ids = {notice.id for notice in strict_notices}

    assert strict_total == 1
    assert strict_ids == {seeded_notice}


def test_notice_repository_supports_score_confidence_and_date_filters(db_session, seeded_notice: str) -> None:
    repository = NoticeRepository(db_session)
    notice = repository.get_by_id(seeded_notice)

    assert notice is not None
    assert notice.analysis is not None
    assert notice.publication_date is not None
    assert notice.deadline is not None

    matching_filters = NoticeListFilters(
        min_score=notice.analysis.score,
        max_score=notice.analysis.score,
        confidence_indicator=notice.analysis.confidence_indicator.value,
        publication_date_from=notice.publication_date,
        publication_date_to=notice.publication_date,
        deadline_from=notice.deadline.date(),
        deadline_to=notice.deadline.date(),
    )
    matching_notices, matching_total = repository.list(matching_filters, page=1, page_size=25)

    assert matching_total == 1
    assert matching_notices[0].id == seeded_notice

    low_score_notices, low_score_total = repository.list(
        NoticeListFilters(max_score=notice.analysis.score - 1),
        page=1,
        page_size=25,
    )
    assert low_score_total == 0
    assert low_score_notices == []

    publication_miss_notices, publication_miss_total = repository.list(
        NoticeListFilters(publication_date_from=notice.publication_date + timedelta(days=1)),
        page=1,
        page_size=25,
    )
    assert publication_miss_total == 0
    assert publication_miss_notices == []

    deadline_miss_notices, deadline_miss_total = repository.list(
        NoticeListFilters(deadline_to=notice.deadline.date() - timedelta(days=1)),
        page=1,
        page_size=25,
    )
    assert deadline_miss_total == 0
    assert deadline_miss_notices == []


def test_notice_repository_orders_by_priority_fit_score_then_deadline(db_session) -> None:
    high_id = _store_scored_notice(
        db_session,
        {
            "publication-number": "90101-2026",
            "notice-title": "Case management workflow and document management platform",
            "buyer-name": "Justice Authority",
            "buyer-country": "DK",
            "publication-date": "2026-03-20",
            "deadline": "2026-06-20T10:00:00Z",
            "additional-information": "Document management, workflow automation, approvals, records governance, migration, integration, training, citizen services and audit trail.",
            "classification-cpv": ["48311000"],
        },
    )
    conditional_id = _store_scored_notice(
        db_session,
        {
            "publication-number": "90102-2026",
            "notice-title": "Document management platform for permits",
            "buyer-name": "Licensing Authority",
            "buyer-country": "DK",
            "publication-date": "2026-03-20",
            "deadline": "2026-06-18T10:00:00Z",
            "additional-information": "Document management and permits workflow. Existing Microsoft licenses already available.",
            "classification-cpv": ["48311000"],
        },
    )
    ignore_id = _store_scored_notice(
        db_session,
        {
            "publication-number": "90103-2026",
            "notice-title": "Supply of vehicles",
            "buyer-name": "Municipal Fleet Unit",
            "buyer-country": "DK",
            "publication-date": "2026-03-20",
            "deadline": "2026-06-10T10:00:00Z",
            "additional-information": "Vehicle procurement only.",
        },
    )

    notices, total = NoticeRepository(db_session).list(NoticeListFilters(), page=1, page_size=10)

    assert total == 3
    assert [notice.id for notice in notices] == [high_id, conditional_id, ignore_id]
