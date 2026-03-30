from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.enums import ConfidenceIndicator, FitLabel, PriorityBucket


class SignalEvidence(BaseModel):
    id: str
    label: str
    points: int
    evidence: list[str] = Field(default_factory=list)
    category: str
    severity: str | None = None


class RuleContribution(BaseModel):
    rule_id: str
    label: str
    points: int
    evidence: list[str] = Field(default_factory=list)


class ScoreResult(BaseModel):
    analysis_timestamp: datetime
    scoring_version: str
    keyword_hits: list[dict[str, Any]] = Field(default_factory=list)
    domain_hits: list[dict[str, Any]] = Field(default_factory=list)
    positive_signals: list[SignalEvidence] = Field(default_factory=list)
    negative_signals: list[SignalEvidence] = Field(default_factory=list)
    platform_lock_signals: list[SignalEvidence] = Field(default_factory=list)
    timing_flags: list[dict[str, Any]] = Field(default_factory=list)
    rules_fired: list[RuleContribution] = Field(default_factory=list)
    score_breakdown: list[RuleContribution] = Field(default_factory=list)
    score: int = 0
    fit_label: FitLabel = FitLabel.NO
    priority_bucket: PriorityBucket = PriorityBucket.IGNORE
    confidence_indicator: ConfidenceIndicator = ConfidenceIndicator.LOW
    qualification_questions: list[str] = Field(default_factory=list)
    reasoning: str = ""
    hard_lock_detected: bool = False
    soft_lock_detected: bool = False
    openness_detected: bool = False
    viable_timing: bool = False

    def repository_payload(self) -> dict[str, Any]:
        return {
            "analysis_timestamp": self.analysis_timestamp,
            "scoring_version": self.scoring_version,
            "keyword_hits": self.keyword_hits,
            "domain_hits": self.domain_hits,
            "positive_signals": [item.model_dump() for item in self.positive_signals],
            "negative_signals": [item.model_dump() for item in self.negative_signals],
            "platform_lock_signals": [item.model_dump() for item in self.platform_lock_signals],
            "timing_flags": self.timing_flags,
            "rules_fired": [item.model_dump() for item in self.rules_fired],
            "score_breakdown": [item.model_dump() for item in self.score_breakdown],
            "score": self.score,
            "fit_label": self.fit_label,
            "priority_bucket": self.priority_bucket,
            "confidence_indicator": self.confidence_indicator,
            "qualification_questions": self.qualification_questions,
            "reasoning": self.reasoning,
            "hard_lock_detected": self.hard_lock_detected,
            "soft_lock_detected": self.soft_lock_detected,
            "openness_detected": self.openness_detected,
            "viable_timing": self.viable_timing,
        }

