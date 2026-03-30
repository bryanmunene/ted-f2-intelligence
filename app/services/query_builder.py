from __future__ import annotations

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


class TedExpertQueryBuilder:
    """
    Centralizes TED expert-query construction so syntax can be tuned in one place if TED's
    official search expression rules evolve.
    """

    def build(self, *, payload: ScanRequestPayload, profile: SearchProfile) -> str:
        clauses: list[str] = []

        search_terms = payload.keyword_override_terms() or profile.search_terms
        if search_terms:
            term_clause = " OR ".join(_quote_term(term) for term in search_terms)
            clauses.append(f"({term_clause})")

        if payload.country:
            clauses.append(f'(buyer-country="{payload.country.upper()}")')

        if payload.cpv:
            cpv = payload.cpv.strip()
            if cpv:
                clauses.append(f'(classification-cpv="{cpv}")')

        if payload.date_from:
            clauses.append(f"(publication-date>={payload.date_from.isoformat()})")

        if payload.date_to:
            clauses.append(f"(publication-date<={payload.date_to.isoformat()})")

        return " AND ".join(clauses) if clauses else "*"

