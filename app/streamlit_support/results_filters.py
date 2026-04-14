from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any

from app.utils import countries as country_utils
from app.utils.time import ensure_utc, format_date, parse_ted_date, parse_ted_datetime


def display_value(value: Any) -> str:
    if value is None:
        return "N/A"
    raw = getattr(value, "value", value)
    if raw is None:
        return "N/A"
    return str(raw)


def normalize_country_filter_values(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [part.strip().upper() for part in value.split(",") if part.strip()]
    if isinstance(value, (list, tuple, set)):
        return [str(part).strip().upper() for part in value if str(part).strip()]
    return []


def score_out_of_ten(value: Any) -> float:
    try:
        return max(0.0, min(10.0, round(float(value or 0) / 10.0, 1)))
    except (TypeError, ValueError):
        return 0.0


def format_score_out_of_ten(value: Any, *, include_suffix: bool = False) -> str:
    score = score_out_of_ten(value)
    formatted = f"{score:.1f}"
    return f"{formatted}/10" if include_suffix else formatted


def country_display_label(value: str | None) -> str:
    helper = getattr(country_utils, "country_display_label", None)
    if callable(helper):
        return str(helper(value))

    normalized = country_utils.normalize_ted_country_code(value)
    if not normalized:
        return "Unknown"

    name_to_code = getattr(country_utils, "COUNTRY_NAME_TO_TED_COUNTRY", {})
    code_to_alpha2 = getattr(country_utils, "TED_COUNTRY_TO_ALPHA2", {})
    code_to_name = {code: name.title() for name, code in name_to_code.items()}
    name = code_to_name.get(normalized, normalized)
    alpha2 = code_to_alpha2.get(normalized)
    return f"{name} ({alpha2})" if alpha2 else name


def country_filter_options() -> list[tuple[str, str]]:
    helper = getattr(country_utils, "country_filter_options", None)
    if callable(helper):
        return list(helper())

    name_to_code = getattr(country_utils, "COUNTRY_NAME_TO_TED_COUNTRY", {})
    code_to_alpha2 = getattr(country_utils, "TED_COUNTRY_TO_ALPHA2", {})

    deduped_by_code: dict[str, str] = {}
    for raw_name, ted_code in name_to_code.items():
        deduped_by_code.setdefault(ted_code, raw_name.title())

    options: list[tuple[str, str]] = []
    for ted_code, name in sorted(deduped_by_code.items(), key=lambda item: item[1]):
        alpha2 = code_to_alpha2.get(ted_code, ted_code)
        options.append((f"{name} ({alpha2})", alpha2))
    return options


def coerce_notice_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return ensure_utc(value)
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time(), tzinfo=UTC)
    if isinstance(value, str):
        return parse_ted_datetime(value)
    return None


def coerce_notice_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return ensure_utc(value).date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return parse_ted_date(value)
    return None


