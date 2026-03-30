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


def test_normalize_notice_handles_multilingual_live_ted_payload() -> None:
    raw_notice = {
        "publication-number": "148106-2016",
        "notice-title": {
            "eng": "Denmark-Copenhagen: Post and courier services",
            "dan": "Danmark-Kobenhavn: Postbefordring og kurtjeneste",
        },
        "buyer-name": {"dan": ["Post Danmark A/S"]},
        "buyer-country": ["DNK"],
        "publication-date": "2016-04-29+02:00",
        "deadline-receipt-tender-date-lot": "2016-05-15",
        "classification-cpv": ["64100000"],
        "links": {
            "html": {"ENG": "https://ted.europa.eu/en/notice/-/detail/148106-2016"},
            "pdf": {"ENG": "https://ted.europa.eu/en/notice/148106-2016/pdf"},
            "xml": {"MUL": "https://ted.europa.eu/en/notice/148106-2016/xml"},
        },
    }

    normalized = normalize_notice(raw_notice, extraction_version="test-version")

    assert normalized.title == "Denmark-Copenhagen: Post and courier services"
    assert normalized.buyer == "Post Danmark A/S"
    assert normalized.buyer_country == "DNK"
    assert normalized.publication_date is not None
    assert normalized.deadline is not None
    assert normalized.html_url == "https://ted.europa.eu/en/notice/-/detail/148106-2016"
    assert normalized.pdf_url == "https://ted.europa.eu/en/notice/148106-2016/pdf"
