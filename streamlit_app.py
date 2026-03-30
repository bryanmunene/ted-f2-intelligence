from __future__ import annotations

from typing import Any

import streamlit as st

from app.api.presenters import notice_to_detail_dict, notice_to_summary_dict, scan_run_to_dict
from app.config import get_settings
from app.database import get_session_factory
from app.repositories.notices import NoticeListFilters, NoticeRepository
from app.repositories.scan_runs import ScanRunRepository
from app.services.demo_bootstrap import ensure_streamlit_demo_data
from app.services.ted_documents import DocumentSpec, TedDocumentService
from app.utils.time import format_date, format_datetime

settings = get_settings()
ensure_streamlit_demo_data()

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
        .main .block-container { padding-top: 1.5rem; padding-bottom: 2rem; }
        .cb-banner {
            background: linear-gradient(135deg, #f8fbff 0%, #e8f1fb 100%);
            border: 1px solid #d7e2ef;
            border-radius: 14px;
            padding: 1rem 1.2rem;
            margin-bottom: 1rem;
        }
        .cb-kicker {
            color: #4f637a;
            font-size: 0.9rem;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            margin-bottom: 0.35rem;
        }
        .cb-title {
            color: #17212d;
            font-size: 2rem;
            font-weight: 700;
            margin: 0;
        }
        .cb-subtitle {
            color: #556577;
            margin-top: 0.35rem;
        }
        .cb-section-title {
            margin-top: 0;
            margin-bottom: 0.3rem;
        }
        .cb-muted {
            color: #5d6b7c;
            font-size: 0.92rem;
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
    hard_lock_only: bool,
    deadline_window_days: int | None,
    include_dismissed: bool,
    saved_only: bool,
    search: str | None,
    page_size: int,
) -> list[dict[str, Any]]:
    session = get_session_factory()()
    try:
        filters = NoticeListFilters(
            country=country,
            fit_label=fit_label,
            priority_bucket=priority_bucket,
            min_score=min_score,
            hard_lock_only=hard_lock_only,
            deadline_window_days=deadline_window_days,
            include_dismissed=include_dismissed,
            saved_only=saved_only,
            search=search,
        )
        notices, _ = NoticeRepository(session).list(filters, page=1, page_size=page_size)
        return [notice_to_summary_dict(notice) for notice in notices]
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


def _seed_selected_notice(notices: list[dict[str, Any]]) -> None:
    if not notices:
        st.session_state.pop("selected_notice_id", None)
        return
    selected = st.session_state.get("selected_notice_id")
    if selected not in {item["id"] for item in notices}:
        st.session_state["selected_notice_id"] = notices[0]["id"]


def _go_to_view(view_name: str) -> None:
    st.session_state["active_view"] = view_name


def _render_banner() -> None:
    st.markdown(
        """
        <div class="cb-banner">
          <div class="cb-kicker">Temporary Streamlit Shell</div>
          <h1 class="cb-title">cBrain TED F2 Intelligence</h1>
          <div class="cb-subtitle">
            Read-only Streamlit interface over the existing database. FastAPI remains the canonical backend.
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_dashboard() -> None:
    payload = load_dashboard_payload()
    metrics = payload["metrics"]
    recent_scans = payload["recent_scans"]
    top_notices = payload["top_notices"]

    st.subheader("Dashboard", anchor=False)
    metric_cols = st.columns(6)
    metric_cols[0].metric("Total Notices", metrics["total_notices"])
    metric_cols[1].metric("High Fit", metrics["high_fit"])
    metric_cols[2].metric("Conditional", metrics["conditional"])
    metric_cols[3].metric("Expiring Soon", metrics["expiring_soon"])
    metric_cols[4].metric("Hard Locks", metrics["hard_lock"])
    metric_cols[5].metric("Scan Freshness", format_datetime(metrics["scan_freshness"], settings.ui_timezone))

    left, right = st.columns([1.05, 0.95], gap="large")
    with left:
        st.markdown("#### Recent Scan Runs")
        if recent_scans:
            st.dataframe(
                [
                    {
                        "Started": format_datetime(scan["started_at"], settings.ui_timezone),
                        "Status": scan["status"],
                        "Ingested": scan["total_notices_ingested"],
                        "High Fit": scan["total_high_fit"],
                        "Requests": scan["request_count"],
                    }
                    for scan in recent_scans
                ],
                width="stretch",
                hide_index=True,
            )
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
                        f"{notice['buyer_country'] or 'N/A'}"
                    )
                    action_cols = st.columns([1, 1, 1, 1])
                    action_cols[0].metric("Score", notice["score"])
                    action_cols[1].metric("Fit", notice["fit_label"] or "N/A")
                    action_cols[2].metric("Priority", notice["priority_bucket"] or "N/A")
                    if action_cols[3].button("Inspect", key=f"inspect_top_{notice['id']}"):
                        st.session_state["selected_notice_id"] = notice["id"]
                        _go_to_view("Notice Detail")
                        st.rerun()
        else:
            st.info("No stored notices available yet.")


def _render_filters() -> list[dict[str, Any]]:
    st.sidebar.markdown("### Results Filters")
    country = st.sidebar.text_input("Country", "").strip() or None
    fit_label = st.sidebar.selectbox("Fit Label", ["Any", "YES", "CONDITIONAL", "NO"], index=0)
    priority_bucket = st.sidebar.selectbox("Priority Bucket", ["Any", "HIGH", "GOOD", "WATCHLIST", "IGNORE"], index=0)
    min_score = st.sidebar.slider("Minimum Score", min_value=0, max_value=100, value=0)
    deadline_window_days = st.sidebar.number_input("Deadline Window (Days)", min_value=0, max_value=365, value=0, step=7)
    search = st.sidebar.text_input("Search", "").strip() or None
    hard_lock_only = st.sidebar.checkbox("Hard Lock Only", value=False)
    saved_only = st.sidebar.checkbox("Saved Only", value=False)
    include_dismissed = st.sidebar.checkbox("Include Dismissed", value=False)
    page_size = st.sidebar.slider("Rows", min_value=10, max_value=100, value=25, step=5)

    notices = load_filtered_notices(
        country=country,
        fit_label=None if fit_label == "Any" else fit_label,
        priority_bucket=None if priority_bucket == "Any" else priority_bucket,
        min_score=min_score if min_score > 0 else None,
        hard_lock_only=hard_lock_only,
        deadline_window_days=deadline_window_days if deadline_window_days > 0 else None,
        include_dismissed=include_dismissed,
        saved_only=saved_only,
        search=search,
        page_size=page_size,
    )
    return notices


def _render_results() -> list[dict[str, Any]]:
    notices = _render_filters()
    _seed_selected_notice(notices)

    st.subheader("Results", anchor=False)
    st.caption(f"{len(notices)} notices match the current filter set.")

    if not notices:
        st.warning("No notices match the current filters.")
        return notices

    st.dataframe(
        [
            {
                "Score": notice["score"],
                "Fit": notice["fit_label"] or "N/A",
                "Priority": notice["priority_bucket"] or "N/A",
                "Publication": notice["publication_number"],
                "Title": notice["title"],
                "Buyer": notice["buyer"] or "Unknown buyer",
                "Country": notice["buyer_country"] or "N/A",
                "Deadline": format_datetime(notice["deadline"], settings.ui_timezone),
                "Hard Lock": "Yes" if notice["hard_lock_detected"] else "No",
            }
            for notice in notices
        ],
        width="stretch",
        hide_index=True,
    )

    selected_notice = st.selectbox(
        "Inspect a tender",
        options=notices,
        format_func=_notice_option_label,
        index=next(
            (
                idx
                for idx, notice in enumerate(notices)
                if notice["id"] == st.session_state.get("selected_notice_id")
            ),
            0,
        ),
        key="results_notice_picker",
    )
    st.session_state["selected_notice_id"] = selected_notice["id"]

    if st.button("Open selected tender detail", key="open_selected_detail"):
        _go_to_view("Notice Detail")
        st.rerun()

    return notices


def _render_download_controls(detail: dict[str, Any]) -> None:
    st.markdown("#### Official TED Documents")
    st.caption("Documents are fetched directly from the official TED URLs and prepared for download here.")

    document_cols = st.columns(3)
    if detail.get("html_url"):
        document_cols[0].link_button("Open Official TED Notice", detail["html_url"], width="stretch")

    for artifact, label, column, media_type in [
        ("pdf", "PDF", document_cols[1], "application/pdf"),
        ("xml", "XML", document_cols[2], "application/xml"),
    ]:
        url = detail.get(f"{artifact}_url")
        if not url:
            column.caption(f"No official {label} available")
            continue

        prep_key = f"prepare_{artifact}_{detail['id']}"
        state_key = f"prepared_{artifact}_{detail['id']}"
        if column.button(f"Prepare {label}", key=prep_key, width="stretch"):
            with st.spinner(f"Fetching official TED {label} document..."):
                try:
                    st.session_state[state_key] = fetch_official_document(
                        url=url,
                        filename=f"{detail['publication_number']}.{artifact}",
                        media_type=media_type,
                    )
                except Exception as exc:
                    st.session_state.pop(state_key, None)
                    st.error(f"Could not fetch the official TED {label} document: {exc}")

        prepared = st.session_state.get(state_key)
        if prepared:
            payload, filename, resolved_media_type = prepared
            column.download_button(
                f"Download {label}",
                data=payload,
                file_name=filename,
                mime=resolved_media_type,
                key=f"download_{artifact}_{detail['id']}",
                width="stretch",
            )
        else:
            column.link_button(f"Open Official {label}", url, width="stretch")


def _render_notice_detail(notice_id: str | None) -> None:
    st.subheader("Notice Detail", anchor=False)
    if not notice_id:
        st.info("Choose a tender from the Results view first.")
        return

    detail = load_notice_detail(notice_id)
    if detail is None:
        st.error("The selected notice could not be found.")
        return

    title_col, score_col = st.columns([0.78, 0.22])
    with title_col:
        st.markdown(f"### {detail['title']}")
        st.caption(
            f"{detail['publication_number']} | {detail['buyer'] or 'Unknown buyer'} | "
            f"{detail['buyer_country'] or 'N/A'}"
        )
    with score_col:
        st.metric("Score", detail["score"])
        st.caption(f"{detail['fit_label']} | {detail['priority_bucket']}")

    _render_download_controls(detail)

    meta_col, assessment_col = st.columns([0.42, 0.58], gap="large")
    with meta_col:
        st.markdown("#### Metadata")
        st.write(f"**Notice Type:** {detail['notice_type'] or 'Unknown'}")
        st.write(f"**Procedure Type:** {detail['procedure_type'] or 'Unknown'}")
        st.write(f"**Publication Date:** {format_date(detail['publication_date'])}")
        st.write(f"**Deadline:** {format_datetime(detail['deadline'], settings.ui_timezone)}")
        st.write(f"**Place of Performance:** {detail['place_of_performance'] or 'Unknown'}")
        st.write(f"**CPV Codes:** {', '.join(detail['cpv_codes']) if detail['cpv_codes'] else 'None'}")
        st.write(f"**Confidence:** {detail['confidence_indicator'] or 'N/A'}")

    with assessment_col:
        st.markdown("#### Fit Assessment")
        st.write(detail["reasoning"] or "No reasoning available.")
        if detail["keyword_hits"]:
            st.markdown("**Keyword Evidence**")
            st.write(
                ", ".join(f"{hit['term']} [{hit['scope']}]" for hit in detail["keyword_hits"])
            )
        if detail["qualification_questions"]:
            st.markdown("**Qualification Questions**")
            for question in detail["qualification_questions"]:
                st.write(f"- {question}")

    breakdown_col, notes_col = st.columns([0.6, 0.4], gap="large")
    with breakdown_col:
        st.markdown("#### Score Breakdown")
        st.dataframe(
            [
                {
                    "Rule": rule["label"],
                    "Points": rule["points"],
                    "Evidence": ", ".join(rule["evidence"]),
                }
                for rule in detail["score_breakdown"]
            ],
            width="stretch",
            hide_index=True,
        )

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

    views = ["Dashboard", "Results", "Notice Detail"]
    active_view = st.session_state.get("active_view", "Dashboard")
    if active_view not in views:
        active_view = "Dashboard"

    st.sidebar.markdown("## Navigation")
    current_view = st.sidebar.radio(
        "View",
        options=views,
        index=views.index(active_view),
    )
    st.session_state["active_view"] = current_view
    st.sidebar.markdown("---")
    st.sidebar.caption(
        "This Streamlit shell is intentionally temporary and read-only. "
        "FastAPI remains the canonical production-oriented app."
    )

    if current_view == "Dashboard":
        _render_dashboard()
    elif current_view == "Results":
        _render_results()
    else:
        notices = _render_filters()
        _seed_selected_notice(notices)
        options = notices if notices else load_filtered_notices(
            country=None,
            fit_label=None,
            priority_bucket=None,
            min_score=None,
            hard_lock_only=False,
            deadline_window_days=None,
            include_dismissed=False,
            saved_only=False,
            search=None,
            page_size=100,
        )
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
