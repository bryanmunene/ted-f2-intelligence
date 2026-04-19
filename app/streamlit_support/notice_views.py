from __future__ import annotations

import html
from collections.abc import Callable
from typing import Any

import streamlit as st

from app.streamlit_support.rendering import (
    render_checklist_table,
    render_chip,
    render_pill,
    render_section_header,
    render_stat_cards,
)
from app.utils.time import format_date, format_datetime


def render_download_controls(
    detail: dict[str, Any],
    *,
    resolve_official_notice_url: Callable[[dict[str, Any]], str | None],
    fetch_official_document: Callable[[str, str, str], tuple[bytes, str, str]],
) -> None:
    render_section_header(
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
    official_notice_url = resolve_official_notice_url(detail)
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
    if pdf_column.button("Prepare PDF", key=prep_key, type="secondary", width="stretch"):
        with st.spinner("Fetching official TED PDF document..."):
            try:
                st.session_state[state_key] = fetch_official_document(
                    pdf_url,
                    f"{detail['publication_number']}.pdf",
                    "application/pdf",
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


def render_checklist_cross_reference(
    detail: dict[str, Any],
    *,
    get_tender_checklist_service: Callable[[], Any],
) -> None:
    render_section_header(
        "Tender Checklist",
        "Checklist cross-reference",
        "Cross-reference this opportunity against the cBrain East Africa tender checklist template. Answers are marked as filled, inferred, or review.",
    )

    state_key = f"show_checklist_{detail['id']}"
    button_cols = st.columns([0.34, 0.66])
    if button_cols[0].button(
        "Run checklist cross-reference",
        key=f"run_checklist_{detail['id']}",
        type="primary",
        width="stretch",
    ):
        st.session_state[state_key] = True

    if not st.session_state.get(state_key):
        button_cols[1].caption("Generate a structured checklist cross-reference for this tender in one click.")
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
    render_checklist_table(report["items"])


def render_keyword_evidence_module(detail: dict[str, Any]) -> None:
    module = detail.get("keyword_evidence_module") or {}
    render_section_header(
        "Eligibility Evidence",
        "Keyword evidence",
        "Deterministic keyword evidence showing exactly why this opportunity was surfaced for F2 review.",
    )

    st.info(module.get("statement") or "No keyword evidence module is available for this notice.")

    render_stat_cards(
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
                            + "".join(render_chip(term) for term in domain["terms"])
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
                        + "".join(render_chip(term) for term in scope_group["terms"])
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


def render_notice_detail_layout(
    detail: dict[str, Any],
    *,
    ui_timezone: str,
    card_tone_class: Callable[[dict[str, Any]], str],
    notice_source_label: Callable[[dict[str, Any]], str],
    format_score_out_of_ten: Callable[..., str],
    display_value: Callable[[Any], str],
    render_download_controls_fn: Callable[[dict[str, Any]], None],
    render_keyword_evidence_module_fn: Callable[[dict[str, Any]], None],
    render_checklist_cross_reference_fn: Callable[[dict[str, Any]], None],
) -> None:
    detail_badges = [
        render_pill(notice_source_label(detail), "source"),
        render_pill(display_value(detail["fit_label"]), "fit"),
        render_pill(display_value(detail["priority_bucket"]), "priority"),
    ]
    detail_card_class = card_tone_class(detail) or "cb-dossier-high"
    if detail.get("hard_lock_detected"):
        detail_badges.append(render_pill("Hard lock", "alert"))
    elif detail.get("viable_timing"):
        detail_badges.append(render_pill("Timing viable", "good"))
    else:
        detail_badges.append(render_pill("Timing review", "watch"))

    st.markdown(
        f"""
        <div class="cb-dossier {detail_card_class}" style="margin-top: 0.3rem;">
          <div class="cb-dossier-grid">
            <div class="cb-dossier-rail">
              <div class="cb-dossier-score">{format_score_out_of_ten(detail['score'])}</div>
              <div class="cb-dossier-score-label">Score / 10</div>
              <div class="cb-dossier-rail-line">
                <div class="cb-dossier-rail-key">Confidence</div>
                <div class="cb-dossier-rail-value">{html.escape(display_value(detail['confidence_indicator']))}</div>
              </div>
              <div class="cb-dossier-rail-line">
                <div class="cb-dossier-rail-key">Deadline</div>
                <div class="cb-dossier-rail-value">{html.escape(format_datetime(detail['deadline'], ui_timezone))}</div>
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

    render_stat_cards(
        [
            {
                "label": "Score",
                "value": format_score_out_of_ten(detail["score"], include_suffix=True),
                "note": "Deterministic F2-fit score",
            },
            {
                "label": "Fit",
                "value": display_value(detail["fit_label"]),
                "note": "Overall fit classification",
            },
            {
                "label": "Priority",
                "value": display_value(detail["priority_bucket"]),
                "note": "Recommended review urgency",
            },
            {
                "label": "Confidence",
                "value": display_value(detail["confidence_indicator"]),
                "note": "Signal quality from extracted evidence",
            },
        ]
    )

    render_download_controls_fn(detail)
    overview_tab, checklist_tab, keywords_tab, audit_tab, raw_tab = st.tabs(
        ["Overview", "Checklist", "Eligibility Keywords", "Audit Trail", "Raw TED"]
    )

    with overview_tab:
        st.info("Start here for the quickest read of fit, timing, and qualification gaps before diving into the detailed evidence.")
        meta_col, assessment_col = st.columns([0.44, 0.56], gap="large")
        with meta_col:
            with st.container(border=True):
                render_section_header(
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
                      <div class="cb-fact-item"><div class="cb-fact-label">Deadline</div><div class="cb-fact-value">{html.escape(format_datetime(detail['deadline'], ui_timezone))}</div></div>
                      <div class="cb-fact-item"><div class="cb-fact-label">Contract duration</div><div class="cb-fact-value">{html.escape(detail['contract_duration'] or 'Unknown')}</div></div>
                      <div class="cb-fact-item"><div class="cb-fact-label">Place of performance</div><div class="cb-fact-value">{html.escape(detail['place_of_performance'] or 'Unknown')}</div></div>
                      <div class="cb-fact-item"><div class="cb-fact-label">CPV codes</div><div class="cb-fact-value">{html.escape(', '.join(detail['cpv_codes']) if detail['cpv_codes'] else 'None')}</div></div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        with assessment_col:
            with st.container(border=True):
                render_section_header(
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
                    st.caption("No qualification questions were generated for this notice yet. You can still use the checklist and keyword evidence modules below.")

    with checklist_tab:
        render_checklist_cross_reference_fn(detail)

    with keywords_tab:
        render_keyword_evidence_module_fn(detail)

    with audit_tab:
        breakdown_col, notes_col = st.columns([0.6, 0.4], gap="large")
        with breakdown_col:
            render_section_header(
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
            render_section_header(
                "Analyst Notes",
                "Internal review notes",
                "Only internal analyst notes are shown here; the tender data itself stays centred on public notice metadata.",
            )
            if detail["notes"]:
                for note in detail["notes"]:
                    with st.container(border=True):
                        st.write(note["note_text"])
                        st.caption(f"{note['user_display_name']} | {format_datetime(note['created_at'], ui_timezone)}")
            else:
                st.info("No analyst notes have been stored for this notice yet. Add one after internal review to keep shared context for the team.")

    with raw_tab:
        render_section_header(
            "Payload Trace",
            "Raw TED payload",
            "Raw payload inspection is available for analysts who need to verify a field, translation artifact, or normalisation choice.",
        )
        st.json(detail["raw_payload_json"])
