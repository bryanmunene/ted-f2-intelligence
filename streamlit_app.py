from __future__ import annotations

import html
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import streamlit as st

from app.api.presenters import notice_to_detail_dict, notice_to_summary_dict, scan_run_to_dict
from app.api.schemas import HistoricalBackfillRequestPayload, ScanRequestPayload
from app.auth import ActorContext
from app.config import get_settings, load_keyword_pack, load_search_profiles
from app.database import get_session_factory
from app.repositories.notices import NoticeListFilters, NoticeRepository
from app.repositories.scan_runs import ScanRunRepository
from app.services.demo_bootstrap import ensure_streamlit_storage
from app.services.historical_backfill import HistoricalBackfillService
from app.services.predictive_outlook import PredictiveOutlookService
from app.services.rescoring import rescore_outdated_notices
from app.services.scan_service import ScanService
from app.services.ted_client import TedApiClient
from app.services.ted_documents import DocumentSpec, TedDocumentService
from app.services.tender_checklist import TenderChecklistService
from app.streamlit_support import (
    build_results_metrics as _build_results_metrics,
)
from app.streamlit_support import (
    country_display_label as _country_display_label,
)
from app.streamlit_support import (
    country_filter_options as _country_filter_options,
)
from app.streamlit_support import (
    default_filter_state as _default_filter_state,
)
from app.streamlit_support import (
    display_value as _display_value,
)
from app.streamlit_support import (
    format_score_out_of_ten as _format_score_out_of_ten,
)
from app.streamlit_support import (
    normalize_country_filter_values as _normalize_country_filter_values,
)
from app.streamlit_support import (
    render_checklist_cross_reference as _render_checklist_cross_reference_impl,
)
from app.streamlit_support import (
    render_chip as _render_chip,
)
from app.streamlit_support import (
    render_download_controls as _render_download_controls_impl,
)
from app.streamlit_support import (
    render_keyword_evidence_module as _render_keyword_evidence_module_impl,
)
from app.streamlit_support import (
    render_notice_detail_layout as _render_notice_detail_layout_impl,
)
from app.streamlit_support import (
    render_predictive_outlook as _render_predictive_outlook_impl,
)
from app.streamlit_support import (
    render_profile_cards as _render_profile_cards_impl,
)
from app.streamlit_support import (
    render_recent_scan_cards as _render_recent_scan_cards_impl,
)
from app.streamlit_support import (
    render_result_card as _render_result_card_impl,
)
from app.streamlit_support import (
    render_section_header as _render_section_header,
)
from app.streamlit_support import (
    render_stat_cards as _render_stat_cards,
)
from app.streamlit_support import (
    summarize_results_filters as _summarize_results_filters,
)
from app.utils.time import format_datetime

settings = get_settings()


@st.cache_resource(show_spinner=False)
def initialize_streamlit_storage() -> dict[str, int]:
    return ensure_streamlit_storage(purge_demo=True)


@st.cache_resource(show_spinner=False)
def get_search_profiles_registry():
    return load_search_profiles(settings.resolved_search_profiles_path)


@st.cache_resource(show_spinner=False)
def get_keyword_pack_resource():
    return load_keyword_pack(settings.resolved_keyword_pack_path)


@st.cache_resource(show_spinner=False)
def get_ted_client_resource() -> TedApiClient:
    return TedApiClient(settings=settings)


initialize_streamlit_storage()

st.set_page_config(
    page_title="cBrain TED F2 Intelligence",
    page_icon="📘",
    layout="wide",
    initial_sidebar_state="expanded",
)


def _apply_theme() -> None:
    css_path = Path(__file__).parent / "app" / "static" / "css" / "streamlit_theme.css"
    css = _load_streamlit_theme_css(int(css_path.stat().st_mtime_ns))
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


@st.cache_data(show_spinner=False)
def _load_streamlit_theme_css(version: int) -> str:
    del version
    css_path = Path(__file__).parent / "app" / "static" / "css" / "streamlit_theme.css"
    return css_path.read_text(encoding="utf-8")


@st.cache_data(ttl=60, show_spinner=False)
def load_dashboard_payload() -> dict[str, Any]:
    session = get_session_factory()()
    try:
        rescore_outdated_notices(session)
        notice_repo = NoticeRepository(session)
        scan_repo = ScanRunRepository(session)
        predictive_outlook = PredictiveOutlookService().build(notice_repo.predictive_history(limit=500))
        return {
            "metrics": notice_repo.dashboard_metrics(),
            "recent_scans": [scan_run_to_dict(scan) for scan in scan_repo.recent(limit=6)],
            "top_notices": [
                notice_to_summary_dict(notice)
                for notice in notice_repo.list(NoticeListFilters(), page=1, page_size=8)[0]
            ],
            "predictive_outlook": predictive_outlook,
        }
    finally:
        session.close()


