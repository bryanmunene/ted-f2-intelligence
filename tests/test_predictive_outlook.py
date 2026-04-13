from __future__ import annotations

from datetime import UTC, date, datetime

from app.models.enums import ConfidenceIndicator, FitLabel, PriorityBucket
from app.repositories.notices import NoticeRepository
from app.services.predictive_outlook import PredictiveOutlookService
from app.utils.time import utcnow


def _store_relevant_notice(
    db_session,
    *,
    publication_number: str,
    title: str,
    buyer: str,
    buyer_country: str,
    publication_date: date,
    deadline: datetime,
    score: int,
    fit_label: FitLabel,
    procedure_type: str,
    raw_payload: dict,
) -> None:
    NoticeRepository(db_session).upsert_notice(
        normalized_notice={
            "ted_notice_id": publication_number,
            "publication_number": publication_number,
            "title": title,
            "title_translated_optional": None,
            "buyer": buyer,
            "buyer_country": buyer_country,
            "place_of_performance": buyer_country,
            "notice_type": "Contract notice",
            "procedure_type": procedure_type,
            "cpv_codes": ["72260000"],
            "publication_date": publication_date,
            "deadline": deadline,
            "contract_duration": "24 MONTH",
            "source_url": f"https://ted.europa.eu/en/notice/-/detail/{publication_number}",
            "html_url": f"https://ted.europa.eu/en/notice/-/detail/{publication_number}",
            "pdf_url": f"https://ted.europa.eu/en/notice/{publication_number}/pdf",
            "xml_url": f"https://ted.europa.eu/en/notice/{publication_number}/xml",
            "summary": "Case management and workflow platform for public administration.",
            "raw_payload_json": raw_payload,
            "extraction_version": "test",
        },
        analysis_payload={
            "scoring_version": "test",
            "analysis_timestamp": utcnow(),
            "keyword_hits": [],
            "domain_hits": [{"label": "Records", "terms": ["records"], "scopes": ["summary"]}],
            "positive_signals": [{"label": "Repository and workflow", "evidence": ["records", "workflow"]}],
            "negative_signals": [],
            "platform_lock_signals": [],
            "timing_flags": [],
            "rules_fired": [],
            "score_breakdown": [],
            "score": score,
            "fit_label": fit_label,
            "priority_bucket": (
                PriorityBucket.HIGH
                if fit_label == FitLabel.YES
                else PriorityBucket.WATCHLIST
                if fit_label == FitLabel.CONDITIONAL
                else PriorityBucket.IGNORE
            ),
            "confidence_indicator": ConfidenceIndicator.HIGH,
            "qualification_questions": [],
            "reasoning": "Relevant public-sector process digitisation opportunity.",
            "hard_lock_detected": False,
            "soft_lock_detected": False,
            "openness_detected": True,
            "viable_timing": True,
        },
    )


def test_predictive_outlook_learns_release_budget_and_country_patterns(db_session) -> None:
    _store_relevant_notice(
        db_session,
        publication_number="10001-2026",
        title="Municipal case management and archive platform",
        buyer="City of Aarhus",
        buyer_country="DNK",
        publication_date=date(2026, 4, 10),
        deadline=datetime(2026, 5, 12, tzinfo=UTC),
        score=78,
        fit_label=FitLabel.YES,
        procedure_type="Open procedure",
        raw_payload={"estimated-value": "EUR 1500000"},
    )
    _store_relevant_notice(
        db_session,
        publication_number="10002-2025",
        title="Regional workflow and records digitisation platform",
        buyer="Region Stockholm",
        buyer_country="SWE",
        publication_date=date(2025, 4, 14),
        deadline=datetime(2025, 5, 20, tzinfo=UTC),
        score=72,
        fit_label=FitLabel.YES,
        procedure_type="Open procedure",
        raw_payload={"estimated total value": "EUR 2400000"},
    )
    _store_relevant_notice(
        db_session,
        publication_number="10003-2024",
        title="Agency correspondence and records platform",
        buyer="Danish Business Authority",
        buyer_country="DNK",
        publication_date=date(2024, 3, 18),
        deadline=datetime(2024, 4, 20, tzinfo=UTC),
        score=61,
        fit_label=FitLabel.NO,
        procedure_type="Restricted procedure",
        raw_payload={"contract value": "EUR 1200000"},
    )
    db_session.commit()

    notices = NoticeRepository(db_session).predictive_history(limit=50)
    outlook = PredictiveOutlookService().build(notices, as_of=datetime(2026, 4, 13, tzinfo=UTC))

    assert outlook["sample_size"] == 3
    assert outlook["budget_summary"]["sample_size"] == 3
    assert "EUR" in outlook["budget_summary"]["range_display"]
    assert outlook["median_lead_days"] == 33
    assert outlook["peak_release_months"][0]["label"] == "April"
    assert outlook["top_countries"][0]["label"].startswith("Denmark")
    assert outlook["top_procedures"][0]["label"] == "Open procedure"
    assert outlook["next_expected_window"]["label"] == "April 2026"
    assert "April" in outlook["forecast_summary"]
