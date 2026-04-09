from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any

from app.config import KeywordPack, SearchProfile
from app.ingestion.models import NormalizedNotice
from app.models.enums import ConfidenceIndicator, FitLabel, PriorityBucket
from app.scoring.types import RuleContribution, ScoreResult, SignalEvidence
from app.utils.text import normalize_text, unique_preserve_order

ACRONYMS = {"bpm", "dms", "ecm", "edms", "erp", "hr", "ocr", "sap", "sso"}

DOMAIN_RULES = (
    ("document_management", "EDMS / ECM / DMS / document management", 20, ("title",), ("document management", "document management system", "records management", "enterprise content management", "content services platform", "electronic document management", "electronic records management", "edms", "ecm", "dms")),
    ("records_archives", "Records / archives / registry", 16, ("summary",), ("records", "records governance", "archives", "archive management", "registry", "file tracking", "file registry", "document repository", "records repository")),
    ("workflow_bpm", "Workflow / BPM / approvals", 14, ("all",), ("workflow", "workflow automation", "workflow management", "workflow system", "bpm", "approvals", "approval workflow", "routing", "process automation")),
    ("case_management", "Case management / complaints / matters", 14, ("all",), ("case management", "case handling", "complaint management", "grievance", "matter management", "case tracking")),
    ("service_delivery", "Service delivery / licensing / permits / e-government", 12, ("all",), ("service delivery", "licensing", "licensing system", "permits", "permit management", "citizen services", "e-government", "digital government", "public service portal")),
    ("correspondence_lifecycle", "Correspondence / lifecycle / retention / archiving", 10, ("all",), ("correspondence", "correspondence management", "contract management", "document lifecycle", "retention", "retention schedule", "archiving", "electronic archiving")),
)
BUYER_TERMS = ("ministry", "authority", "agency", "municipality", "municipal", "city of", "court", "regulator", "tax", "customs", "justice", "interior", "finance", "department")
ENTERPRISE_TERMS = ("enterprise-wide", "enterprise wide", "cross-department", "cross department", "compliance", "audit", "records governance", "all departments", "organisation-wide", "organization-wide")
DELIVERY_TERMS = ("implementation", "migration", "integration", "training", "support", "rollout", "deployment")

REPOSITORY_TERMS = ("repository", "document repository", "records repository")
WORKFLOW_TERMS = ("workflow", "workflow automation", "workflow management", "process automation", "routing")
RECORDS_TERMS = ("records", "records management", "records governance", "archive", "archives")
SEARCH_TERMS = ("search", "retrieval", "indexing")
RETENTION_TERMS = ("retention", "retention schedule", "archiving")
APPROVAL_TERMS = ("approval", "approvals", "approval workflow")
NOTIFICATION_TERMS = ("notification", "notifications", "alerts")
AUDIT_TERMS = ("audit trail", "audit trails", "audit log", "audit logs")
INTEGRATION_SYSTEM_TERMS = ("erp", "hr", "email", "identity", "sso", "active directory", "idm")

NEGATIVE_RULES = (
    ("hardware_only", "Hardware-only scope", -25, ("hardware supply", "hardware procurement", "supply of laptops", "supply of servers", "desktop computers", "printers", "switches", "routers", "storage arrays")),
    ("infrastructure_only", "Network / infrastructure / hosting-only scope", -20, ("network infrastructure", "data centre", "data center", "hosting services", "cloud hosting", "server hosting", "network equipment", "telecommunications infrastructure")),
    ("website_only", "Website redesign-only scope", -18, ("website redesign", "website redevelopment", "website refresh", "web design", "public website")),
    ("mobile_only", "Mobile-app-only scope", -18, ("mobile application", "mobile app", "android app", "ios app")),
    ("erp_only", "Generic ERP scope with no process/document angle", -16, ("erp implementation", "enterprise resource planning", "sap erp", "oracle erp")),
    ("security_only", "Cybersecurity-tooling-only scope", -15, ("cybersecurity", "firewall", "firewalls", "antivirus", "email security", "endpoint protection", "siem")),
    ("construction_only", "Construction / works / facilities / vehicles scope", -15, ("construction works", "civil works", "facilities management", "vehicle fleet", "vehicles", "building works")),
)

