from __future__ import annotations

from app.api.presenters import notice_to_detail_dict
from app.repositories.notices import NoticeRepository
from app.services.tender_checklist import (
    CHECKLIST_STATUS_FILLED,
    CHECKLIST_STATUS_INFERRED,
    CHECKLIST_STATUS_REVIEW,
    TenderChecklistService,
)


def test_tender_checklist_report_for_seeded_notice(db_session, seeded_notice: str) -> None:
    notice = NoticeRepository(db_session).get_by_id(seeded_notice)
    assert notice is not None

    detail = notice_to_detail_dict(notice)
    report = TenderChecklistService.from_settings().evaluate_notice(detail)
    items = {item["id"]: item for item in report["items"]}

    assert report["template_name"] == "Tender Document Checklist for cBrain East Africa"
    assert len(report["items"]) == 12

    assert items["deadline_tender"]["status"] == CHECKLIST_STATUS_FILLED
    assert "2026-05-10" in items["deadline_tender"]["answer"]

    assert items["f2_relevance"]["status"] == CHECKLIST_STATUS_INFERRED
    assert items["f2_relevance"]["answer"].startswith("FitLabel.YES")

    assert items["contract_duration"]["status"] == CHECKLIST_STATUS_FILLED
    assert items["contract_duration"]["answer"] == "48 MONTH"

    assert items["number_integrations"]["status"] == CHECKLIST_STATUS_INFERRED
    assert "count is not stated" in items["number_integrations"]["answer"].lower()

    assert items["budget"]["status"] == CHECKLIST_STATUS_REVIEW


def test_tender_checklist_markdown_export(db_session, seeded_notice: str) -> None:
    notice = NoticeRepository(db_session).get_by_id(seeded_notice)
    assert notice is not None

    detail = notice_to_detail_dict(notice)
    service = TenderChecklistService.from_settings()
    markdown = service.build_markdown(service.evaluate_notice(detail))

    assert "# Tender Document Checklist for cBrain East Africa" in markdown
    assert "| Checklist Element | Status | Answer | Basis |" in markdown
    assert "Deadline for tender" in markdown
