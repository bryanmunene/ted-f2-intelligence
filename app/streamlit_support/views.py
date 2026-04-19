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


def render_recent_scan_cards(
    recent_scans: list[dict[str, Any]],
    *,
    ui_timezone: str,
    open_shortlist_view: Callable[[], None] | None = None,
    open_search_view: Callable[[], None] | None = None,
) -> None:
    for index, scan in enumerate(recent_scans):
        added = int(scan.get("total_notices_ingested") or 0)
        strong_matches = int(scan.get("total_high_fit") or 0)
        headline = "Your shortlist was updated" if added else "This search did not add anything new"
        helper_text = (
            f"{added} new items were added, including {strong_matches} strong options."
            if added
            else "Try another search if you want more options."
        )

        with st.container(border=True):
            st.markdown(
                f"""
                <div class="cb-note-title">{html.escape(headline)}</div>
                <div class="cb-note-copy">{html.escape(helper_text)} Updated {html.escape(format_datetime(scan['started_at'], ui_timezone))}</div>
                """,
                unsafe_allow_html=True,
            )

            action_cols = st.columns(2, gap="small")
            if action_cols[0].button(
                "Open shortlist",
                key=f"recent_scan_shortlist_{scan.get('id', index)}",
                type="secondary",
                width="stretch",
            ):
                if open_shortlist_view is not None:
                    open_shortlist_view()
                    st.rerun()
            if action_cols[1].button(
                "Search again",
                key=f"recent_scan_search_{scan.get('id', index)}",
                type="secondary",
                width="stretch",
            ):
                if open_search_view is not None:
                    open_search_view()
                    st.rerun()

            if scan["rate_limit_events"]:
                st.caption("The source was briefly busy during this search.")


def render_predictive_outlook(outlook: dict[str, Any]) -> None:
    if not outlook or not outlook.get("sample_size"):
        st.info("Helpful planning hints will appear once the app has seen enough matching notices.")
        return

    render_section_header(
        "",
        "Helpful hints",
        "A few simple patterns from past notices to help you plan your next search.",
    )

    next_window = outlook.get("next_expected_window") or {}
    budget_summary = outlook.get("budget_summary") or {}
    render_stat_cards(
        [
            {
                "label": "Past examples",
                "value": str(outlook.get("sample_size", 0)),
                "note": "Matching notices the app has learned from",
            },
            {
                "label": "Usual time left",
                "value": str(outlook.get("median_lead_days") or "Unknown"),
                "note": "Typical days between notice and deadline",
            },
            {
                "label": "Typical budget",
                "value": str(budget_summary.get("range_display") or "Unknown"),
                "note": str(budget_summary.get("note") or "Budget clues are still limited"),
            },
            {
                "label": "Next likely window",
                "value": str(next_window.get("label") or "Unknown"),
                "note": str(next_window.get("reason") or "More history is needed for a stronger signal"),
            },
        ]
    )
    st.info(str(outlook.get("forecast_summary") or "No planning summary is available yet."))

    with st.expander("Show deeper pattern details", expanded=False):
        st.caption(
            f"Based on notices from {format_date(outlook.get('publication_span_start'))} to {format_date(outlook.get('publication_span_end'))}"
        )
        top_left, top_right = st.columns(2, gap="medium")
        with top_left:
            render_ranked_signal_list(
                "Busy months",
                outlook.get("peak_release_months", []),
                empty_message="No month pattern is available yet.",
            )
            render_ranked_signal_list(
                "Common countries",
                outlook.get("top_countries", []),
                empty_message="No country pattern is visible yet.",
            )
            render_ranked_signal_list(
                "Common procedures",
                outlook.get("top_procedures", []),
                empty_message="No procedure pattern is available yet.",
            )
        with top_right:
            render_ranked_signal_list(
                "Busy weekdays",
                outlook.get("peak_release_weekdays", []),
                empty_message="No weekday pattern is available yet.",
            )
            render_ranked_signal_list(
                "Repeat buyers",
                outlook.get("top_buyers", []),
                empty_message="No buyer pattern is available yet.",
            )
            render_ranked_signal_list(
                "Common categories",
                outlook.get("top_cpv_families", []),
                empty_message="No category pattern is available yet.",
            )


