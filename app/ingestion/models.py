from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field

from app.utils.text import unique_preserve_order


class NormalizedNotice(BaseModel):
    ted_notice_id: str | None = None
    publication_number: str
    title: str
    title_translated_optional: str | None = None
    buyer: str | None = None
    buyer_country: str | None = None
    place_of_performance: str | None = None
    notice_type: str | None = None
    procedure_type: str | None = None
    cpv_codes: list[str] = Field(default_factory=list)
    publication_date: date | None = None
    deadline: datetime | None = None
    contract_duration: str | None = None
    source_url: str | None = None
    html_url: str | None = None
    pdf_url: str | None = None
    xml_url: str | None = None
    summary: str | None = None
    raw_payload_json: dict[str, Any] = Field(default_factory=dict)
    extraction_version: str

    def repository_payload(self) -> dict[str, Any]:
        payload = self.model_dump()
        payload["cpv_codes"] = unique_preserve_order(payload["cpv_codes"])
        return payload

    def searchable_fragments(self) -> list[str]:
        return [
            self.title,
            self.title_translated_optional or "",
            self.buyer or "",
            self.notice_type or "",
            self.procedure_type or "",
            self.summary or "",
            " ".join(self.cpv_codes),
        ]