PLATFORMS = ("power platform", "sharepoint", "salesforce", "servicenow", "sap", "oracle")
LOCK_HARD = ("must use", "shall use", "mandatory", "required to use", "delivery platform", "implementation base", "fixed platform", "preselected platform")
LOCK_SOFT = ("existing microsoft environment", "existing microsoft licenses", "licenses already available", "preferred platform", "preferred stack", "existing sharepoint environment", "existing sap environment", "current platform", "incumbent platform")
LOCK_OPEN = ("equivalent solutions accepted", "equivalent solution accepted", "or equivalent", "alternative platform", "functionally equivalent", "outcome based")

SCANNING_TERMS = ("ocr", "capture", "bulk digitization", "bulk digitisation", "document imaging", "capture factory")
CERTIFICATION_TERMS = ("oem", "certification required", "certified partner", "gold partner", "sector reference", "mandatory local certification")

CPV_RULES = (
    ("cpv_document_management", "Document-management-adjacent CPV", 12, ("48311000", "48311100", "48316000", "48317000"), (), ("document management", "records management", "content management")),
    ("cpv_workflow_case", "Workflow / case-management-adjacent CPV", 10, ("72212330", "72212331", "72262000", "72268000"), (), ("workflow", "process automation", "case management", "software implementation")),
    ("cpv_archiving_records", "Archiving / records / scanning-adjacent CPV", 8, ("79995100", "79999100", "92512000", "72317000"), (), ("archiving", "archives", "digitization", "digitisation", "scanning", "records")),
    ("cpv_infrastructure_only", "Infrastructure-only CPV", -15, (), ("302", "324", "325", "488", "503", "516"), ("network equipment", "telecommunications", "server", "hosting", "infrastructure")),
    ("cpv_construction_only", "Construction-only CPV", -15, (), ("45",), ("construction", "civil works", "building works")),
    ("cpv_security_only", "Security-tooling-only CPV", -12, (), ("351", "4873", "4876"), ("security", "firewall", "antivirus", "endpoint protection")),
)


@dataclass(slots=True)
class MatchContext:
    scopes: dict[str, str]
    lot_titles: list[str]
    lot_descriptions: list[str]
    cpv_codes: list[str]
    cpv_labels: list[str]

    @property
    def full_text(self) -> str:
        return self.scopes["all"]


@dataclass(slots=True)
class TermMatch:
    term: str
    scope: str
    matched_as: str


