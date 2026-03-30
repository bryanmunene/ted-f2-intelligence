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

