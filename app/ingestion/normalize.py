from __future__ import annotations

from typing import Any, Iterable

from app.ingestion.models import NormalizedNotice
from app.utils.time import parse_ted_date, parse_ted_datetime

PREFERRED_LANGUAGE_KEYS = ("ENG", "eng", "EN", "en", "MUL", "mul")


def normalize_notice(raw_notice: dict[str, Any], *, extraction_version: str) -> NormalizedNotice:
    publication_number = _first_string(
        raw_notice,
        "publication-number",
        "publicationNumber",
        "publication_number",
    )
    if not publication_number:
        raise ValueError("TED notice payload is missing publication number.")

    title = _first_string(raw_notice, "notice-title", "announcement-title", "title")
    if not title:
        raise ValueError(f"TED notice {publication_number} is missing title.")

    buyer = _first_string(raw_notice, "buyer-name", "buyerName", "business-name")
    buyer_country = _first_string(raw_notice, "buyer-country", "buyerCountry", "business-country")
    place_of_performance = _first_joined(
        raw_notice,
        "place-of-performance",
        "place_of_performance",
        "place-of-performance-country-proc",
        "place-of-performance-other-proc",
    )
    notice_type = _first_string(raw_notice, "notice-type", "noticeType", "form-type")
    procedure_type = _first_string(raw_notice, "procedure-type", "procedureType")
    summary = _first_joined(raw_notice, "additional-information", "summary", "description")
    ted_notice_id = _first_string(
        raw_notice,
        "notice-identifier",
        "notice-id",
        "noticeIdentifier",
        "id",
    )
    contract_duration = _first_string(raw_notice, "contract-duration", "contract-duration-period-lot", "duration")
    cpv_codes = _extract_cpv_codes(raw_notice)
    publication_date = parse_ted_date(
        _first_string(raw_notice, "publication-date", "publicationDate", "dispatch-date")
    )
    deadline = parse_ted_datetime(
        _first_string(
            raw_notice,
            "deadline",
            "submission-deadline",
            "deadline-receipt-tender-date",
            "deadline-receipt-request",
            "deadline-receipt-tender-date-lot",
            "deadline-date-lot",
            "receipt-expression-interest",
        )
    )
    html_url, pdf_url, xml_url = _extract_links(raw_notice, publication_number)

    return NormalizedNotice(
        ted_notice_id=ted_notice_id,
        publication_number=publication_number,
        title=title,
        title_translated_optional=_first_string(raw_notice, "title-translated", "translated-title"),
        buyer=buyer,
        buyer_country=buyer_country,
        place_of_performance=place_of_performance,
        notice_type=notice_type,
        procedure_type=procedure_type,
        cpv_codes=cpv_codes,
        publication_date=publication_date,
        deadline=deadline,
        contract_duration=contract_duration,
        source_url=html_url,
        html_url=html_url,
        pdf_url=pdf_url,
        xml_url=xml_url,
        summary=summary,
        raw_payload_json=raw_notice,
        extraction_version=extraction_version,
    )


def _extract_links(raw_notice: dict[str, Any], publication_number: str) -> tuple[str, str, str]:
    html_url: str | None = None
    pdf_url: str | None = None
    xml_url: str | None = None
    links = raw_notice.get("links") or raw_notice.get("urls") or []
    if isinstance(links, list):
        for item in links:
            if not isinstance(item, dict):
                continue
            format_value = str(item.get("format", "")).lower()
            url = item.get("url")
            if not isinstance(url, str):
                continue
            if format_value in {"html", "htm"} and html_url is None:
                html_url = url
            elif format_value in {"pdf", "pdfs"} and pdf_url is None:
                pdf_url = url
            elif format_value == "xml" and xml_url is None:
                xml_url = url
    elif isinstance(links, dict):
        html_url = _pick_link_url(links.get("html")) or _pick_link_url(links.get("htmlDirect"))
        pdf_url = _pick_link_url(links.get("pdf")) or _pick_link_url(links.get("pdfs"))
        xml_url = _pick_link_url(links.get("xml"))
    base_url = f"https://ted.europa.eu/en/notice/{publication_number}"
    return (
        html_url or f"https://ted.europa.eu/en/notice/-/detail/{publication_number}",
        pdf_url or f"{base_url}/pdf",
        xml_url or f"{base_url}/xml",
    )


def _extract_cpv_codes(raw_notice: dict[str, Any]) -> list[str]:
    values = _first_value(
        raw_notice,
        "classification-cpv",
        "main-classification-cpv",
        "cpv_codes",
        "main-cpv-code",
    )
    flattened: list[str] = []
    if isinstance(values, list):
        for item in values:
            if isinstance(item, dict):
                code = item.get("code") or item.get("value")
                if isinstance(code, str):
                    flattened.append(code)
            elif isinstance(item, str):
                flattened.append(item)
    elif isinstance(values, dict):
        code = values.get("code") or values.get("value")
        if isinstance(code, str):
            flattened.append(code)
    elif isinstance(values, str):
        flattened.extend(part.strip() for part in values.split(",") if part.strip())
    return flattened


def _first_string(raw_notice: dict[str, Any], *keys: str) -> str | None:
    value = _first_value(raw_notice, *keys)
    if value is None:
        return None
    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned or None
    if isinstance(value, list):
        for item in value:
            if isinstance(item, str) and item.strip():
                return item.strip()
            if isinstance(item, dict):
                for field_name in ("value", "label", "name", "text"):
                    nested = item.get(field_name)
                    if isinstance(nested, str) and nested.strip():
                        return nested.strip()
    if isinstance(value, dict):
        for field_name in ("value", "label", "name", "text"):
            nested = value.get(field_name)
            if isinstance(nested, str) and nested.strip():
                return nested.strip()
    values = _stringify_values(value)
    return values[0] if values else None


def _first_joined(raw_notice: dict[str, Any], *keys: str) -> str | None:
    value = _first_value(raw_notice, *keys)
    values = _stringify_values(value)
    if not values:
        return None
    return "; ".join(values)


def _first_value(raw_notice: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in raw_notice:
            return raw_notice[key]
        alt = key.replace("-", "_")
        if alt in raw_notice:
            return raw_notice[alt]
    return None


def _stringify_values(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if isinstance(value, dict):
        for field_name in ("value", "label", "name", "text"):
            nested = value.get(field_name)
            if isinstance(nested, str) and nested.strip():
                return [nested.strip()]
        preferred_values: list[str] = []
        for key in PREFERRED_LANGUAGE_KEYS:
            if key in value:
                preferred_values.extend(_stringify_values(value[key]))
        if preferred_values:
            return preferred_values

        flattened: list[str] = []
        for nested in value.values():
            flattened.extend(_stringify_values(nested))
        return flattened
    if isinstance(value, Iterable) and not isinstance(value, (bytes, bytearray)):
        flattened: list[str] = []
        for item in value:
            flattened.extend(_stringify_values(item))
        return flattened
    return []


def _pick_link_url(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    if isinstance(value, dict):
        for key in PREFERRED_LANGUAGE_KEYS:
            candidate = value.get(key)
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
        for candidate in value.values():
            resolved = _pick_link_url(candidate)
            if resolved:
                return resolved
    if isinstance(value, Iterable) and not isinstance(value, (bytes, bytearray, str)):
        for candidate in value:
            resolved = _pick_link_url(candidate)
            if resolved:
                return resolved
    return None
