from __future__ import annotations

from datetime import UTC, datetime, timedelta

from streamlit_app import (
    _build_results_metrics,
    _default_filter_state,
    _default_live_scan_max_pages,
    settings,
)


def test_results_metrics_handle_naive_and_string_dates() -> None:
    now = datetime.now(tz=UTC)
    notices = [
        {
            "score": 82,
            "priority_bucket": "HIGH",
            "fit_label": "YES",
            "hard_lock_detected": False,
            "is_demo_record": False,
            "deadline": (now + timedelta(days=3)).replace(tzinfo=None),
            "publication_date": now.date().isoformat(),
        },
        {
            "score": 61,
            "priority_bucket": "GOOD",
            "fit_label": "CONDITIONAL",
            "hard_lock_detected": True,
            "is_demo_record": False,
            "deadline": (now + timedelta(days=10)).isoformat(),
            "publication_date": now.date().isoformat(),
        },
    ]

    cards = _build_results_metrics(notices, total_matches=2)
    by_label = {card["label"]: card for card in cards}

    assert by_label["Matching Results"]["value"] == "2"
    assert by_label["Review Now"]["value"] == "2"
    assert "1 due within 7 days" in by_label["Review Now"]["note"]
    assert by_label["Hard Locks"]["value"] == "1"
    assert "2 published in the last 30 days" in by_label["Hard Locks"]["note"]


def test_streamlit_default_results_filter_hides_expired_tenders() -> None:
    default_state = _default_filter_state()

    assert default_state["min_days_remaining"] == 0


def test_overall_live_scan_fetches_deeper_than_country_scan() -> None:
    assert _default_live_scan_max_pages("DNK") == 1
    assert _default_live_scan_max_pages(" DK ") == 1
    assert _default_live_scan_max_pages(None) == min(3, settings.ted_max_pages_per_scan)
