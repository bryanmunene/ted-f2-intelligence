from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, IdMixin, TimestampMixin
from app.models.enums import ConfidenceIndicator, FitLabel, PriorityBucket


class Notice(IdMixin, TimestampMixin, Base):
    __tablename__ = "notices"

    ted_notice_id: Mapped[str | None] = mapped_column(String(255), index=True, nullable=True)
    publication_number: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    title_translated_optional: Mapped[str | None] = mapped_column(Text, nullable=True)
    buyer: Mapped[str | None] = mapped_column(String(512), nullable=True)
    buyer_country: Mapped[str | None] = mapped_column(String(8), index=True, nullable=True)
    place_of_performance: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notice_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    procedure_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cpv_codes: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    publication_date: Mapped[date | None] = mapped_column(Date, index=True, nullable=True)
    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True, nullable=True)
    contract_duration: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    html_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    pdf_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    xml_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_payload_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    extraction_version: Mapped[str] = mapped_column(String(64), nullable=False)
    saved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    dismissed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    last_scan_run_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("scan_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    analysis = relationship(
        "NoticeAnalysis",
        back_populates="notice",
        uselist=False,
        cascade="all, delete-orphan",
    )
    notes = relationship(
        "AnalystNote",
        back_populates="notice",
        cascade="all, delete-orphan",
        order_by="desc(AnalystNote.created_at)",
    )


class NoticeAnalysis(IdMixin, TimestampMixin, Base):
    __tablename__ = "notice_analysis"

    notice_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("notices.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    scoring_version: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    analysis_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    keyword_hits: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    domain_hits: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    positive_signals: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    negative_signals: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    platform_lock_signals: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    timing_flags: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    rules_fired: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    score_breakdown: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    score: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)
    fit_label: Mapped[FitLabel] = mapped_column(
        Enum(FitLabel, native_enum=False),
        nullable=False,
        default=FitLabel.NO,
        index=True,
    )
    priority_bucket: Mapped[PriorityBucket] = mapped_column(
        Enum(PriorityBucket, native_enum=False),
        nullable=False,
        default=PriorityBucket.IGNORE,
        index=True,
    )
    confidence_indicator: Mapped[ConfidenceIndicator] = mapped_column(
        Enum(ConfidenceIndicator, native_enum=False),
        nullable=False,
        default=ConfidenceIndicator.LOW,
    )
    qualification_questions: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    reasoning: Mapped[str] = mapped_column(Text, nullable=False)
    hard_lock_detected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    soft_lock_detected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    openness_detected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    viable_timing: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)

    notice = relationship("Notice", back_populates="analysis")

