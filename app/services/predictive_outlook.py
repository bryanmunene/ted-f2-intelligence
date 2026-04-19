from __future__ import annotations

import json
import re
from calendar import month_name
from collections import Counter
from collections.abc import Callable, Iterable, Sequence
from datetime import date, datetime
from statistics import median
from typing import Any

from app.models import Notice
from app.models.enums import FitLabel
from app.utils.countries import country_display_label
from app.utils.time import ensure_utc, utcnow

_BUDGET_KEY_TERMS = (
    "budget",
    "estimated value",
    "estimated-value",
    "contract value",
    "contract-value",
    "value excluding vat",
    "estimated total value",
    "contract amount",
    "award amount",
)
_CURRENCY_PATTERN = re.compile(r"\b(EUR|USD|GBP|DKK|SEK|NOK|CHF|PLN|CZK|HUF|RON|BGN)\b", flags=re.IGNORECASE)
_AMOUNT_PATTERN = re.compile(r"(?<!\d)(\d{1,3}(?:[ \u00A0,\.]\d{3})+(?:[.,]\d{2})?|\d+(?:[.,]\d{2})?)(?!\d)")
_WEEKDAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


class PredictiveOutlookService:
    def build(self, notices: Sequence[Notice], *, as_of: datetime | None = None) -> dict[str, Any]:
        evaluated_at = ensure_utc(as_of or utcnow())
        relevant = [notice for notice in notices if self._is_relevant(notice)]
        if not relevant:
            return self._empty_payload()

        publication_dates = [notice.publication_date for notice in relevant if notice.publication_date is not None]
        lead_days = self._lead_days(relevant)
        scores = [int(notice.analysis.score) for notice in relevant if notice.analysis is not None]

        month_counts = Counter(value.month for value in publication_dates)
        weekday_counts = Counter(value.weekday() for value in publication_dates)
        country_counts = Counter(
            country_display_label(notice.buyer_country)
            for notice in relevant
            if country_display_label(notice.buyer_country) != "Unknown"
        )
        buyer_counts = Counter(
            self._clean_label(notice.buyer)
            for notice in relevant
            if self._clean_label(notice.buyer)
        )
        procedure_counts = Counter(
            self._clean_label(notice.procedure_type)
            for notice in relevant
            if self._clean_label(notice.procedure_type)
        )
        cpv_family_counts = Counter(
            f"{code[:4]}xx"
            for notice in relevant
            for code in (notice.cpv_codes or [])
            if isinstance(code, str) and len(code.strip()) >= 4
        )

        budget_samples = [
            budget
            for notice in relevant
            if (budget := self._extract_primary_budget_sample(notice.raw_payload_json or {})) is not None
        ]
        budget_summary = self._summarize_budget_samples(budget_samples, len(relevant))
        next_expected_window = self._forecast_next_window(month_counts, evaluated_at)
        confidence = self._confidence_label(len(relevant))

        payload = {
            "sample_size": len(relevant),
            "confidence": confidence,
            "average_score_ten": round((sum(scores) / len(scores)) / 10.0, 1) if scores else 0.0,
            "median_lead_days": int(median(lead_days)) if lead_days else None,
            "publication_span_start": min(publication_dates) if publication_dates else None,
            "publication_span_end": max(publication_dates) if publication_dates else None,
            "budget_summary": budget_summary,
            "next_expected_window": next_expected_window,
            "peak_release_months": self._top_items(month_counts, label_fn=lambda month: month_name[month]),
            "peak_release_weekdays": self._top_items(weekday_counts, label_fn=lambda index: _WEEKDAY_NAMES[index]),
            "top_countries": self._top_items(country_counts),
            "top_buyers": self._top_items(buyer_counts),
            "top_procedures": self._top_items(procedure_counts),
            "top_cpv_families": self._top_items(cpv_family_counts),
        }
        payload["forecast_summary"] = self._build_summary(payload)
        return payload

    def _empty_payload(self) -> dict[str, Any]:
        return {
            "sample_size": 0,
            "confidence": "Low",
            "average_score_ten": 0.0,
            "median_lead_days": None,
            "publication_span_start": None,
            "publication_span_end": None,
            "budget_summary": {
                "sample_size": 0,
                "range_display": "No usable budget data",
                "median_display": "Unknown",
                "note": "No historically relevant notices with budget fields are stored yet.",
            },
            "next_expected_window": None,
            "peak_release_months": [],
            "peak_release_weekdays": [],
            "top_countries": [],
            "top_buyers": [],
            "top_procedures": [],
            "top_cpv_families": [],
            "forecast_summary": "Not enough historically relevant TED notices are stored yet to produce a forecast.",
        }

    def _is_relevant(self, notice: Notice) -> bool:
        analysis = notice.analysis
        if analysis is None:
            return False
        if analysis.fit_label not in {FitLabel.YES, FitLabel.CONDITIONAL}:
            if analysis.hard_lock_detected:
                return False
            if analysis.score < 45:
                return False
            if not analysis.domain_hits and not analysis.positive_signals:
                return False
        raw_payload = notice.raw_payload_json or {}
        return not bool(raw_payload.get("_seed_fixture"))

    def _lead_days(self, notices: Sequence[Notice]) -> list[int]:
        values: list[int] = []
        for notice in notices:
            if notice.publication_date is None or notice.deadline is None:
                continue
            delta = (ensure_utc(notice.deadline).date() - notice.publication_date).days
            if delta >= 0:
                values.append(delta)
        return values

    def _top_items(
        self,
        counts: Counter[Any],
        *,
        label_fn: Callable[[Any], str] | None = None,
        limit: int = 3,
    ) -> list[dict[str, Any]]:
        if not counts:
            return []
        total = sum(counts.values()) or 1
        rows: list[dict[str, Any]] = []
        for key, count in counts.most_common(limit):
            label = label_fn(key) if label_fn else str(key)
            rows.append(
                {
                    "label": str(label),
                    "count": int(count),
                    "share": round((count / total) * 100, 1),
                }
            )
        return rows

    def _forecast_next_window(self, month_counts: Counter[int], as_of: datetime) -> dict[str, str] | None:
        if not month_counts:
            return None
        peak_months = [month for month, _ in month_counts.most_common(2)]
        next_month = min(
            peak_months,
            key=lambda month: ((month - as_of.month) % 12, -month_counts[month], month),
        )
        year = as_of.year if next_month >= as_of.month else as_of.year + 1
        label = date(year, next_month, 1).strftime("%B %Y")
        months_phrase = ", ".join(month_name[month] for month in peak_months)
        return {
            "label": label,
            "reason": f"Historically relevant TED notices cluster most often in {months_phrase}.",
        }

    def _confidence_label(self, sample_size: int) -> str:
        if sample_size >= 15:
            return "High"
        if sample_size >= 6:
            return "Medium"
        return "Low"

    def _build_summary(self, payload: dict[str, Any]) -> str:
        sample_size = int(payload["sample_size"])
        confidence = payload["confidence"]
        months = payload["peak_release_months"]
        countries = payload["top_countries"]
        procedures = payload["top_procedures"]
        lead_days = payload["median_lead_days"]
        budget = payload["budget_summary"]["range_display"]
        next_window = payload["next_expected_window"]["label"] if payload["next_expected_window"] else "Unknown"

        month_text = ", ".join(item["label"] for item in months[:2]) if months else "no clear month cluster yet"
        country_text = ", ".join(item["label"] for item in countries[:2]) if countries else "no dominant country yet"
        procedure_text = procedures[0]["label"] if procedures else "no dominant procedure yet"
        lead_text = f"median response window {lead_days} days" if lead_days is not None else "response-window pattern not yet stable"

        return (
            f"Based on {sample_size} historically relevant TED notices ({confidence.lower()} confidence), "
            f"opportunities most often surface in {month_text}. The next likely release window is {next_window}. "
            f"Typical budget signals sit around {budget}. The strongest country pattern is {country_text}, "
            f"and the prevailing procedure is {procedure_text}. Lead-time pattern: {lead_text}."
        )

    def _extract_primary_budget_sample(self, payload: Any) -> dict[str, Any] | None:
        candidates: list[dict[str, Any]] = []
        for key, value in self._walk_payload(payload):
            normalized_key = self._normalize_key(key)
            if not any(term in normalized_key for term in _BUDGET_KEY_TERMS):
                continue
            candidates.extend(self._extract_budget_candidates(value))
        if not candidates:
            return None
        return max(candidates, key=lambda item: item["amount"])

    def _extract_budget_candidates(self, value: Any) -> list[dict[str, Any]]:
        if value is None:
            return []
        if isinstance(value, (dict, list)):
            fallback_currency = self._extract_currency_hint(value)
            rendered = json.dumps(value, ensure_ascii=False)
        else:
            fallback_currency = None
            rendered = str(value)

        currency_matches = [match.upper() for match in _CURRENCY_PATTERN.findall(rendered)]
        currency = currency_matches[0] if currency_matches else fallback_currency or "Unknown"

        candidates: list[dict[str, Any]] = []
        for raw_amount in _AMOUNT_PATTERN.findall(rendered):
            amount = self._parse_amount(raw_amount)
            if amount is None or amount < 1000:
                continue
            candidates.append({"amount": amount, "currency": currency})
        return candidates

    def _extract_currency_hint(self, value: Any) -> str | None:
        for key, nested in self._walk_payload(value):
            normalized_key = self._normalize_key(key)
            if "currency" not in normalized_key:
                continue
            if isinstance(nested, str):
                match = _CURRENCY_PATTERN.search(nested)
                if match:
                    return match.group(1).upper()
        return None

    def _parse_amount(self, raw_value: str) -> float | None:
        cleaned = raw_value.replace("\u00A0", "").replace(" ", "")
        if not cleaned:
            return None

        if "," in cleaned and "." in cleaned:
            decimal_mark = "," if cleaned.rfind(",") > cleaned.rfind(".") else "."
            thousands_mark = "." if decimal_mark == "," else ","
            cleaned = cleaned.replace(thousands_mark, "").replace(decimal_mark, ".")
        elif "," in cleaned:
            cleaned = cleaned.replace(",", ".") if len(cleaned.split(",")[-1]) <= 2 else cleaned.replace(",", "")
        elif "." in cleaned and len(cleaned.split(".")[-1]) != 2:
            cleaned = cleaned.replace(".", "")

        try:
            return float(cleaned)
        except ValueError:
            return None

    def _summarize_budget_samples(self, samples: list[dict[str, Any]], total_relevant: int) -> dict[str, Any]:
        if not samples:
            return {
                "sample_size": 0,
                "range_display": "No usable budget data",
                "median_display": "Unknown",
                "note": f"No explicit budget values were found across {total_relevant} relevant notices.",
            }

        by_currency: dict[str, list[float]] = {}
        for sample in samples:
            by_currency.setdefault(sample["currency"], []).append(float(sample["amount"]))

        dominant_currency, dominant_values = max(by_currency.items(), key=lambda item: (len(item[1]), sum(item[1])))
        ordered_values = sorted(dominant_values)
        currency_prefix = "" if dominant_currency == "Unknown" else f"{dominant_currency} "
        return {
            "sample_size": len(samples),
            "range_display": f"{currency_prefix}{self._format_amount(ordered_values[0])} to {currency_prefix}{self._format_amount(ordered_values[-1])}",
            "median_display": f"{currency_prefix}{self._format_amount(median(ordered_values))}",
            "note": f"Budget values were identified in {len(samples)} of {total_relevant} relevant notices; dominant currency: {dominant_currency}.",
        }

    def _format_amount(self, value: float) -> str:
        if value >= 1_000_000:
            return f"{value / 1_000_000:.1f}M"
        if value >= 1000:
            return f"{value / 1000:.0f}k"
        return f"{value:.0f}"

    def _walk_payload(self, value: Any, prefix: str = "") -> Iterable[tuple[str, Any]]:
        if isinstance(value, dict):
            for key, nested in value.items():
                key_str = str(key)
                path = f"{prefix}.{key_str}" if prefix else key_str
                yield path, nested
                yield from self._walk_payload(nested, path)
        elif isinstance(value, list):
            for index, nested in enumerate(value):
                path = f"{prefix}[{index}]"
                yield path, nested
                yield from self._walk_payload(nested, path)

    def _normalize_key(self, value: str) -> str:
        return value.lower().replace("_", " ").replace("-", " ")

    def _clean_label(self, value: str | None) -> str:
        return " ".join((value or "").split()).strip()
