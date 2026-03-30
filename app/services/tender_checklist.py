from __future__ import annotations

import re
from datetime import UTC, datetime
from functools import lru_cache
from typing import Any, Iterable

from app.config import (
    Settings,
    TenderChecklistTemplate,
    get_settings,
    load_tender_checklist_template,
)
from app.utils.time import format_datetime


CHECKLIST_STATUS_FILLED = "filled"
CHECKLIST_STATUS_INFERRED = "inferred"
CHECKLIST_STATUS_REVIEW = "review"


class TenderChecklistService:
    def __init__(self, *, settings: Settings, template: TenderChecklistTemplate) -> None:
        self.settings = settings
        self.template = template

    @classmethod
    def from_settings(cls, settings: Settings | None = None) -> TenderChecklistService:
        active_settings = settings or get_settings()
        return cls(
            settings=active_settings,
            template=load_tender_checklist_template(active_settings.resolved_tender_checklist_template_path),
        )

    def evaluate_notice(self, notice: dict[str, Any]) -> dict[str, Any]:
        items = [self._evaluate_item(item.id, item.label, notice) for item in self.template.items]
        filled_count = sum(1 for item in items if item["status"] == CHECKLIST_STATUS_FILLED)
        inferred_count = sum(1 for item in items if item["status"] == CHECKLIST_STATUS_INFERRED)
        review_count = sum(1 for item in items if item["status"] == CHECKLIST_STATUS_REVIEW)

        return {
            "template_name": self.template.name,
            "template_version": self.template.version,
            "source_document": self.template.source_document,
            "generated_at": datetime.now(tz=UTC),
            "notice_id": notice.get("id"),
            "publication_number": notice.get("publication_number"),
            "filled_count": filled_count,
            "inferred_count": inferred_count,
            "review_count": review_count,
            "items": items,
        }

    def build_markdown(self, report: dict[str, Any]) -> str:
        lines = [
            f"# {report['template_name']}",
            "",
            f"- Publication number: {report['publication_number'] or 'Unknown'}",
            f"- Generated at: {report['generated_at'].isoformat()}",
            f"- Status summary: {report['filled_count']} filled, {report['inferred_count']} inferred, {report['review_count']} review",
            "",
            "| Checklist Element | Status | Answer | Basis |",
            "| --- | --- | --- | --- |",
        ]
        for item in report["items"]:
            lines.append(
                f"| {item['label']} | {item['status'].upper()} | {self._escape_table(item['answer'])} | {self._escape_table(item['basis'])} |"
            )
        return "\n".join(lines)

    def _evaluate_item(self, item_id: str, label: str, notice: dict[str, Any]) -> dict[str, str]:
        handler = getattr(self, f"_item_{item_id}", None)
        if handler is None:
            return self._item_result(
                item_id=item_id,
                label=label,
                status=CHECKLIST_STATUS_REVIEW,
                answer="No checklist logic has been configured for this item yet.",
                basis="Template item requires manual review logic.",
            )
        return handler(item_id, label, notice)

    def _item_deadline_tender(self, item_id: str, label: str, notice: dict[str, Any]) -> dict[str, str]:
        deadline = notice.get("deadline")
        if deadline is not None:
            return self._item_result(
                item_id=item_id,
                label=label,
                status=CHECKLIST_STATUS_FILLED,
                answer=format_datetime(deadline, self.settings.ui_timezone),
                basis="Directly populated from the stored TED submission deadline.",
            )
        return self._review_result(item_id, label, "No tender deadline is stored for this notice.")

    def _item_deadline_prebid(self, item_id: str, label: str, notice: dict[str, Any]) -> dict[str, str]:
        hit = self._search_raw_value(
            notice.get("raw_payload_json") or {},
            ["pre-bid", "pre bid", "briefing", "site visit", "clarification deadline"],
        )
        if hit:
            return self._item_result(
                item_id=item_id,
                label=label,
                status=CHECKLIST_STATUS_FILLED,
                answer=hit,
                basis="Matched a pre-bid or briefing related field in the stored notice payload.",
            )
        return self._review_result(
            item_id,
            label,
            "No pre-bid meeting date was found in the stored TED metadata. Check the notice page and PDF.",
        )

    def _item_f2_relevance(self, item_id: str, label: str, notice: dict[str, Any]) -> dict[str, str]:
        fit_label = str(notice.get("fit_label") or "UNKNOWN")
        reasoning = str(notice.get("reasoning") or "").strip()
        if reasoning:
            return self._item_result(
                item_id=item_id,
                label=label,
                status=CHECKLIST_STATUS_INFERRED,
                answer=f"{fit_label}. {reasoning}",
                basis="Derived from the deterministic F2-fit scoring engine and stored reasoning.",
            )
        return self._review_result(item_id, label, "No relevance reasoning is available for this notice.")

    def _item_budget(self, item_id: str, label: str, notice: dict[str, Any]) -> dict[str, str]:
        hit = self._search_raw_value(
            notice.get("raw_payload_json") or {},
            [
                "budget",
                "estimated value",
                "estimated-value",
                "contract-value",
                "contract value",
                "value excluding vat",
                "estimated total value",
            ],
        )
        if hit:
            return self._item_result(
                item_id=item_id,
                label=label,
                status=CHECKLIST_STATUS_FILLED,
                answer=hit,
                basis="Matched a budget or contract-value field in the stored notice payload.",
            )
        return self._review_result(
            item_id,
            label,
            "No explicit budget or estimated contract value was found in the stored notice data.",
        )

    def _item_number_users(self, item_id: str, label: str, notice: dict[str, Any]) -> dict[str, str]:
        corpus = self._notice_corpus(notice)
        match = re.search(
            r"\b(?P<count>\d[\d,\.]*)\s+(?:named\s+)?(?:end\s+)?users?\b",
            corpus,
            flags=re.IGNORECASE,
        )
        if match:
            return self._item_result(
                item_id=item_id,
                label=label,
                status=CHECKLIST_STATUS_FILLED,
                answer=match.group("count"),
                basis="Extracted a user-count pattern from the stored notice text.",
            )
        return self._review_result(
            item_id,
            label,
            "No explicit number of users was found in the stored notice data.",
        )

    def _item_number_integrations(self, item_id: str, label: str, notice: dict[str, Any]) -> dict[str, str]:
        corpus = self._notice_corpus(notice)
        match = re.search(
            r"\b(?P<count>\d[\d,\.]*)\s+(?:required\s+)?(?:system\s+)?(?:api\s+)?(?:integrations?|interfaces?)\b",
            corpus,
            flags=re.IGNORECASE,
        )
        if match:
            return self._item_result(
                item_id=item_id,
                label=label,
                status=CHECKLIST_STATUS_FILLED,
                answer=match.group("count"),
                basis="Extracted an explicit integration-count pattern from the stored notice text.",
            )
        if re.search(r"\bintegrations?\b|\binterfaces?\b|\binteroperability\b", corpus, flags=re.IGNORECASE):
            return self._item_result(
                item_id=item_id,
                label=label,
                status=CHECKLIST_STATUS_INFERRED,
                answer="Integrations are mentioned, but the count is not stated.",
                basis="Integration requirements are referenced in the stored notice text without a numeric count.",
            )
        return self._review_result(
            item_id,
            label,
            "No explicit number of integrations was found in the stored notice data.",
        )

    def _item_contract_duration(self, item_id: str, label: str, notice: dict[str, Any]) -> dict[str, str]:
        contract_duration = str(notice.get("contract_duration") or "").strip()
        if contract_duration:
            return self._item_result(
                item_id=item_id,
                label=label,
                status=CHECKLIST_STATUS_FILLED,
                answer=contract_duration,
                basis="Directly populated from the normalized TED contract duration field.",
            )
        return self._review_result(item_id, label, "No contract duration is stored for this notice.")

    def _item_hosting_included(self, item_id: str, label: str, notice: dict[str, Any]) -> dict[str, str]:
        corpus = self._notice_corpus(notice)
        if re.search(r"\bhosting\b", corpus, flags=re.IGNORECASE):
            if re.search(r"\bhosting\b.{0,40}\b(?:included|in scope|required)\b", corpus, flags=re.IGNORECASE):
                return self._item_result(
                    item_id=item_id,
                    label=label,
                    status=CHECKLIST_STATUS_FILLED,
                    answer="Hosting appears to be included or in scope.",
                    basis="The stored notice text explicitly links hosting with inclusion or scope.",
                )
            return self._item_result(
                item_id=item_id,
                label=label,
                status=CHECKLIST_STATUS_INFERRED,
                answer="Hosting is mentioned, but whether it is included in price is unclear.",
                basis="Hosting appears in the stored notice text, but the commercial treatment is not explicit.",
            )
        return self._review_result(
            item_id,
            label,
            "No clear hosting statement was found in the stored notice data.",
        )

    def _item_multiple_lots(self, item_id: str, label: str, notice: dict[str, Any]) -> dict[str, str]:
        raw_payload = notice.get("raw_payload_json") or {}
        lot_count = self._detect_lot_count(raw_payload)
        if lot_count > 1:
            return self._item_result(
                item_id=item_id,
                label=label,
                status=CHECKLIST_STATUS_FILLED,
                answer=f"Yes, {lot_count} lots were identified in the stored notice payload.",
                basis="Multiple lot records were detected in the stored TED payload.",
            )
        if lot_count == 1:
            return self._item_result(
                item_id=item_id,
                label=label,
                status=CHECKLIST_STATUS_INFERRED,
                answer="A lot structure is referenced, but only one lot was identified in the stored payload.",
                basis="A lot collection was detected without evidence of multiple lots.",
            )
        return self._item_result(
            item_id=item_id,
            label=label,
            status=CHECKLIST_STATUS_INFERRED,
            answer="No explicit multi-lot structure was identified in the stored notice data.",
            basis="No lot collection was found in the normalized notice payload.",
        )

    def _item_financial_evaluation_criteria(self, item_id: str, label: str, notice: dict[str, Any]) -> dict[str, str]:
        hit = self._search_raw_value(
            notice.get("raw_payload_json") or {},
            [
                "evaluation criteria",
                "award criteria",
                "financial evaluation",
                "lowest cost",
                "lowest price",
                "lowest evaluated tender",
                "best price-quality ratio",
            ],
        )
        if hit:
            return self._item_result(
                item_id=item_id,
                label=label,
                status=CHECKLIST_STATUS_FILLED,
                answer=hit,
                basis="Matched an evaluation or award-criteria field in the stored notice payload.",
            )
        return self._review_result(
            item_id,
            label,
            "No explicit financial evaluation method was found in the stored notice data.",
        )

    def _item_evaluation_weight_split(self, item_id: str, label: str, notice: dict[str, Any]) -> dict[str, str]:
        corpus = self._notice_corpus(notice)
        ratio_match = re.search(
            r"\b(?P<left>\d{1,3})\s*(?:/|:)\s*(?P<right>\d{1,3})\b",
            corpus,
            flags=re.IGNORECASE,
        )
        if ratio_match:
            return self._item_result(
                item_id=item_id,
                label=label,
                status=CHECKLIST_STATUS_FILLED,
                answer=f"{ratio_match.group('left')}/{ratio_match.group('right')}",
                basis="Matched a weighted evaluation ratio in the stored notice text.",
            )
        return self._review_result(
            item_id,
            label,
            "No technical-versus-financial weighting split was found in the stored notice data.",
        )

    def _item_hardware_scope(self, item_id: str, label: str, notice: dict[str, Any]) -> dict[str, str]:
        corpus = self._notice_corpus(notice)
        if re.search(
            r"\bhardware\b|\bservers?\b|\bnetwork(?:ing)?\s+gear\b|\blaptops?\b|\bdesktops?\b|\bprinters?\b",
            corpus,
            flags=re.IGNORECASE,
        ):
            return self._item_result(
                item_id=item_id,
                label=label,
                status=CHECKLIST_STATUS_FILLED,
                answer="Yes, a hardware component appears to be in scope.",
                basis="Hardware-related language was found in the stored notice text.",
            )
        return self._item_result(
            item_id=item_id,
            label=label,
            status=CHECKLIST_STATUS_INFERRED,
            answer="No explicit hardware component was detected in the stored notice data.",
            basis="No hardware-related language was found in the title, summary, or raw payload text.",
        )

    def _notice_corpus(self, notice: dict[str, Any]) -> str:
        parts = [
            str(notice.get("title") or ""),
            str(notice.get("summary") or ""),
            str(notice.get("reasoning") or ""),
            str(notice.get("buyer") or ""),
            str(notice.get("notice_type") or ""),
            str(notice.get("procedure_type") or ""),
            " ".join(str(item) for item in (notice.get("qualification_questions") or [])),
        ]
        parts.extend(self._flatten_strings(notice.get("raw_payload_json") or {}))
        return " ".join(part for part in parts if part).strip()

    def _search_raw_value(self, payload: Any, patterns: list[str]) -> str | None:
        normalized_patterns = [self._normalize_key(pattern) for pattern in patterns]
        for key, value in self._walk_payload(payload):
            normalized_key = self._normalize_key(key)
            if any(pattern in normalized_key for pattern in normalized_patterns):
                rendered = self._stringify_scalar(value)
                if rendered:
                    return rendered

        corpus = " ".join(self._flatten_strings(payload))
        for pattern in patterns:
            match = re.search(
                rf"(.{{0,40}}{re.escape(pattern)}.{{0,60}})",
                corpus,
                flags=re.IGNORECASE,
            )
            if match:
                return match.group(1).strip(" ;,.")
        return None

    def _detect_lot_count(self, payload: Any) -> int:
        for key, value in self._walk_payload(payload):
            normalized_key = self._normalize_key(key)
            if "lots" in normalized_key or normalized_key.endswith("lot"):
                if isinstance(value, list):
                    return len(value)
                if isinstance(value, dict):
                    return len(value)
                if isinstance(value, str):
                    if "lot" in value.lower():
                        return 1
        return 0

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

    def _flatten_strings(self, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            cleaned = value.strip()
            return [cleaned] if cleaned else []
        if isinstance(value, dict):
            flattened: list[str] = []
            for key, nested in value.items():
                flattened.append(str(key))
                flattened.extend(self._flatten_strings(nested))
            return flattened
        if isinstance(value, Iterable) and not isinstance(value, (bytes, bytearray)):
            flattened: list[str] = []
            for nested in value:
                flattened.extend(self._flatten_strings(nested))
            return flattened
        scalar = self._stringify_scalar(value)
        return [scalar] if scalar else []

    def _stringify_scalar(self, value: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, bool):
            return "Yes" if value else "No"
        if isinstance(value, (int, float)):
            return str(value)
        if isinstance(value, datetime):
            return format_datetime(value, self.settings.ui_timezone)
        rendered = str(value).strip()
        return rendered or None

    def _normalize_key(self, value: str) -> str:
        return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()

    def _item_result(
        self,
        *,
        item_id: str,
        label: str,
        status: str,
        answer: str,
        basis: str,
    ) -> dict[str, str]:
        return {
            "id": item_id,
            "label": label,
            "status": status,
            "answer": answer,
            "basis": basis,
        }

    def _review_result(self, item_id: str, label: str, answer: str) -> dict[str, str]:
        return self._item_result(
            item_id=item_id,
            label=label,
            status=CHECKLIST_STATUS_REVIEW,
            answer=answer,
            basis="Manual follow-up is required against the official TED notice and PDF.",
        )

    def _escape_table(self, value: str) -> str:
        return value.replace("|", "\\|").replace("\n", " ").strip()


@lru_cache(maxsize=1)
def get_tender_checklist_service_cached() -> TenderChecklistService:
    return TenderChecklistService.from_settings()
