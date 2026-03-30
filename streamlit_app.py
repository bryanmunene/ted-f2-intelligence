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
        @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=Space+Grotesk:wght@500;700&display=swap');
        :root {
            --cb-bg: #06101b;
            --cb-bg-soft: #0a1625;
            --cb-surface: #0d192b;
            --cb-surface-2: #112239;
            --cb-surface-3: #152844;
            --cb-line: rgba(132, 166, 214, 0.22);
            --cb-text: #edf4ff;
            --cb-text-soft: #a9bdd9;
            --cb-text-dim: #7d93b1;
            --cb-accent: #4b8ef4;
            --cb-accent-2: #8fd0ff;
            --cb-good: #3da786;
            --cb-watch: #d6a457;
            --cb-risk: #e07b69;
            --cb-glow: 0 24px 54px rgba(0, 0, 0, 0.28);
        }
        html, body, [class*="css"] {
            font-family: "IBM Plex Sans", "Segoe UI", sans-serif;
        }
        .stApp,
        [data-testid="stAppViewContainer"],
        [data-testid="stAppViewContainer"] > .main,
        [data-testid="stMain"] {
            background:
                radial-gradient(circle at 8% 0%, rgba(75, 142, 244, 0.17), transparent 24%),
                radial-gradient(circle at 92% 0%, rgba(143, 208, 255, 0.12), transparent 22%),
                linear-gradient(180deg, #07111d 0%, #091321 42%, #0a1420 100%);
            color: var(--cb-text);
        }
        [data-testid="stHeader"] {
            background: rgba(6, 12, 21, 0.82);
            border-bottom: 1px solid rgba(132, 166, 214, 0.14);
            backdrop-filter: blur(16px);
        }
        [data-testid="stSidebar"] {
            background:
                linear-gradient(180deg, rgba(11, 23, 37, 0.98) 0%, rgba(12, 27, 44, 0.98) 44%, rgba(15, 34, 57, 0.98) 100%);
            border-right: 1px solid rgba(132, 166, 214, 0.12);
        }
        [data-testid="stSidebar"] * {
            color: var(--cb-text);
        }
        [data-testid="stSidebarNav"] {
            display: none;
        }
        .main .block-container {
            max-width: 1410px;
            padding-top: 1.05rem;
            padding-bottom: 3rem;
        }
        h1, h2, h3, h4, h5, h6 {
            color: var(--cb-text);
            font-family: "Space Grotesk", "IBM Plex Sans", sans-serif;
            letter-spacing: -0.03em;
        }
        p, li, label, span, div {
            color: inherit;
        }
        [data-testid="stMarkdownContainer"] p,
        [data-testid="stMarkdownContainer"] li {
            color: inherit;
        }
        div[data-testid="stMetric"] {
            background: linear-gradient(180deg, rgba(18, 33, 53, 0.96) 0%, rgba(10, 21, 36, 0.98) 100%);
            border: 1px solid var(--cb-line);
            border-radius: 22px;
            padding: 1rem 1.05rem;
            box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.03), var(--cb-glow);
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
            background: linear-gradient(180deg, rgba(16, 30, 48, 0.94) 0%, rgba(11, 22, 37, 0.98) 100%);
            border: 1px solid var(--cb-line);
            border-radius: 24px;
            box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.03), var(--cb-glow);
        }
        div[data-testid="stForm"] {
            padding: 1.1rem 1.15rem 1.15rem;
        }
        div[data-baseweb="input"] > div,
        div[data-baseweb="select"] > div,
        div[data-baseweb="textarea"] > div,
        .stDateInput > div > div,
        .stNumberInput > div > div {
            background: rgba(7, 17, 29, 0.98);
            border: 1px solid rgba(132, 166, 214, 0.18);
            border-radius: 14px;
            color: var(--cb-text);
        }
        input, textarea {
            color: var(--cb-text) !important;
        }
        .stButton > button,
        .stDownloadButton > button {
            background: linear-gradient(135deg, #4b8ef4 0%, #2a67be 100%);
            color: #f7fbff;
            border: 1px solid rgba(143, 208, 255, 0.28);
            border-radius: 999px;
            min-height: 2.8rem;
            font-weight: 700;
            letter-spacing: 0.02em;
            box-shadow: 0 18px 34px rgba(41, 89, 166, 0.24);
        }
        .stButton > button:hover,
        .stDownloadButton > button:hover {
            background: linear-gradient(135deg, #63a1ff 0%, #316fca 100%);
            border-color: rgba(143, 208, 255, 0.44);
            color: #ffffff;
        }
        .stLinkButton a {
            background: rgba(12, 27, 44, 0.86);
            color: var(--cb-text);
            border: 1px solid rgba(132, 166, 214, 0.18);
            border-radius: 999px;
            min-height: 2.8rem;
            font-weight: 700;
            letter-spacing: 0.02em;
        }
        .stLinkButton a:hover {
            background: rgba(18, 37, 59, 0.96);
            border-color: rgba(132, 166, 214, 0.3);
            color: #ffffff;
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
            background: rgba(12, 27, 44, 0.82);
            border: 1px solid rgba(132, 166, 214, 0.16);
            color: var(--cb-text-soft);
            padding: 0 1rem;
        }
        button[data-baseweb="tab"][aria-selected="true"] {
            background: linear-gradient(135deg, rgba(75, 142, 244, 0.18) 0%, rgba(19, 42, 74, 0.9) 100%);
            border-color: rgba(143, 208, 255, 0.3);
            color: var(--cb-text);
        }
        [data-testid="stExpander"] {
            background: linear-gradient(180deg, rgba(16, 30, 48, 0.94) 0%, rgba(11, 22, 37, 0.98) 100%);
            border: 1px solid var(--cb-line);
            border-radius: 20px;
        }
        .cb-shell-hero {
            position: relative;
            overflow: hidden;
            border: 1px solid rgba(132, 166, 214, 0.18);
            border-radius: 30px;
            padding: 1.5rem 1.55rem;
            margin-bottom: 1.2rem;
            background: linear-gradient(135deg, rgba(16, 29, 47, 0.98) 0%, rgba(9, 18, 31, 0.94) 44%, rgba(11, 26, 43, 0.98) 100%);
            box-shadow: var(--cb-glow);
        }
        .cb-shell-hero::before {
            content: "";
            position: absolute;
            inset: 0;
            background:
                linear-gradient(110deg, rgba(75, 142, 244, 0.12) 0%, transparent 34%),
                repeating-linear-gradient(90deg, rgba(132, 166, 214, 0.05) 0 1px, transparent 1px 76px);
            pointer-events: none;
        }
        .cb-shell-grid {
            position: relative;
            display: grid;
            grid-template-columns: minmax(0, 1.8fr) minmax(280px, 0.95fr);
            gap: 1.2rem;
            align-items: end;
        }
        .cb-shell-kicker,
        .cb-panel-kicker,
        .cb-sidebar-line {
            color: var(--cb-accent-2);
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 0.16em;
            margin-bottom: 0.45rem;
            font-weight: 700;
        }
        .cb-shell-title {
            margin: 0;
            font-size: clamp(2rem, 2.5vw, 3rem);
            line-height: 1.04;
            max-width: 9.5em;
        }
        .cb-shell-copy,
        .cb-panel-copy {
            color: var(--cb-text-soft);
            line-height: 1.6;
            font-size: 0.98rem;
            max-width: 60rem;
            margin-top: 0.75rem;
            margin-bottom: 0;
        }
        .cb-shell-aside {
            position: relative;
            border: 1px solid rgba(132, 166, 214, 0.14);
            border-radius: 24px;
            padding: 1rem 1.05rem;
            background: rgba(8, 17, 29, 0.68);
            backdrop-filter: blur(10px);
        }
        .cb-shell-aside-item {
            padding: 0.48rem 0;
            border-bottom: 1px solid rgba(132, 166, 214, 0.08);
        }
        .cb-shell-aside-item:last-child {
            border-bottom: none;
        }
        .cb-shell-aside-label {
            color: var(--cb-text-dim);
            font-size: 0.72rem;
            text-transform: uppercase;
            letter-spacing: 0.12em;
            margin-bottom: 0.12rem;
        }
        .cb-shell-aside-value {
            color: var(--cb-text);
            font-size: 0.95rem;
            font-weight: 600;
        }
        .cb-panel-head {
            margin-bottom: 0.8rem;
        }
        .cb-panel-title {
            color: var(--cb-text);
            font-family: "Space Grotesk", "IBM Plex Sans", sans-serif;
            font-size: 1.35rem;
            line-height: 1.08;
            margin: 0;
        }
        .cb-signal-card {
            min-height: 11.2rem;
            padding: 1rem 1.05rem;
            border-radius: 24px;
            border: 1px solid rgba(132, 166, 214, 0.18);
            background: linear-gradient(180deg, rgba(18, 33, 53, 0.96) 0%, rgba(10, 21, 36, 0.98) 100%);
            box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.03), var(--cb-glow);
        }
        .cb-signal-label {
            color: var(--cb-text-dim);
            font-size: 0.72rem;
            text-transform: uppercase;
            letter-spacing: 0.14em;
            font-weight: 700;
        }
        .cb-signal-value {
            margin-top: 0.9rem;
            color: var(--cb-text);
            font-family: "Space Grotesk", "IBM Plex Sans", sans-serif;
            font-size: clamp(1.8rem, 2vw, 2.45rem);
            font-weight: 700;
            line-height: 1;
        }
        .cb-signal-note {
            margin-top: 1rem;
            color: var(--cb-text-soft);
            line-height: 1.5;
            font-size: 0.92rem;
        }
        .cb-sidebar-brand {
            position: relative;
            padding: 0.45rem 0 1.1rem 0;
            margin-bottom: 1rem;
            border-bottom: 1px solid rgba(132, 166, 214, 0.12);
        }
        .cb-sidebar-mark {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 3rem;
            height: 3rem;
            border-radius: 50%;
            background: radial-gradient(circle at 30% 30%, #8fd0ff 0%, #4b8ef4 46%, #244c82 100%);
            color: #08111d;
            font-family: "Space Grotesk", "IBM Plex Sans", sans-serif;
            font-size: 0.88rem;
            font-weight: 700;
            margin-bottom: 0.75rem;
            box-shadow: 0 0 0 8px rgba(75, 142, 244, 0.08);
        }
        .cb-sidebar-title {
            color: var(--cb-text);
            font-family: "Space Grotesk", "IBM Plex Sans", sans-serif;
            font-size: 1.18rem;
            line-height: 1.08;
            margin-bottom: 0.35rem;
        }
        .cb-sidebar-subtitle {
            color: var(--cb-text-soft);
            font-size: 0.87rem;
            line-height: 1.6;
        }
        .cb-badge {
            display: inline-flex;
            align-items: center;
            padding: 0.34rem 0.65rem;
            border-radius: 999px;
            border: 1px solid rgba(132, 166, 214, 0.18);
            font-size: 0.72rem;
            font-weight: 700;
            line-height: 1;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            background: rgba(12, 27, 44, 0.8);
            color: var(--cb-text-soft);
        }
        .cb-badge-source { color: var(--cb-accent-2); border-color: rgba(75, 142, 244, 0.22); }
        .cb-badge-fit { color: #dce8f9; }
        .cb-badge-priority { color: #cce0ff; }
        .cb-badge-good { color: #9ce0c9; border-color: rgba(61, 167, 134, 0.24); }
        .cb-badge-watch { color: #f2d6a4; border-color: rgba(214, 164, 87, 0.24); }
        .cb-badge-alert { color: #f5beb5; border-color: rgba(224, 123, 105, 0.28); }
        .cb-badge-neutral { color: var(--cb-text-dim); }
        .cb-chip-row {
            display: flex;
            flex-wrap: wrap;
            gap: 0.42rem;
            margin-top: 0.9rem;
        }
        .cb-chip {
            display: inline-flex;
            align-items: center;
            padding: 0.32rem 0.62rem;
            border-radius: 999px;
            background: rgba(14, 30, 49, 0.92);
            border: 1px solid rgba(132, 166, 214, 0.16);
            color: var(--cb-text-soft);
            font-size: 0.77rem;
            font-weight: 600;
            line-height: 1;
        }
        .cb-dossier {
            position: relative;
            overflow: hidden;
            border-radius: 28px;
            border: 1px solid rgba(132, 166, 214, 0.18);
            background: linear-gradient(180deg, rgba(17, 31, 50, 0.96) 0%, rgba(10, 21, 36, 0.98) 100%);
            box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.03), var(--cb-glow);
            padding: 1.2rem;
            margin-bottom: 1rem;
        }
        .cb-dossier::before {
            content: "";
            position: absolute;
            inset: 0 auto 0 0;
            width: 4px;
            background: rgba(132, 166, 214, 0.26);
        }
        .cb-dossier-high::before { background: linear-gradient(180deg, #8fd0ff 0%, #4b8ef4 100%); }
        .cb-dossier-good::before { background: linear-gradient(180deg, #6dd4b6 0%, #3da786 100%); }
        .cb-dossier-watch::before { background: linear-gradient(180deg, #f2d08d 0%, #d6a457 100%); }
        .cb-dossier-ignore::before { background: linear-gradient(180deg, #94a4ba 0%, #66778e 100%); }
        .cb-dossier-conditional::before { background: linear-gradient(180deg, #f1ae95 0%, #e07b69 100%); }
        .cb-dossier-grid {
            display: grid;
            grid-template-columns: minmax(150px, 0.22fr) minmax(0, 1fr);
            gap: 1rem;
            align-items: start;
        }
        .cb-dossier-rail {
            padding-right: 1rem;
            border-right: 1px solid rgba(132, 166, 214, 0.12);
        }
        .cb-dossier-score {
            color: var(--cb-text);
            font-family: "Space Grotesk", "IBM Plex Sans", sans-serif;
            font-size: 2.6rem;
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
            border: 1px solid rgba(132, 166, 214, 0.14);
            border-radius: 24px;
            padding: 1rem 1.05rem;
            background: rgba(9, 18, 31, 0.72);
            box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.03);
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
            background: rgba(8, 17, 29, 0.86);
            border: 1px solid rgba(132, 166, 214, 0.18);
            border-radius: 22px;
            overflow: hidden;
        }
        .cb-checklist-table thead th {
            background: rgba(18, 33, 53, 0.96);
            color: var(--cb-text-dim);
            font-size: 0.75rem;
            font-weight: 700;
            letter-spacing: 0.13em;
            text-transform: uppercase;
            padding: 0.95rem 1rem;
            text-align: left;
            border-bottom: 1px solid rgba(132, 166, 214, 0.14);
        }
        .cb-checklist-table tbody tr:nth-child(even) {
            background: rgba(12, 24, 39, 0.85);
        }
        .cb-checklist-table tbody tr:hover {
            background: rgba(18, 33, 53, 0.92);
        }
        .cb-checklist-table td {
            padding: 0.95rem 1rem;
            border-top: 1px solid rgba(132, 166, 214, 0.08);
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
        @media (max-width: 980px) {
            .cb-shell-grid,
            .cb-dossier-grid {
                grid-template-columns: 1fr;
            }
            .cb-dossier-rail {
                padding-right: 0;
                padding-bottom: 0.9rem;
                border-right: none;
                border-bottom: 1px solid rgba(132, 166, 214, 0.12);
            }
            .cb-signal-card {
                min-height: auto;
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


def _escape_text(value: Any) -> str:
    return html.escape(_display_value(value))


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
    body = f"<p class='cb-panel-copy'>{html.escape(copy)}</p>" if copy else ""
    st.markdown(
        f"""
        <div class="cb-panel-head">
          <div class="cb-panel-kicker">{html.escape(kicker)}</div>
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
    if filter_state.get("min_days_remaining") is not None:
        chips.append(f"Deadline >= {filter_state['min_days_remaining']} days")
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
          <div class="cb-sidebar-line">cBrain Signal Studio</div>
          <div class="cb-sidebar-mark">F2</div>
          <div class="cb-sidebar-title">TED Opportunity Intelligence</div>
          <div class="cb-sidebar-subtitle">Creative internal review shell for official TED notices, F2-fit scoring, and qualification decisions.</div>
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
        top_line_badges.append(_render_pill("Timing review", "watch"))

    buyer = notice.get("buyer") or "Unknown buyer"
    country = notice.get("buyer_country") or "N/A"
    publication = notice.get("publication_number") or "Unknown publication"
    deadline = format_datetime(notice.get("deadline"), settings.ui_timezone)
    publication_date = format_date(notice.get("publication_date"))
    title = notice.get("title") or "Untitled notice"
    keyword_chips = "".join(_render_chip(label) for label in _notice_keyword_labels(notice))
    if not keyword_chips:
        keyword_chips = _render_chip("No keyword evidence captured yet")
    narrative_parts = [
        f"Buyer: {buyer}.",
        f"Publication: {publication_date}.",
        f"Deadline: {deadline}.",
        f"Confidence: {confidence}.",
    ]
    if notice.get("hard_lock_detected"):
        narrative_parts.append("Platform lock signals are present and should be qualified early.")
    elif notice.get("viable_timing"):
        narrative_parts.append("Timing posture currently looks workable for review.")
    else:
        narrative_parts.append("Timing posture needs analyst attention.")

    st.markdown(
        f"""
        <div class="cb-dossier {card_class}">
          <div class="cb-dossier-grid">
            <div class="cb-dossier-rail">
              <div class="cb-dossier-score">{notice['score']}</div>
              <div class="cb-dossier-score-label">Signal Score</div>
              <div class="cb-dossier-rail-line">
                <div class="cb-dossier-rail-key">Fit</div>
                <div class="cb-dossier-rail-value">{html.escape(fit_label)}</div>
              </div>
              <div class="cb-dossier-rail-line">
                <div class="cb-dossier-rail-key">Priority</div>
                <div class="cb-dossier-rail-value">{html.escape(priority_bucket)}</div>
              </div>
              <div class="cb-dossier-rail-line">
                <div class="cb-dossier-rail-key">Country</div>
                <div class="cb-dossier-rail-value">{html.escape(country)}</div>
              </div>
              <div class="cb-dossier-rail-line">
                <div class="cb-dossier-rail-key">Deadline</div>
                <div class="cb-dossier-rail-value">{html.escape(deadline)}</div>
              </div>
            </div>
            <div>
              <div class="cb-dossier-topline">
              {''.join(top_line_badges)}
              </div>
              <div class="cb-dossier-meta">{html.escape(publication)} | {html.escape(buyer)} | {html.escape(country)}</div>
              <div class="cb-dossier-title">{html.escape(title)}</div>
              <div class="cb-dossier-summary">{html.escape(" ".join(narrative_parts))}</div>
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


def _render_banner(current_view: str) -> None:
    storage_state = initialize_streamlit_storage()
    purged_demo_notices = storage_state.get("purged_demo_notices", 0)
    view_copy = {
        "Dashboard": {
            "kicker": "Opportunity Briefing",
            "title": "F2 signal desk for official TED market intelligence.",
            "copy": "Track live procurement momentum, review scan freshness, and steer analysts toward the strongest public-sector process digitisation opportunities.",
        },
        "Live Scan": {
            "kicker": "Acquisition Workspace",
            "title": "Interrogate TED's public API with an F2-first lens.",
            "copy": "Configure a precise search posture, respect TED request budgets, and feed scored notices into the review queue without touching unsupported scraping routes.",
        },
        "Results": {
            "kicker": "Signal Board",
            "title": "Read each notice as a dossier, not a spreadsheet row.",
            "copy": "Surface timing, fit, platform risk, and keyword evidence together so cBrain teams can decide quickly where F2 deserves attention.",
        },
        "Notice Detail": {
            "kicker": "Opportunity Dossier",
            "title": "Open one tender and inspect the reasoning in depth.",
            "copy": "Review fit logic, supporting evidence, qualification questions, checklist coverage, and official TED documents from one audit-ready workspace.",
        },
    }.get(
        current_view,
        {
            "kicker": "cBrain Signal Studio",
            "title": "Official TED-only tender intelligence for F2 teams.",
            "copy": "Review live notices, fit signals, and qualification context inside a single internal workspace.",
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
            <div class="cb-shell-aside">
              <div class="cb-shell-aside-item">
                <div class="cb-shell-aside-label">Source posture</div>
                <div class="cb-shell-aside-value">Official TED public API and official notice routes only</div>
              </div>
              <div class="cb-shell-aside-item">
                <div class="cb-shell-aside-label">Scoring model</div>
                <div class="cb-shell-aside-value">Deterministic F2-fit rules with audit trail support</div>
              </div>
              <div class="cb-shell-aside-item">
                <div class="cb-shell-aside-label">Business timezone</div>
                <div class="cb-shell-aside-value">{html.escape(settings.ui_timezone)}</div>
              </div>
            </div>
          </div>
        </section>
        """,
        unsafe_allow_html=True,
    )
    if purged_demo_notices:
        st.info(
            f"Removed {purged_demo_notices} seeded demo notices from the local store so the app can focus on live TED data."
        )


def _render_live_scan() -> None:
    profiles = get_search_profiles_registry()

    _render_section_header(
        "Live TED Scan",
        "Acquisition workspace",
        "Configure a live TED search run, keep the request posture polite, and push fresh notices into the same scored datastore used by the rest of the shell.",
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

    st.markdown(
        """
        <div class="cb-note-card" style="margin: 1rem 0 1.1rem 0;">
          <div class="cb-note-title">Scan posture</div>
          <div class="cb-note-copy">Profiles broaden or narrow the acquisition logic, but the source of truth remains TED's official public search interface. Query parameters below let you steer the run without leaving the guarded ingestion path.</div>
        </div>
        """,
        unsafe_allow_html=True,
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
        st.info("Run a scan to populate the shell with live TED notices and retire empty or demo-only surfaces.")
        _render_section_header(
            "Configured Strategies",
            "Search profiles",
            "Each profile changes keyword groups, exclusions, and sensitivity so you can explore the market with different F2 hypotheses.",
        )
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

    _render_section_header(
        "Configured Strategies",
        "Search profiles",
        "The live run has completed. You can immediately run another acquisition pass with a different profile or move to the signal board.",
    )
    _render_profile_cards()

    st.session_state["active_view"] = "Results"
    st.rerun()


def _render_dashboard() -> None:
    payload = load_dashboard_payload()
    metrics = payload["metrics"]
    recent_scans = payload["recent_scans"]
    top_notices = payload["top_notices"]

    _render_section_header(
        "Command Overview",
        "Dashboard",
        "Read the current opportunity temperature, see whether acquisition is fresh enough, and jump straight into the queue that most deserves analyst time.",
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
        _render_section_header(
            "Acquisition Feed",
            "Recent scan runs",
            "These are the latest TED ingestion runs and their operational yield.",
        )
        if recent_scans:
            _render_recent_scan_cards(recent_scans)
        else:
            st.info("No scan history found.")

    with right:
        _render_section_header(
            "Review Queue",
            "Immediate attention set",
            "The shortlist below is tuned to put the most actionable F2 signals in front of analysts first.",
        )
        if top_notices:
            for notice in top_notices:
                with st.container(border=True):
                    st.markdown(
                        f"""
                        <div class="cb-note-title">{html.escape(notice['title'])}</div>
                        <div class="cb-note-copy">{html.escape(notice['publication_number'])} | {html.escape(notice['buyer'] or 'Unknown buyer')} | {html.escape(notice['buyer_country'] or 'N/A')} | Source: {html.escape(_notice_source_label(notice))}</div>
                        """,
                        unsafe_allow_html=True,
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
    st.sidebar.markdown("### Signal Filters")
    st.sidebar.caption(
        "Expired notices stay hidden. Use the controls below to decide how broad or strict the active review surface should be."
    )
    country = st.sidebar.text_input("Country (DK or DNK)", "").strip() or None
    search = st.sidebar.text_input("Search", "").strip() or None

    st.sidebar.markdown("#### Relevance Gate")
    relevant_only = st.sidebar.checkbox("Relevant to F2 Only", value=True)
    fit_label = st.sidebar.selectbox("Fit Label", ["Any", "YES", "CONDITIONAL", "NO"], index=0)
    priority_bucket = st.sidebar.selectbox("Priority Bucket", ["Any", "HIGH", "GOOD", "WATCHLIST", "IGNORE"], index=0)
    confidence_indicator = st.sidebar.selectbox("Confidence", ["Any", "HIGH", "MEDIUM", "LOW"], index=0)

    st.sidebar.markdown("#### Signal Strength")
    score_range = st.sidebar.slider("Score Range", min_value=0, max_value=100, value=(0, 100))

    st.sidebar.markdown("#### Publication Window")
    publication_date_from = st.sidebar.date_input("Published From", value=None)
    publication_date_to = st.sidebar.date_input("Published To", value=None)
    publication_date_from, publication_date_to = _normalize_date_range(publication_date_from, publication_date_to)

    st.sidebar.markdown("#### Timing Window")
    min_days_remaining = st.sidebar.number_input("Minimum Days Remaining", min_value=0, max_value=30, value=1, step=1)
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
        relevant_only=relevant_only,
        min_days_remaining=min_days_remaining if min_days_remaining > 0 else None,
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
        "relevant_only": relevant_only,
        "min_days_remaining": min_days_remaining if min_days_remaining > 0 else None,
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

    _render_section_header(
        "Signal Board",
        "Results",
        "Every opportunity below is presented as a briefing card so timing, fit, and platform risk can be read together instead of as isolated table columns.",
    )
    total_matches = filter_state["total_matches"]
    st.markdown(
        f"""
        <div class="cb-note-card" style="margin-bottom: 1rem;">
          <div class="cb-note-title">Current review surface</div>
          <div class="cb-note-copy">{total_matches} notices match the active filter posture. {len(notices)} are loaded into the current signal board.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if not notices:
        st.warning("No notices match the current filters.")
        return notices

    active_filter_chips = _summarize_results_filters(filter_state)
    if active_filter_chips:
        st.markdown(
            "<div class='cb-note-card'><div class='cb-note-title'>Active filter posture</div><div class='cb-chip-row'>"
            + "".join(_render_chip(chip) for chip in active_filter_chips)
            + "</div></div>",
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
    _render_section_header(
        "Opportunity Dossier",
        "Notice detail",
        "Inspect one opportunity in depth, including fit logic, qualification questions, evidence, checklist coverage, and official TED source access.",
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
              <div class="cb-dossier-score">{detail['score']}</div>
              <div class="cb-dossier-score-label">Signal Score</div>
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
        "Dashboard": "Briefing",
        "Live Scan": "Acquisition",
        "Results": "Signal Board",
        "Notice Detail": "Dossier",
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
    _render_banner(current_view)
    st.sidebar.markdown("---")
    st.sidebar.caption(
        "Experimental Streamlit shell. FastAPI remains the canonical production backend, and live scans stay on TED's public API."
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
                relevant_only=True,
                min_days_remaining=1,
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
