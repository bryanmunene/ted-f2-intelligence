from __future__ import annotations

from typing import Any

from app.models import Notice, NoticeAnalysis, ScanRun
from app.services.keyword_evidence import build_keyword_evidence_module


def _analysis_or_default(notice: Notice) -> NoticeAnalysis | None:
    return notice.analysis


def notice_to_summary_dict(notice: Notice) -> dict[str, Any]:
    analysis = _analysis_or_default(notice)
    raw_payload = notice.raw_payload_json or {}
    return {
        "id": notice.id,
        "publication_number": notice.publication_number,
        "title": notice.title,
        "buyer": notice.buyer,
        "buyer_country": notice.buyer_country,
        "publication_date": notice.publication_date,
        "deadline": notice.deadline,
        "source_url": notice.source_url,
        "html_url": notice.html_url,
        "pdf_url": notice.pdf_url,
        "xml_url": notice.xml_url,
        "score": analysis.score if analysis else 0,
        "fit_label": analysis.fit_label if analysis else None,
        "priority_bucket": analysis.priority_bucket if analysis else None,
        "confidence_indicator": analysis.confidence_indicator if analysis else None,
        "hard_lock_detected": analysis.hard_lock_detected if analysis else False,
        "viable_timing": analysis.viable_timing if analysis else False,
        "keyword_hits": analysis.keyword_hits if analysis else [],
        "saved": notice.saved,
        "dismissed": notice.dismissed,
        "is_demo_record": bool(raw_payload.get("_seed_fixture")),
    }


def notice_to_detail_dict(notice: Notice) -> dict[str, Any]:
    analysis = _analysis_or_default(notice)
    payload = notice_to_summary_dict(notice)
    payload.update(
        {
            "ted_notice_id": notice.ted_notice_id,
            "place_of_performance": notice.place_of_performance,
            "notice_type": notice.notice_type,
            "procedure_type": notice.procedure_type,
            "cpv_codes": notice.cpv_codes,
            "contract_duration": notice.contract_duration,
            "source_url": notice.source_url,
            "html_url": notice.html_url,
            "pdf_url": notice.pdf_url,
            "xml_url": notice.xml_url,
            "summary": notice.summary,
            "reasoning": analysis.reasoning if analysis else "",
            "qualification_questions": analysis.qualification_questions if analysis else [],
            "score_breakdown": analysis.score_breakdown if analysis else [],
            "domain_hits": analysis.domain_hits if analysis else [],
            "positive_signals": analysis.positive_signals if analysis else [],
            "negative_signals": analysis.negative_signals if analysis else [],
            "platform_lock_signals": analysis.platform_lock_signals if analysis else [],
            "timing_flags": analysis.timing_flags if analysis else [],
            "raw_payload_json": notice.raw_payload_json,
            "notes": [
                {
                    "id": note.id,
                    "created_at": note.created_at,
                    "user_display_name": note.user.display_name if note.user else "Internal Analyst",
                    "note_text": note.note_text,
                }
                for note in notice.notes
            ],
        }
    )
    payload["keyword_evidence_module"] = build_keyword_evidence_module(payload)
    return payload


def scan_run_to_dict(scan_run: ScanRun) -> dict[str, Any]:
    return {
        "id": scan_run.id,
        "status": scan_run.status.value,
        "started_at": scan_run.started_at,
        "completed_at": scan_run.completed_at,
        "total_notices_returned": scan_run.total_notices_returned,
        "total_notices_ingested": scan_run.total_notices_ingested,
        "total_after_timing_filters": scan_run.total_after_timing_filters,
        "total_high_fit": scan_run.total_high_fit,
        "total_conditional": scan_run.total_conditional,
        "total_ignored": scan_run.total_ignored,
        "request_count": scan_run.request_count,
        "rate_limit_events": scan_run.rate_limit_events,
        "error_count": scan_run.error_count,
    }
