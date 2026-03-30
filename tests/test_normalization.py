from __future__ import annotations

from app.ingestion.normalize import normalize_notice


def test_normalize_notice_maps_core_fields(ted_fixture_payload: dict) -> None:
    raw_notice = ted_fixture_payload["results"][0]
    normalized = normalize_notice(raw_notice, extraction_version="test-version")

    assert normalized.publication_number == "12345-2026"
    assert normalized.buyer == "City of Aarhus"
    assert normalized.buyer_country == "DK"
    assert "72260000" in normalized.cpv_codes
    assert normalized.html_url.endswith("/12345-2026/html")
    assert normalized.summary is not None

