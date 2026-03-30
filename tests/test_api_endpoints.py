from __future__ import annotations

import httpx
import respx
from fastapi.testclient import TestClient

from app.deps import get_db
from app.database import get_db_session
from app.main import create_app
from app.repositories.notices import NoticeRepository


def test_dashboard_and_notice_endpoints(db_session, seeded_notice: str) -> None:
    app = create_app()

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db_session] = override_get_db
    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    dashboard = client.get("/api/v1/dashboard")
    assert dashboard.status_code == 200
    assert dashboard.json()["total_notices"] == 1

    notice = client.get(f"/api/v1/notices/{seeded_notice}")
    assert notice.status_code == 200
    assert notice.json()["id"] == seeded_notice

    checklist = client.get(f"/api/v1/notices/{seeded_notice}/checklist")
    assert checklist.status_code == 200
    assert checklist.json()["publication_number"] == "12345-2026"
    assert len(checklist.json()["items"]) == 12

    results_page = client.get("/results")
    assert results_page.status_code == 200
    assert "TED F2 Intelligence" in results_page.text


@respx.mock
def test_official_ted_actions(db_session, seeded_notice: str) -> None:
    app = create_app()

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db_session] = override_get_db
    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    redirect_response = client.get(f"/results/{seeded_notice}/open-ted", follow_redirects=False)
    assert redirect_response.status_code == 307
    assert redirect_response.headers["location"].endswith("/notice/-/detail/12345-2026")

    respx.get("https://ted.europa.eu/en/notice/12345-2026/pdf").mock(
        return_value=httpx.Response(
            200,
            content=b"%PDF-1.7 sample",
            headers={"content-type": "application/pdf"},
        )
    )

    download_response = client.get(f"/results/{seeded_notice}/download/pdf")
    assert download_response.status_code == 200
    assert download_response.headers["content-type"] == "application/pdf"
    assert '12345-2026.pdf' in download_response.headers["content-disposition"]
    assert download_response.content.startswith(b"%PDF")


def test_demo_notice_disables_live_ted_redirect(db_session, seeded_notice: str) -> None:
    app = create_app()

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db_session] = override_get_db
    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    notice = NoticeRepository(db_session).get_by_id(seeded_notice)
    assert notice is not None
    notice.raw_payload_json = dict(notice.raw_payload_json | {"_seed_fixture": True})
    db_session.commit()

    redirect_response = client.get(f"/results/{seeded_notice}/open-ted", follow_redirects=False)
    assert redirect_response.status_code == 404
    assert "seeded demo data" in redirect_response.json()["detail"].lower()
