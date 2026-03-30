from __future__ import annotations

from sqlalchemy import Enum, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, IdMixin, TimestampMixin
from app.models.enums import AuditEventType


class AuditEvent(IdMixin, TimestampMixin, Base):
    __tablename__ = "audit_events"

    event_type: Mapped[AuditEventType] = mapped_column(
        Enum(AuditEventType, native_enum=False),
        nullable=False,
        index=True,
    )
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    actor_user_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    actor_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    actor_display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    actor_user = relationship("User", back_populates="audit_events")

