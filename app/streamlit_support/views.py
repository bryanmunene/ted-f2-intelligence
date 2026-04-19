from __future__ import annotations

import html
from collections.abc import Callable
from typing import Any

import streamlit as st

from app.streamlit_support.rendering import (
    render_chip,
    render_pill,
    render_ranked_signal_list,
    render_section_header,
    render_stat_cards,
    truncate_text,
)
from app.streamlit_support.results_filters import display_value, format_score_out_of_ten
from app.utils.time import format_date, format_datetime


def render_profile_cards(
    *,
    profiles: list[Any],
    positive_groups: dict[str, Any],
) -> None:
    if not profiles:
        return

    per_row = 3
    for start in range(0, len(profiles), per_row):
        row_profiles = profiles[start : start + per_row]
        columns = st.columns(len(row_profiles), gap="medium")
        for column, profile in zip(columns, row_profiles):
            with column:
                with st.container(border=True):
                    st.markdown(
                        f"""
                        <div class="cb-note-title">{html.escape(profile.name)}</div>
                        <div class="cb-note-copy">{html.escape(profile.description)}</div>
                        """,
                        unsafe_allow_html=True,
                    )
                    category_labels = [
                        positive_groups[group_id].name
                        for group_id in profile.keyword_group_ids
                        if group_id in positive_groups
                    ]
                    if category_labels:
                        st.markdown(
                            "<div class='cb-chip-row'>"
                            + "".join(render_chip(label) for label in category_labels)
                            + "</div>",
                            unsafe_allow_html=True,
                        )
                    elif profile.search_terms:
                        st.markdown(
                            "<div class='cb-chip-row'>"
                            + "".join(render_chip(term) for term in profile.search_terms)
                            + "</div>",
                            unsafe_allow_html=True,
                        )


def render_recent_scan_cards(recent_scans: list[dict[str, Any]], *, ui_timezone: str) -> None:
    for scan in recent_scans:
        with st.container(border=True):
            st.markdown(
                f"""
                <div class="cb-note-title">{html.escape(str(scan['status']).replace('_', ' ').title())}</div>
                <div class="cb-note-copy">Started {html.escape(format_datetime(scan['started_at'], ui_timezone))}</div>
                """,
                unsafe_allow_html=True,
            )
            detail_cols = st.columns(3, gap="small")
            detail_cols[0].metric("Added", scan["total_notices_ingested"])
            detail_cols[1].metric("Strong matches", scan["total_high_fit"])
            detail_cols[2].metric("Searches", scan["request_count"])
            if scan["rate_limit_events"]:
                st.caption(f"Rate-limit events: {scan['rate_limit_events']}")


def render_predictive_outlook(outlook: dict[str, Any]) -> None:
    if not outlook or not outlook.get("sample_size"):
        st.info("Predictive outlook will appear once the app has enough relevant TED history to learn from.")
        return

    render_section_header(
        "",
        "Predictive Outlook",
        "Historical patterns from relevant TED notices to help anticipate where and when similar opportunities appear.",
    )

    next_window = outlook.get("next_expected_window") or {}
    budget_summary = outlook.get("budget_summary") or {}
    render_stat_cards(
        [
            {
                "label": "Relevant History",
                "value": str(outlook.get("sample_size", 0)),
                "note": f"{outlook.get('confidence', 'Low')} confidence sample",
            },
            {
                "label": "Typical Lead Time",
                "value": str(outlook.get("median_lead_days") or "Unknown"),
                "note": "Median days from publication to deadline",
            },
            {
                "label": "Budget Range",
                "value": str(budget_summary.get("range_display") or "Unknown"),
                "note": str(budget_summary.get("note") or "No budget pattern available"),
            },
            {
                "label": "Next Likely Window",
                "value": str(next_window.get("label") or "Unknown"),
                "note": str(next_window.get("reason") or "Not enough month history yet"),
            },
        ]
    )
    st.caption(
        f"Historical span: {format_date(outlook.get('publication_span_start'))} to {format_date(outlook.get('publication_span_end'))} | "
        f"Average score: {outlook.get('average_score_ten', 0.0):.1f}/10"
    )
    st.info(str(outlook.get("forecast_summary") or "No forecast summary available yet."))

    top_left, top_right = st.columns(2, gap="medium")
    with top_left:
        render_ranked_signal_list(
            "Peak Release Months",
            outlook.get("peak_release_months", []),
            empty_message="No publication-month pattern available yet.",
        )
        render_ranked_signal_list(
            "Top Countries",
            outlook.get("top_countries", []),
            empty_message="No country concentration visible yet.",
        )
        render_ranked_signal_list(
            "Common Procedures",
            outlook.get("top_procedures", []),
            empty_message="No procedure pattern available yet.",
        )
    with top_right:
        render_ranked_signal_list(
            "Peak Release Weekdays",
            outlook.get("peak_release_weekdays", []),
            empty_message="No weekday publication pattern available yet.",
        )
        render_ranked_signal_list(
            "Repeat Buyers",
            outlook.get("top_buyers", []),
            empty_message="No repeat-buyer pattern available yet.",
        )
        render_ranked_signal_list(
            "Common CPV Families",
            outlook.get("top_cpv_families", []),
            empty_message="No CPV-family pattern available yet.",
        )


