from __future__ import annotations

from datetime import date

from app.api.schemas import ScanRequestPayload
from app.config import SearchProfile

TED_CANONICAL_FIELDS = [
    "publication-number",
    "notice-title",
    "buyer-name",
    "buyer-country",
    "place-of-performance",
    "notice-type",
    "procedure-type",
    "classification-cpv",
    "publication-date",
    "deadline",
    "contract-duration",
    "additional-information",
]


def _quote_term(term: str) -> str:
    return "\"" + term.replace("\"", "\\\"") + "\""


def _format_text_term(term: str) -> str:
    cleaned = term.strip()
    if not cleaned:
        return ""
    return _quote_term(cleaned)


def _format_date_term(value: date) -> str:
    return value.strftime("%Y%m%d")


class TedExpertQueryBuilder:
    """
    Centralizes TED expert-query construction so syntax can be tuned in one place if TED's
    official search expression rules evolve.
    """

    def build(self, *, payload: ScanRequestPayload, profile: SearchProfile) -> str:
        clauses: list[str] = []

        search_terms = payload.keyword_override_terms() or profile.search_terms
        if search_terms:
            text_clauses = [f"FT~{_format_text_term(term)}" for term in search_terms if term.strip()]
            if text_clauses:
                clauses.append("(" + " OR ".join(text_clauses) + ")")

        if payload.country:
            clauses.append(f"buyer-country={payload.country.upper()}")

        if payload.cpv:
            cpv = payload.cpv.strip()
            if cpv:
                clauses.append(f"classification-cpv={cpv}")

        if payload.date_from:
            clauses.append(f"publication-date>={_format_date_term(payload.date_from)}")

        if payload.date_to:
            clauses.append(f"publication-date<={_format_date_term(payload.date_to)}")

        if not clauses:
            raise ValueError("At least one TED search criterion is required to build a live query.")
        return " AND ".join(clauses)
