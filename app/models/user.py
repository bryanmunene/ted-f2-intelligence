from __future__ import annotations

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, IdMixin, TimestampMixin


class User(IdMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    auth_provider: Mapped[str] = mapped_column(String(64), nullable=False, default="internal-default")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    saved_searches = relationship("SavedSearch", back_populates="created_by")
    analyst_notes = relationship("AnalystNote", back_populates="user")
    audit_events = relationship("AuditEvent", back_populates="actor_user")

