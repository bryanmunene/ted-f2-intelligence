from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Enum, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdMixin
from app.models.enums import ScanStatus


class ScanRun(IdMixin, Base):
    __tablename__ = "scan_runs"

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[ScanStatus] = mapped_column(
        Enum(ScanStatus, native_enum=False),
        default=ScanStatus.STARTED,
        nullable=False,
        index=True,
    )
    profile_name: Mapped[str] = mapped_column(String(100), nullable=False)
    query_parameters: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    total_notices_returned: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_notices_ingested: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_after_timing_filters: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_high_fit: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_conditional: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_ignored: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    request_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rate_limit_events: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)