def render_result_card(
    notice: dict[str, Any],
    *,
    card_index: int,
    ui_timezone: str,
    open_notice_detail: Callable[[str], None],
    resolve_official_notice_url: Callable[[dict[str, Any]], str | None],
) -> None:
    fit_label = display_value(notice.get("fit_label"))
    priority_bucket = display_value(notice.get("priority_bucket"))
    confidence = display_value(notice.get("confidence_indicator"))

    card_class = card_tone_class(notice)
    top_line_badges = [
        render_pill(notice_source_label(notice), "source"),
        render_pill(fit_label, "fit"),
        render_pill(priority_bucket, "priority"),
    ]
    if notice.get("hard_lock_detected"):
        top_line_badges.append(render_pill("Hard lock", "alert"))
    elif notice.get("viable_timing"):
        top_line_badges.append(render_pill("Timing viable", "good"))
    else:
        top_line_badges.append(render_pill("Timing review", "watch"))

    buyer = notice.get("buyer") or "Unknown buyer"
    country = notice.get("buyer_country") or "N/A"
    publication = notice.get("publication_number") or "Unknown publication"
    deadline = format_datetime(notice.get("deadline"), ui_timezone)
    publication_date = format_date(notice.get("publication_date"))
    title = notice.get("title") or "Untitled notice"
    summary_text = truncate_text(
        notice.get("reasoning") or notice.get("summary") or "No summary available.",
        limit=240,
    )
    keyword_chips = "".join(render_chip(label) for label in notice_keyword_labels(notice))
    if not keyword_chips:
        keyword_chips = render_chip("No keyword evidence captured yet")
    meta_parts = [
        publication,
        buyer,
        country,
        f"Published {publication_date}",
        f"Deadline {deadline}",
        f"Confidence {confidence}",
    ]

    st.markdown(
        f"""
                <div class="cb-result-card cb-flow-surface {card_class}" style="--cb-enter-delay: {min(card_index * 45, 360)}ms;">
          <div class="cb-result-head">
            <div class="cb-result-score-block">
              <div class="cb-result-score">{format_score_out_of_ten(notice['score'])}</div>
              <div class="cb-result-score-label">Score / 10</div>
            </div>
            <div class="cb-result-main">
              <div class="cb-dossier-topline">
              {''.join(top_line_badges)}
              </div>
              <div class="cb-result-title">{html.escape(title)}</div>
              <div class="cb-result-meta">{html.escape(' | '.join(meta_parts))}</div>
              <div class="cb-result-summary">{html.escape(summary_text)}</div>
              <div class="cb-chip-row">{keyword_chips}</div>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    action_cols = st.columns([1, 1], gap="small")
    official_url = resolve_official_notice_url(notice)
    if official_url:
        action_cols[0].link_button("Official notice", official_url, width="stretch")
    elif notice.get("is_demo_record"):
        action_cols[0].caption("No live TED link")
    else:
        action_cols[0].caption("No official TED URL")

    if action_cols[1].button(
        "Open summary",
        key=f"review_notice_{card_index}_{notice['id']}",
        type="primary",
        width="stretch",
    ):
        open_notice_detail(notice["id"])
        st.rerun()


def notice_source_label(item: dict[str, Any]) -> str:
    return "DEMO" if item.get("is_demo_record") else "LIVE"


def notice_keyword_labels(notice: dict[str, Any], *, limit: int = 4) -> list[str]:
    labels: list[str] = []
    for hit in notice.get("keyword_hits", [])[:limit]:
        term = hit.get("term")
        scope = hit.get("scope")
        if term and scope:
            labels.append(f"{term} [{scope}]")
        elif term:
            labels.append(str(term))
    return labels


def card_tone_class(notice: dict[str, Any]) -> str:
    priority = display_value(notice.get("priority_bucket")).upper()
    fit = display_value(notice.get("fit_label")).upper()
    if fit == "CONDITIONAL" or notice.get("hard_lock_detected"):
        return "cb-dossier-conditional"
    if priority == "HIGH":
        return "cb-dossier-high"
    if priority == "GOOD":
        return "cb-dossier-good"
    if priority == "WATCHLIST":
        return "cb-dossier-watch"
    if priority == "IGNORE":
        return "cb-dossier-ignore"
    return ""
