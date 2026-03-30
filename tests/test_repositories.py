from __future__ import annotations

from datetime import timedelta

from app.repositories.notices import NoticeListFilters, NoticeRepository


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
