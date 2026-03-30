from __future__ import annotations

from datetime import date

from app.api.schemas import ScanRequestPayload
from app.config import get_settings, load_search_profiles


def test_f2_core_profile_covers_full_f2_category_set() -> None:
    profiles = load_search_profiles(get_settings().resolved_search_profiles_path)
    profile = profiles.by_name("F2 Core")

    assert profile.keyword_group_ids == [
        "document_management",
        "records_management",
        "case_management",
        "workflow_bpm",
        "correspondence_registry",
        "digital_services",
        "egov",
        "compliance_audit",
        "digitisation_platform",
        "interoperability",
    ]


def test_query_builder_uses_ted_expert_search_syntax() -> None:
    from app.services.query_builder import TedExpertQueryBuilder

    profiles = load_search_profiles(get_settings().resolved_search_profiles_path)
    profile = profiles.by_name("F2 Core")

    query = TedExpertQueryBuilder().build(
        payload=ScanRequestPayload(
            profile_name="F2 Core",
            country="dk",
            cpv="72260000",
            date_from=date(2026, 3, 1),
            date_to=date(2026, 3, 31),
        ),
        profile=profile,
    )

    assert 'FT~"case management"' in query
    assert 'FT~"workflow automation"' in query
    assert "buyer-country=DNK" in query
    assert "classification-cpv=72260000" in query
    assert "publication-date>=20260301" in query
    assert "publication-date<=20260331" in query
    assert "*" not in query


def test_query_builder_requires_at_least_one_clause() -> None:
    from app.services.query_builder import TedExpertQueryBuilder

    profiles = load_search_profiles(get_settings().resolved_search_profiles_path)
    profile = profiles.by_name("F2 Core")
    profile.search_terms = []

    try:
        TedExpertQueryBuilder().build(payload=ScanRequestPayload(profile_name="F2 Core"), profile=profile)
    except ValueError as exc:
        assert "At least one TED search criterion" in str(exc)
    else:
        raise AssertionError("Expected ValueError for empty TED query.")
