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
from app.services.rescoring import rescore_outdated_notices
from app.services.tender_checklist import TenderChecklistService
from app.services.ted_client import TedApiClient
from app.services.ted_documents import DocumentSpec, TedDocumentService
from app.utils import countries as country_utils
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
        @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&display=swap');
        :root {
            --cb-bg: #f4f7fb;
            --cb-bg-soft: #edf3f9;
            --cb-surface: #ffffff;
            --cb-surface-2: #f8fbff;
            --cb-surface-3: #eef4fb;
            --cb-line: #dbe4f0;
            --cb-text: #142033;
            --cb-text-soft: #4d627c;
            --cb-text-dim: #73849c;
            --cb-accent: #2f67d8;
            --cb-accent-2: #5b8def;
            --cb-good: #1f8a63;
            --cb-watch: #a87006;
            --cb-risk: #c75454;
            --cb-sidebar: #0f1b2d;
        }
        html, body, [class*="css"] {
            font-family: "IBM Plex Sans", "Segoe UI", sans-serif;
        }
        .stApp,
        [data-testid="stAppViewContainer"],
        [data-testid="stAppViewContainer"] > .main,
        [data-testid="stMain"] {
            background:
                radial-gradient(circle at top left, rgba(47, 103, 216, 0.06), transparent 22%),
                linear-gradient(180deg, #f6f8fc 0%, #f3f6fb 100%);
            color: var(--cb-text);
        }
        [data-testid="stHeader"] {
            background: rgba(255, 255, 255, 0.92);
            border-bottom: 1px solid var(--cb-line);
        }
        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, #0f1b2d 0%, #14233a 100%);
            border-right: 1px solid rgba(255, 255, 255, 0.08);
            min-width: 250px !important;
            max-width: 250px !important;
        }
        [data-testid="stSidebar"] * {
            color: #edf4ff;
        }
        [data-testid="stSidebar"] [data-testid="stExpander"] {
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid rgba(255, 255, 255, 0.08);
        }
        [data-testid="stSidebar"] div[data-baseweb="input"] > div,
        [data-testid="stSidebar"] div[data-baseweb="select"] > div,
        [data-testid="stSidebar"] div[data-baseweb="textarea"] > div,
        [data-testid="stSidebar"] .stDateInput > div > div,
        [data-testid="stSidebar"] .stNumberInput > div > div {
            background: rgba(255, 255, 255, 0.04);
            border: 1px solid rgba(255, 255, 255, 0.12);
            color: #edf4ff;
        }
        [data-testid="stSidebar"] input,
        [data-testid="stSidebar"] textarea {
            color: #edf4ff !important;
        }
        [data-testid="stSidebarNav"] {
            display: none;
        }
        .main .block-container {
            max-width: 1120px;
            padding-top: 1rem;
            padding-bottom: 2.2rem;
        }
        h1, h2, h3, h4, h5, h6 {
            color: var(--cb-text);
            font-family: "IBM Plex Sans", sans-serif;
            letter-spacing: -0.02em;
        }
        p, li, label, span, div {
            color: inherit;
        }
        [data-testid="stMarkdownContainer"] p,
        [data-testid="stMarkdownContainer"] li {
            color: inherit;
        }
        div[data-testid="stMetric"] {
            background: var(--cb-surface);
            border: 1px solid var(--cb-line);
            border-radius: 14px;
            padding: 0.85rem 0.95rem;
            box-shadow: 0 4px 18px rgba(20, 32, 51, 0.04);
        }
        div[data-testid="stMetricLabel"] p {
            color: var(--cb-text-dim);
            font-size: 0.72rem;
            text-transform: uppercase;
            letter-spacing: 0.12em;
        }
        div[data-testid="stMetricValue"] {
            color: var(--cb-text);
        }
        div[data-testid="stForm"],
        div[data-testid="stVerticalBlockBorderWrapper"] {
            background: var(--cb-surface);
            border: 1px solid var(--cb-line);
            border-radius: 14px;
            box-shadow: 0 4px 18px rgba(20, 32, 51, 0.04);
        }
        div[data-testid="stForm"] {
            padding: 0.95rem 1rem 1rem;
        }
        div[data-baseweb="input"] > div,
        div[data-baseweb="select"] > div,
        div[data-baseweb="textarea"] > div,
        .stDateInput > div > div,
        .stNumberInput > div > div {
            background: #ffffff;
            border: 1px solid var(--cb-line);
            border-radius: 10px;
            color: var(--cb-text);
        }
        input, textarea {
            color: var(--cb-text) !important;
        }
        .stButton > button,
        .stDownloadButton > button {
            background: var(--cb-accent);
            color: #f7fbff;
            border: 1px solid #2a59bb;
            border-radius: 10px;
            min-height: 2.6rem;
            font-weight: 700;
            letter-spacing: 0.01em;
            box-shadow: none;
        }
        .stButton > button:hover,
        .stDownloadButton > button:hover {
            background: #2556bb;
            border-color: #214ea9;
            color: #ffffff;
        }
        .stLinkButton a {
            background: #ffffff;
            color: var(--cb-text);
            border: 1px solid var(--cb-line);
            border-radius: 10px;
            min-height: 2.6rem;
            font-weight: 700;
            letter-spacing: 0.01em;
        }
        .stLinkButton a:hover {
            background: #f7faff;
            border-color: #c8d7ea;
            color: var(--cb-text);
        }
        .stAlert {
            border-radius: 20px;
        }
        [data-baseweb="tab-list"] {
            gap: 0.5rem;
            background: transparent;
        }
        button[data-baseweb="tab"] {
            height: 2.6rem;
            border-radius: 999px;
            background: #f2f6fb;
            border: 1px solid #dbe4f0;
            color: var(--cb-text-soft);
            padding: 0 1rem;
        }
        button[data-baseweb="tab"][aria-selected="true"] {
            background: #eaf1ff;
            border-color: #bfd2f5;
            color: #17315f;
        }
        [data-testid="stExpander"] {
            background: var(--cb-surface);
            border: 1px solid var(--cb-line);
            border-radius: 12px;
        }
        .cb-shell-hero {
            border: 1px solid var(--cb-line);
            border-radius: 14px;
            padding: 0.85rem 1rem;
            margin-bottom: 0.9rem;
            background: var(--cb-surface);
        }
        .cb-shell-grid {
            display: block;
        }
        .cb-shell-kicker,
        .cb-panel-kicker,
        .cb-sidebar-line {
            color: var(--cb-accent);
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 0.16em;
            margin-bottom: 0.45rem;
            font-weight: 700;
        }
        .cb-shell-title {
            margin: 0;
            font-size: clamp(1.45rem, 2vw, 2.05rem);
            line-height: 1.12;
            max-width: none;
        }
        .cb-shell-copy,
        .cb-panel-copy {
            color: var(--cb-text-soft);
            line-height: 1.5;
            font-size: 0.92rem;
            max-width: 60rem;
            margin-top: 0.35rem;
            margin-bottom: 0;
        }
        .cb-panel-head {
            margin-bottom: 0.45rem;
        }
        .cb-panel-title {
            color: var(--cb-text);
            font-family: "IBM Plex Sans", sans-serif;
            font-size: 1.02rem;
            line-height: 1.14;
            margin: 0;
        }
        .cb-signal-card {
            min-height: 7rem;
            padding: 0.85rem 0.95rem;
            border-radius: 14px;
            border: 1px solid var(--cb-line);
            background: var(--cb-surface);
            box-shadow: 0 4px 18px rgba(20, 32, 51, 0.04);
        }
        .cb-signal-label {
            color: var(--cb-text-dim);
            font-size: 0.72rem;
            text-transform: uppercase;
            letter-spacing: 0.14em;
            font-weight: 700;
        }
        .cb-signal-value {
            margin-top: 0.55rem;
            color: var(--cb-text);
            font-family: "Space Grotesk", "IBM Plex Sans", sans-serif;
            font-size: clamp(1.4rem, 1.7vw, 1.95rem);
            font-weight: 700;
            line-height: 1;
        }
        .cb-signal-note {
            margin-top: 0.55rem;
            color: var(--cb-text-soft);
            line-height: 1.45;
            font-size: 0.84rem;
        }
        .cb-sidebar-brand {
            position: relative;
            padding: 0.3rem 0 0.8rem 0;
            margin-bottom: 0.75rem;
            border-bottom: 1px solid rgba(255, 255, 255, 0.08);
        }
        .cb-sidebar-mark {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 2.5rem;
            height: 2.5rem;
            border-radius: 50%;
            background: radial-gradient(circle at 30% 30%, #8fd0ff 0%, #4b8ef4 46%, #244c82 100%);
            color: #08111d;
            font-family: "Space Grotesk", "IBM Plex Sans", sans-serif;
            font-size: 0.8rem;
            font-weight: 700;
            margin-bottom: 0.55rem;
            box-shadow: 0 0 0 6px rgba(75, 142, 244, 0.08);
        }
        .cb-sidebar-title {
            color: var(--cb-text);
            font-family: "IBM Plex Sans", sans-serif;
            font-size: 0.95rem;
            line-height: 1.08;
            margin-bottom: 0;
        }
        .cb-sidebar-subtitle {
            color: var(--cb-text-soft);
            font-size: 0.78rem;
            line-height: 1.35;
        }
        .cb-badge {
            display: inline-flex;
            align-items: center;
            padding: 0.3rem 0.6rem;
            border-radius: 999px;
            border: 1px solid #d6e1f0;
            font-size: 0.7rem;
            font-weight: 700;
            line-height: 1;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            background: #f4f8ff;
            color: #395272;
        }
        .cb-badge-source { color: var(--cb-accent); border-color: #c8d8f8; background: #edf4ff; }
        .cb-badge-fit { color: #17315f; }
        .cb-badge-priority { color: #17315f; }
        .cb-badge-good { color: var(--cb-good); border-color: #cce9dd; background: #effaf5; }
        .cb-badge-watch { color: var(--cb-watch); border-color: #efdcb6; background: #fff8ea; }
        .cb-badge-alert { color: var(--cb-risk); border-color: #f1cdcd; background: #fff2f2; }
        .cb-badge-neutral { color: var(--cb-text-dim); }
        .cb-chip-row {
            display: flex;
            flex-wrap: wrap;
            gap: 0.42rem;
            margin-top: 0.75rem;
        }
        .cb-chip {
            display: inline-flex;
            align-items: center;
            padding: 0.32rem 0.62rem;
            border-radius: 999px;
            background: #f3f7fc;
            border: 1px solid #d9e3ef;
            color: #48617d;
            font-size: 0.77rem;
            font-weight: 600;
            line-height: 1;
        }
        .cb-dossier {
            position: relative;
            overflow: hidden;
            border-radius: 14px;
            border: 1px solid var(--cb-line);
            background: var(--cb-surface);
            box-shadow: 0 6px 22px rgba(20, 32, 51, 0.05);
            padding: 1rem;
            margin-bottom: 0.9rem;
        }
        .cb-dossier::before {
            content: "";
            position: absolute;
            inset: 0 auto 0 0;
            width: 4px;
            background: #cedaec;
        }
        .cb-dossier-high::before { background: #2f67d8; }
        .cb-dossier-good::before { background: #1f8a63; }
        .cb-dossier-watch::before { background: #a87006; }
        .cb-dossier-ignore::before { background: #8a98ab; }
        .cb-dossier-conditional::before { background: #c75454; }
        .cb-dossier-grid {
            display: grid;
            grid-template-columns: minmax(120px, 0.18fr) minmax(0, 1fr);
            gap: 0.9rem;
            align-items: start;
        }
        .cb-dossier-rail {
            padding-right: 0.85rem;
            border-right: 1px solid #e6edf5;
        }
        .cb-dossier-score {
            color: var(--cb-text);
            font-family: "IBM Plex Sans", sans-serif;
            font-size: 2.2rem;
            line-height: 0.95;
            font-weight: 700;
            margin-bottom: 0.22rem;
        }
        .cb-dossier-score-label {
            color: var(--cb-text-dim);
            font-size: 0.76rem;
            text-transform: uppercase;
            letter-spacing: 0.14em;
            margin-bottom: 0.85rem;
        }
        .cb-dossier-rail-line {
            margin-bottom: 0.7rem;
        }
        .cb-dossier-rail-key {
            color: var(--cb-text-dim);
            font-size: 0.72rem;
            text-transform: uppercase;
            letter-spacing: 0.12em;
            margin-bottom: 0.15rem;
        }
        .cb-dossier-rail-value {
            color: var(--cb-text);
            font-size: 0.94rem;
            line-height: 1.45;
            font-weight: 600;
        }
        .cb-dossier-topline {
            display: flex;
            flex-wrap: wrap;
            gap: 0.42rem;
            margin-bottom: 0.8rem;
        }
        .cb-dossier-meta {
            color: var(--cb-text-dim);
            font-size: 0.84rem;
            letter-spacing: 0.03em;
            margin-bottom: 0.45rem;
        }
        .cb-dossier-title {
            color: var(--cb-text);
            font-family: "Space Grotesk", "IBM Plex Sans", sans-serif;
            font-size: 1.32rem;
            line-height: 1.18;
            margin-bottom: 0.55rem;
        }
        .cb-dossier-summary {
            color: var(--cb-text-soft);
            font-size: 0.98rem;
            line-height: 1.65;
            margin-bottom: 0.45rem;
            max-width: 60rem;
        }
        .cb-fact-list {
            display: grid;
            gap: 0.75rem;
        }
        .cb-fact-item {
            border-bottom: 1px solid rgba(132, 166, 214, 0.09);
            padding-bottom: 0.7rem;
        }
        .cb-fact-item:last-child {
            border-bottom: none;
            padding-bottom: 0;
        }
        .cb-fact-label {
            color: var(--cb-text-dim);
            font-size: 0.73rem;
            text-transform: uppercase;
            letter-spacing: 0.12em;
            margin-bottom: 0.18rem;
        }
        .cb-fact-value {
            color: var(--cb-text);
            font-size: 0.98rem;
            line-height: 1.55;
        }
        .cb-note-card {
            border: 1px solid var(--cb-line);
            border-radius: 14px;
            padding: 0.9rem 1rem;
            background: var(--cb-surface);
            box-shadow: 0 4px 18px rgba(20, 32, 51, 0.04);
        }
        .cb-note-title {
            color: var(--cb-text);
            font-size: 1rem;
            font-weight: 700;
            margin-bottom: 0.22rem;
        }
        .cb-note-copy {
            color: var(--cb-text-soft);
            line-height: 1.55;
            font-size: 0.92rem;
        }
        .cb-checklist-table-wrap {
            overflow-x: auto;
            margin-top: 0.9rem;
        }
        .cb-checklist-table {
            width: 100%;
            border-collapse: separate;
            border-spacing: 0;
            background: #ffffff;
            border: 1px solid var(--cb-line);
            border-radius: 14px;
            overflow: hidden;
        }
        .cb-checklist-table thead th {
            background: #f5f8fc;
            color: var(--cb-text-dim);
            font-size: 0.75rem;
            font-weight: 700;
            letter-spacing: 0.13em;
            text-transform: uppercase;
            padding: 0.95rem 1rem;
            text-align: left;
            border-bottom: 1px solid var(--cb-line);
        }
        .cb-checklist-table tbody tr:nth-child(even) {
            background: #fbfdff;
        }
        .cb-checklist-table tbody tr:hover {
            background: #f3f7fc;
        }
        .cb-checklist-table td {
            padding: 0.95rem 1rem;
            border-top: 1px solid #edf2f7;
            vertical-align: top;
            font-size: 0.92rem;
            line-height: 1.55;
            color: var(--cb-text-soft);
            word-break: break-word;
        }
        .cb-checklist-table td.cb-checklist-col-item {
            width: 20%;
            font-weight: 700;
            color: var(--cb-text);
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
            color: var(--cb-text-dim);
        }
        .cb-result-card {
            border: 1px solid var(--cb-line);
            border-left: 4px solid #d7e2f0;
            border-radius: 14px;
            background: var(--cb-surface);
            padding: 1rem 1.05rem;
            margin-bottom: 0.85rem;
            box-shadow: 0 4px 18px rgba(20, 32, 51, 0.04);
        }
        .cb-result-card.cb-dossier-high { border-left-color: #2f67d8; }
        .cb-result-card.cb-dossier-good { border-left-color: #1f8a63; }
        .cb-result-card.cb-dossier-watch { border-left-color: #a87006; }
        .cb-result-card.cb-dossier-ignore { border-left-color: #8a98ab; }
        .cb-result-card.cb-dossier-conditional { border-left-color: #c75454; }
        .cb-result-head {
            display: grid;
            grid-template-columns: 84px minmax(0, 1fr);
            gap: 1rem;
            align-items: start;
        }
        .cb-result-score-block {
            background: #f5f8fd;
            border: 1px solid #dde6f2;
            border-radius: 12px;
            padding: 0.8rem 0.7rem;
            text-align: center;
        }
        .cb-result-score {
            color: var(--cb-text);
            font-family: "IBM Plex Sans", sans-serif;
            font-size: 1.8rem;
            font-weight: 700;
            line-height: 1;
        }
        .cb-result-score-label {
            color: var(--cb-text-dim);
            font-size: 0.72rem;
            text-transform: uppercase;
            letter-spacing: 0.12em;
            margin-top: 0.25rem;
        }
        .cb-result-main {
            min-width: 0;
        }
        .cb-result-title {
            color: var(--cb-text);
            font-family: "IBM Plex Sans", sans-serif;
            font-size: 1.08rem;
            line-height: 1.28;
            margin: 0.35rem 0 0.35rem 0;
        }
        .cb-result-meta {
            color: var(--cb-text-dim);
            font-size: 0.85rem;
            line-height: 1.55;
        }
        .cb-result-summary {
            color: var(--cb-text-soft);
            font-size: 0.94rem;
            line-height: 1.6;
            margin-top: 0.55rem;
        }
        @media (max-width: 980px) {
            .cb-shell-grid,
            .cb-dossier-grid,
            .cb-result-head {
                grid-template-columns: 1fr;
            }
            .cb-dossier-rail {
                padding-right: 0;
                padding-bottom: 0.9rem;
                border-right: none;
                border-bottom: 1px solid #e6edf5;
            }
            .cb-signal-card {
                min-height: auto;
            }
            .cb-result-score-block {
                max-width: 88px;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


@st.cache_data(ttl=60, show_spinner=False)
def load_dashboard_payload() -> dict[str, Any]:
    session = get_session_factory()()
    try:
        rescore_outdated_notices(session)
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


def _display_value(value: Any) -> str:
    if value is None:
        return "N/A"
    raw = getattr(value, "value", value)
    if raw is None:
        return "N/A"
    return str(raw)


def _normalize_country_filter_values(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [part.strip().upper() for part in value.split(",") if part.strip()]
    if isinstance(value, (list, tuple, set)):
        return [str(part).strip().upper() for part in value if str(part).strip()]
    return []


def _score_out_of_ten(value: Any) -> float:
    try:
        return max(0.0, min(10.0, round(float(value or 0) / 10.0, 1)))
    except (TypeError, ValueError):
        return 0.0


def _format_score_out_of_ten(value: Any, *, include_suffix: bool = False) -> str:
    score = _score_out_of_ten(value)
    formatted = f"{score:.1f}"
    return f"{formatted}/10" if include_suffix else formatted


def _country_display_label(value: str | None) -> str:
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


def _country_filter_options() -> list[tuple[str, str]]:
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


def _escape_text(value: Any) -> str:
    return html.escape(_display_value(value))


def _truncate_text(value: str | None, *, limit: int = 220) -> str:
    if not value:
        return ""
    cleaned = " ".join(str(value).split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1].rstrip() + "…"


def _render_pill(label: str, tone: str) -> str:
    safe_label = html.escape(label)
    return f"<span class='cb-badge cb-badge-{tone}'>{safe_label}</span>"


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


def _render_section_header(kicker: str, title: str, copy: str | None = None) -> None:
    kicker_html = f"<div class='cb-panel-kicker'>{html.escape(kicker)}</div>" if kicker else ""
    body = f"<p class='cb-panel-copy'>{html.escape(copy)}</p>" if copy else ""
    st.markdown(
        f"""
        <div class="cb-panel-head">
          {kicker_html}
          <h2 class="cb-panel-title">{html.escape(title)}</h2>
          {body}
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_stat_cards(cards: list[dict[str, str]]) -> None:
    if not cards:
        return

    per_row = 4
    for start in range(0, len(cards), per_row):
        row_cards = cards[start : start + per_row]
        columns = st.columns(len(row_cards), gap="medium")
        for column, card in zip(columns, row_cards):
            with column:
                st.markdown(
                    f"""
                    <div class="cb-signal-card">
                      <div class="cb-signal-label">{html.escape(card["label"])}</div>
                      <div class="cb-signal-value">{html.escape(card["value"])}</div>
                      <div class="cb-signal-note">{html.escape(card["note"])}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )


def _render_profile_cards() -> None:
    profiles = get_search_profiles_registry().profiles
    if not profiles:
        return

    keyword_pack = get_keyword_pack_resource()
    positive_groups = keyword_pack.positive_group_map()

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
                            + "".join(_render_chip(label) for label in category_labels)
                            + "</div>",
                            unsafe_allow_html=True,
                        )
                    elif profile.search_terms:
                        st.markdown(
                            "<div class='cb-chip-row'>"
                            + "".join(_render_chip(term) for term in profile.search_terms)
                            + "</div>",
                            unsafe_allow_html=True,
                        )


def _render_recent_scan_cards(recent_scans: list[dict[str, Any]]) -> None:
    for scan in recent_scans:
        with st.container(border=True):
            st.markdown(
                f"""
                <div class="cb-note-title">{html.escape(scan['status'])}</div>
                <div class="cb-note-copy">Started {html.escape(format_datetime(scan['started_at'], settings.ui_timezone))}</div>
                """,
                unsafe_allow_html=True,
            )
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
    if filter_state.get("relevant_only"):
        chips.append("Relevant to F2 Only")
    if filter_state.get("min_days_remaining") not in {None, 0}:
        chips.append(f"Deadline >= {filter_state['min_days_remaining']} days")
    selected_countries = _normalize_country_filter_values(filter_state.get("countries", filter_state.get("country")))
    if selected_countries:
        country_labels = [_country_display_label(country) for country in selected_countries]
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
        chips.append(f"Score >= {_format_score_out_of_ten(score_min, include_suffix=True)}")
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
    review_now = high_fit + good_fit

    return [
        {
            "label": "Matching Results",
            "value": str(total_matches),
            "note": f"{len(notices)} notices loaded into the current review surface.",
        },
        {
            "label": "Average Score",
            "value": _format_score_out_of_ten(avg_score, include_suffix=True),
            "note": f"Highest current score: {_format_score_out_of_ten(highest_score, include_suffix=True)}",
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


def _render_sidebar_brand() -> None:
    st.sidebar.markdown(
        """
        <div class="cb-sidebar-brand">
          <div class="cb-sidebar-line">cBrain</div>
          <div class="cb-sidebar-mark">F2</div>
          <div class="cb-sidebar-title">TED F2 Intelligence</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _default_filter_state() -> dict[str, Any]:
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
        top_line_badges.append(_render_pill("Timing review", "watch"))

    buyer = notice.get("buyer") or "Unknown buyer"
    country = notice.get("buyer_country") or "N/A"
    publication = notice.get("publication_number") or "Unknown publication"
    deadline = format_datetime(notice.get("deadline"), settings.ui_timezone)
    publication_date = format_date(notice.get("publication_date"))
    title = notice.get("title") or "Untitled notice"
    summary_text = _truncate_text(
        notice.get("reasoning") or notice.get("summary") or "No summary available.",
        limit=240,
    )
    keyword_chips = "".join(_render_chip(label) for label in _notice_keyword_labels(notice))
    if not keyword_chips:
        keyword_chips = _render_chip("No keyword evidence captured yet")
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
        <div class="cb-result-card {card_class}">
          <div class="cb-result-head">
            <div class="cb-result-score-block">
              <div class="cb-result-score">{_format_score_out_of_ten(notice['score'])}</div>
              <div class="cb-result-score-label">Score / 10</div>
            </div>
            <div class="cb-result-main">
              <div class="cb-dossier-topline">
              {''.join(top_line_badges)}
              </div>
              <div class="cb-result-title">{html.escape(title)}</div>
              <div class="cb-result-meta">{html.escape(" | ".join(meta_parts))}</div>
              <div class="cb-result-summary">{html.escape(summary_text)}</div>
              <div class="cb-chip-row">{keyword_chips}</div>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    action_cols = st.columns([1, 1], gap="small")
    official_url = _resolve_official_notice_url(notice)
    if official_url:
        action_cols[0].link_button("Open TED notice", official_url, width="stretch")
    elif notice.get("is_demo_record"):
        action_cols[0].caption("No live TED link")
    else:
        action_cols[0].caption("No official TED URL")

    if action_cols[1].button("Review notice", key=f"review_notice_{card_index}_{notice['id']}", width="stretch"):
        _open_notice_detail(notice["id"])
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
            exclude_old=False,
            include_soft_locks=True,
            page_size=settings.ted_default_page_size,
            max_pages=1,
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


def _render_banner(current_view: str) -> None:
    storage_state = initialize_streamlit_storage()
    purged_demo_notices = storage_state.get("purged_demo_notices", 0)
    view_copy = {
        "Dashboard": {
            "kicker": "Opportunity Briefing",
            "title": "Dashboard",
            "copy": "Live TED opportunity picture for F2 review.",
        },
        "Live Scan": {
            "kicker": "Acquisition Workspace",
            "title": "Live TED Scan",
            "copy": "Run an official TED search and refresh the review queue.",
        },
        "Results": {
            "kicker": "Signal Board",
            "title": "Results",
            "copy": "Review scored notices.",
        },
        "Notice Detail": {
            "kicker": "Opportunity Dossier",
            "title": "Notice Detail",
            "copy": "Inspect one tender in depth.",
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
        st.caption("Scan uses the default review settings.")

        submitted = st.form_submit_button("Run live TED scan", width="stretch")

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


def _render_dashboard() -> None:
    payload = load_dashboard_payload()
    metrics = payload["metrics"]
    recent_scans = payload["recent_scans"]
    top_notices = payload["top_notices"]

    _render_section_header(
        "",
        "Dashboard",
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

    scans_tab, queue_tab = st.tabs(["Recent scan runs", "Immediate attention"])
    with scans_tab:
        if recent_scans:
            _render_recent_scan_cards(recent_scans)
        else:
            st.info("No scan history found.")

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
                    if action_cols[1].button("Inspect", key=f"inspect_top_{notice['id']}", width="stretch"):
                        _open_notice_detail(notice["id"])
                        st.rerun()
                    official_url = _resolve_official_notice_url(notice)
                    if official_url:
                        action_cols[2].link_button("TED notice", official_url, width="stretch")
        else:
            st.info("No stored notices available yet.")


def _render_filters(*, render_sidebar: bool = True) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    filter_state = dict(st.session_state.get("results_filter_state", _default_filter_state()))
    if filter_state.get("min_days_remaining") is None:
        filter_state["min_days_remaining"] = 0
    selected_countries = _normalize_country_filter_values(filter_state.get("countries", filter_state.get("country")))
    filter_state["countries"] = selected_countries

    if not render_sidebar:
        return _load_notices_for_filter_state(filter_state)

    st.sidebar.markdown("### Signal Filters")
    st.sidebar.caption("Use a few simple filters to narrow the review queue.")
    country_options = _country_filter_options()
    country_labels = ["Any"] + [label for label, _ in country_options]
    country_code_by_label = {"Any": ""}
    country_code_by_label.update({label: code for label, code in country_options})
    selected_country = selected_countries[0] if selected_countries else ""
    selected_country_label = next((label for label, code in country_options if code == selected_country), "Any")

    selected_country_label = st.sidebar.selectbox(
        "Country",
        options=country_labels,
        index=country_labels.index(selected_country_label),
    )
    countries = [country_code_by_label[selected_country_label]] if country_code_by_label[selected_country_label] else []
    search = st.sidebar.text_input("Search", value=filter_state.get("search") or "").strip() or None
    minimum_score_ten = st.sidebar.slider(
        "Minimum Score",
        min_value=0.0,
        max_value=10.0,
        value=float(int(filter_state.get("score_min") or 0) / 10),
        step=0.5,
    )
    relevant_only = st.sidebar.checkbox("Relevant to F2 Only", value=bool(filter_state.get("relevant_only")))

    with st.sidebar.expander("More Filters", expanded=False):
        fit_options = ["Any", "YES", "CONDITIONAL", "NO"]
        priority_options = ["Any", "HIGH", "GOOD", "WATCHLIST", "IGNORE"]
        confidence_options = ["Any", "HIGH", "MEDIUM", "LOW"]
        fit_label = st.selectbox(
            "Fit Label",
            fit_options,
            index=fit_options.index(filter_state.get("fit_label") or "Any"),
        )
        priority_bucket = st.selectbox(
            "Priority Bucket",
            priority_options,
            index=priority_options.index(filter_state.get("priority_bucket") or "Any"),
        )
        confidence_indicator = st.selectbox(
            "Confidence",
            confidence_options,
            index=confidence_options.index(filter_state.get("confidence_indicator") or "Any"),
        )
        min_days_remaining = st.number_input(
            "Minimum Days Remaining",
            min_value=0,
            max_value=30,
            value=int(filter_state.get("min_days_remaining") or 0),
            step=1,
        )
        hard_lock_only = st.checkbox("Hard Lock Only", value=bool(filter_state.get("hard_lock_only")))
        saved_only = st.checkbox("Saved Only", value=bool(filter_state.get("saved_only")))
        include_dismissed = st.checkbox("Include Dismissed", value=bool(filter_state.get("include_dismissed")))

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
    if st.session_state.get("results_return_view") == "Live Scan":
        if nav_cols[0].button("Back to Scan", key="results_back_to_scan", width="stretch"):
            _go_to_view("Live Scan")
            st.rerun()

    _render_section_header(
        "",
        "Results",
    )
    total_matches = filter_state["total_matches"]

    if not notices:
        st.warning("No notices match the current filters.")
        return notices

    st.caption(f"{total_matches} notices match the current filter posture. {len(notices)} are loaded right now.")

    active_filter_chips = _summarize_results_filters(filter_state)
    if active_filter_chips:
        with st.expander("Active filters", expanded=False):
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
    _render_section_header(
        "Official Source Access",
        "TED notice and document actions",
        "Use the official TED notice route for live review, or fetch the official PDF directly into the dossier workspace.",
    )

    if detail.get("is_demo_record"):
        st.info(
            "This record is not linked to a live TED notice, so official notice and document actions are unavailable."
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
    _render_section_header(
        "Tender Checklist",
        "Checklist cross-reference",
        "Cross-reference this opportunity against the cBrain East Africa tender checklist template. Answers are marked as filled, inferred, or review.",
    )

    state_key = f"show_checklist_{detail['id']}"
    button_cols = st.columns([0.34, 0.66])
    if button_cols[0].button("Run checklist cross-reference", key=f"run_checklist_{detail['id']}", width="stretch"):
        st.session_state[state_key] = True

    if not st.session_state.get(state_key):
        button_cols[1].caption("Generate a structured checklist cross-reference for this tender.")
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

    st.caption("Reference table for structured tender review.")
    _render_checklist_table(report["items"])


def _render_keyword_evidence_module(detail: dict[str, Any]) -> None:
    module = detail.get("keyword_evidence_module") or {}
    _render_section_header(
        "Eligibility Evidence",
        "Keyword evidence",
        "Deterministic keyword evidence showing exactly why this opportunity was surfaced for F2 review.",
    )

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
    return_view = st.session_state.get("detail_return_view", "Results")
    nav_cols = st.columns([0.2, 0.8], gap="small")
    if nav_cols[0].button(f"Back to {return_view if return_view != 'Notice Detail' else 'Results'}", key="detail_back_button", width="stretch"):
        _go_to_view(return_view if return_view != "Notice Detail" else "Results")
        st.rerun()

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

    detail_badges = [
        _render_pill(_notice_source_label(detail), "source"),
        _render_pill(_display_value(detail["fit_label"]), "fit"),
        _render_pill(_display_value(detail["priority_bucket"]), "priority"),
    ]
    detail_card_class = _card_tone_class(detail) or "cb-dossier-high"
    if detail.get("hard_lock_detected"):
        detail_badges.append(_render_pill("Hard lock", "alert"))
    elif detail.get("viable_timing"):
        detail_badges.append(_render_pill("Timing viable", "good"))
    else:
        detail_badges.append(_render_pill("Timing review", "watch"))

    st.markdown(
        f"""
        <div class="cb-dossier {detail_card_class}" style="margin-top: 0.3rem;">
          <div class="cb-dossier-grid">
            <div class="cb-dossier-rail">
              <div class="cb-dossier-score">{_format_score_out_of_ten(detail['score'])}</div>
              <div class="cb-dossier-score-label">Score / 10</div>
              <div class="cb-dossier-rail-line">
                <div class="cb-dossier-rail-key">Confidence</div>
                <div class="cb-dossier-rail-value">{html.escape(_display_value(detail["confidence_indicator"]))}</div>
              </div>
              <div class="cb-dossier-rail-line">
                <div class="cb-dossier-rail-key">Deadline</div>
                <div class="cb-dossier-rail-value">{html.escape(format_datetime(detail["deadline"], settings.ui_timezone))}</div>
              </div>
              <div class="cb-dossier-rail-line">
                <div class="cb-dossier-rail-key">Country</div>
                <div class="cb-dossier-rail-value">{html.escape(detail['buyer_country'] or 'N/A')}</div>
              </div>
            </div>
            <div>
              <div class="cb-dossier-topline">{''.join(detail_badges)}</div>
              <div class="cb-dossier-meta">{html.escape(detail['publication_number'])} | {html.escape(detail['buyer'] or 'Unknown buyer')} | {html.escape(detail['buyer_country'] or 'N/A')}</div>
              <div class="cb-dossier-title">{html.escape(detail['title'])}</div>
              <div class="cb-dossier-summary">{html.escape(detail['reasoning'] or detail['summary'] or 'No summary available.')}</div>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    _render_stat_cards(
        [
            {
                "label": "Score",
                "value": _format_score_out_of_ten(detail["score"], include_suffix=True),
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
    overview_tab, keywords_tab, checklist_tab, audit_tab, raw_tab = st.tabs(
        ["Overview", "Eligibility Keywords", "Checklist", "Audit Trail", "Raw TED"]
    )

    with overview_tab:
        meta_col, assessment_col = st.columns([0.44, 0.56], gap="large")
        with meta_col:
            with st.container(border=True):
                _render_section_header(
                    "Notice Facts",
                    "Operational metadata",
                    "Core public tender facts normalised from TED for reviewer use.",
                )
                st.markdown(
                    f"""
                    <div class="cb-fact-list">
                      <div class="cb-fact-item"><div class="cb-fact-label">Notice type</div><div class="cb-fact-value">{html.escape(detail['notice_type'] or 'Unknown')}</div></div>
                      <div class="cb-fact-item"><div class="cb-fact-label">Procedure type</div><div class="cb-fact-value">{html.escape(detail['procedure_type'] or 'Unknown')}</div></div>
                      <div class="cb-fact-item"><div class="cb-fact-label">Publication date</div><div class="cb-fact-value">{html.escape(format_date(detail['publication_date']))}</div></div>
                      <div class="cb-fact-item"><div class="cb-fact-label">Deadline</div><div class="cb-fact-value">{html.escape(format_datetime(detail['deadline'], settings.ui_timezone))}</div></div>
                      <div class="cb-fact-item"><div class="cb-fact-label">Contract duration</div><div class="cb-fact-value">{html.escape(detail['contract_duration'] or 'Unknown')}</div></div>
                      <div class="cb-fact-item"><div class="cb-fact-label">Place of performance</div><div class="cb-fact-value">{html.escape(detail['place_of_performance'] or 'Unknown')}</div></div>
                      <div class="cb-fact-item"><div class="cb-fact-label">CPV codes</div><div class="cb-fact-value">{html.escape(', '.join(detail['cpv_codes']) if detail['cpv_codes'] else 'None')}</div></div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        with assessment_col:
            with st.container(border=True):
                _render_section_header(
                    "Assessment Readout",
                    "Why this opportunity matters",
                    "Use this narrative and the generated qualification prompts to decide whether the tender deserves cBrain pursuit.",
                )
                st.write(detail["reasoning"] or "No reasoning available.")
                if detail["qualification_questions"]:
                    st.markdown("**Qualification Questions**")
                    for question in detail["qualification_questions"]:
                        st.write(f"- {question}")
                else:
                    st.caption("No qualification questions were generated for this notice.")

    with keywords_tab:
        _render_keyword_evidence_module(detail)

    with checklist_tab:
        _render_checklist_cross_reference(detail)

    with audit_tab:
        breakdown_col, notes_col = st.columns([0.6, 0.4], gap="large")
        with breakdown_col:
            _render_section_header(
                "Scoring Audit",
                "Rule contributions",
                "Every rule contribution is stored to keep the fit decision explainable and reproducible.",
            )
            for rule in detail["score_breakdown"]:
                with st.container(border=True):
                    rule_cols = st.columns([0.72, 0.28], gap="small")
                    rule_cols[0].markdown(f"**{rule['label']}**")
                    rule_cols[1].metric("Points", rule["points"])
                    st.caption(", ".join(rule["evidence"]) if rule["evidence"] else "No evidence attached.")
        with notes_col:
            _render_section_header(
                "Analyst Notes",
                "Internal review notes",
                "Only internal analyst notes are shown here; the tender data itself stays centred on public notice metadata.",
            )
            if detail["notes"]:
                for note in detail["notes"]:
                    with st.container(border=True):
                        st.write(note["note_text"])
                        st.caption(
                            f"{note['user_display_name']} | {format_datetime(note['created_at'], settings.ui_timezone)}"
                        )
            else:
                st.info("No analyst notes stored for this notice yet.")

    with raw_tab:
        _render_section_header(
            "Payload Trace",
            "Raw TED payload",
            "Raw payload inspection is available for analysts who need to verify a field, translation artifact, or normalisation choice.",
        )
        st.json(detail["raw_payload_json"])


def main() -> None:
    _apply_theme()

    views = ["Dashboard", "Live Scan", "Results", "Notice Detail"]
    view_labels = {
        "Dashboard": "Dashboard",
        "Live Scan": "Scan",
        "Results": "Results",
        "Notice Detail": "Detail",
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
    elif current_view == "Results":
        _render_results()
    else:
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
