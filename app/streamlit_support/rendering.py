from __future__ import annotations

import html
from typing import Any

import streamlit as st

from app.streamlit_support.results_filters import display_value


def escape_text(value: Any) -> str:
    return html.escape(display_value(value))


def truncate_text(value: str | None, *, limit: int = 220) -> str:
    if not value:
        return ""
    cleaned = " ".join(str(value).split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1].rstrip() + "..."


def render_pill(label: str, tone: str) -> str:
    safe_label = html.escape(label)
    return f"<span class='cb-badge cb-badge-{tone}'>{safe_label}</span>"


def render_chip(label: str) -> str:
    return f"<span class='cb-chip'>{html.escape(label)}</span>"


def render_rich_text_cell(value: Any) -> str:
    return html.escape(display_value(value)).replace("\n", "<br>")


def render_section_header(kicker: str, title: str, copy: str | None = None) -> None:
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


def render_stat_cards(cards: list[dict[str, str]]) -> None:
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


def render_ranked_signal_list(title: str, items: list[dict[str, Any]], *, empty_message: str) -> None:
    with st.container(border=True):
        st.markdown(f"**{title}**")
        if not items:
            st.caption(empty_message)
            return
        for item in items:
            st.markdown(f"- `{item['count']}` {item['label']} ({item['share']:.1f}%)")


def render_checklist_table(items: list[dict[str, Any]]) -> None:
    if not items:
        st.info("No checklist items are available for this notice.")
        return

    rows: list[str] = []
    for item in items:
        status = display_value(item.get("status")).upper()
        rows.append(
            "<tr>"
            f"<td class='cb-checklist-col-item'>{render_rich_text_cell(item.get('label'))}</td>"
            f"<td class='cb-checklist-col-status'>{render_pill(status, status_tone(status))}</td>"
            f"<td class='cb-checklist-col-answer'>{render_rich_text_cell(item.get('answer'))}</td>"
            f"<td class='cb-checklist-col-basis'>{render_rich_text_cell(item.get('basis'))}</td>"
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


def status_tone(status: str) -> str:
    normalized = status.strip().lower()
    if normalized in {"filled", "high", "yes"}:
        return "good"
    if normalized in {"review", "no"}:
        return "alert"
    if normalized in {"inferred", "conditional", "watchlist"}:
        return "priority"
    return "neutral"
