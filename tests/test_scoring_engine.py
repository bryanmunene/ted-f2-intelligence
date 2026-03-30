from __future__ import annotations

from datetime import UTC, datetime

from app.config import get_settings, load_keyword_pack, load_search_profiles
from app.ingestion.normalize import normalize_notice
from app.models.enums import FitLabel, PriorityBucket
from app.scoring.engine import ScoringEngine


def test_scoring_engine_flags_strong_f2_fit(ted_fixture_payload: dict) -> None:
    settings = get_settings()
    keyword_pack = load_keyword_pack(settings.resolved_keyword_pack_path)
    profiles = load_search_profiles(settings.resolved_search_profiles_path)
    notice = normalize_notice(ted_fixture_payload["results"][0], extraction_version="test-version")
    score = ScoringEngine(keyword_pack=keyword_pack, scoring_version=settings.scoring_version).score(
        notice,
        profile=profiles.by_name("F2 Core"),
        evaluated_at=datetime(2026, 3, 30, tzinfo=UTC),
    )

    assert score.fit_label == FitLabel.YES
    assert score.priority_bucket in {PriorityBucket.HIGH, PriorityBucket.GOOD}
    assert score.openness_detected is True
    assert score.score >= 70
    assert any(hit["scope"] == "title" for hit in score.keyword_hits)
    assert any(rule.rule_id == "combo.case_workflow_pattern" for rule in score.score_breakdown)


def test_scoring_engine_penalizes_hard_lock_and_timing(ted_fixture_payload: dict) -> None:
    settings = get_settings()
    keyword_pack = load_keyword_pack(settings.resolved_keyword_pack_path)
    profiles = load_search_profiles(settings.resolved_search_profiles_path)
    notice = normalize_notice(ted_fixture_payload["results"][1], extraction_version="test-version")
    score = ScoringEngine(keyword_pack=keyword_pack, scoring_version=settings.scoring_version).score(
        notice,
        profile=profiles.by_name("F2 Core"),
        evaluated_at=datetime(2026, 3, 30, tzinfo=UTC),
    )

    assert score.hard_lock_detected is True
    assert score.viable_timing is False
    assert score.fit_label in {FitLabel.NO, FitLabel.CONDITIONAL}
    assert score.priority_bucket in {PriorityBucket.WATCHLIST, PriorityBucket.IGNORE}


def test_keyword_requires_context_and_title_bonus_applies() -> None:
    settings = get_settings()
    keyword_pack = load_keyword_pack(settings.resolved_keyword_pack_path)
    profiles = load_search_profiles(settings.resolved_search_profiles_path)
    scorer = ScoringEngine(keyword_pack=keyword_pack, scoring_version=settings.scoring_version)

    contextless_registry_notice = normalize_notice(
        {
            "publication-number": "11111-2026",
            "notice-title": "Registry refresh for municipal office",
            "buyer-name": "Town Office",
            "buyer-country": "DK",
            "publication-date": "2026-03-25",
            "deadline": "2026-05-20T10:00:00Z",
            "additional-information": "General office tooling refresh.",
        },
        extraction_version="test-version",
    )
    score_without_context = scorer.score(
        contextless_registry_notice,
        profile=profiles.by_name("F2 Core"),
        evaluated_at=datetime(2026, 3, 30, tzinfo=UTC),
    )

    contextual_notice = normalize_notice(
        {
            "publication-number": "22222-2026",
            "notice-title": "Document registry and records management platform",
            "buyer-name": "Town Office",
            "buyer-country": "DK",
            "publication-date": "2026-03-25",
            "deadline": "2026-05-20T10:00:00Z",
            "additional-information": "Document registry, correspondence management, and records retention capabilities required.",
        },
        extraction_version="test-version",
    )
    score_with_context = scorer.score(
        contextual_notice,
        profile=profiles.by_name("F2 Core"),
        evaluated_at=datetime(2026, 3, 30, tzinfo=UTC),
    )

    assert all(hit["term"] != "registry" for hit in score_without_context.keyword_hits)
    assert any(hit["term"] == "registry" and hit["scope"] == "title" for hit in score_with_context.keyword_hits)
    assert score_with_context.score > score_without_context.score


def test_scoring_engine_accepts_notices_with_five_plus_days_remaining() -> None:
    settings = get_settings()
    keyword_pack = load_keyword_pack(settings.resolved_keyword_pack_path)
    profiles = load_search_profiles(settings.resolved_search_profiles_path)
    scorer = ScoringEngine(keyword_pack=keyword_pack, scoring_version=settings.scoring_version)

    notice = normalize_notice(
        {
            "publication-number": "33333-2026",
            "notice-title": "Case management and document workflow platform",
            "buyer-name": "Municipal Services Office",
            "buyer-country": "DK",
            "publication-date": "2026-03-28",
            "deadline": "2026-04-05T10:00:00Z",
            "additional-information": "Case handling, workflow automation, records management, and correspondence tracking.",
        },
        extraction_version="test-version",
    )
    score = scorer.score(
        notice,
        profile=profiles.by_name("F2 Core"),
        evaluated_at=datetime(2026, 3, 30, tzinfo=UTC),
    )

    assert score.viable_timing is True
    assert all(flag["flag"] != "expiring_soon" for flag in score.timing_flags)