def render_result_card(
    notice: dict[str, Any],
    *,
    card_index: int,
    ui_timezone: str,
    open_notice_detail: Callable[[str], None],
    resolve_official_notice_url: Callable[[dict[str, Any]], str | None],
) -> None:
    raw_fit_label = str(display_value(notice.get("fit_label")))
    fit_label = {
        "YES": "Strong fit",
        "CONDITIONAL": "Worth a look",
        "NO": "Lower fit",
    }.get(raw_fit_label.upper(), raw_fit_label)
    confidence = str(display_value(notice.get("confidence_indicator")))
    card_class = card_tone_class(notice)

    top_line_badges = [render_pill(fit_label, "fit")]
    if notice.get("hard_lock_detected"):
        top_line_badges.append(render_pill("Needs caution", "alert"))
        status_title = "Needs caution"
        status_note = "A key requirement may need checking first."
    elif notice.get("viable_timing"):
        top_line_badges.append(render_pill("Ready to review", "good"))
        status_title = "Ready to review"
        status_note = "The timing still looks workable."
    else:
        top_line_badges.append(render_pill("Timing check", "watch"))
        status_title = "Timing check"
        status_note = "Check the closing date before going deeper."

    buyer = notice.get("buyer") or "Unknown buyer"
    country = notice.get("buyer_country") or "N/A"
    source_label = notice_source_label(notice)
    publication = notice.get("publication_number") or "Unknown publication"
    deadline = format_datetime(notice.get("deadline"), ui_timezone)
    publication_date = format_date(notice.get("publication_date"))
    title = notice.get("title") or "Untitled notice"
    summary_text = truncate_text(
        notice.get("reasoning") or notice.get("summary") or "Open the summary to see the full tender details and evidence.",
        limit=180,
    )
    keyword_labels = notice_keyword_labels(notice, limit=2)
    keyword_chips = "".join(render_chip(label) for label in keyword_labels)
    if not keyword_chips:
        keyword_chips = render_chip("More details inside")

    quick_facts_html = "".join(
        [
            f'<div class="cb-result-quickfact"><div class="cb-result-quickfact-label">Buyer</div><div class="cb-result-quickfact-value">{html.escape(str(buyer))}</div></div>',
            f'<div class="cb-result-quickfact"><div class="cb-result-quickfact-label">Deadline</div><div class="cb-result-quickfact-value">{html.escape(str(deadline))}</div></div>',
            f'<div class="cb-result-quickfact"><div class="cb-result-quickfact-label">Confidence</div><div class="cb-result-quickfact-value">{html.escape(confidence)}</div></div>',
        ]
    )

    with st.container(border=True):
        st.markdown(
            f"""
            <div class="cb-result-shell cb-flow-surface {card_class}" style="--cb-enter-delay: {min(card_index * 45, 360)}ms;">
              <div class="cb-result-toprow">
                <div class="cb-result-score-block">
                  <div class="cb-result-score">{format_score_out_of_ten(notice['score'])}</div>
                  <div class="cb-result-score-label">Match</div>
                </div>
                <div class="cb-result-main">
                  <div class="cb-dossier-topline">{''.join(top_line_badges)}</div>
                  <div class="cb-result-title">{html.escape(title)}</div>
                  <div class="cb-result-meta">{html.escape(buyer)} • {html.escape(country)} • {html.escape(source_label)}</div>
                  <div class="cb-result-summary">{html.escape(summary_text)}</div>
                </div>
              </div>
              <div class="cb-result-quickfacts">{quick_facts_html}</div>
              <div class="cb-chip-row">{keyword_chips}</div>
              <div class="cb-result-helper"><span class="cb-result-helper-title">{html.escape(status_title)}:</span><span>{html.escape(status_note)}</span></div>
              <div class="cb-result-reference">Reference {html.escape(publication)} • Published {html.escape(publication_date)}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        action_cols = st.columns([1.1, 1], gap="small")
        if action_cols[0].button(
            "Open summary",
            key=f"review_notice_{card_index}_{notice['id']}",
            type="primary",
            width="stretch",
        ):
            open_notice_detail(notice["id"])
            st.rerun()

        official_url = resolve_official_notice_url(notice)
        if official_url:
            action_cols[1].link_button("Official notice", official_url, width="stretch")
        elif notice.get("is_demo_record"):
            action_cols[1].caption("No live source link")
        else:
            action_cols[1].caption("No official source link")


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
