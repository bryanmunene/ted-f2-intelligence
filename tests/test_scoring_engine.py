from __future__ import annotations

from datetime import UTC, datetime

from app.config import get_settings, load_keyword_pack, load_search_profiles
from app.ingestion.normalize import normalize_notice
from app.models.enums import FitLabel, PriorityBucket
from app.scoring.engine import ScoringEngine


def _scorer() -> tuple[ScoringEngine, object]:
    settings = get_settings()
    keyword_pack = load_keyword_pack(settings.resolved_keyword_pack_path)
    profiles = load_search_profiles(settings.resolved_search_profiles_path)
    scorer = ScoringEngine(keyword_pack=keyword_pack, scoring_version=settings.scoring_version)
    return scorer, profiles.by_name("F2 Core")


def test_scoring_engine_flags_strong_ted_f2_fit(ted_fixture_payload: dict) -> None:
    scorer, profile = _scorer()
    notice = normalize_notice(ted_fixture_payload["results"][0], extraction_version="test-version")

    score = scorer.score(notice, profile=profile, evaluated_at=datetime(2026, 3, 30, tzinfo=UTC))

    assert score.fit_label in {FitLabel.YES, FitLabel.CONDITIONAL}
    assert score.priority_bucket in {PriorityBucket.HIGH, PriorityBucket.GOOD, PriorityBucket.WATCHLIST}
    assert score.score >= 65
    assert score.openness_detected is True
    assert any(hit["term"] == "case management" for hit in score.keyword_hits)
    assert any(domain["group_id"] == "workflow_bpm" for domain in score.domain_hits)
    assert "Matched domains:" in score.reasoning


def test_scoring_engine_rejects_deadlines_under_seven_days(ted_fixture_payload: dict) -> None:
    scorer, profile = _scorer()
    notice = normalize_notice(ted_fixture_payload["results"][1], extraction_version="test-version")

    score = scorer.score(notice, profile=profile, evaluated_at=datetime(2026, 3, 30, tzinfo=UTC))

    assert score.fit_label == FitLabel.NO
    assert score.priority_bucket == PriorityBucket.IGNORE
    assert score.score == 0
    assert score.viable_timing is False
    assert "Deadline under 7 days" in score.reasoning


def test_scoring_engine_flags_hard_platform_lock_even_with_good_scope() -> None:
    scorer, profile = _scorer()
    notice = normalize_notice(
        {
            "publication-number": "44555-2026",
            "notice-title": "Document management and workflow platform",
            "buyer-name": "Justice Authority",
            "buyer-country": "DK",
            "publication-date": "2026-03-25",
            "deadline": "2026-05-30T10:00:00Z",
            "additional-information": "The solution must use Power Platform and SharePoint as the delivery platform. Integration, migration and training are in scope.",
            "classification-cpv": ["48311000"],
        },
        extraction_version="test-version",
    )

    score = scorer.score(notice, profile=profile, evaluated_at=datetime(2026, 3, 30, tzinfo=UTC))

    assert score.hard_lock_detected is True
    assert score.fit_label == FitLabel.NO
    assert score.priority_bucket == PriorityBucket.IGNORE
    assert any(signal["severity"] == "hard" for signal in [item.model_dump() for item in score.platform_lock_signals])


def test_scoring_engine_penalizes_missing_deadline_but_keeps_reviewable_scope() -> None:
    scorer, profile = _scorer()
    notice = normalize_notice(
        {
            "publication-number": "55666-2026",
            "notice-title": "Case management and records platform",
            "buyer-name": "Municipal Licensing Authority",
            "buyer-country": "DK",
            "publication-date": "2026-03-20",
            "additional-information": "Case management, workflow automation, records governance, approvals, integration, migration and training are required.",
            "classification-cpv": ["48311000"],
        },
        extraction_version="test-version",
    )

    score = scorer.score(notice, profile=profile, evaluated_at=datetime(2026, 3, 30, tzinfo=UTC))

    assert score.fit_label in {FitLabel.YES, FitLabel.CONDITIONAL}
    assert score.viable_timing is False
    assert any(flag["flag"] == "missing_deadline" for flag in score.timing_flags)
    assert "What is the submission deadline?" in score.qualification_questions


def test_scoring_engine_rejects_publications_older_than_ninety_days() -> None:
    scorer, profile = _scorer()
    notice = normalize_notice(
        {
            "publication-number": "66777-2026",
            "notice-title": "Records management platform",
            "buyer-name": "Public Agency",
            "buyer-country": "DK",
            "publication-date": "2025-11-01",
            "deadline": "2026-05-30T10:00:00Z",
            "additional-information": "Records management, workflow, archiving and approvals.",
        },
        extraction_version="test-version",
    )

    score = scorer.score(notice, profile=profile, evaluated_at=datetime(2026, 3, 30, tzinfo=UTC))

    assert score.fit_label == FitLabel.NO
    assert score.priority_bucket == PriorityBucket.IGNORE
    assert score.score == 0


def test_scoring_engine_rejects_clear_poor_fit_hardware_scope() -> None:
    scorer, profile = _scorer()
    notice = normalize_notice(
        {
            "publication-number": "77888-2026",
            "notice-title": "Supply of routers, switches and firewalls",
            "buyer-name": "Regional IT Operations",
            "buyer-country": "DK",
            "publication-date": "2026-03-20",
            "deadline": "2026-05-30T10:00:00Z",
            "additional-information": "Hardware procurement for network infrastructure and endpoint protection.",
            "classification-cpv": ["32420000", "48730000"],
        },
        extraction_version="test-version",
    )

    score = scorer.score(notice, profile=profile, evaluated_at=datetime(2026, 3, 30, tzinfo=UTC))

    assert score.fit_label == FitLabel.NO
    assert score.priority_bucket == PriorityBucket.IGNORE
    assert any(signal.id == "hardware_only" for signal in score.negative_signals)
