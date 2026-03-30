from __future__ import annotations

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, IdMixin, TimestampMixin


class AnalystNote(IdMixin, TimestampMixin, Base):
    __tablename__ = "analyst_notes"

    notice_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("notices.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    note_text: Mapped[str] = mapped_column(Text, nullable=False)

    notice = relationship("Notice", back_populates="notes")
    user = relationship("User", back_populates="analyst_notes")

