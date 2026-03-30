from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from math import floor

from app.config import KeywordPack, SearchProfile
from app.ingestion.models import NormalizedNotice
from app.models.enums import ConfidenceIndicator, FitLabel, PriorityBucket
from app.scoring.types import RuleContribution, ScoreResult, SignalEvidence
from app.utils.text import normalize_text, unique_preserve_order


@dataclass(slots=True)
class MatchContext:
    normalized_scopes: dict[str, str]
    raw_scopes: dict[str, str]

    @property
    def aggregate_normalized(self) -> str:
        return " ".join(value for value in self.normalized_scopes.values() if value)


@dataclass(slots=True)
class TermMatch:
    term: str
    matched_as: str
    scope: str
    weight_delta: int = 0


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
        now = (evaluated_at or datetime.now(tz=UTC)).astimezone(UTC)
        context = self._build_match_context(notice)
        corpus = context.aggregate_normalized
        title_corpus = context.normalized_scopes["title"]

        result = ScoreResult(
            analysis_timestamp=now,
            scoring_version=self.scoring_version,
        )

        raw_score = 0
        matched_positive_group_ids: set[str] = set()
        pack_positive = self.keyword_pack.positive_group_map()
        pack_negative = self.keyword_pack.negative_group_map()

        for group_id in profile.keyword_group_ids:
            group = pack_positive.get(group_id)
            if group is None:
                continue
            matches = self._match_terms(group.materialized_terms(), context)
            if not matches:
                continue
            matched_positive_group_ids.add(group.id)
            score_delta = (
                group.weight
                + max(0, len(matches) - 1) * group.extra_match_weight
                + sum(match.weight_delta for match in matches)
            )
            if any(match.scope == "title" for match in matches):
                score_delta += group.title_match_bonus
            if group.max_score is not None:
                score_delta = min(score_delta, group.max_score)
            raw_score += score_delta
            result.keyword_hits.extend(
                {
                    "group_id": group.id,
                    "term": match.term,
                    "matched_as": match.matched_as,
                    "scope": match.scope,
                }
                for match in matches
            )
            result.domain_hits.append(
                {
                    "group_id": group.id,
                    "label": group.name,
                    "terms": [match.term for match in matches],
                    "scopes": unique_preserve_order(match.scope for match in matches),
                }
            )
            signal = SignalEvidence(
                id=group.id,
                label=group.name,
                points=score_delta,
                evidence=self._format_match_evidence(matches),
                category="positive",
            )
            contribution = RuleContribution(
                rule_id=f"positive.{group.id}",
                label=group.name,
                points=score_delta,
                evidence=self._format_match_evidence(matches),
            )
            result.positive_signals.append(signal)
            result.rules_fired.append(contribution)
            result.score_breakdown.append(contribution)

        for group_id in profile.negative_group_ids:
            group = pack_negative.get(group_id)
            if group is None:
                continue
            matches = self._match_terms(group.materialized_terms(), context)
            if not matches:
                continue
            penalty = (
                group.penalty
                + max(0, len(matches) - 1) * group.extra_match_penalty
                + sum(match.weight_delta for match in matches)
            )
            if any(match.scope == "title" for match in matches):
                penalty += group.title_match_bonus
            if group.max_penalty is not None:
                penalty = min(penalty, group.max_penalty)
            raw_score -= penalty
            signal = SignalEvidence(
                id=group.id,
                label=group.name,
                points=-penalty,
                evidence=self._format_match_evidence(matches),
                category="negative",
            )
            contribution = RuleContribution(
                rule_id=f"negative.{group.id}",
                label=group.name,
                points=-penalty,
                evidence=self._format_match_evidence(matches),
            )
            result.negative_signals.append(signal)
            result.rules_fired.append(contribution)
            result.score_breakdown.append(contribution)

        raw_score += self._apply_combo_rules(result=result, matched_positive_group_ids=matched_positive_group_ids)
        raw_score += self._apply_platform_lock_logic(
            context=context,
            result=result,
            profile=profile,
            include_soft_locks=include_soft_locks,
        )
        raw_score += self._apply_timing_logic(
            notice=notice,
            result=result,
            evaluated_at=now,
            exclude_old=exclude_old,
        )
        raw_score += self._apply_strategic_weighting(notice=notice, corpus=corpus, profile=profile, result=result)

        result.score = max(0, min(100, raw_score))
        result.confidence_indicator = self._determine_confidence(result, notice)
        result.fit_label = self._determine_fit_label(result)
        result.priority_bucket = self._determine_priority(result)
        result.qualification_questions = self._build_questions(result, notice)
        result.reasoning = self._build_reasoning(result, title_corpus)
        result.keyword_hits = self._dedupe_keyword_hits(result.keyword_hits)
        return result

    def _apply_platform_lock_logic(
        self,
        *,
        context: MatchContext,
        result: ScoreResult,
        profile: SearchProfile,
        include_soft_locks: bool,
    ) -> int:
        total_delta = 0

        for signal in self.keyword_pack.platform_signals.hard_lock:
            matches = self._match_terms(signal.materialized_terms(), context)
            if not matches:
                continue
            penalty = floor(signal.penalty * profile.hard_lock_penalty_multiplier)
            total_delta -= penalty
            result.hard_lock_detected = True
            evidence = SignalEvidence(
                id=signal.id,
                label=signal.name,
                points=-penalty,
                evidence=self._format_match_evidence(matches),
                category="platform_lock",
                severity="hard",
            )
            contribution = RuleContribution(
                rule_id=f"platform.hard.{signal.id}",
                label=signal.name,
                points=-penalty,
                evidence=self._format_match_evidence(matches),
            )
            result.platform_lock_signals.append(evidence)
            result.rules_fired.append(contribution)
            result.score_breakdown.append(contribution)

        if include_soft_locks:
            for signal in self.keyword_pack.platform_signals.soft_lock:
                matches = self._match_terms(signal.materialized_terms(), context)
                if not matches:
                    continue
                penalty = floor(signal.penalty * profile.soft_lock_penalty_multiplier)
                total_delta -= penalty
                result.soft_lock_detected = True
                evidence = SignalEvidence(
                    id=signal.id,
                    label=signal.name,
                    points=-penalty,
                    evidence=self._format_match_evidence(matches),
                    category="platform_lock",
                    severity="soft",
                )
                contribution = RuleContribution(
                    rule_id=f"platform.soft.{signal.id}",
                    label=signal.name,
                    points=-penalty,
                    evidence=self._format_match_evidence(matches),
                )
                result.platform_lock_signals.append(evidence)
                result.rules_fired.append(contribution)
                result.score_breakdown.append(contribution)

        for signal in self.keyword_pack.platform_signals.openness:
            matches = self._match_terms(signal.materialized_terms(), context)
            if not matches:
                continue
            bonus = floor(signal.bonus * profile.openness_bonus_multiplier)
            total_delta += bonus
            result.openness_detected = True
            evidence = SignalEvidence(
                id=signal.id,
                label=signal.name,
                points=bonus,
                evidence=self._format_match_evidence(matches),
                category="platform_openness",
                severity="open",
            )
            contribution = RuleContribution(
                rule_id=f"platform.open.{signal.id}",
                label=signal.name,
                points=bonus,
                evidence=self._format_match_evidence(matches),
            )
            result.platform_lock_signals.append(evidence)
            result.rules_fired.append(contribution)
            result.score_breakdown.append(contribution)

        return total_delta

    def _apply_combo_rules(self, *, result: ScoreResult, matched_positive_group_ids: set[str]) -> int:
        total_delta = 0
        for combo_rule in self.keyword_pack.combo_rules:
            if not combo_rule.group_ids:
                continue
            if not all(group_id in matched_positive_group_ids for group_id in combo_rule.group_ids):
                continue
            total_delta += combo_rule.bonus
            signal = SignalEvidence(
                id=combo_rule.id,
                label=combo_rule.name,
                points=combo_rule.bonus,
                evidence=combo_rule.group_ids,
                category="combo",
            )
            contribution = RuleContribution(
                rule_id=f"combo.{combo_rule.id}",
                label=combo_rule.name,
                points=combo_rule.bonus,
                evidence=combo_rule.group_ids,
            )
            result.positive_signals.append(signal)
            result.rules_fired.append(contribution)
            result.score_breakdown.append(contribution)
        return total_delta

    def _apply_timing_logic(
        self,
        *,
        notice: NormalizedNotice,
        result: ScoreResult,
        evaluated_at: datetime,
        exclude_old: bool,
    ) -> int:
        timing = self.keyword_pack.timing
        score_delta = 0
        viable_timing = True

        if notice.deadline is None:
            viable_timing = False
            score_delta -= timing.missing_deadline_penalty
            result.timing_flags.append({"flag": "missing_deadline", "message": "Submission deadline missing."})
            contribution = RuleContribution(
                rule_id="timing.missing_deadline",
                label="Missing submission deadline",
                points=-timing.missing_deadline_penalty,
                evidence=[],
            )
            result.rules_fired.append(contribution)
            result.score_breakdown.append(contribution)
        else:
            days_to_deadline = (notice.deadline - evaluated_at).total_seconds() / 86400
            if days_to_deadline < timing.min_days_to_deadline:
                viable_timing = False
                score_delta -= timing.short_deadline_penalty
                result.timing_flags.append(
                    {
                        "flag": "expiring_soon",
                        "message": f"Deadline is within {timing.min_days_to_deadline} days.",
                    }
                )
                contribution = RuleContribution(
                    rule_id="timing.short_deadline",
                    label="Short submission window",
                    points=-timing.short_deadline_penalty,
                    evidence=[notice.deadline.isoformat()],
                )
                result.rules_fired.append(contribution)
                result.score_breakdown.append(contribution)
            else:
                score_delta += timing.viable_timing_bonus
                contribution = RuleContribution(
                    rule_id="timing.viable",
                    label="Viable submission timing",
                    points=timing.viable_timing_bonus,
                    evidence=[notice.deadline.isoformat()],
                )
                result.rules_fired.append(contribution)
                result.score_breakdown.append(contribution)

        if notice.publication_date is None:
            score_delta -= timing.missing_publication_date_penalty
            result.timing_flags.append(
                {"flag": "missing_publication_date", "message": "Publication date missing or unparseable."}
            )
            contribution = RuleContribution(
                rule_id="timing.missing_publication_date",
                label="Missing publication date",
                points=-timing.missing_publication_date_penalty,
                evidence=[],
            )
            result.rules_fired.append(contribution)
            result.score_breakdown.append(contribution)
        else:
            age_days = (evaluated_at.date() - notice.publication_date).days
            if exclude_old and age_days > timing.exclude_after_days_since_publication:
                viable_timing = False
                score_delta -= timing.stale_publication_penalty
                result.timing_flags.append(
                    {
                        "flag": "stale_publication",
                        "message": f"Notice was published more than {timing.exclude_after_days_since_publication} days ago.",
                    }
                )
                contribution = RuleContribution(
                    rule_id="timing.stale_publication",
                    label="Publication date outside viable review window",
                    points=-timing.stale_publication_penalty,
                    evidence=[notice.publication_date.isoformat()],
                )
                result.rules_fired.append(contribution)
                result.score_breakdown.append(contribution)

        result.viable_timing = viable_timing
        return score_delta

    def _apply_strategic_weighting(
        self,
        *,
        notice: NormalizedNotice,
        corpus: str,
        profile: SearchProfile,
        result: ScoreResult,
    ) -> int:
        strategic = self.keyword_pack.strategic_weighting
        total = 0

        if notice.buyer_country:
            country_code = notice.buyer_country.upper()
            if country_code in strategic.preferred_countries:
                points = strategic.preferred_countries[country_code]
                total += points
                contribution = RuleContribution(
                    rule_id=f"strategic.country.{country_code}",
                    label=f"Preferred country: {country_code}",
                    points=points,
                    evidence=[country_code],
                )
                result.rules_fired.append(contribution)
                result.score_breakdown.append(contribution)
            if country_code in profile.country_bias:
                points = profile.country_bias[country_code]
                total += points
                contribution = RuleContribution(
                    rule_id=f"profile.country.{country_code}",
                    label=f"Profile country bias: {country_code}",
                    points=points,
                    evidence=[country_code],
                )
                result.rules_fired.append(contribution)
                result.score_breakdown.append(contribution)

        buyer_text = normalize_text(notice.buyer)
        for keyword, points in strategic.preferred_buyer_keywords.items():
            if keyword in buyer_text:
                total += points
                contribution = RuleContribution(
                    rule_id=f"strategic.buyer.{keyword}",
                    label=f"Preferred buyer signal: {keyword}",
                    points=points,
                    evidence=[keyword],
                )
                result.rules_fired.append(contribution)
                result.score_breakdown.append(contribution)

        for keyword, points in strategic.preferred_sector_keywords.items():
            if keyword in corpus:
                total += points
                contribution = RuleContribution(
                    rule_id=f"strategic.sector.{keyword}",
                    label=f"Preferred sector signal: {keyword}",
                    points=points,
                    evidence=[keyword],
                )
                result.rules_fired.append(contribution)
                result.score_breakdown.append(contribution)

        for prefix in strategic.deprioritized_cpv_prefixes:
            if any(code.startswith(prefix) for code in notice.cpv_codes):
                penalty = strategic.deprioritization_penalty
                total -= penalty
                contribution = RuleContribution(
                    rule_id=f"strategic.cpv.{prefix}",
                    label=f"Deprioritized CPV prefix: {prefix}",
                    points=-penalty,
                    evidence=[prefix],
                )
                result.rules_fired.append(contribution)
                result.score_breakdown.append(contribution)
                break

        return total

    def _determine_confidence(self, result: ScoreResult, notice: NormalizedNotice) -> ConfidenceIndicator:
        evidence_count = len(result.positive_signals) + len(result.platform_lock_signals)
        missing_critical = int(not notice.deadline) + int(not notice.publication_date) + int(not notice.summary)
        if evidence_count >= 4 and missing_critical == 0:
            return ConfidenceIndicator.HIGH
        if evidence_count >= 2 and missing_critical <= 1:
            return ConfidenceIndicator.MEDIUM
        return ConfidenceIndicator.LOW

    def _determine_fit_label(self, result: ScoreResult) -> FitLabel:
        if result.hard_lock_detected and result.score < 70:
            return FitLabel.NO
        if result.hard_lock_detected and result.score >= 70:
            return FitLabel.CONDITIONAL
        if not result.viable_timing and result.score < 60:
            return FitLabel.NO
        if result.score >= 60:
            return FitLabel.YES
        if result.score >= 35:
            return FitLabel.CONDITIONAL
        return FitLabel.NO

    def _determine_priority(self, result: ScoreResult) -> PriorityBucket:
        if result.fit_label == FitLabel.YES:
            if result.score >= 75 and result.viable_timing and not result.hard_lock_detected:
                return PriorityBucket.HIGH
            return PriorityBucket.GOOD
        if result.fit_label == FitLabel.CONDITIONAL:
            if result.score >= 70 and result.viable_timing and not result.hard_lock_detected:
                return PriorityBucket.GOOD
            if result.score >= 35:
                return PriorityBucket.WATCHLIST
        return PriorityBucket.IGNORE

    def _build_questions(self, result: ScoreResult, notice: NormalizedNotice) -> list[str]:
        questions = list(self.keyword_pack.qualification_questions.default)
        if not notice.deadline:
            questions.extend(self.keyword_pack.qualification_questions.missing_deadline)
        if result.hard_lock_detected:
            questions.extend(self.keyword_pack.qualification_questions.hard_lock)
        elif result.soft_lock_detected:
            questions.extend(self.keyword_pack.qualification_questions.soft_lock)
        if any(signal.id == "interoperability" for signal in result.positive_signals):
            questions.extend(self.keyword_pack.qualification_questions.integration)
        if not result.viable_timing:
            questions.extend(self.keyword_pack.qualification_questions.timing)
        return unique_preserve_order(questions)

    def _build_reasoning(self, result: ScoreResult, title_corpus: str) -> str:
        positives = ", ".join(signal.label for signal in result.positive_signals[:3]) or "no strong F2 domain signals"
        negatives = ", ".join(signal.label for signal in result.negative_signals[:2]) or "no major penalty signals"
        lock_text = "hard platform lock detected" if result.hard_lock_detected else (
            "soft platform lock detected" if result.soft_lock_detected else "no strong platform lock detected"
        )
        timing_text = "timing appears viable" if result.viable_timing else "timing needs qualification or is weak"
        urgency = (
            "Review immediately."
            if result.priority_bucket == PriorityBucket.HIGH
            else "Review when capacity allows."
            if result.priority_bucket in {PriorityBucket.GOOD, PriorityBucket.WATCHLIST}
            else "Low review priority."
        )
        title_note = "Notice title is sparse." if len(title_corpus.split()) < 4 else ""
        return " ".join(
            part
            for part in [
                f"Positive fit drivers: {positives}.",
                f"Weakening factors: {negatives}.",
                f"Timing assessment: {timing_text}.",
                f"Platform assessment: {lock_text}.",
                title_note,
                urgency,
            ]
            if part
        )

    def _build_match_context(self, notice: NormalizedNotice) -> MatchContext:
        raw_scopes = {
            "title": notice.title or "",
            "summary": notice.summary or "",
            "buyer": notice.buyer or "",
            "metadata": " ".join(
                value
                for value in [
                    notice.title_translated_optional or "",
                    notice.notice_type or "",
                    notice.procedure_type or "",
                    notice.place_of_performance or "",
                    notice.contract_duration or "",
                    " ".join(notice.cpv_codes),
                ]
                if value
            ),
        }
        return MatchContext(
            normalized_scopes={scope: normalize_text(value) for scope, value in raw_scopes.items()},
            raw_scopes=raw_scopes,
        )

    def _match_terms(self, terms, context: MatchContext) -> list[TermMatch]:
        matches: list[TermMatch] = []
        for term in terms:
            if term.requires_all and not all(
                self._match_requirement(requirement, context.aggregate_normalized) for requirement in term.requires_all
            ):
                continue
            matched = self._match_single_term(term, context)
            if matched:
                matches.append(matched)
        return matches

    def _match_single_term(self, term, context: MatchContext) -> TermMatch | None:
        candidates = [term.text, *term.aliases]
        for scope in self._scopes_for(term.scope):
            normalized_text = context.normalized_scopes.get(scope, "")
            raw_text = context.raw_scopes.get(scope, "")
            if not normalized_text and not raw_text:
                continue
            for candidate in candidates:
                if self._candidate_matches(term.match_mode, candidate, normalized_text, raw_text):
                    return TermMatch(
                        term=term.text,
                        matched_as=candidate,
                        scope=scope,
                        weight_delta=term.weight_delta,
                    )
        return None

    def _candidate_matches(
        self,
        match_mode: str,
        candidate: str,
        normalized_text: str,
        raw_text: str,
    ) -> bool:
        if not candidate:
            return False
        if match_mode == "contains":
            return normalize_text(candidate) in normalized_text
        if match_mode == "acronym":
            pattern = re.compile(rf"(?<![A-Za-z0-9]){re.escape(candidate)}(?![A-Za-z0-9])")
            return bool(pattern.search(raw_text))
        normalized_candidate = normalize_text(candidate)
        if not normalized_candidate:
            return False
        pattern = re.compile(rf"(?<![a-z0-9]){re.escape(normalized_candidate)}(?![a-z0-9])")
        return bool(pattern.search(normalized_text))

    def _match_requirement(self, requirement: str, normalized_text: str) -> bool:
        normalized_requirement = normalize_text(requirement)
        if not normalized_requirement:
            return False
        pattern = re.compile(rf"(?<![a-z0-9]){re.escape(normalized_requirement)}(?![a-z0-9])")
        return bool(pattern.search(normalized_text))

    def _scopes_for(self, scope: str) -> list[str]:
        if scope == "all":
            return ["title", "summary", "buyer", "metadata"]
        return [scope]

    def _format_match_evidence(self, matches: list[TermMatch]) -> list[str]:
        evidence: list[str] = []
        for match in matches:
            if match.matched_as == match.term:
                evidence.append(f"{match.term} [{match.scope}]")
            else:
                evidence.append(f"{match.matched_as} -> {match.term} [{match.scope}]")
        return evidence

    def _dedupe_keyword_hits(self, hits: list[dict]) -> list[dict]:
        ordered_keys = unique_preserve_order(
            f"{hit['group_id']}::{hit['term']}::{hit['matched_as']}::{hit['scope']}" for hit in hits
        )
        deduped: list[dict] = []
        for key in ordered_keys:
            group_id, term, matched_as, scope = key.split("::", 3)
            deduped.append(
                {
                    "group_id": group_id,
                    "term": term,
                    "matched_as": matched_as,
                    "scope": scope,
                }
            )
        return deduped