def summarize_results_filters(filter_state: dict[str, Any]) -> list[str]:
    chips: list[str] = []
    if filter_state.get("relevant_only"):
        chips.append("Relevant to F2 Only")
    if filter_state.get("min_days_remaining") not in {None, 0}:
        chips.append(f"Deadline >= {filter_state['min_days_remaining']} days")
    selected_countries = normalize_country_filter_values(filter_state.get("countries", filter_state.get("country")))
    if selected_countries:
        country_labels = [country_display_label(country) for country in selected_countries]
        if len(country_labels) > 3:
            chips.append(f"Countries: {', '.join(country_labels[:3])} +{len(country_labels) - 3} more")
        else:
            chips.append(f"Countries: {', '.join(country_labels)}")
    if filter_state.get("fit_label"):
        chips.append(f"Fit: {filter_state['fit_label']}")
    if filter_state.get("priority_bucket"):
        chips.append(f"Priority: {filter_state['priority_bucket']}")
    if filter_state.get("confidence_indicator"):
        chips.append(f"Confidence: {filter_state['confidence_indicator']}")
    score_min = int(filter_state.get("score_min") or 0)
    if score_min > 0:
        chips.append(f"Score >= {format_score_out_of_ten(score_min, include_suffix=True)}")
    publication_date_from = filter_state.get("publication_date_from")
    publication_date_to = filter_state.get("publication_date_to")
    if publication_date_from or publication_date_to:
        chips.append(
            "Publication: "
            f"{format_date(publication_date_from) if publication_date_from else 'Any'}"
            " -> "
            f"{format_date(publication_date_to) if publication_date_to else 'Any'}"
        )
    deadline_from = filter_state.get("deadline_from")
    deadline_to = filter_state.get("deadline_to")
    if deadline_from or deadline_to:
        chips.append(
            "Deadline: "
            f"{format_date(deadline_from) if deadline_from else 'Any'}"
            " -> "
            f"{format_date(deadline_to) if deadline_to else 'Any'}"
        )
    if filter_state.get("deadline_window_days"):
        chips.append(f"Deadline <= {filter_state['deadline_window_days']} days")
    if filter_state.get("search"):
        chips.append(f"Search: {filter_state['search']}")
    if filter_state.get("hard_lock_only"):
        chips.append("Hard Locks Only")
    if filter_state.get("saved_only"):
        chips.append("Saved Only")
    if filter_state.get("include_dismissed"):
        chips.append("Including Dismissed")
    return chips


def build_results_metrics(notices: list[dict[str, Any]], *, total_matches: int) -> list[dict[str, str]]:
    if not notices:
        return [
            {
                "label": "Matching Results",
                "value": str(total_matches),
                "note": "No notices currently loaded for review.",
            }
        ]

    now = datetime.now(tz=UTC)
    today = now.date()
    avg_score = sum(int(notice.get("score") or 0) for notice in notices) / len(notices)
    high_fit = sum(1 for notice in notices if display_value(notice.get("priority_bucket")).upper() == "HIGH")
    good_fit = sum(1 for notice in notices if display_value(notice.get("priority_bucket")).upper() == "GOOD")
    expiring_soon = sum(
        1
        for notice in notices
        if (deadline := coerce_notice_datetime(notice.get("deadline"))) is not None
        and now <= deadline <= now + timedelta(days=7)
    )
    hard_locks = sum(1 for notice in notices if notice.get("hard_lock_detected"))
    recent_publications = sum(
        1
        for notice in notices
        if (publication_date := coerce_notice_date(notice.get("publication_date"))) is not None
        and 0 <= (today - publication_date).days <= 30
    )
    live_notices = sum(1 for notice in notices if not notice.get("is_demo_record"))
    highest_score = max(int(notice.get("score") or 0) for notice in notices)
    review_now = high_fit + good_fit

    return [
        {
            "label": "Matching Results",
            "value": str(total_matches),
            "note": f"{len(notices)} notices loaded into the current review surface.",
        },
        {
            "label": "Average Score",
            "value": format_score_out_of_ten(avg_score, include_suffix=True),
            "note": f"Highest current score: {format_score_out_of_ten(highest_score, include_suffix=True)}",
        },
        {
            "label": "Review Now",
            "value": str(review_now),
            "note": f"{expiring_soon} due within 7 days, {high_fit} marked HIGH priority.",
        },
        {
            "label": "Hard Locks",
            "value": str(hard_locks),
            "note": f"{live_notices} linked to live TED records, {recent_publications} published in the last 30 days.",
        },
    ]


def default_filter_state() -> dict[str, Any]:
    return {
        "countries": [],
        "search": None,
        "relevant_only": False,
        "fit_label": None,
        "priority_bucket": None,
        "confidence_indicator": None,
        "score_min": 0,
        "score_max": 100,
        "publication_date_from": None,
        "publication_date_to": None,
        "min_days_remaining": 0,
        "deadline_from": None,
        "deadline_to": None,
        "deadline_window_days": None,
        "hard_lock_only": False,
        "saved_only": False,
        "include_dismissed": False,
        "page_size": 20,
        "total_matches": 0,
    }