@st.cache_data(ttl=60, show_spinner=False)
def load_filtered_notices(
    *,
    country: str | list[str] | None,
    fit_label: str | None,
    priority_bucket: str | None,
    min_score: int | None,
    max_score: int | None,
    confidence_indicator: str | None,
    relevant_only: bool,
    min_days_remaining: int | None,
    hard_lock_only: bool,
    publication_date_from: date | None,
    publication_date_to: date | None,
    deadline_from: date | None,
    deadline_to: date | None,
    deadline_window_days: int | None,
    include_dismissed: bool,
    saved_only: bool,
    search: str | None,
    page_size: int,
) -> dict[str, Any]:
    session = get_session_factory()()
    try:
        rescore_outdated_notices(session)
        filters = NoticeListFilters(
            country=country,
            fit_label=fit_label,
            priority_bucket=priority_bucket,
            min_score=min_score,
            max_score=max_score,
            confidence_indicator=confidence_indicator,
            relevant_only=relevant_only,
            min_days_remaining=min_days_remaining,
            hard_lock_only=hard_lock_only,
            publication_date_from=publication_date_from,
            publication_date_to=publication_date_to,
            deadline_from=deadline_from,
            deadline_to=deadline_to,
            deadline_window_days=deadline_window_days,
            include_dismissed=include_dismissed,
            saved_only=saved_only,
            search=search,
        )
        notices, total = NoticeRepository(session).list(filters, page=1, page_size=page_size)
        return {
            "items": [notice_to_summary_dict(notice) for notice in notices],
            "total": total,
        }
    finally:
        session.close()


@st.cache_data(ttl=60, show_spinner=False)
def load_notice_detail(notice_id: str) -> dict[str, Any] | None:
    session = get_session_factory()()
    try:
        rescore_outdated_notices(session)
        notice = NoticeRepository(session).get_by_id(notice_id)
        return notice_to_detail_dict(notice) if notice else None
    finally:
        session.close()


@st.cache_data(ttl=900, show_spinner=False)
def fetch_official_document(url: str, filename: str, media_type: str) -> tuple[bytes, str, str]:
    service = TedDocumentService(settings=settings)
    payload, resolved_media_type = service.fetch_download(
        DocumentSpec(
            format_name=filename.rsplit(".", 1)[-1],
            url=url,
            filename=filename,
            media_type=media_type,
        )
    )
    return payload, filename, resolved_media_type


def _notice_option_label(item: dict[str, Any]) -> str:
    return f"{item['score']:>3} | {item['publication_number']} | {item['title']}"


def _notice_source_label(item: dict[str, Any]) -> str:
    return "DEMO" if item.get("is_demo_record") else "LIVE"


def _card_tone_class(notice: dict[str, Any]) -> str:
    priority = _display_value(notice.get("priority_bucket")).upper()
    fit = _display_value(notice.get("fit_label")).upper()
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


def _render_profile_cards() -> None:
    profiles = get_search_profiles_registry().profiles
    keyword_pack = get_keyword_pack_resource()
    _render_profile_cards_impl(
        profiles=profiles,
        positive_groups=keyword_pack.positive_group_map(),
    )


def _render_recent_scan_cards(recent_scans: list[dict[str, Any]]) -> None:
    _render_recent_scan_cards_impl(recent_scans, ui_timezone=settings.ui_timezone)


def _render_predictive_outlook(outlook: dict[str, Any]) -> None:
    _render_predictive_outlook_impl(outlook)


def _normalize_date_range(start: date | None, end: date | None) -> tuple[date | None, date | None]:
    if start is not None and end is not None and start > end:
        return end, start
    return start, end


