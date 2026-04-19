from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any
from urllib.parse import unquote, urlparse

import httpx

from app.config import Settings
from app.models import Notice


@dataclass(frozen=True, slots=True)
class DocumentSpec:
    format_name: str
    url: str
    filename: str
    media_type: str


class DocumentDownloadAccessError(RuntimeError):
    pass


KNOWN_DOCUMENT_KEYS = {
    "documents",
    "document",
    "attachments",
    "attachment",
    "procurement-documents",
    "procurement_documents",
    "tender-documents",
    "tender_documents",
    "files",
    "file",
    "links",
    "urls",
}

URL_KEYS = {"url", "href", "link", "download-url", "download_url", "uri"}

LABEL_KEYS = {
    "title",
    "name",
    "label",
    "description",
    "document-title",
    "document_title",
    "file-name",
    "file_name",
}

EXTENSION_MEDIA_TYPES = {
    ".pdf": "application/pdf",
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xls": "application/vnd.ms-excel",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".zip": "application/zip",
    ".txt": "text/plain",
    ".rtf": "application/rtf",
    ".xml": "application/xml",
}


class TedDocumentService:
    def __init__(self, *, settings: Settings) -> None:
        self.settings = settings

    def is_demo_notice(self, notice: Notice) -> bool:
        payload = notice.raw_payload_json or {}
        return bool(payload.get("_seed_fixture"))

    def resolve_notice_page_url(self, notice: Notice) -> str:
        if self.is_demo_notice(notice):
            raise ValueError("This record is not linked to a corresponding live TED notice.")
        if notice.publication_number:
            return f"https://ted.europa.eu/en/notice/-/detail/{notice.publication_number}"
        for candidate in (notice.source_url, notice.html_url, notice.pdf_url, notice.xml_url):
            if candidate:
                return candidate
        raise ValueError("No official TED notice URL is available for this notice.")

    def resolve_download(self, notice: Notice, *, artifact: str) -> DocumentSpec:
        if self.is_demo_notice(notice):
            raise ValueError("This record is not linked to corresponding live TED documents.")
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

    def list_tender_documents(self, notice: Notice) -> list[DocumentSpec]:
        if self.is_demo_notice(notice):
            return []
        payload = notice.raw_payload_json or {}
        candidates = self._collect_tender_documents(payload)
        documents: list[DocumentSpec] = []
        seen_urls: set[str] = set()
        for candidate in candidates:
            url = candidate.get("url")
            if not isinstance(url, str):
                continue
            normalized_url = url.strip()
            if not normalized_url or normalized_url in seen_urls:
                continue
            if self._is_official_notice_artifact_url(normalized_url, notice):
                continue
            seen_urls.add(normalized_url)
            label = candidate.get("label")
            filename = self._filename_from_url_or_label(
                normalized_url,
                label if isinstance(label, str) else None,
                notice.publication_number,
                len(documents) + 1,
            )
            documents.append(
                DocumentSpec(
                    format_name="tender-document",
                    url=normalized_url,
                    filename=filename,
                    media_type=self._guess_media_type(filename),
                )
            )
        return documents

    def resolve_tender_document_download(self, notice: Notice, *, document_index: int) -> DocumentSpec:
        documents = self.list_tender_documents(notice)
        if document_index < 0 or document_index >= len(documents):
            raise ValueError("Requested tender document was not found for this notice.")
        return documents[document_index]

    def fetch_download(self, spec: DocumentSpec) -> tuple[bytes, str]:
        self._validate_remote_url(spec.url)
        max_bytes = max(1, self.settings.ted_document_max_download_bytes)
        with httpx.Client(
            follow_redirects=True,
            timeout=self.settings.ted_request_timeout_seconds,
            headers={"User-Agent": "cBrain-TED-F2-Intelligence/0.1"},
        ) as client:
            response = client.get(spec.url)
            response.raise_for_status()
            content_length = response.headers.get("content-length")
            if content_length and content_length.isdigit() and int(content_length) > max_bytes:
                raise DocumentDownloadAccessError(
                    f"Document exceeds download size limit of {max_bytes} bytes."
                )

            payload = bytearray()
            for chunk in response.iter_bytes(chunk_size=65536):
                if not chunk:
                    continue
                payload.extend(chunk)
                if len(payload) > max_bytes:
                    raise DocumentDownloadAccessError(
                        f"Document exceeds download size limit of {max_bytes} bytes."
                    )
            media_type = response.headers.get("content-type", spec.media_type).split(";")[0].strip() or spec.media_type
            return bytes(payload), media_type

    def _validate_remote_url(self, raw_url: str) -> None:
        parsed = urlparse(raw_url)
        if parsed.scheme not in {"http", "https"}:
            raise DocumentDownloadAccessError("Only HTTP(S) document URLs are allowed.")

        hostname = parsed.hostname
        if not hostname:
            raise DocumentDownloadAccessError("Document URL is missing a valid host.")

        if self.settings.ted_document_allow_private_hosts:
            return

        blocked_hostnames = {"localhost", "127.0.0.1", "::1"}
        if hostname.lower() in blocked_hostnames:
            raise DocumentDownloadAccessError("Local/private hosts are not allowed for document downloads.")

        self._validate_host_is_public(hostname)

    def _validate_host_is_public(self, hostname: str) -> None:
        try:
            addr_info = socket.getaddrinfo(hostname, None)
        except socket.gaierror:
            # If DNS is temporarily unavailable, defer to the HTTP client outcome.
            return

        for entry in addr_info:
            ip_text = entry[4][0]
            try:
                address = ipaddress.ip_address(ip_text)
            except ValueError:
                continue
            if (
                address.is_private
                or address.is_loopback
                or address.is_link_local
                or address.is_reserved
                or address.is_multicast
            ):
                raise DocumentDownloadAccessError("Local/private hosts are not allowed for document downloads.")

    def _collect_tender_documents(self, payload: Any) -> list[dict[str, str]]:
        collected: list[dict[str, str]] = []

        def walk(node: Any, parent_key: str | None = None) -> None:
            if isinstance(node, dict):
                key_lower_map = {str(key).lower(): value for key, value in node.items()}

                for url_key in URL_KEYS:
                    url_value = key_lower_map.get(url_key)
                    if isinstance(url_value, str) and url_value.strip():
                        label = self._pick_label(node)
                        collected.append({"url": url_value.strip(), "label": label})

                for key, value in key_lower_map.items():
                    if key in KNOWN_DOCUMENT_KEYS or parent_key in KNOWN_DOCUMENT_KEYS:
                        walk(value, parent_key=key)
                    elif isinstance(value, (dict, list)):
                        walk(value, parent_key=key)

            elif isinstance(node, list):
                for item in node:
                    walk(item, parent_key=parent_key)

        walk(payload)
        return collected

    def _pick_label(self, node: dict[str, Any]) -> str:
        lowered = {str(key).lower(): value for key, value in node.items()}
        for key in LABEL_KEYS:
            value = lowered.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ""

    def _is_official_notice_artifact_url(self, url: str, notice: Notice) -> bool:
        official_urls = {candidate for candidate in (notice.source_url, notice.html_url, notice.pdf_url, notice.xml_url) if candidate}
        if url in official_urls:
            return True

        parsed = urlparse(url)
        if "ted.europa.eu" not in (parsed.netloc or ""):
            return False

        path = (parsed.path or "").lower()
        publication_number = (notice.publication_number or "").lower()
        if publication_number and publication_number in path and ("/pdf" in path or "/xml" in path or "/detail/" in path):
            return True
        return False

    def _filename_from_url_or_label(
        self,
        url: str,
        label: str | None,
        publication_number: str,
        index: int,
    ) -> str:
        parsed = urlparse(url)
        basename = unquote(PurePosixPath(parsed.path).name)
        if basename:
            return basename

        if label:
            compact = "_".join(part for part in "".join(ch if ch.isalnum() else " " for ch in label).split())
            if compact:
                return f"{compact}.bin"

        return f"{publication_number}-tender-document-{index}.bin"

    def _guess_media_type(self, filename: str) -> str:
        suffix = PurePosixPath(filename).suffix.lower()
        return EXTENSION_MEDIA_TYPES.get(suffix, "application/octet-stream")
