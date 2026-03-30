from __future__ import annotations

from dataclasses import dataclass

import httpx

from app.config import Settings
from app.models import Notice


@dataclass(frozen=True, slots=True)
class DocumentSpec:
    format_name: str
    url: str
    filename: str
    media_type: str


class TedDocumentService:
    def __init__(self, *, settings: Settings) -> None:
        self.settings = settings

    def resolve_notice_page_url(self, notice: Notice) -> str:
        for candidate in (notice.html_url, notice.source_url, notice.pdf_url, notice.xml_url):
            if candidate:
                return candidate
        raise ValueError("No official TED page URL is available for this notice.")

    def resolve_download(self, notice: Notice, *, artifact: str) -> DocumentSpec:
        normalized_artifact = artifact.lower()
        if normalized_artifact == "pdf" and notice.pdf_url:
            return DocumentSpec(
                format_name="pdf",
                url=notice.pdf_url,
                filename=f"{notice.publication_number}.pdf",
                media_type="application/pdf",
            )
        if normalized_artifact == "xml" and notice.xml_url:
            return DocumentSpec(
                format_name="xml",
                url=notice.xml_url,
                filename=f"{notice.publication_number}.xml",
                media_type="application/xml",
            )
        raise ValueError(f"No official TED {artifact.upper()} document is available for this notice.")

    def fetch_download(self, spec: DocumentSpec) -> tuple[bytes, str]:
        with httpx.Client(
            follow_redirects=True,
            timeout=self.settings.ted_request_timeout_seconds,
            headers={"User-Agent": "cBrain-TED-F2-Intelligence/0.1"},
        ) as client:
            response = client.get(spec.url)
            response.raise_for_status()
            media_type = response.headers.get("content-type", spec.media_type).split(";")[0].strip() or spec.media_type
            return response.content, media_type

