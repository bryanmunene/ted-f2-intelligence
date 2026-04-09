from __future__ import annotations

from datetime import UTC, datetime, timedelta

from streamlit_app import _build_results_metrics


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
