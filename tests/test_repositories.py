from __future__ import annotations

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