class ScoringEngine:
    def __init__(self, *, keyword_pack: KeywordPack, scoring_version: str) -> None:
        self.keyword_pack = keyword_pack
        self.scoring_version = scoring_version

    def score(
        self,
        notice: NormalizedNotice,
        *,
        profile: SearchProfile,
        evaluated_at: datetime | None = None,
        exclude_old: bool = True,
        include_soft_locks: bool = True,
    ) -> ScoreResult:
        del profile
        now = (evaluated_at or datetime.now(tz=UTC)).astimezone(UTC)
        context = self._build_match_context(notice)
        result = ScoreResult(analysis_timestamp=now, scoring_version=self.scoring_version)

        matched_domains: list[str] = []
        positive_reasons: list[str] = []
        negative_reasons: list[str] = []
        hard_blockers: list[str] = []
        soft_blockers: list[str] = []
        questions: list[str] = []

        deadline_days = self._days_until_deadline(notice.deadline, now)
        publication_days = self._publication_age_days(notice.publication_date, now.date())
        if deadline_days is not None and deadline_days < 7:
            result.viable_timing = False
            hard_blockers.append("deadline under 7 days")
            negative_reasons.append("deadline under 7 days")
            result.timing_flags.append({"flag": "deadline_under_7_days", "message": "Submission deadline is under 7 days away."})
            self._record_signal(
                result,
                signal_list=result.negative_signals,
                signal=SignalEvidence(id="timing.deadline_under_7_days", label="Deadline under 7 days", points=-10, evidence=[notice.deadline.isoformat()] if notice.deadline else [], category="negative"),
                rule_id="timing.deadline_under_7_days",
            )
        if exclude_old and publication_days is not None and publication_days > 90:
            result.viable_timing = False
            hard_blockers.append("publication older than 90 days")
            negative_reasons.append("publication older than 90 days")
            result.timing_flags.append({"flag": "publication_older_than_90_days", "message": "Notice was published more than 90 days ago."})
            self._record_signal(
                result,
                signal_list=result.negative_signals,
                signal=SignalEvidence(id="timing.publication_older_than_90_days", label="Publication older than 90 days", points=-10, evidence=[notice.publication_date.isoformat()] if notice.publication_date else [], category="negative"),
                rule_id="timing.publication_older_than_90_days",
            )

        score = 0
        score += self.score_positive_domains(context, result, matched_domains, positive_reasons)
        score += self.score_public_sector_signals(context, notice, result, positive_reasons)
        score += self.score_structural_fit(context, result, positive_reasons)
        score += self.score_cpv(context.cpv_codes, context.cpv_labels, result, positive_reasons, negative_reasons)
        score += self.score_negative_scope(context.full_text, result, negative_reasons, hard_blockers)

        lock_status, lock_matches, openness_matches = self.detect_platform_lock(context.full_text)
        if openness_matches:
            result.openness_detected = True
            self._record_signal(
                result,
                signal_list=result.platform_lock_signals,
                signal=SignalEvidence(id="platform_openness", label="Platform openness detected", points=0, evidence=openness_matches, category="platform_openness", severity="open"),
                rule_id="platform.open",
            )
        if lock_status == "hard":
            result.hard_lock_detected = True
            hard_blockers.append("hard platform lock")
            questions.append("Is the authority open to an alternative platform?")
            score -= 35
            negative_reasons.append("hard platform lock")
            self._record_signal(
                result,
                signal_list=result.platform_lock_signals,
                signal=SignalEvidence(id="hard_platform_lock", label="Hard platform lock detected", points=-35, evidence=lock_matches, category="platform_lock", severity="hard"),
                rule_id="platform.hard_lock",
            )
        elif lock_status == "soft" and include_soft_locks:
            result.soft_lock_detected = True
            soft_blockers.append("soft platform lock")
            questions.append("Is the buyer open to an alternative platform?")
            score -= 10
            negative_reasons.append("soft platform lock")
            self._record_signal(
                result,
                signal_list=result.platform_lock_signals,
                signal=SignalEvidence(id="soft_platform_lock", label="Soft platform lock detected", points=-10, evidence=lock_matches, category="platform_lock", severity="soft"),
                rule_id="platform.soft_lock",
            )

        if notice.deadline is None:
            result.viable_timing = False
            result.timing_flags.append({"flag": "missing_deadline", "message": "Submission deadline missing."})
            questions.append("What is the submission deadline?")
            negative_reasons.append("deadline missing")
            score -= 6
            self._record_signal(
                result,
                signal_list=result.negative_signals,
                signal=SignalEvidence(id="timing.missing_deadline", label="Missing submission deadline", points=-6, evidence=[], category="negative"),
                rule_id="timing.missing_deadline",
            )
        else:
            if not hard_blockers:
                result.viable_timing = True
            self._record_rule(result, rule_id="timing.deadline_viable", label="Deadline at or above 7 days", points=0, evidence=[notice.deadline.isoformat()])

        if self.thin_scope_text(notice, context):
            negative_reasons.append("limited scope text")
            score -= 3
            self._record_signal(
                result,
                signal_list=result.negative_signals,
                signal=SignalEvidence(id="scope.thin_text", label="Description too thin for confident classification", points=-3, evidence=[], category="negative"),
                rule_id="scope.thin_text",
            )
        if self._only_lot_title_present(context, notice):
            negative_reasons.append("lot title only")
            score -= 3
            self._record_signal(
                result,
                signal_list=result.negative_signals,
                signal=SignalEvidence(id="scope.only_lot_title", label="Only lot title present with no usable scope text", points=-3, evidence=context.lot_titles[:2], category="negative"),
                rule_id="scope.only_lot_title",
            )
        if self._detect_scanning_mix_soft_blocker(context.full_text):
            soft_blockers.append("heavy scanning / OCR mix")
            questions.append("Are OCR, capture, and bulk digitization expected from the same vendor?")
        if self._detect_certification_soft_blocker(context.full_text):
            soft_blockers.append("certification or OEM restrictions")
            questions.append("Are there mandatory local OEM or certification requirements?")
        if self._detect_fixed_stack_uncertainty(context.full_text):
            soft_blockers.append("product vs implementation scope unclear")
            questions.append("Is the scope a product/platform procurement or implementation of a fixed stack?")
        if any(signal.id == "delivery_scope" for signal in result.positive_signals):
            questions.append("What integrations are mandatory?")
        if any(self._contains_term(context.full_text, normalize_text(term)) for term in ("hosting", "cloud hosting", "saas")):
            questions.append("Is hosting part of the tender?")
        questions.append("How many end-users and departments are in scope?")

        if self._is_nonsoftware_hard_blocker(context.full_text, matched_domains, result.negative_signals):
            hard_blockers.append("notice is clearly non-software / hardware-only / works-only")

        result.score = max(0, min(100, score))
        result.fit_label = self.classify(score=result.score, blockers=hard_blockers, soft_blockers=soft_blockers, force_no=bool(hard_blockers))
        result.priority_bucket = self._determine_priority(result.fit_label, result.score)
        result.confidence_indicator = self._determine_confidence(result, notice, context)
        result.qualification_questions = unique_preserve_order(question for question in questions if question)
        result.reasoning = self._build_reasoning(result, matched_domains, positive_reasons, negative_reasons, hard_blockers, soft_blockers, deadline_days)
        result.keyword_hits = self._dedupe_keyword_hits(result.keyword_hits)
        return result

    def score_positive_domains(self, context: MatchContext, result: ScoreResult, matched_domains: list[str], positive_reasons: list[str]) -> int:
        total = 0
        for group_id, label, points, scopes, terms in DOMAIN_RULES:
            matches = self._match_terms(context, terms, scopes=scopes)
            if not matches:
                continue
            total += points
            matched_domains.append(label)
            positive_reasons.append(label)
            self._record_domain_match(result, group_id=group_id, label=label, points=points, matches=matches)
        return total

    def score_public_sector_signals(self, context: MatchContext, notice: NormalizedNotice, result: ScoreResult, positive_reasons: list[str]) -> int:
        del notice
        total = 0
        buyer_matches = self._match_terms(context, BUYER_TERMS, scopes=("buyer", "title", "summary"))
        if buyer_matches:
            total += 12
            positive_reasons.append("public-sector buyer signal")
            self._record_positive_signal(result, signal_id="public_sector_buyer", label="Public-sector buyer signal", points=12, matches=buyer_matches)
        enterprise_matches = self._match_terms(context, ENTERPRISE_TERMS, scopes=("summary", "metadata", "all"))
        if enterprise_matches:
            total += 8
            positive_reasons.append("enterprise-wide or governance signal")
            self._record_positive_signal(result, signal_id="enterprise_rollout", label="Enterprise-wide / governance signal", points=8, matches=enterprise_matches)
        delivery_matches = self._match_terms(context, DELIVERY_TERMS, scopes=("summary", "metadata", "all"))
        if delivery_matches:
            total += 6
            positive_reasons.append("implementation and rollout scope")
            self._record_positive_signal(result, signal_id="delivery_scope", label="Implementation / migration / integration scope", points=6, matches=delivery_matches)
        return total

    def score_structural_fit(self, context: MatchContext, result: ScoreResult, positive_reasons: list[str]) -> int:
        total = 0
        repository_workflow = self._collect_combo_evidence(context.full_text, REPOSITORY_TERMS, WORKFLOW_TERMS)
        if repository_workflow:
            total += 10
            positive_reasons.append("repository and workflow combined")
            self._record_combo_signal(result, signal_id="repository_workflow", label="Repository + workflow combined scope", points=10, evidence=repository_workflow)
        records_search_retention = self._collect_combo_evidence(context.full_text, RECORDS_TERMS, SEARCH_TERMS, RETENTION_TERMS)
        if records_search_retention:
            total += 8
            positive_reasons.append("records, search, and retention combined")
            self._record_combo_signal(result, signal_id="records_search_retention", label="Records + search + retention pattern", points=8, evidence=records_search_retention)
        approvals_notifications_audit = self._collect_combo_evidence(context.full_text, APPROVAL_TERMS, NOTIFICATION_TERMS, AUDIT_TERMS)
        if approvals_notifications_audit:
            total += 8
            positive_reasons.append("approvals, notifications, and audit trail combined")
            self._record_combo_signal(result, signal_id="approvals_notifications_audit", label="Approvals + notifications + audit trail pattern", points=8, evidence=approvals_notifications_audit)
        integration_stack = self._collect_combo_evidence(context.full_text, ("integration", "integrations"), INTEGRATION_SYSTEM_TERMS)
        if integration_stack:
            total += 6
            positive_reasons.append("integration with enterprise systems")
            self._record_combo_signal(result, signal_id="integration_enterprise_systems", label="Integration with ERP / HR / email / identity", points=6, evidence=integration_stack)
        return total

    def score_cpv(self, codes: list[str], labels: list[str], result: ScoreResult, positive_reasons: list[str], negative_reasons: list[str]) -> int:
        total = 0
        normalized_codes = unique_preserve_order(code.strip() for code in codes if code and code.strip())
        normalized_labels = [normalize_text(label) for label in labels if label]
        for rule_id, label, points, exact_codes, prefixes, label_terms in CPV_RULES:
            evidence: list[str] = [code for code in normalized_codes if code in exact_codes or any(code.startswith(prefix) for prefix in prefixes)]
            for normalized_label in normalized_labels:
                for term in label_terms:
                    if self._contains_term(normalized_label, normalize_text(term)):
                        evidence.append(term)
            evidence = unique_preserve_order(evidence)
            if not evidence:
                continue
            total += points
            signal = SignalEvidence(id=rule_id, label=label, points=points, evidence=evidence, category="positive" if points > 0 else "negative")
            self._record_signal(result, signal_list=result.positive_signals if points > 0 else result.negative_signals, signal=signal, rule_id=rule_id)
            if points > 0:
                positive_reasons.append(label)
            else:
                negative_reasons.append(label)
        return total

    def score_negative_scope(self, text: str, result: ScoreResult, negative_reasons: list[str], hard_blockers: list[str]) -> int:
        total = 0
        for rule_id, label, points, terms in NEGATIVE_RULES:
            evidence = [term for term in terms if self._contains_term(text, normalize_text(term))]
            if not evidence:
                continue
            total += points
            negative_reasons.append(label)
            self._record_signal(result, signal_list=result.negative_signals, signal=SignalEvidence(id=rule_id, label=label, points=points, evidence=evidence, category="negative"), rule_id=rule_id)
            if rule_id in {"hardware_only", "construction_only"}:
                hard_blockers.append(label)
        return total

    def detect_platform_lock(self, text: str) -> tuple[str, list[str], list[str]]:
        open_hits = unique_preserve_order(term for term in LOCK_OPEN if self._contains_term(text, normalize_text(term)))
        hard_hits: list[str] = []
        soft_hits: list[str] = []
        for platform in PLATFORMS:
            normalized_platform = normalize_text(platform)
            if not self._contains_term(text, normalized_platform):
                continue
            if any(self._contains_term(text, normalize_text(trigger)) for trigger in LOCK_HARD):
                hard_hits.append(platform)
            elif any(self._contains_term(text, normalize_text(trigger)) for trigger in LOCK_SOFT):
                soft_hits.append(platform)
            if any(self._contains_term(text, normalize_text(term)) for term in (f"implementation partner for {platform}", f"implementation of {platform}", f"{platform} as the delivery platform")):
                hard_hits.append(platform)
        hard_hits = unique_preserve_order(hard_hits)
        soft_hits = unique_preserve_order(soft_hits)
        if hard_hits and not open_hits:
            return "hard", hard_hits, open_hits
        if hard_hits or soft_hits:
            return "soft", hard_hits or soft_hits, open_hits
        return "none", [], open_hits

    def thin_scope_text(self, notice: NormalizedNotice, context: MatchContext) -> bool:
        return len(normalize_text(notice.summary or "")) < 40 and len(" ".join(context.lot_titles + context.lot_descriptions)) < 40

    def classify(self, *, score: int, blockers: list[str], soft_blockers: list[str], force_no: bool = False) -> FitLabel:
        if force_no or blockers or score < 30:
            return FitLabel.NO
        if 30 <= score <= 59 or (score >= 60 and soft_blockers):
            return FitLabel.CONDITIONAL
        return FitLabel.YES

    def _determine_priority(self, fit_label: FitLabel, score: int) -> PriorityBucket:
        if fit_label == FitLabel.YES:
            return PriorityBucket.HIGH if score >= 70 else PriorityBucket.GOOD
        return PriorityBucket.WATCHLIST if fit_label == FitLabel.CONDITIONAL else PriorityBucket.IGNORE

    def _determine_confidence(self, result: ScoreResult, notice: NormalizedNotice, context: MatchContext) -> ConfidenceIndicator:
        evidence_count = len(result.keyword_hits) + len(result.positive_signals)
        has_scope = len(context.scopes["summary"]) >= 80 or len(" ".join(context.lot_descriptions)) >= 80
        if evidence_count >= 8 and notice.deadline is not None and has_scope:
            return ConfidenceIndicator.HIGH
        if evidence_count >= 4 and (notice.deadline is not None or has_scope):
            return ConfidenceIndicator.MEDIUM
        return ConfidenceIndicator.LOW

    def _build_reasoning(self, result: ScoreResult, matched_domains: list[str], positive_reasons: list[str], negative_reasons: list[str], hard_blockers: list[str], soft_blockers: list[str], deadline_days: int | None) -> str:
        domains = ", ".join(unique_preserve_order(matched_domains)[:4]) or "none"
        positives = ", ".join(unique_preserve_order(positive_reasons)[:4]) or "none"
        negatives = f"Weakening factors: {', '.join(unique_preserve_order(negative_reasons)[:3])}." if negative_reasons else "No major weakening factors detected."
        platform_text = "Hard blocker detected." if hard_blockers else "Soft commercial blocker detected." if soft_blockers else "No hard platform lock detected." if not result.openness_detected else "No hard platform lock detected and platform openness is indicated."
        timing = "Deadline missing and review is needed." if deadline_days is None else f"Deadline {deadline_days} days away."
        return f"Matched domains: {domains}. Positive signals: {positives}. {negatives} {platform_text} {timing} Classification: {result.fit_label.value} / {result.priority_bucket.value}."

    def _build_match_context(self, notice: NormalizedNotice) -> MatchContext:
        raw = notice.raw_payload_json or {}
        lot_titles = self._extract_lot_text(raw, title_only=True)
        lot_descriptions = self._extract_lot_text(raw, title_only=False)
        cpv_labels = self._extract_cpv_labels(raw)
        scopes = {
            "title": normalize_text(notice.title or ""),
            "summary": normalize_text(" ".join(fragment for fragment in [notice.summary or "", " ".join(lot_titles), " ".join(lot_descriptions)] if fragment)),
            "buyer": normalize_text(notice.buyer or ""),
            "metadata": normalize_text(" ".join(fragment for fragment in [notice.notice_type or "", notice.procedure_type or "", notice.place_of_performance or "", notice.contract_duration or "", " ".join(cpv_labels), " ".join(notice.cpv_codes)] if fragment)),
        }
        scopes["all"] = normalize_text(" ".join(value for value in scopes.values() if value))
        return MatchContext(scopes=scopes, lot_titles=lot_titles, lot_descriptions=lot_descriptions, cpv_codes=unique_preserve_order(notice.cpv_codes), cpv_labels=cpv_labels)

    def _extract_lot_text(self, raw: dict[str, Any], *, title_only: bool) -> list[str]:
        preferred_keys = {"lot-title", "lot_title", "lotTitle", "title"} if title_only else {"lot-description", "lot_description", "lotDescription", "description", "summary"}
        values: list[str] = []
        def walk(node: Any, in_lot_branch: bool = False) -> None:
            if isinstance(node, dict):
                branch_is_lot = in_lot_branch or any("lot" in str(key).lower() for key in node)
                for key, value in node.items():
                    if branch_is_lot and str(key) in preferred_keys and isinstance(value, str) and value.strip():
                        values.append(value.strip())
                    walk(value, branch_is_lot)
            elif isinstance(node, list):
                for item in node:
                    walk(item, in_lot_branch)
        walk(raw)
        return unique_preserve_order(values)

    def _extract_cpv_labels(self, raw: dict[str, Any]) -> list[str]:
        labels: list[str] = []
        for key in ("classification-cpv", "main-classification-cpv", "cpv_codes", "cpv-labels", "cpvLabels"):
            labels.extend(self._stringify_cpv_labels(raw.get(key) or raw.get(key.replace("-", "_"))))
        return unique_preserve_order(labels)

    def _stringify_cpv_labels(self, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            value = value.strip()
            return [value] if value and not value.isdigit() else []
        if isinstance(value, dict):
            labels: list[str] = []
            for field_name in ("label", "name", "text", "value"):
                field = value.get(field_name)
                if isinstance(field, str) and field.strip() and not field.strip().isdigit():
                    labels.append(field.strip())
            for nested in value.values():
                labels.extend(self._stringify_cpv_labels(nested))
            return labels
        if isinstance(value, list):
            labels: list[str] = []
            for item in value:
                labels.extend(self._stringify_cpv_labels(item))
            return labels
        return []

    def _match_terms(self, context: MatchContext, terms: tuple[str, ...] | list[str], *, scopes: tuple[str, ...]) -> list[TermMatch]:
        matches: list[TermMatch] = []
        for term in terms:
            normalized = normalize_text(term)
            if not normalized:
                continue
            for scope in scopes:
                candidate_scopes = ("title", "summary", "buyer", "metadata") if scope == "all" else (scope,)
                matched_scope = next(
                    (
                        candidate_scope
                        for candidate_scope in candidate_scopes
                        if context.scopes.get(candidate_scope, "")
                        and self._contains_term(context.scopes[candidate_scope], normalized)
                    ),
                    None,
                )
                if matched_scope:
                    matches.append(TermMatch(term=term, scope=matched_scope, matched_as=normalized))
                    break
        deduped: list[TermMatch] = []
        seen: set[tuple[str, str]] = set()
        for match in matches:
            key = (match.term.lower(), match.scope)
            if key not in seen:
                seen.add(key)
                deduped.append(match)
        return deduped

    def _contains_term(self, text: str, term: str) -> bool:
        if not text or not term:
            return False
        if term in ACRONYMS or (" " not in term and len(term) <= 4):
            return re.search(rf"(?<!\w){re.escape(term)}(?!\w)", text) is not None
        return term in text

    def _collect_combo_evidence(self, text: str, *term_groups: tuple[str, ...]) -> list[str]:
        evidence: list[str] = []
        for group in term_groups:
            match = next((term for term in group if self._contains_term(text, normalize_text(term))), None)
            if not match:
                return []
            evidence.append(match)
        return evidence

    def _record_domain_match(self, result: ScoreResult, *, group_id: str, label: str, points: int, matches: list[TermMatch]) -> None:
        result.keyword_hits.extend({"group_id": group_id, "term": match.term, "matched_as": match.matched_as, "scope": match.scope} for match in matches)
        result.domain_hits.append({"group_id": group_id, "label": label, "terms": unique_preserve_order(match.term for match in matches), "scopes": unique_preserve_order(match.scope for match in matches)})
        self._record_signal(result, signal_list=result.positive_signals, signal=SignalEvidence(id=group_id, label=label, points=points, evidence=self._format_match_evidence(matches), category="positive"), rule_id=f"positive.{group_id}")

    def _record_positive_signal(self, result: ScoreResult, *, signal_id: str, label: str, points: int, matches: list[TermMatch]) -> None:
        self._record_signal(result, signal_list=result.positive_signals, signal=SignalEvidence(id=signal_id, label=label, points=points, evidence=self._format_match_evidence(matches), category="positive"), rule_id=f"positive.{signal_id}")

    def _record_combo_signal(self, result: ScoreResult, *, signal_id: str, label: str, points: int, evidence: list[str]) -> None:
        self._record_signal(result, signal_list=result.positive_signals, signal=SignalEvidence(id=signal_id, label=label, points=points, evidence=evidence, category="positive"), rule_id=f"positive.{signal_id}")

    def _record_signal(self, result: ScoreResult, *, signal_list: list[SignalEvidence], signal: SignalEvidence, rule_id: str) -> None:
        signal_list.append(signal)
        contribution = RuleContribution(rule_id=rule_id, label=signal.label, points=signal.points, evidence=signal.evidence)
        result.rules_fired.append(contribution)
        result.score_breakdown.append(contribution)

    def _record_rule(self, result: ScoreResult, *, rule_id: str, label: str, points: int, evidence: list[str]) -> None:
        contribution = RuleContribution(rule_id=rule_id, label=label, points=points, evidence=evidence)
        result.rules_fired.append(contribution)
        result.score_breakdown.append(contribution)

    def _forced_no(self, result: ScoreResult, rule_id: str, label: str, reasoning: str, evidence: list[str]) -> ScoreResult:
        result.viable_timing = False
        self._record_rule(result, rule_id=rule_id, label=label, points=0, evidence=evidence)
        result.score = 0
        result.fit_label = FitLabel.NO
        result.priority_bucket = PriorityBucket.IGNORE
        result.confidence_indicator = ConfidenceIndicator.HIGH
        result.reasoning = reasoning
        return result

    def _days_until_deadline(self, deadline: datetime | None, now: datetime) -> int | None:
        return None if deadline is None else int((deadline - now).total_seconds() // 86400)

    def _publication_age_days(self, publication_date: date | None, today: date) -> int | None:
        return None if publication_date is None else (today - publication_date).days

    def _format_match_evidence(self, matches: list[TermMatch]) -> list[str]:
        return unique_preserve_order(f"{match.term} [{match.scope}]" for match in matches)

    def _only_lot_title_present(self, context: MatchContext, notice: NormalizedNotice) -> bool:
        return bool(context.lot_titles) and not notice.summary and not context.lot_descriptions

    def _detect_scanning_mix_soft_blocker(self, text: str) -> bool:
        return any(self._contains_term(text, normalize_text(term)) for term in SCANNING_TERMS) and any(self._contains_term(text, normalize_text(term)) for term in ("document management", "records management", "workflow", "case management"))

    def _detect_certification_soft_blocker(self, text: str) -> bool:
        return any(self._contains_term(text, normalize_text(term)) for term in CERTIFICATION_TERMS)

    def _detect_fixed_stack_uncertainty(self, text: str) -> bool:
        return self._contains_term(text, "implementation partner") or self._contains_term(text, "implementation services")

    def _is_nonsoftware_hard_blocker(self, text: str, matched_domains: list[str], negative_signals: list[SignalEvidence]) -> bool:
        if matched_domains:
            return False
        strong_negative_ids = {signal.id for signal in negative_signals} & {"hardware_only", "construction_only", "infrastructure_only"}
        return bool(strong_negative_ids and any(self._contains_term(text, normalize_text(term)) for term in ("supply of", "construction works", "network infrastructure")))

    def _dedupe_keyword_hits(self, hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
        deduped: list[dict[str, Any]] = []
        seen: set[tuple[str, str, str]] = set()
        for hit in hits:
            key = (str(hit.get("group_id") or ""), str(hit.get("term") or "").lower(), str(hit.get("scope") or "").lower())
            if key in seen:
                continue
            seen.add(key)
            deduped.append(hit)
        return deduped