def _render_sidebar_brand() -> None:
    st.sidebar.markdown(
        """
        <div class="cb-sidebar-brand">
          <div class="cb-sidebar-line">cBrain</div>
          <div class="cb-sidebar-mark">F2</div>
          <div class="cb-sidebar-title">TED F2 Intelligence</div>
          <div class="cb-sidebar-subtitle">Official TED review workspace for F2 teams.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _ensure_live_scan_state(profile_names: list[str]) -> None:
    default_profile = profile_names[0] if profile_names else ""
    defaults: dict[str, Any] = {
        "live_scan_profile_name": default_profile,
        "live_scan_country": "",
        "live_scan_cpv": "",
        "live_scan_keyword_override": "",
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)

    if profile_names and st.session_state.get("live_scan_profile_name") not in profile_names:
        st.session_state["live_scan_profile_name"] = default_profile


def _ensure_backfill_state(profile_names: list[str]) -> None:
    default_profile = profile_names[0] if profile_names else ""
    defaults: dict[str, Any] = {
        "backfill_profile_name": default_profile,
        "backfill_country": "",
        "backfill_cpv": "",
        "backfill_keyword_override": "",
        "backfill_date_from": date(datetime.now(tz=UTC).year - 1, 1, 1),
        "backfill_date_to": datetime.now(tz=UTC).date(),
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)

    if profile_names and st.session_state.get("backfill_profile_name") not in profile_names:
        st.session_state["backfill_profile_name"] = default_profile


def _load_notices_for_filter_state(filter_state: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    countries = _normalize_country_filter_values(filter_state.get("countries", filter_state.get("country")))
    payload = load_filtered_notices(
        country=countries or None,
        fit_label=filter_state.get("fit_label"),
        priority_bucket=filter_state.get("priority_bucket"),
        min_score=filter_state.get("score_min") if (filter_state.get("score_min") or 0) > 0 else None,
        max_score=filter_state.get("score_max") if (filter_state.get("score_max") or 100) < 100 else None,
        confidence_indicator=filter_state.get("confidence_indicator"),
        relevant_only=bool(filter_state.get("relevant_only")),
        min_days_remaining=filter_state.get("min_days_remaining"),
        hard_lock_only=bool(filter_state.get("hard_lock_only")),
        publication_date_from=filter_state.get("publication_date_from"),
        publication_date_to=filter_state.get("publication_date_to"),
        deadline_from=filter_state.get("deadline_from"),
        deadline_to=filter_state.get("deadline_to"),
        deadline_window_days=filter_state.get("deadline_window_days"),
        include_dismissed=bool(filter_state.get("include_dismissed")),
        saved_only=bool(filter_state.get("saved_only")),
        search=filter_state.get("search"),
        page_size=int(filter_state.get("page_size") or 20),
    )
    updated_state = dict(filter_state)
    updated_state["total_matches"] = int(payload["total"])
    return payload["items"], updated_state


def _render_result_card(notice: dict[str, Any], *, card_index: int) -> None:
    _render_result_card_impl(
        notice,
        card_index=card_index,
        ui_timezone=settings.ui_timezone,
        open_notice_detail=_open_notice_detail,
        resolve_official_notice_url=_resolve_official_notice_url,
    )


def _seed_selected_notice(notices: list[dict[str, Any]]) -> None:
    if not notices:
        st.session_state.pop("selected_notice_id", None)
        return
    selected = st.session_state.get("selected_notice_id")
    if selected not in {item["id"] for item in notices}:
        st.session_state["selected_notice_id"] = notices[0]["id"]


def _go_to_view(view_name: str) -> None:
    st.session_state["active_view"] = view_name


def _open_notice_detail(notice_id: str) -> None:
    st.session_state["selected_notice_id"] = notice_id
    st.session_state["detail_return_view"] = st.session_state.get("active_view", "Results")
    _go_to_view("Notice Detail")


def _resolve_official_notice_url(notice: dict[str, Any]) -> str | None:
    if notice.get("is_demo_record"):
        return None
    publication_number = notice.get("publication_number")
    if publication_number:
        return f"https://ted.europa.eu/en/notice/-/detail/{publication_number}"
    return notice.get("source_url") or notice.get("html_url") or notice.get("pdf_url")


def _default_live_scan_max_pages(country: str | None) -> int:
    normalized_country = (country or "").strip()
    if normalized_country:
        return 1
    return min(3, settings.ted_max_pages_per_scan)


def run_live_scan(
    *,
    profile_name: str,
    country: str | None,
    cpv: str | None,
    keyword_override: str | None,
) -> dict[str, Any]:
    session = get_session_factory()()
    try:
        service = ScanService(
            session=session,
            settings=settings,
            ted_client=get_ted_client_resource(),
            keyword_pack=get_keyword_pack_resource(),
            search_profiles=get_search_profiles_registry(),
            actor=ActorContext(
                email=settings.default_user_email,
                display_name=settings.default_user_name,
                auth_provider="streamlit-shell",
            ),
        )
        payload = ScanRequestPayload(
            profile_name=profile_name,
            country=country or None,
            cpv=cpv or None,
            keyword_override=keyword_override or None,
            date_from=None,
            date_to=None,
            include_conditional=True,
            exclude_old=True,
            include_soft_locks=True,
            page_size=settings.ted_default_page_size,
            max_pages=_default_live_scan_max_pages(country),
        )
        outcome = service.run_manual_scan(payload)
        session.commit()
        return {
            "scan_run_id": outcome.scan_run_id,
            "total_notices_returned": outcome.total_notices_returned,
            "total_notices_ingested": outcome.total_notices_ingested,
            "total_after_timing_filters": outcome.total_after_timing_filters,
            "total_high_fit": outcome.total_high_fit,
            "total_conditional": outcome.total_conditional,
            "total_ignored": outcome.total_ignored,
            "request_count": outcome.request_count,
            "rate_limit_events": outcome.rate_limit_events,
        }
    finally:
        session.close()


def run_historical_backfill(
    *,
    profile_name: str,
    date_from: date,
    date_to: date,
    country: str | None,
    cpv: str | None,
    keyword_override: str | None,
) -> dict[str, Any]:
    session = get_session_factory()()
    try:
        scan_service = ScanService(
            session=session,
            settings=settings,
            ted_client=get_ted_client_resource(),
            keyword_pack=get_keyword_pack_resource(),
            search_profiles=get_search_profiles_registry(),
            actor=ActorContext(
                email=settings.default_user_email,
                display_name=settings.default_user_name,
                auth_provider="streamlit-shell",
            ),
        )
        payload = HistoricalBackfillRequestPayload(
            profile_name=profile_name,
            date_from=date_from,
            date_to=date_to,
            country=country or None,
            cpv=cpv or None,
            keyword_override=keyword_override or None,
        )
        outcome = HistoricalBackfillService(scan_service=scan_service, settings=settings).run(payload)
        session.commit()
        return {
            "date_from": outcome.date_from,
            "date_to": outcome.date_to,
            "window_months": outcome.window_months,
            "total_windows": outcome.total_windows,
            "completed_windows": outcome.completed_windows,
            "total_notices_returned": outcome.total_notices_returned,
            "total_notices_ingested": outcome.total_notices_ingested,
            "total_after_timing_filters": outcome.total_after_timing_filters,
            "total_high_fit": outcome.total_high_fit,
            "total_conditional": outcome.total_conditional,
            "total_ignored": outcome.total_ignored,
            "request_count": outcome.request_count,
            "rate_limit_events": outcome.rate_limit_events,
            "windows": [
                {
                    "date_from": window.date_from,
                    "date_to": window.date_to,
                    "scan_run_id": window.scan_run_id,
                    "total_notices_returned": window.total_notices_returned,
                    "total_notices_ingested": window.total_notices_ingested,
                }
                for window in outcome.windows
            ],
        }
    finally:
        session.close()


def _render_banner(current_view: str) -> None:
    storage_state = initialize_streamlit_storage()
    purged_demo_notices = storage_state.get("purged_demo_notices", 0)
    view_copy = {
        "Dashboard": {
            "kicker": "Overview",
            "title": "Dashboard",
            "copy": "A clear snapshot of the most relevant TED opportunities for your team.",
        },
        "Live Scan": {
            "kicker": "Explore Opportunities",
            "title": "Live TED Scan",
            "copy": "Find fresh public tenders and send the best matches into your review queue.",
        },
        "Results": {
            "kicker": "Review Queue",
            "title": "Results",
            "copy": "Browse the most relevant opportunities with simple, guided filtering.",
        },
        "Notice Detail": {
            "kicker": "Tender Summary",
            "title": "Notice Detail",
            "copy": "Review one opportunity with the key facts, evidence, and notes in one place.",
        },
    }.get(
        current_view,
        {
            "kicker": "cBrain Signal Studio",
            "title": "TED Opportunity Intelligence",
            "copy": "Official TED-only tender intelligence for F2 teams.",
        },
    )
    st.markdown(
        f"""
        <section class="cb-shell-hero">
          <div class="cb-shell-grid">
            <div>
              <div class="cb-shell-kicker">{html.escape(view_copy["kicker"])}</div>
              <h1 class="cb-shell-title">{html.escape(view_copy["title"])}</h1>
              <p class="cb-shell-copy">{html.escape(view_copy["copy"])}</p>
            </div>
          </div>
        </section>
        """,
        unsafe_allow_html=True,
    )
    if purged_demo_notices:
        st.info(f"Removed {purged_demo_notices} local sample records from storage.")


def _render_live_scan() -> None:
    profiles = get_search_profiles_registry()
    _ensure_live_scan_state(profiles.names)

    _render_section_header(
        "",
        "Live TED Scan",
        "Run an official TED search to refresh the review queue.",
    )
    st.info(
        "Quick start: choose a search profile, optionally narrow by country or CPV, then run the scan. "
        "The results view will rank the strongest live opportunities first."
    )

    with st.form("live_ted_scan_form"):
        profile_name = st.selectbox(
            "Search Profile",
            options=profiles.names,
            key="live_scan_profile_name",
        )
        selected_profile = next((profile for profile in profiles.profiles if profile.name == profile_name), None)
        if selected_profile:
            st.caption(selected_profile.description)

        primary_left, primary_right = st.columns(2, gap="medium")
        country_options = _country_filter_options()
        country_labels = ["Any"] + [label for label, _ in country_options]
        country_value_by_label = {"Any": ""}
        country_value_by_label.update({label: code for label, code in country_options})
        current_country_value = str(st.session_state.get("live_scan_country") or "")
        current_country_label = next((label for label, code in country_options if code == current_country_value), "Any")
        with primary_left:
            selected_country_label = st.selectbox(
                "Buyer Country",
                options=country_labels,
                index=country_labels.index(current_country_label),
            )
            country = country_value_by_label[selected_country_label]
            st.session_state["live_scan_country"] = country
            cpv = st.text_input("CPV Code", key="live_scan_cpv", placeholder="72260000")
        with primary_right:
            keyword_override = st.text_input(
                "Keyword Override",
                key="live_scan_keyword_override",
                placeholder="case management, workflow automation",
            )
        if country:
            st.caption(f"Country filter: {_country_display_label(country)}")
            st.caption("Country scans use a focused TED pull.")
        else:
            st.caption("Overall scans use a deeper TED pull across multiple result pages.")
        st.caption("Scan uses the default review settings.")

        submitted = st.form_submit_button("Run live TED scan", type="primary", width="stretch")

    if not submitted:
        return

    with st.spinner("Querying TED public API and scoring notices..."):
        try:
            outcome = run_live_scan(
                profile_name=profile_name,
                country=country.strip() or None,
                cpv=cpv.strip() or None,
                keyword_override=keyword_override.strip() or None,
            )
        except Exception as exc:
            st.error(f"Live TED scan failed: {exc}")
            return

    st.cache_data.clear()
    st.success(
        f"Live TED scan completed. Ingested {outcome['total_notices_ingested']} notices from "
        f"{outcome['request_count']} TED API requests."
    )
    outcome_cols = st.columns(4)
    outcome_cols[0].metric("Returned", outcome["total_notices_returned"])
    outcome_cols[1].metric("Ingested", outcome["total_notices_ingested"])
    outcome_cols[2].metric("High Fit", outcome["total_high_fit"])
    outcome_cols[3].metric("Conditional", outcome["total_conditional"])

    st.session_state["results_return_view"] = "Live Scan"
    st.session_state["active_view"] = "Results"
    st.rerun()


def _render_historical_backfill() -> None:
    profiles = get_search_profiles_registry()
    _ensure_backfill_state(profiles.names)

    _render_section_header(
        "",
        "Historical Backfill",
        "Import older TED notices to strengthen pattern learning without changing the live review workflow.",
    )
    st.info(
        "Use backfill when you want extra market context or pattern learning. The active review queue still stays focused on current tenders."
    )
    st.caption(
        "This backfill runs official TED Search API windows, scores the notices with the existing F2 logic, "
        "and feeds the predictive outlook. Expired notices remain out of the active queue by default."
    )

    with st.form("historical_backfill_form"):
        profile_name = st.selectbox(
            "Search Profile",
            options=profiles.names,
            key="backfill_profile_name",
        )
        selected_profile = next((profile for profile in profiles.profiles if profile.name == profile_name), None)
        if selected_profile:
            st.caption(selected_profile.description)

        date_cols = st.columns(2, gap="medium")
        with date_cols[0]:
            date_from = st.date_input("From", key="backfill_date_from")
        with date_cols[1]:
            date_to = st.date_input("To", key="backfill_date_to")

        field_cols = st.columns(2, gap="medium")
        country_options = _country_filter_options()
        country_labels = ["Any"] + [label for label, _ in country_options]
        country_value_by_label = {"Any": ""}
        country_value_by_label.update({label: code for label, code in country_options})
        current_country_value = str(st.session_state.get("backfill_country") or "")
        current_country_label = next((label for label, code in country_options if code == current_country_value), "Any")
        with field_cols[0]:
            selected_country_label = st.selectbox(
                "Buyer Country",
                options=country_labels,
                index=country_labels.index(current_country_label),
            )
            country = country_value_by_label[selected_country_label]
            st.session_state["backfill_country"] = country
            cpv = st.text_input("CPV Code", key="backfill_cpv", placeholder="72260000")
        with field_cols[1]:
            keyword_override = st.text_input(
                "Keyword Override",
                key="backfill_keyword_override",
                placeholder="case management, records management",
            )

        st.caption("Backfill runs in monthly windows with a deeper historical pull to stay polite to TED and preserve traceability.")
        submitted = st.form_submit_button("Run historical TED backfill", type="primary", width="stretch")

    if not submitted:
        return

    if date_from > date_to:
        st.error("The start date must be on or before the end date.")
        return

    with st.spinner("Backfilling historical TED notices and updating predictive outlook..."):
        try:
            outcome = run_historical_backfill(
                profile_name=profile_name,
                date_from=date_from,
                date_to=date_to,
                country=country.strip() or None,
                cpv=cpv.strip() or None,
                keyword_override=keyword_override.strip() or None,
            )
        except Exception as exc:
            st.error(f"Historical TED backfill failed: {exc}")
            return

    st.cache_data.clear()
    st.success(
        f"Historical backfill completed across {outcome['completed_windows']} windows. "
        f"Ingested {outcome['total_notices_ingested']} notices from {outcome['request_count']} TED API requests."
    )
    outcome_cols = st.columns(4)
    outcome_cols[0].metric("Windows", outcome["completed_windows"])
    outcome_cols[1].metric("Ingested", outcome["total_notices_ingested"])
    outcome_cols[2].metric("High Fit", outcome["total_high_fit"])
    outcome_cols[3].metric("Conditional", outcome["total_conditional"])

    with st.expander("Backfill windows", expanded=False):
        for window in outcome["windows"]:
            st.write(
                f"{window['date_from']} to {window['date_to']} | "
                f"Returned {window['total_notices_returned']} | Ingested {window['total_notices_ingested']}"
            )

    action_cols = st.columns(2, gap="medium")
    if action_cols[0].button("Open Dashboard", key="backfill_open_dashboard", type="secondary", width="stretch"):
        _go_to_view("Dashboard")
        st.rerun()
    if action_cols[1].button("Open Results", key="backfill_open_results", type="primary", width="stretch"):
        st.session_state["results_return_view"] = "Historical Backfill"
        _go_to_view("Results")
        st.rerun()


def _render_dashboard() -> None:
    payload = load_dashboard_payload()
    metrics = payload["metrics"]
    recent_scans = payload["recent_scans"]
    top_notices = payload["top_notices"]
    predictive_outlook = payload["predictive_outlook"]

    _render_section_header(
        "",
        "Dashboard",
    )
    st.info(
        "Suggested workflow: run a live scan, review the top-ranked results, then open a notice detail page for evidence, checklist support, and internal notes."
    )
    _render_stat_cards(
        [
            {
                "label": "Total Notices",
                "value": str(metrics["total_notices"]),
                "note": "Current stored review queue",
            },
            {
                "label": "High Fit",
                "value": str(metrics["high_fit"]),
                "note": "Immediate follow-up candidates",
            },
            {
                "label": "Conditional",
                "value": str(metrics["conditional"]),
                "note": "Relevant with qualification risk",
            },
            {
                "label": "Scan Freshness",
                "value": format_datetime(metrics["scan_freshness"], settings.ui_timezone),
                "note": "Latest completed scan",
            },
        ]
    )
    st.caption(
        f"Expiring soon: {metrics['expiring_soon']} | Hard locks: {metrics['hard_lock']}"
    )

    scans_tab, queue_tab, forecast_tab = st.tabs(["Recent activity", "Top opportunities", "Outlook"])
    with scans_tab:
        if recent_scans:
            _render_recent_scan_cards(recent_scans)
        else:
            st.info("No scan history is available yet. Run a live TED scan to start building the workspace.")

    with queue_tab:
        if top_notices:
            for notice in top_notices[:4]:
                with st.container(border=True):
                    st.markdown(
                        f"""
                        <div class="cb-note-title">{html.escape(notice['title'])}</div>
                        <div class="cb-note-copy">{html.escape(notice['publication_number'])} | {html.escape(notice['buyer'] or 'Unknown buyer')} | {html.escape(notice['buyer_country'] or 'N/A')}</div>
                        """,
                        unsafe_allow_html=True,
                    )
                    action_cols = st.columns([0.8, 1.2, 1.2], gap="small")
                    action_cols[0].metric("Score", _format_score_out_of_ten(notice["score"], include_suffix=True))
                    if action_cols[1].button("Inspect", key=f"inspect_top_{notice['id']}", type="primary", width="stretch"):
                        _open_notice_detail(notice["id"])
                        st.rerun()
                    official_url = _resolve_official_notice_url(notice)
                    if official_url:
                        action_cols[2].link_button("TED notice", official_url, width="stretch")
        else:
            st.info("No notices are ready for review yet. Run a live scan or widen the filters to surface opportunities.")

    with forecast_tab:
        _render_predictive_outlook(predictive_outlook)


def _render_filters(*, render_sidebar: bool = True) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    filter_state = dict(st.session_state.get("results_filter_state", _default_filter_state()))
    if filter_state.get("min_days_remaining") is None:
        filter_state["min_days_remaining"] = 0
    selected_countries = _normalize_country_filter_values(filter_state.get("countries", filter_state.get("country")))
    filter_state["countries"] = selected_countries

    if not render_sidebar:
        return _load_notices_for_filter_state(filter_state)

    st.sidebar.markdown("### Refine results")
    st.sidebar.caption("Use a few simple filters to narrow the review queue.")
    st.sidebar.info("Active tenders are prioritised by default so the review queue stays current and actionable.")
    country_options = _country_filter_options()
    country_labels = ["Any"] + [label for label, _ in country_options]
    country_code_by_label = {"Any": ""}
    country_code_by_label.update({label: code for label, code in country_options})
    selected_country = selected_countries[0] if selected_countries else ""
    selected_country_label = next((label for label, code in country_options if code == selected_country), "Any")

    raw_score_min = filter_state.get("score_min")
    score_min_ten_default = 0.0
    if isinstance(raw_score_min, (int, float)):
        score_min_ten_default = max(0.0, min(10.0, float(raw_score_min) / 10.0))

    st.session_state.setdefault("results_country_label", selected_country_label)
    st.session_state.setdefault("results_search", filter_state.get("search") or "")
    st.session_state.setdefault("results_minimum_score_ten", score_min_ten_default)
    st.session_state.setdefault("results_relevant_only", bool(filter_state.get("relevant_only")))
    st.session_state.setdefault("results_fit_label", filter_state.get("fit_label") or "Any")
    st.session_state.setdefault("results_priority_bucket", filter_state.get("priority_bucket") or "Any")
    st.session_state.setdefault("results_confidence_indicator", filter_state.get("confidence_indicator") or "Any")
    st.session_state.setdefault("results_min_days_remaining", int(filter_state.get("min_days_remaining") or 0))
    st.session_state.setdefault("results_hard_lock_only", bool(filter_state.get("hard_lock_only")))
    st.session_state.setdefault("results_saved_only", bool(filter_state.get("saved_only")))
    st.session_state.setdefault("results_include_dismissed", bool(filter_state.get("include_dismissed")))

    selected_country_label = st.sidebar.selectbox(
        "Country",
        options=country_labels,
        index=country_labels.index(st.session_state.get("results_country_label", "Any")),
        key="results_country_label",
    )
    countries = [country_code_by_label[selected_country_label]] if country_code_by_label[selected_country_label] else []
    search = (
        st.sidebar.text_input(
            "Search title or buyer",
            key="results_search",
            placeholder="e.g. document management, ministry, archive",
        ).strip()
        or None
    )

    minimum_score_ten = st.sidebar.slider(
        "Minimum Score",
        min_value=0.0,
        max_value=10.0,
        value=float(st.session_state.get("results_minimum_score_ten", score_min_ten_default)),
        step=0.5,
        key="results_minimum_score_ten",
    )
    filter_action_cols = st.sidebar.columns(2, gap="small")
    if filter_action_cols[0].button("Reset score", use_container_width=True, type="secondary"):
        st.session_state["results_minimum_score_ten"] = 0.0
        st.rerun()
    if filter_action_cols[1].button("Clear all", use_container_width=True, type="secondary"):
        default_state = _default_filter_state()
        st.session_state["results_filter_state"] = dict(default_state)
        st.session_state["results_country_label"] = "Any"
        st.session_state["results_search"] = ""
        st.session_state["results_minimum_score_ten"] = 0.0
        st.session_state["results_relevant_only"] = bool(default_state.get("relevant_only"))
        st.session_state["results_fit_label"] = "Any"
        st.session_state["results_priority_bucket"] = "Any"
        st.session_state["results_confidence_indicator"] = "Any"
        st.session_state["results_min_days_remaining"] = int(default_state.get("min_days_remaining") or 0)
        st.session_state["results_hard_lock_only"] = bool(default_state.get("hard_lock_only"))
        st.session_state["results_saved_only"] = bool(default_state.get("saved_only"))
        st.session_state["results_include_dismissed"] = bool(default_state.get("include_dismissed"))
        st.cache_data.clear()
        st.rerun()
    relevant_only = st.sidebar.checkbox("Relevant to F2 Only", key="results_relevant_only")

    advanced_filters_active = any(
        [
            (filter_state.get("fit_label") or "Any") != "Any",
            (filter_state.get("priority_bucket") or "Any") != "Any",
            (filter_state.get("confidence_indicator") or "Any") != "Any",
            int(filter_state.get("min_days_remaining") or 0) > 0,
            bool(filter_state.get("hard_lock_only")),
            bool(filter_state.get("saved_only")),
            bool(filter_state.get("include_dismissed")),
        ]
    )

    with st.sidebar.expander("More Filters", expanded=advanced_filters_active):
        fit_options = ["Any", "YES", "CONDITIONAL", "NO"]
        priority_options = ["Any", "HIGH", "GOOD", "WATCHLIST", "IGNORE"]
        confidence_options = ["Any", "HIGH", "MEDIUM", "LOW"]
        fit_label = st.selectbox(
            "Fit Label",
            fit_options,
            index=fit_options.index(st.session_state.get("results_fit_label", "Any")),
            key="results_fit_label",
        )
        priority_bucket = st.selectbox(
            "Priority Bucket",
            priority_options,
            index=priority_options.index(st.session_state.get("results_priority_bucket", "Any")),
            key="results_priority_bucket",
        )
        confidence_indicator = st.selectbox(
            "Confidence",
            confidence_options,
            index=confidence_options.index(st.session_state.get("results_confidence_indicator", "Any")),
            key="results_confidence_indicator",
        )
        min_days_remaining = st.number_input(
            "Minimum Days Remaining",
            min_value=0,
            max_value=30,
            value=int(st.session_state.get("results_min_days_remaining", filter_state.get("min_days_remaining") or 0)),
            step=1,
            key="results_min_days_remaining",
        )
        hard_lock_only = st.checkbox("Hard Lock Only", key="results_hard_lock_only")
        saved_only = st.checkbox("Saved Only", key="results_saved_only")
        include_dismissed = st.checkbox("Include Dismissed", key="results_include_dismissed")

    filter_state = {
        "countries": countries,
        "search": search,
        "relevant_only": relevant_only,
        "fit_label": None if fit_label == "Any" else fit_label,
        "priority_bucket": None if priority_bucket == "Any" else priority_bucket,
        "confidence_indicator": None if confidence_indicator == "Any" else confidence_indicator,
        "score_min": int(round(minimum_score_ten * 10)),
        "score_max": 100,
        "publication_date_from": None,
        "publication_date_to": None,
        "min_days_remaining": min_days_remaining,
        "deadline_from": None,
        "deadline_to": None,
        "deadline_window_days": None,
        "hard_lock_only": hard_lock_only,
        "saved_only": saved_only,
        "include_dismissed": include_dismissed,
        "page_size": 20,
    }
    notices, updated_state = _load_notices_for_filter_state(filter_state)
    st.session_state["results_filter_state"] = dict(updated_state)
    return notices, updated_state


def _render_results() -> list[dict[str, Any]]:
    notices, filter_state = _render_filters()
    _seed_selected_notice(notices)

    nav_cols = st.columns([0.18, 0.82], gap="small")
    results_return_view = st.session_state.get("results_return_view")
    if results_return_view in {"Live Scan", "Historical Backfill"}:
        back_label = "Back to Scan" if results_return_view == "Live Scan" else "Back to Backfill"
        if nav_cols[0].button(back_label, key="results_back_to_source", type="secondary", width="stretch"):
            _go_to_view(results_return_view)
            st.rerun()

    _render_section_header(
        "",
        "Results",
    )
    total_matches = filter_state["total_matches"]

    if not notices:
        st.warning("No notices match the current filters. Clear a filter or lower the minimum score to widen the review queue.")
        return notices

    st.caption(f"Showing {len(notices)} of {total_matches} ranked notices for the current review posture.")
    st.info("Use Open TED notice for the public source record and Review notice for the internal dossier with evidence, checklist support, and audit detail.")

    active_filter_chips = _summarize_results_filters(filter_state)
    if active_filter_chips:
        with st.expander("Active filters", expanded=True):
            st.markdown(
                "<div class='cb-chip-row'>"
                + "".join(_render_chip(chip) for chip in active_filter_chips)
                + "</div>",
                unsafe_allow_html=True,
            )

    _render_stat_cards(_build_results_metrics(notices, total_matches=total_matches))

    for index, notice in enumerate(notices):
        _render_result_card(notice, card_index=index)

    return notices


def _render_download_controls(detail: dict[str, Any]) -> None:
    _render_download_controls_impl(
        detail,
        resolve_official_notice_url=_resolve_official_notice_url,
        fetch_official_document=fetch_official_document,
    )


@st.cache_resource(show_spinner=False)
def get_tender_checklist_service() -> TenderChecklistService:
    return TenderChecklistService.from_settings(settings)


def _render_checklist_cross_reference(detail: dict[str, Any]) -> None:
    _render_checklist_cross_reference_impl(detail, get_tender_checklist_service=get_tender_checklist_service)


def _render_keyword_evidence_module(detail: dict[str, Any]) -> None:
    _render_keyword_evidence_module_impl(detail)


def _render_notice_detail(notice_id: str | None) -> None:
    return_view = st.session_state.get("detail_return_view", "Results")
    nav_cols = st.columns([0.2, 0.8], gap="small")
    if nav_cols[0].button(
        f"Back to {return_view if return_view != 'Notice Detail' else 'Results'}",
        key="detail_back_button",
        type="secondary",
        width="stretch",
    ):
        _go_to_view(return_view if return_view != "Notice Detail" else "Results")
        st.rerun()

    st.caption(f"{return_view} → Notice detail")
    _render_section_header(
        "",
        "Notice detail",
    )
    if not notice_id:
        st.info("Choose a tender from the Results view first.")
        return

    detail = load_notice_detail(notice_id)
    if detail is None:
        st.error("The selected notice could not be found.")
        return
    _render_notice_detail_layout_impl(
        detail,
        ui_timezone=settings.ui_timezone,
        card_tone_class=_card_tone_class,
        notice_source_label=_notice_source_label,
        format_score_out_of_ten=_format_score_out_of_ten,
        display_value=_display_value,
        render_download_controls_fn=_render_download_controls,
        render_keyword_evidence_module_fn=_render_keyword_evidence_module,
        render_checklist_cross_reference_fn=_render_checklist_cross_reference,
    )


def _render_notice_detail_workspace() -> None:
    notices, _ = _render_filters(render_sidebar=False)
    _seed_selected_notice(notices)
    options = notices
    if not options:
        fallback_payload = load_filtered_notices(
            country=None,
            fit_label=None,
            priority_bucket=None,
            min_score=None,
            max_score=None,
            confidence_indicator=None,
            relevant_only=False,
            min_days_remaining=0,
            hard_lock_only=False,
            publication_date_from=None,
            publication_date_to=None,
            deadline_from=None,
            deadline_to=None,
            deadline_window_days=None,
            include_dismissed=False,
            saved_only=False,
            search=None,
            page_size=100,
        )
        options = fallback_payload["items"]
    if options:
        selected = st.selectbox(
            "Choose a tender to review",
            options=options,
            format_func=_notice_option_label,
            index=next(
                (
                    idx
                    for idx, notice in enumerate(options)
                    if notice["id"] == st.session_state.get("selected_notice_id")
                ),
                0,
            ),
            key="detail_notice_picker",
        )
        st.session_state["selected_notice_id"] = selected["id"]
    _render_notice_detail(st.session_state.get("selected_notice_id"))


def main() -> None:
    _apply_theme()

    views = ["Dashboard", "Live Scan", "Historical Backfill", "Results", "Notice Detail"]
    view_labels = {
        "Dashboard": "📊 Dashboard",
        "Live Scan": "🔎 Live Scan",
        "Historical Backfill": "🗂 Historical Backfill",
        "Results": "📋 Results",
        "Notice Detail": "📘 Notice Detail",
    }
    inverse_view_labels = {label: key for key, label in view_labels.items()}
    active_view = st.session_state.get("active_view", "Dashboard")
    if active_view not in views:
        active_view = "Dashboard"

    _render_sidebar_brand()
    st.sidebar.markdown("## Workspaces")
    selected_label = st.sidebar.radio(
        "Workspace",
        options=[view_labels[view] for view in views],
        index=[view_labels[view] for view in views].index(view_labels[active_view]),
        label_visibility="collapsed",
    )
    current_view = inverse_view_labels[selected_label]
    st.session_state["active_view"] = current_view
    if current_view == "Dashboard":
        _render_dashboard()
    elif current_view == "Live Scan":
        _render_live_scan()
    elif current_view == "Historical Backfill":
        _render_historical_backfill()
    elif current_view == "Results":
        _render_results()
    else:
        _render_notice_detail_workspace()


if __name__ == "__main__":
    main()

