from __future__ import annotations

from datetime import UTC, datetime

from app.config import get_settings, load_keyword_pack, load_search_profiles
from app.ingestion.normalize import normalize_notice
from app.scoring.engine import ScoringEngine
from app.services.keyword_evidence import build_keyword_evidence_module


def test_keyword_evidence_module_explains_positive_matches(ted_fixture_payload: dict) -> None:
    settings = get_settings()
    keyword_pack = load_keyword_pack(settings.resolved_keyword_pack_path)
    profiles = load_search_profiles(settings.resolved_search_profiles_path)
    notice = normalize_notice(ted_fixture_payload["results"][0], extraction_version="test-version")
    score = ScoringEngine(keyword_pack=keyword_pack, scoring_version=settings.scoring_version).score(
        notice,
        profile=profiles.by_name("F2 Core"),
        evaluated_at=datetime(2026, 3, 30, tzinfo=UTC),
    )

    module = build_keyword_evidence_module(
        {
            "fit_label": score.fit_label,
            "keyword_hits": score.keyword_hits,
            "domain_hits": score.domain_hits,
            "positive_signals": [item.model_dump() for item in score.positive_signals],
            "negative_signals": [item.model_dump() for item in score.negative_signals],
        }
    )

    assert module["matched_keyword_count"] >= 3
    assert module["matched_domain_count"] >= 2
    assert "surfaced because" in module["statement"]
    assert any(group["scope"] == "title" for group in module["scope_hits"])
    assert any("case management" in domain["terms"] for domain in module["domain_matches"])


def test_keyword_evidence_module_handles_missing_positive_evidence() -> None:
    module = build_keyword_evidence_module(
        {
            "fit_label": "NO",
            "keyword_hits": [],
            "domain_hits": [],
            "positive_signals": [],
            "negative_signals": [],
        }
    )

    assert module["matched_keyword_count"] == 0
    assert module["matched_domain_count"] == 0
    assert module["headline"] == "No positive keyword evidence stored"
