from __future__ import annotations

from typing import Any

from app.utils.text import unique_preserve_order

SCOPE_LABELS = {
    "title": "Title",
    "summary": "Summary",
    "buyer": "Buyer",
    "metadata": "Metadata",
    "all": "All fields",
}


def build_keyword_evidence_module(notice: dict[str, Any]) -> dict[str, Any]:
    keyword_hits = notice.get("keyword_hits") or []
    domain_hits = notice.get("domain_hits") or []
    positive_signals = notice.get("positive_signals") or []
    negative_signals = notice.get("negative_signals") or []

    signal_points_by_id: dict[str, int] = {}
    for signal in positive_signals:
        signal_id = _string_value(signal.get("id"))
        if signal_id:
            signal_points_by_id[signal_id] = _int_value(signal.get("points"))

    scope_terms: dict[str, list[str]] = {key: [] for key in SCOPE_LABELS}
    all_terms: list[str] = []
    for hit in keyword_hits:
        term = _string_value(hit.get("term"))
        if not term:
            continue
        scope = (_string_value(hit.get("scope")) or "all").lower()
        normalized_scope = scope if scope in scope_terms else "all"
        scope_terms[normalized_scope].append(term)
        all_terms.append(term)

    all_terms = unique_preserve_order(all_terms)

    domain_matches: list[dict[str, Any]] = []
    matched_domain_ids: set[str] = set()
    for domain_hit in domain_hits:
        group_id = _string_value(domain_hit.get("group_id"))
        label = _string_value(domain_hit.get("label")) or group_id or "Matched domain"
        terms = unique_preserve_order(_string_list(domain_hit.get("terms")))
        scopes = [scope.lower() for scope in _string_list(domain_hit.get("scopes"))]
        scopes = unique_preserve_order(scope for scope in scopes if scope)
        domain_matches.append(
            {
                "group_id": group_id,
                "label": label,
                "points": signal_points_by_id.get(group_id, 0),
                "terms": terms,
                "scopes": scopes,
                "scope_labels": [SCOPE_LABELS.get(scope, scope.title()) for scope in scopes],
            }
        )
        if group_id:
            matched_domain_ids.add(group_id)

    amplifiers = [
        {
            "label": _string_value(signal.get("label")) or "Positive signal",
            "points": _int_value(signal.get("points")),
            "evidence": _string_list(signal.get("evidence")),
        }
        for signal in positive_signals
        if (_string_value(signal.get("id")) or "") not in matched_domain_ids
    ]

    weakening_factors = [
        {
            "label": _string_value(signal.get("label")) or "Weakening factor",
            "points": _int_value(signal.get("points")),
            "evidence": _string_list(signal.get("evidence")),
        }
        for signal in negative_signals
    ]

    scope_groups = [
        {
            "scope": scope,
            "label": label,
            "terms": unique_preserve_order(scope_terms[scope]),
            "count": len(unique_preserve_order(scope_terms[scope])),
        }
        for scope, label in SCOPE_LABELS.items()
        if scope_terms[scope]
    ]

    matched_keyword_count = len(all_terms)
    matched_domain_count = len(domain_matches)
    fit_label = _string_value(getattr(notice.get("fit_label"), "value", notice.get("fit_label"))).upper() or "NO"

    return {
        "headline": _build_headline(matched_keyword_count=matched_keyword_count, matched_domain_count=matched_domain_count),
        "statement": _build_statement(
            fit_label=fit_label,
            matched_keyword_count=matched_keyword_count,
            matched_domain_count=matched_domain_count,
            domain_matches=domain_matches,
            all_terms=all_terms,
            weakening_factors=weakening_factors,
            title_terms=scope_terms["title"],
        ),
        "matched_keyword_count": matched_keyword_count,
        "matched_domain_count": matched_domain_count,
        "title_keyword_count": len(unique_preserve_order(scope_terms["title"])),
        "summary_keyword_count": len(unique_preserve_order(scope_terms["summary"])),
        "top_terms": all_terms[:8],
        "domain_matches": domain_matches,
        "scope_hits": scope_groups,
        "amplifiers": amplifiers,
        "weakening_factors": weakening_factors,
    }


def _build_headline(*, matched_keyword_count: int, matched_domain_count: int) -> str:
    if matched_keyword_count == 0:
        return "No positive keyword evidence stored"
    keyword_label = "keyword" if matched_keyword_count == 1 else "keywords"
    domain_label = "domain" if matched_domain_count == 1 else "domains"
    return f"{matched_keyword_count} matched {keyword_label} across {matched_domain_count} F2 {domain_label}"


def _build_statement(
    *,
    fit_label: str,
    matched_keyword_count: int,
    matched_domain_count: int,
    domain_matches: list[dict[str, Any]],
    all_terms: list[str],
    weakening_factors: list[dict[str, Any]],
    title_terms: list[str],
) -> str:
    if matched_keyword_count == 0:
        return "No positive keyword evidence has been stored for this opportunity yet."

    top_domains = ", ".join(match["label"] for match in domain_matches[:3]) or "no mapped domains"
    top_terms = ", ".join(all_terms[:5]) or "no matched terms"

    sentences: list[str] = []
    if fit_label in {"YES", "CONDITIONAL"}:
        sentences.append(
            f"This opportunity was surfaced because it matched {matched_keyword_count} distinct F2 keywords across {matched_domain_count} domain groups."
        )
    else:
        sentences.append(
            f"This opportunity still matched {matched_keyword_count} F2-related keywords across {matched_domain_count} domain groups, but the overall fit stayed below the decision threshold."
        )
    sentences.append(f"Strongest matched domains: {top_domains}.")
    sentences.append(f"Key matched terms: {top_terms}.")
    if title_terms:
        sentences.append("Title matches strengthened the signal.")
    if weakening_factors:
        weakening_labels = ", ".join(item["label"] for item in weakening_factors[:2] if item["label"])
        if weakening_labels:
            sentences.append(f"Weakened by: {weakening_labels}.")
    return " ".join(sentences)


def _string_value(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _int_value(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        cleaned = value.strip()
        return [cleaned] if cleaned else []
    if isinstance(value, list):
        flattened: list[str] = []
        for item in value:
            flattened.extend(_string_list(item))
        return flattened
    return []
