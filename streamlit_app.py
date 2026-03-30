from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
import html
from typing import Any

import streamlit as st

from app.api.presenters import notice_to_detail_dict, notice_to_summary_dict, scan_run_to_dict
from app.api.schemas import ScanRequestPayload
from app.auth import ActorContext
from app.config import get_settings, load_keyword_pack, load_search_profiles
from app.database import get_session_factory
from app.repositories.notices import NoticeListFilters, NoticeRepository
from app.repositories.scan_runs import ScanRunRepository
from app.services.demo_bootstrap import ensure_streamlit_storage
from app.services.scan_service import ScanService
from app.services.tender_checklist import TenderChecklistService
from app.services.ted_client import TedApiClient
from app.services.ted_documents import DocumentSpec, TedDocumentService
from app.utils.time import ensure_utc, format_date, format_datetime, parse_ted_date, parse_ted_datetime

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
    st.markdown(
        """
        <style>
        .stApp,
        [data-testid="stAppViewContainer"],
        [data-testid="stAppViewContainer"] > .main,
        [data-testid="stMain"] {
            background: #f3f5f8;
            color: #162434;
        }
        [data-testid="stHeader"] {
            background: rgba(255, 255, 255, 0.96);
            border-bottom: 1px solid #d9e1ea;
        }
        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, #17324d 0%, #12283f 100%);
            border-right: 1px solid rgba(255, 255, 255, 0.08);
        }
        [data-testid="stSidebar"] * {
            color: #eef4fb;
        }
        .main .block-container {
            padding-top: 1.35rem;
            padding-bottom: 2rem;
            max-width: 1320px;
        }
        h1, h2, h3, h4, h5, h6, p, li, label, span, div {
            color: inherit;
        }
        div[data-testid="stMetric"] {
            background: #ffffff;
            border: 1px solid #d9e1ea;
            border-radius: 10px;
            padding: 0.85rem 1rem;
            box-shadow: 0 4px 14px rgba(15, 33, 56, 0.04);
        }
        div[data-testid="stMetricLabel"] p {
            color: #6c7b8b;
            font-size: 0.82rem;
            text-transform: uppercase;
            letter-spacing: 0.04em;
        }
        div[data-testid="stMetricValue"] {
            color: #162434;
        }
        div[data-testid="stForm"] {
            background: #ffffff;
            border: 1px solid #d9e1ea;
            border-radius: 12px;
            padding: 0.9rem 1rem 1rem;
            box-shadow: 0 6px 18px rgba(15, 33, 56, 0.04);
        }
        div[data-baseweb="input"] > div,
        div[data-baseweb="select"] > div,
        div[data-baseweb="textarea"] > div {
            background: #ffffff;
            border: 1px solid #cfd8e3;
            border-radius: 8px;
        }
        div[data-testid="stVerticalBlockBorderWrapper"] {
            background: #ffffff;
            border: 1px solid #d9e1ea;
            border-radius: 12px;
            box-shadow: 0 6px 18px rgba(15, 33, 56, 0.04);
        }
        .stButton > button,
        .stDownloadButton > button {
            background: #1f5aa6;
            color: #ffffff;
            border: 1px solid #1f5aa6;
            border-radius: 8px;
            min-height: 2.7rem;
            font-weight: 600;
            box-shadow: none;
        }
        .stButton > button:hover,
        .stDownloadButton > button:hover {
            border-color: #184a88;
            background: #184a88;
            color: #ffffff;
        }
        .stLinkButton a {
            background: #ffffff;
            color: #1f5aa6;
            border: 1px solid #cfd8e3;
            border-radius: 8px;
            min-height: 2.7rem;
            font-weight: 600;
        }
        .stLinkButton a:hover {
            background: #f6f9fc;
            border-color: #bcc9d7;
            color: #173f74;
        }
        .stAlert {
            border-radius: 10px;
        }
        .cb-banner {
            background: #ffffff;
            border: 1px solid #d9e1ea;
            border-left: 5px solid #1f5aa6;
            border-radius: 10px;
            padding: 0.95rem 1.1rem;
            margin-bottom: 1.1rem;
            box-shadow: 0 6px 18px rgba(15, 33, 56, 0.04);
        }
        .cb-kicker {
            color: #5d6c7c;
            font-size: 0.78rem;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            margin-bottom: 0.25rem;
        }
        .cb-title {
            color: #162434;
            font-size: 1.85rem;
            font-weight: 700;
            margin: 0;
        }
        .cb-subtitle {
            color: #607084;
            margin-top: 0.3rem;
        }
        .cb-section-title {
            margin-top: 0;
            margin-bottom: 0.3rem;
        }
        .cb-muted {
            color: #667585;
            font-size: 0.92rem;
        }
        .cb-sidebar-brand {
            padding: 0.35rem 0 1rem 0;
            margin-bottom: 0.9rem;
            border-bottom: 1px solid rgba(255, 255, 255, 0.08);
        }
        .cb-sidebar-logo {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 2rem;
            height: 2rem;
            border-radius: 6px;
            background: #2b67b7;
            color: #ffffff;
            font-weight: 700;
            font-size: 0.9rem;
            margin-bottom: 0.6rem;
        }
        .cb-sidebar-title {
            color: #f4f8fc;
            font-size: 1rem;
            font-weight: 700;
            margin-bottom: 0.2rem;
        }
        .cb-sidebar-subtitle {
            color: #a9bdd3;
            font-size: 0.84rem;
            line-height: 1.45;
        }
        .cb-result-card {
            background: #ffffff;
            border: 1px solid #d9e1ea;
            border-left: 4px solid #b8c7d8;
            border-radius: 10px;
            padding: 1rem 1rem 0.9rem 1rem;
            box-shadow: 0 6px 18px rgba(15, 33, 56, 0.04);
            margin-bottom: 0.75rem;
        }
        .cb-result-card-high { border-left-color: #1f5aa6; }
        .cb-result-card-good { border-left-color: #2d7c64; }
        .cb-result-card-watch { border-left-color: #9b6b18; }
        .cb-result-card-ignore { border-left-color: #8a97a8; }
        .cb-result-card-conditional { border-left-color: #b85b3d; }
        .cb-result-topline {
            display: flex;
            justify-content: space-between;
            gap: 0.75rem;
            align-items: flex-start;
            margin-bottom: 0.75rem;
        }
        .cb-result-topline-left {
            display: flex;
            flex-wrap: wrap;
            gap: 0.4rem;
        }
        .cb-result-score {
            text-align: right;
        }
        .cb-result-score-label {
            color: #6b7a8a;
            font-size: 0.78rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }
        .cb-result-score-value {
            color: #162434;
            font-size: 1.45rem;
            font-weight: 700;
            line-height: 1.1;
        }
        .cb-result-title {
            color: #162434;
            font-size: 1.04rem;
            font-weight: 700;
            line-height: 1.35;
            margin-bottom: 0.55rem;
        }
        .cb-result-meta {
            color: #657587;
            font-size: 0.9rem;
            margin-bottom: 0.3rem;
        }
        .cb-pill {
            display: inline-flex;
            align-items: center;
            padding: 0.22rem 0.46rem;
            border-radius: 6px;
            border: 1px solid #d6dee8;
            font-size: 0.73rem;
            font-weight: 600;
            line-height: 1;
            letter-spacing: 0.03em;
            text-transform: uppercase;
            background: #f7f9fb;
            color: #44586d;
        }
        .cb-pill-source {
            background: #edf3fb;
            border-color: #c8d8ee;
            color: #1f5aa6;
        }
        .cb-pill-fit {
            background: #eef2f5;
            border-color: #d2dbe4;
            color: #3a536b;
        }
        .cb-pill-priority {
            background: #eef3fb;
            border-color: #cad8ea;
            color: #355784;
        }
        .cb-pill-alert {
            background: #fbefeb;
            border-color: #efd0c6;
            color: #a14e38;
        }
        .cb-pill-good {
            background: #edf5f1;
            border-color: #cce0d6;
            color: #2f6c54;
        }
        .cb-pill-neutral {
            background: #f2f4f7;
            border-color: #d7dee6;
            color: #596a7c;
        }
        .cb-chip-row {
            display: flex;
            flex-wrap: wrap;
            gap: 0.38rem;
            margin-top: 0.8rem;
        }
        .cb-chip {
            display: inline-flex;
            align-items: center;
            padding: 0.22rem 0.46rem;
            border-radius: 6px;
            border: 1px solid #d4dde7;
            background: #f7f9fb;
            color: #4b6074;
            font-size: 0.74rem;
            font-weight: 600;
            line-height: 1;
        }
        .cb-detail-block {
            display: flex;
            flex-direction: column;
            gap: 0.55rem;
        }
        .cb-detail-line {
            color: #23384d;
            font-size: 0.93rem;
            line-height: 1.45;
        }
        .cb-detail-line strong {
            color: #162434;
        }
        .cb-checklist-table-wrap {
            overflow-x: auto;
            margin-top: 0.75rem;
        }
        .cb-checklist-table {
            width: 100%;
            border-collapse: separate;
            border-spacing: 0;
            background: #ffffff;
            border: 1px solid #d9e1ea;
            border-radius: 12px;
            overflow: hidden;
        }
        .cb-checklist-table thead th {
            background: #eef3f8;
            color: #4f6276;
            font-size: 0.78rem;
            font-weight: 700;
            letter-spacing: 0.05em;
            text-transform: uppercase;
            padding: 0.8rem 0.9rem;
            text-align: left;
            border-bottom: 1px solid #d9e1ea;
        }
        .cb-checklist-table tbody tr:nth-child(even) {
            background: #fbfcfe;
        }
        .cb-checklist-table tbody tr:hover {
            background: #f5f8fc;
        }
        .cb-checklist-table td {
            padding: 0.8rem 0.9rem;
            border-top: 1px solid #e3e9f0;
            vertical-align: top;
            font-size: 0.92rem;
            line-height: 1.45;
            color: #23384d;
            word-break: break-word;
        }
        .cb-checklist-table td.cb-checklist-col-item {
            width: 20%;
            font-weight: 700;
            color: #162434;
        }
        .cb-checklist-table td.cb-checklist-col-status {
            width: 11%;
            white-space: nowrap;
        }
        .cb-checklist-table td.cb-checklist-col-answer {
            width: 34%;
        }
        .cb-checklist-table td.cb-checklist-col-basis {
            width: 35%;
            color: #5f7185;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


@st.cache_data(ttl=60, show_spinner=False)
def load_dashboard_payload() -> dict[str, Any]:
    session = get_session_factory()()
    try:
        notice_repo = NoticeRepository(session)
        scan_repo = ScanRunRepository(session)
        return {
            "metrics": notice_repo.dashboard_metrics(),
            "recent_scans": [scan_run_to_dict(scan) for scan in scan_repo.recent(limit=6)],
            "top_notices": [
                notice_to_summary_dict(notice)
                for notice in notice_repo.list(NoticeListFilters(), page=1, page_size=8)[0]
            ],
        }
    finally:
        session.close()


@st.cache_data(ttl=60, show_spinner=False)
def load_filtered_notices(
    *,
    country: str | None,
    fit_label: str | None,
    priority_bucket: str | None,
    min_score: int | None,
    max_score: int | None,
    confidence_indicator: str | None,
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
        filters = NoticeListFilters(
            country=country,
            fit_label=fit_label,
            priority_bucket=priority_bucket,
            min_score=min_score,
            max_score=max_score,
            confidence_indicator=confidence_indicator,
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


def _display_value(value: Any) -> str:
    if value is None:
        return "N/A"
    raw = getattr(value, "value", value)
    if raw is None:
        return "N/A"
    return str(raw)


def _render_pill(label: str, tone: str) -> str:
    safe_label = html.escape(label)
    return f"<span class='cb-pill cb-pill-{tone}'>{safe_label}</span>"


def _render_chip(label: str) -> str:
    return f"<span class='cb-chip'>{html.escape(label)}</span>"


def _render_rich_text_cell(value: Any) -> str:
    return html.escape(_display_value(value)).replace("\n", "<br>")


def _coerce_notice_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return ensure_utc(value)
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time(), tzinfo=UTC)
    if isinstance(value, str):
        return parse_ted_datetime(value)
    return None


def _coerce_notice_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return ensure_utc(value).date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return parse_ted_date(value)
    return None


def _card_tone_class(notice: dict[str, Any]) -> str:
    priority = _display_value(notice.get("priority_bucket")).upper()
    fit = _display_value(notice.get("fit_label")).upper()
    if fit == "CONDITIONAL" or notice.get("hard_lock_detected"):
        return "cb-result-card-conditional"
    if priority == "HIGH":
        return "cb-result-card-high"
    if priority == "GOOD":
        return "cb-result-card-good"
    if priority == "WATCHLIST":
        return "cb-result-card-watch"
    if priority == "IGNORE":
        return "cb-result-card-ignore"
    return ""


def _render_stat_cards(cards: list[dict[str, str]]) -> None:
    if not cards:
        return

    per_row = 4
    for start in range(0, len(cards), per_row):
        row_cards = cards[start : start + per_row]
        columns = st.columns(len(row_cards), gap="medium")
        for column, card in zip(columns, row_cards):
            with column:
                with st.container(border=True):
                    st.caption(card["label"].upper())
                    st.markdown(f"### {card['value']}")
                    st.caption(card["note"])


def _render_profile_cards() -> None:
    profiles = get_search_profiles_registry().profiles
    if not profiles:
        return

    per_row = 3
    for start in range(0, len(profiles), per_row):
        row_profiles = profiles[start : start + per_row]
        columns = st.columns(len(row_profiles), gap="medium")
        for column, profile in zip(columns, row_profiles):
            with column:
                with st.container(border=True):
                    st.markdown(f"**{profile.name}**")
                    st.caption(profile.description)
                    if profile.search_terms:
                        st.markdown(
                            "<div class='cb-chip-row'>"
                            + "".join(_render_chip(term) for term in profile.search_terms[:4])
                            + "</div>",
                            unsafe_allow_html=True,
                        )


def _render_recent_scan_cards(recent_scans: list[dict[str, Any]]) -> None:
    for scan in recent_scans:
        with st.container(border=True):
            st.markdown(f"**{scan['status']}**")
            st.caption(f"Started {format_datetime(scan['started_at'], settings.ui_timezone)}")
            detail_cols = st.columns(3, gap="small")
            detail_cols[0].metric("Ingested", scan["total_notices_ingested"])
            detail_cols[1].metric("High Fit", scan["total_high_fit"])
            detail_cols[2].metric("Requests", scan["request_count"])
            if scan["rate_limit_events"]:
                st.caption(f"Rate-limit events: {scan['rate_limit_events']}")


def _normalize_date_range(start: date | None, end: date | None) -> tuple[date | None, date | None]:
    if start is not None and end is not None and start > end:
        return end, start
    return start, end


def _render_checklist_table(items: list[dict[str, Any]]) -> None:
    if not items:
        st.info("No checklist items are available for this notice.")
        return

    rows: list[str] = []
    for item in items:
        status = _display_value(item.get("status")).upper()
        rows.append(
            "<tr>"
            f"<td class='cb-checklist-col-item'>{_render_rich_text_cell(item.get('label'))}</td>"
            f"<td class='cb-checklist-col-status'>{_render_pill(status, _status_tone(status))}</td>"
            f"<td class='cb-checklist-col-answer'>{_render_rich_text_cell(item.get('answer'))}</td>"
            f"<td class='cb-checklist-col-basis'>{_render_rich_text_cell(item.get('basis'))}</td>"
            "</tr>"
        )

    st.markdown(
        """
        <div class="cb-checklist-table-wrap">
          <table class="cb-checklist-table">
            <thead>
              <tr>
                <th>Checklist Element</th>
                <th>Status</th>
                <th>Answer</th>
                <th>Basis</th>
              </tr>
            </thead>
            <tbody>
        """
        + "".join(rows)
        + """
            </tbody>
          </table>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _status_tone(status: str) -> str:
    normalized = status.strip().lower()
    if normalized in {"filled", "high", "yes"}:
        return "good"
    if normalized in {"review", "no"}:
        return "alert"
    if normalized in {"inferred", "conditional", "watchlist"}:
        return "priority"
    return "neutral"


def _summarize_results_filters(filter_state: dict[str, Any]) -> list[str]:
    chips: list[str] = []
    if filter_state.get("country"):
        chips.append(f"Country: {filter_state['country']}")
    if filter_state.get("fit_label"):
        chips.append(f"Fit: {filter_state['fit_label']}")
    if filter_state.get("priority_bucket"):
        chips.append(f"Priority: {filter_state['priority_bucket']}")
    if filter_state.get("confidence_indicator"):
        chips.append(f"Confidence: {filter_state['confidence_indicator']}")
    score_min = filter_state.get("score_min")
    score_max = filter_state.get("score_max")
    if score_min != 0 or score_max != 100:
        chips.append(f"Score: {score_min}-{score_max}")
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


def _build_results_metrics(notices: list[dict[str, Any]], *, total_matches: int) -> list[dict[str, str]]:
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
    high_fit = sum(1 for notice in notices if _display_value(notice.get("priority_bucket")).upper() == "HIGH")
    good_fit = sum(1 for notice in notices if _display_value(notice.get("priority_bucket")).upper() == "GOOD")
    expiring_soon = sum(
        1
        for notice in notices
        if (deadline := _coerce_notice_datetime(notice.get("deadline"))) is not None
        and now <= deadline <= now + timedelta(days=7)
    )
    hard_locks = sum(1 for notice in notices if notice.get("hard_lock_detected"))
    recent_publications = sum(
        1
        for notice in notices
        if (publication_date := _coerce_notice_date(notice.get("publication_date"))) is not None
        and 0 <= (today - publication_date).days <= 30
    )
    live_notices = sum(1 for notice in notices if not notice.get("is_demo_record"))
    highest_score = max(int(notice.get("score") or 0) for notice in notices)

    return [
        {
            "label": "Matching Results",
            "value": str(total_matches),
            "note": f"{len(notices)} notices loaded into the current review surface.",
        },
        {
            "label": "Average Score",
            "value": f"{avg_score:.1f}",
            "note": f"Highest current score: {highest_score}",
        },
        {
            "label": "High Priority",
            "value": str(high_fit),
            "note": "Priority bucket HIGH in the current result set.",
        },
        {
            "label": "Good Priority",
            "value": str(good_fit),
            "note": "Priority bucket GOOD in the current result set.",
        },
        {
            "label": "Expiring Soon",
            "value": str(expiring_soon),
            "note": "Submission deadline within the next 7 days.",
        },
        {
            "label": "Hard Locks",
            "value": str(hard_locks),
            "note": "Mandatory platform constraints flagged by scoring.",
        },
        {
            "label": "Published 30d",
            "value": str(recent_publications),
            "note": "Notices published in the last 30 days.",
        },
        {
            "label": "Live TED",
            "value": str(live_notices),
            "note": "Non-demo notices linked back to official TED records.",
        },
    ]


def _render_sidebar_brand() -> None:
    st.sidebar.markdown(
        """
        <div class="cb-sidebar-brand">
          <div class="cb-sidebar-logo">CB</div>
          <div class="cb-sidebar-title">TED F2 Intelligence</div>
          <div class="cb-sidebar-subtitle">Internal cBrain opportunity review for official TED notices only.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _notice_keyword_labels(notice: dict[str, Any], *, limit: int = 4) -> list[str]:
    labels: list[str] = []
    for hit in notice.get("keyword_hits", [])[:limit]:
        term = hit.get("term")
        scope = hit.get("scope")
        if term and scope:
            labels.append(f"{term} [{scope}]")
        elif term:
            labels.append(str(term))
    return labels


def _render_result_card(notice: dict[str, Any], *, card_index: int) -> None:
    fit_label = _display_value(notice.get("fit_label"))
    priority_bucket = _display_value(notice.get("priority_bucket"))
    confidence = _display_value(notice.get("confidence_indicator"))
    card_class = _card_tone_class(notice)
    top_line_badges = [
        _render_pill(_notice_source_label(notice), "source"),
        _render_pill(fit_label, "fit"),
        _render_pill(priority_bucket, "priority"),
    ]
    if notice.get("hard_lock_detected"):
        top_line_badges.append(_render_pill("Hard lock", "alert"))
    elif notice.get("viable_timing"):
        top_line_badges.append(_render_pill("Timing viable", "good"))
    else:
        top_line_badges.append(_render_pill("Timing review", "neutral"))

    buyer = notice.get("buyer") or "Unknown buyer"
    country = notice.get("buyer_country") or "N/A"
    publication = notice.get("publication_number") or "Unknown publication"
    deadline = format_datetime(notice.get("deadline"), settings.ui_timezone)
    publication_date = format_date(notice.get("publication_date"))
    summary = notice.get("title") or "Untitled notice"
    keyword_chips = "".join(_render_chip(label) for label in _notice_keyword_labels(notice))
    if not keyword_chips:
        keyword_chips = _render_chip("No keyword evidence captured yet")

    st.markdown(
        f"""
        <div class="cb-result-card {card_class}">
          <div class="cb-result-topline">
            <div class="cb-result-topline-left">
              {''.join(top_line_badges)}
            </div>
            <div class="cb-result-score">
              <div class="cb-result-score-label">Score</div>
              <div class="cb-result-score-value">{notice['score']}</div>
            </div>
          </div>
          <div class="cb-result-title">{html.escape(summary)}</div>
          <div class="cb-result-meta">{html.escape(publication)} | {html.escape(buyer)} | {html.escape(country)}</div>
          <div class="cb-result-meta">Published {html.escape(publication_date)} | Deadline {html.escape(deadline)}</div>
          <div class="cb-result-meta">Confidence {html.escape(confidence)}</div>
          <div class="cb-chip-row">{keyword_chips}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    action_cols = st.columns([1, 1], gap="small")
    official_url = _resolve_official_notice_url(notice)
    if official_url:
        action_cols[0].link_button("Open TED notice", official_url, width="stretch")
    elif notice.get("is_demo_record"):
        action_cols[0].caption("Demo-only notice")
    else:
        action_cols[0].caption("No official TED URL")

    if action_cols[1].button("Review notice", key=f"review_notice_{card_index}_{notice['id']}", width="stretch"):
        st.session_state["selected_notice_id"] = notice["id"]
        _go_to_view("Notice Detail")
        st.rerun()


def _seed_selected_notice(notices: list[dict[str, Any]]) -> None:
    if not notices:
        st.session_state.pop("selected_notice_id", None)
        return
    selected = st.session_state.get("selected_notice_id")
    if selected not in {item["id"] for item in notices}:
        st.session_state["selected_notice_id"] = notices[0]["id"]


def _go_to_view(view_name: str) -> None:
    st.session_state["active_view"] = view_name


def _resolve_official_notice_url(notice: dict[str, Any]) -> str | None:
    if notice.get("is_demo_record"):
        return None
    publication_number = notice.get("publication_number")
    if publication_number:
        return f"https://ted.europa.eu/en/notice/-/detail/{publication_number}"
    return notice.get("source_url") or notice.get("html_url") or notice.get("pdf_url")


def run_live_scan(
    *,
    profile_name: str,
    country: str | None,
    cpv: str | None,
    keyword_override: str | None,
    date_from: date | None,
    date_to: date | None,
    include_conditional: bool,
    exclude_old: bool,
    include_soft_locks: bool,
    page_size: int,
    max_pages: int,
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
            date_from=date_from,
            date_to=date_to,
            include_conditional=include_conditional,
            exclude_old=exclude_old,
            include_soft_locks=include_soft_locks,
            page_size=page_size,
            max_pages=max_pages,
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


def _render_banner() -> None:
    storage_state = initialize_streamlit_storage()
    purged_demo_notices = storage_state.get("purged_demo_notices", 0)
    st.markdown(
        """
        <div class="cb-banner">
          <div class="cb-kicker">cBrain Internal Service Shell</div>
          <h1 class="cb-title">cBrain TED F2 Intelligence</h1>
          <div class="cb-subtitle">
            Official TED-only opportunity review for F2-fit assessment. FastAPI remains the canonical backend and live scans use TED's public API.
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if purged_demo_notices:
        st.info(
            f"Removed {purged_demo_notices} seeded demo notices from the local store so the app can focus on live TED data."
        )


def _render_live_scan() -> None:
    profiles = get_search_profiles_registry()

    st.subheader("Live TED Scan", anchor=False)
    st.caption(
        "Run a live search against TED's public Search API. This populates the same database used by the rest of the app."
    )

    _render_stat_cards(
        [
            {
                "label": "Search Profiles",
                "value": str(len(profiles.names)),
                "note": "Configured TED scan strategies",
            },
            {
                "label": "TED RPM",
                "value": str(settings.ted_requests_per_minute),
                "note": "Polite request budget per minute",
            },
            {
                "label": "Max Pages",
                "value": str(settings.ted_max_pages_per_scan),
                "note": "Live scan page cap per run",
            },
            {
                "label": "UI Timezone",
                "value": settings.ui_timezone,
                "note": "Business-facing date display",
            },
        ]
    )

    with st.form("live_ted_scan_form"):
        left, right = st.columns(2, gap="large")
        with left:
            profile_name = st.selectbox("Search Profile", options=profiles.names, index=0)
            country = st.text_input("Buyer Country", value="", placeholder="DK or DNK")
            st.caption("The app accepts common 2-letter country codes like DK and converts them to TED's 3-letter format.")
            cpv = st.text_input("CPV Code", value="", placeholder="72260000")
            keyword_override = st.text_input(
                "Keyword Override",
                value="",
                placeholder="case management, workflow automation",
            )
            date_from = st.date_input("Publication Date From", value=None)
            date_to = st.date_input("Publication Date To", value=None)
        with right:
            page_size = st.slider("Page Size", min_value=10, max_value=100, value=25, step=5)
            max_pages = st.slider("Max Pages", min_value=1, max_value=settings.ted_max_pages_per_scan, value=1)
            include_conditional = st.checkbox("Include Conditional", value=True)
            exclude_old = st.checkbox("Exclude Older Notices", value=True)
            include_soft_locks = st.checkbox("Include Soft Locks", value=True)

        submitted = st.form_submit_button("Run live TED scan", width="stretch")

    if not submitted:
        st.info("Run a scan to replace empty or demo-only views with real TED notices.")
        st.markdown("#### Search Profiles")
        _render_profile_cards()
        return

    with st.spinner("Querying TED public API and scoring notices..."):
        try:
            outcome = run_live_scan(
                profile_name=profile_name,
                country=country.strip() or None,
                cpv=cpv.strip() or None,
                keyword_override=keyword_override.strip() or None,
                date_from=date_from,
                date_to=date_to,
                include_conditional=include_conditional,
                exclude_old=exclude_old,
                include_soft_locks=include_soft_locks,
                page_size=page_size,
                max_pages=max_pages,
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

    st.markdown("#### Search Profiles")
    _render_profile_cards()

    st.session_state["active_view"] = "Results"
    st.rerun()


def _render_dashboard() -> None:
    payload = load_dashboard_payload()
    metrics = payload["metrics"]
    recent_scans = payload["recent_scans"]
    top_notices = payload["top_notices"]

    st.subheader("Dashboard", anchor=False)
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
                "label": "Expiring Soon",
                "value": str(metrics["expiring_soon"]),
                "note": "Deadlines within seven days",
            },
            {
                "label": "Hard Locks",
                "value": str(metrics["hard_lock"]),
                "note": "Named platform delivery constraints",
            },
            {
                "label": "Scan Freshness",
                "value": format_datetime(metrics["scan_freshness"], settings.ui_timezone),
                "note": "Latest completed scan",
            },
        ]
    )

    left, right = st.columns([1.05, 0.95], gap="large")
    with left:
        st.markdown("#### Recent Scan Runs")
        if recent_scans:
            _render_recent_scan_cards(recent_scans)
        else:
            st.info("No scan history found.")

    with right:
        st.markdown("#### Top Review Queue")
        if top_notices:
            for notice in top_notices:
                with st.container(border=True):
                    st.markdown(f"**{notice['title']}**")
                    st.caption(
                        f"{notice['publication_number']} | {notice['buyer'] or 'Unknown buyer'} | "
                        f"{notice['buyer_country'] or 'N/A'} | Source: {_notice_source_label(notice)}"
                    )
                    action_cols = st.columns([1, 1, 1, 1])
                    action_cols[0].metric("Score", notice["score"])
                    action_cols[1].metric("Fit", _display_value(notice["fit_label"]))
                    action_cols[2].metric("Priority", _display_value(notice["priority_bucket"]))
                    if action_cols[3].button("Inspect", key=f"inspect_top_{notice['id']}"):
                        st.session_state["selected_notice_id"] = notice["id"]
                        _go_to_view("Notice Detail")
                        st.rerun()
                    official_url = _resolve_official_notice_url(notice)
                    if official_url:
                        st.link_button(
                            "Open live TED notice",
                            official_url,
                            width="stretch",
                        )
        else:
            st.info("No stored notices available yet.")


def _render_filters() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    st.sidebar.markdown("### Results Filters")
    st.sidebar.caption("Filter the current review queue by fit, timing, score, and publication window.")
    country = st.sidebar.text_input("Country (DK or DNK)", "").strip() or None
    search = st.sidebar.text_input("Search", "").strip() or None

    st.sidebar.markdown("#### Qualification")
    fit_label = st.sidebar.selectbox("Fit Label", ["Any", "YES", "CONDITIONAL", "NO"], index=0)
    priority_bucket = st.sidebar.selectbox("Priority Bucket", ["Any", "HIGH", "GOOD", "WATCHLIST", "IGNORE"], index=0)
    confidence_indicator = st.sidebar.selectbox("Confidence", ["Any", "HIGH", "MEDIUM", "LOW"], index=0)

    st.sidebar.markdown("#### Score")
    score_range = st.sidebar.slider("Score Range", min_value=0, max_value=100, value=(0, 100))

    st.sidebar.markdown("#### Publication Window")
    publication_date_from = st.sidebar.date_input("Published From", value=None)
    publication_date_to = st.sidebar.date_input("Published To", value=None)
    publication_date_from, publication_date_to = _normalize_date_range(publication_date_from, publication_date_to)

    st.sidebar.markdown("#### Deadline Window")
    deadline_from = st.sidebar.date_input("Deadline From", value=None)
    deadline_to = st.sidebar.date_input("Deadline To", value=None)
    deadline_from, deadline_to = _normalize_date_range(deadline_from, deadline_to)
    deadline_window_days = st.sidebar.number_input("Deadline Within (Days)", min_value=0, max_value=365, value=0, step=7)

    st.sidebar.markdown("#### Flags")
    hard_lock_only = st.sidebar.checkbox("Hard Lock Only", value=False)
    saved_only = st.sidebar.checkbox("Saved Only", value=False)
    include_dismissed = st.sidebar.checkbox("Include Dismissed", value=False)
    page_size = st.sidebar.slider("Cards to Load", min_value=10, max_value=100, value=25, step=5)

    payload = load_filtered_notices(
        country=country,
        fit_label=None if fit_label == "Any" else fit_label,
        priority_bucket=None if priority_bucket == "Any" else priority_bucket,
        min_score=score_range[0] if score_range[0] > 0 else None,
        max_score=score_range[1] if score_range[1] < 100 else None,
        confidence_indicator=None if confidence_indicator == "Any" else confidence_indicator,
        hard_lock_only=hard_lock_only,
        publication_date_from=publication_date_from,
        publication_date_to=publication_date_to,
        deadline_from=deadline_from,
        deadline_to=deadline_to,
        deadline_window_days=deadline_window_days if deadline_window_days > 0 else None,
        include_dismissed=include_dismissed,
        saved_only=saved_only,
        search=search,
        page_size=page_size,
    )
    filter_state = {
        "country": country,
        "fit_label": None if fit_label == "Any" else fit_label,
        "priority_bucket": None if priority_bucket == "Any" else priority_bucket,
        "confidence_indicator": None if confidence_indicator == "Any" else confidence_indicator,
        "score_min": score_range[0],
        "score_max": score_range[1],
        "publication_date_from": publication_date_from,
        "publication_date_to": publication_date_to,
        "deadline_from": deadline_from,
        "deadline_to": deadline_to,
        "deadline_window_days": deadline_window_days if deadline_window_days > 0 else None,
        "search": search,
        "hard_lock_only": hard_lock_only,
        "saved_only": saved_only,
        "include_dismissed": include_dismissed,
        "page_size": page_size,
        "total_matches": int(payload["total"]),
    }
    return payload["items"], filter_state


def _render_results() -> list[dict[str, Any]]:
    notices, filter_state = _render_filters()
    _seed_selected_notice(notices)

    st.subheader("Results", anchor=False)
    total_matches = filter_state["total_matches"]
    st.caption(
        f"{total_matches} notices match the current filter set. "
        f"{len(notices)} are currently loaded into the review surface."
    )

    if not notices:
        st.warning("No notices match the current filters.")
        return notices

    active_filter_chips = _summarize_results_filters(filter_state)
    if active_filter_chips:
        st.markdown(
            "<div class='cb-chip-row'>" + "".join(_render_chip(chip) for chip in active_filter_chips) + "</div>",
            unsafe_allow_html=True,
        )

    _render_stat_cards(_build_results_metrics(notices, total_matches=total_matches))

    grid_cols = st.columns(2, gap="large")
    for index, notice in enumerate(notices):
        with grid_cols[index % 2]:
            _render_result_card(notice, card_index=index)

    return notices


def _render_download_controls(detail: dict[str, Any]) -> None:
    st.markdown("#### Official TED Documents")
    st.caption("Open the official TED notice page or fetch the official TED PDF.")

    if detail.get("is_demo_record"):
        st.info(
            "This notice comes from seeded demo data. Live TED notice and document links are disabled "
            "because the sample publication number does not correspond to a real TED notice."
        )
        return

    document_cols = st.columns(2)
    official_notice_url = _resolve_official_notice_url(detail)
    if official_notice_url:
        document_cols[0].link_button("Open Official TED Notice", official_notice_url, width="stretch")
    else:
        document_cols[0].caption("No official TED notice URL available")

    pdf_url = detail.get("pdf_url")
    pdf_column = document_cols[1]
    if not pdf_url:
        pdf_column.caption("No official PDF available")
        return

    prep_key = f"prepare_pdf_{detail['id']}"
    state_key = f"prepared_pdf_{detail['id']}"
    if pdf_column.button("Prepare PDF", key=prep_key, width="stretch"):
        with st.spinner("Fetching official TED PDF document..."):
            try:
                st.session_state[state_key] = fetch_official_document(
                    url=pdf_url,
                    filename=f"{detail['publication_number']}.pdf",
                    media_type="application/pdf",
                )
            except Exception as exc:
                st.session_state.pop(state_key, None)
                st.error(f"Could not fetch the official TED PDF document: {exc}")

    prepared = st.session_state.get(state_key)
    if prepared:
        payload, filename, resolved_media_type = prepared
        pdf_column.download_button(
            "Download PDF",
            data=payload,
            file_name=filename,
            mime=resolved_media_type,
            key=f"download_pdf_{detail['id']}",
            width="stretch",
        )
    else:
        pdf_column.link_button("Open Official PDF", pdf_url, width="stretch")


@st.cache_resource(show_spinner=False)
def get_tender_checklist_service() -> TenderChecklistService:
    return TenderChecklistService.from_settings(settings)


def _render_checklist_cross_reference(detail: dict[str, Any]) -> None:
    st.markdown("#### cBrain Tender Checklist")
    st.caption(
        "Cross-reference this opportunity against the cBrain East Africa tender checklist template. "
        "Answers are marked as filled, inferred, or review."
    )

    state_key = f"show_checklist_{detail['id']}"
    button_cols = st.columns([0.34, 0.66])
    if button_cols[0].button("Run checklist cross-reference", key=f"run_checklist_{detail['id']}", width="stretch"):
        st.session_state[state_key] = True

    if not st.session_state.get(state_key):
        button_cols[1].caption("Run the checklist when you want a structured cross-reference for this tender.")
        return

    service = get_tender_checklist_service()
    report = service.evaluate_notice(detail)

    summary_cols = st.columns(3)
    summary_cols[0].metric("Filled", report["filled_count"])
    summary_cols[1].metric("Inferred", report["inferred_count"])
    summary_cols[2].metric("Review", report["review_count"])

    button_cols[1].download_button(
        "Download checklist summary",
        data=service.build_markdown(report),
        file_name=f"{detail['publication_number']}-checklist.md",
        mime="text/markdown",
        key=f"download_checklist_{detail['id']}",
        width="stretch",
    )

    st.caption("Reference table for analyst review and handoff.")
    _render_checklist_table(report["items"])


def _render_keyword_evidence_module(detail: dict[str, Any]) -> None:
    module = detail.get("keyword_evidence_module") or {}
    st.markdown("#### Eligibility Keywords")
    st.caption("Deterministic keyword evidence showing exactly why this opportunity was surfaced for F2 review.")

    st.info(module.get("statement") or "No keyword evidence module is available for this notice.")

    _render_stat_cards(
        [
            {
                "label": "Matched Keywords",
                "value": str(module.get("matched_keyword_count", 0)),
                "note": "Distinct positive keyword matches",
            },
            {
                "label": "Matched Domains",
                "value": str(module.get("matched_domain_count", 0)),
                "note": "F2-aligned domain groups triggered",
            },
            {
                "label": "Title Hits",
                "value": str(module.get("title_keyword_count", 0)),
                "note": "Matches found directly in the notice title",
            },
            {
                "label": "Summary Hits",
                "value": str(module.get("summary_keyword_count", 0)),
                "note": "Matches found in summary or body text",
            },
        ]
    )

    left, right = st.columns([0.58, 0.42], gap="large")
    with left:
        st.markdown("**Matched Domains**")
        if module.get("domain_matches"):
            for domain in module["domain_matches"]:
                with st.container(border=True):
                    header_cols = st.columns([0.72, 0.28], gap="small")
                    header_cols[0].markdown(f"**{domain['label']}**")
                    header_cols[1].metric("Points", domain.get("points", 0))
                    if domain.get("terms"):
                        st.markdown(
                            "<div class='cb-chip-row'>"
                            + "".join(_render_chip(term) for term in domain["terms"])
                            + "</div>",
                            unsafe_allow_html=True,
                        )
                    if domain.get("scope_labels"):
                        st.caption("Matched in: " + ", ".join(domain["scope_labels"]))
        else:
            st.caption("No mapped F2 domain groups were stored for this notice.")

    with right:
        st.markdown("**Keyword Scope Map**")
        if module.get("scope_hits"):
            for scope_group in module["scope_hits"]:
                with st.container(border=True):
                    st.markdown(f"**{scope_group['label']}**")
                    st.caption(f"{scope_group['count']} matched term(s)")
                    st.markdown(
                        "<div class='cb-chip-row'>"
                        + "".join(_render_chip(term) for term in scope_group["terms"])
                        + "</div>",
                        unsafe_allow_html=True,
                    )
        else:
            st.caption("No positive keyword hits were stored for this notice.")

        if module.get("amplifiers"):
            st.markdown("**Eligibility Amplifiers**")
            for amplifier in module["amplifiers"]:
                with st.container(border=True):
                    st.markdown(f"**{amplifier['label']}**")
                    st.caption(f"Points: {amplifier['points']}")
                    if amplifier.get("evidence"):
                        st.caption(", ".join(amplifier["evidence"]))

        if module.get("weakening_factors"):
            st.markdown("**Weakening Factors**")
            for weakening in module["weakening_factors"]:
                with st.container(border=True):
                    st.markdown(f"**{weakening['label']}**")
                    st.caption(f"Points: {weakening['points']}")
                    if weakening.get("evidence"):
                        st.caption(", ".join(weakening["evidence"]))


def _render_notice_detail(notice_id: str | None) -> None:
    st.subheader("Notice Detail", anchor=False)
    if not notice_id:
        st.info("Choose a tender from the Results view first.")
        return

    detail = load_notice_detail(notice_id)
    if detail is None:
        st.error("The selected notice could not be found.")
        return

    st.markdown(f"### {detail['title']}")
    st.caption(
        f"{detail['publication_number']} | {detail['buyer'] or 'Unknown buyer'} | "
        f"{detail['buyer_country'] or 'N/A'} | Source: {_notice_source_label(detail)}"
    )

    _render_stat_cards(
        [
            {
                "label": "Score",
                "value": str(detail["score"]),
                "note": "Deterministic F2-fit score",
            },
            {
                "label": "Fit",
                "value": _display_value(detail["fit_label"]),
                "note": "Overall fit classification",
            },
            {
                "label": "Priority",
                "value": _display_value(detail["priority_bucket"]),
                "note": "Recommended review urgency",
            },
            {
                "label": "Confidence",
                "value": _display_value(detail["confidence_indicator"]),
                "note": "Signal quality from extracted evidence",
            },
        ]
    )

    _render_download_controls(detail)
    _render_checklist_cross_reference(detail)

    meta_col, assessment_col = st.columns([0.42, 0.58], gap="large")
    with meta_col:
        with st.container(border=True):
            st.markdown("#### Metadata")
            st.markdown(
                f"""
                <div class="cb-detail-block">
                  <div class="cb-detail-line"><strong>Notice Type:</strong> {html.escape(detail['notice_type'] or 'Unknown')}</div>
                  <div class="cb-detail-line"><strong>Procedure Type:</strong> {html.escape(detail['procedure_type'] or 'Unknown')}</div>
                  <div class="cb-detail-line"><strong>Publication Date:</strong> {html.escape(format_date(detail['publication_date']))}</div>
                  <div class="cb-detail-line"><strong>Deadline:</strong> {html.escape(format_datetime(detail['deadline'], settings.ui_timezone))}</div>
                  <div class="cb-detail-line"><strong>Contract Duration:</strong> {html.escape(detail['contract_duration'] or 'Unknown')}</div>
                  <div class="cb-detail-line"><strong>Place of Performance:</strong> {html.escape(detail['place_of_performance'] or 'Unknown')}</div>
                  <div class="cb-detail-line"><strong>CPV Codes:</strong> {html.escape(', '.join(detail['cpv_codes']) if detail['cpv_codes'] else 'None')}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    with assessment_col:
        with st.container(border=True):
            st.markdown("#### Fit Assessment")
            st.write(detail["reasoning"] or "No reasoning available.")
            if detail["qualification_questions"]:
                st.markdown("**Qualification Questions**")
                for question in detail["qualification_questions"]:
                    st.write(f"- {question}")

    _render_keyword_evidence_module(detail)

    breakdown_col, notes_col = st.columns([0.6, 0.4], gap="large")
    with breakdown_col:
        st.markdown("#### Score Breakdown")
        for rule in detail["score_breakdown"]:
            with st.container(border=True):
                rule_cols = st.columns([0.72, 0.28], gap="small")
                rule_cols[0].markdown(f"**{rule['label']}**")
                rule_cols[1].metric("Points", rule["points"])
                st.caption(", ".join(rule["evidence"]) if rule["evidence"] else "No evidence attached.")

    with notes_col:
        st.markdown("#### Analyst Notes")
        if detail["notes"]:
            for note in detail["notes"]:
                with st.container(border=True):
                    st.write(note["note_text"])
                    st.caption(
                        f"{note['user_display_name']} | {format_datetime(note['created_at'], settings.ui_timezone)}"
                    )
        else:
            st.info("No analyst notes stored for this notice yet.")

    with st.expander("Raw TED Payload"):
        st.json(detail["raw_payload_json"])


def main() -> None:
    _apply_theme()
    _render_banner()

    views = ["Dashboard", "Live Scan", "Results", "Notice Detail"]
    active_view = st.session_state.get("active_view", "Dashboard")
    if active_view not in views:
        active_view = "Dashboard"

    _render_sidebar_brand()
    st.sidebar.markdown("## Navigation")
    current_view = st.sidebar.radio(
        "View",
        options=views,
        index=views.index(active_view),
    )
    st.session_state["active_view"] = current_view
    st.sidebar.markdown("---")
    st.sidebar.caption(
        "Temporary Streamlit shell. FastAPI remains the canonical production backend, and live scans use TED's public API."
    )

    if current_view == "Dashboard":
        _render_dashboard()
    elif current_view == "Live Scan":
        _render_live_scan()
    elif current_view == "Results":
        _render_results()
    else:
        notices, _ = _render_filters()
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
                "Choose a tender",
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


if __name__ == "__main__":
    main()
