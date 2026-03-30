from __future__ import annotations

from sqlalchemy import JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdMixin, TimestampMixin


class AppSetting(IdMixin, TimestampMixin, Base):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    value_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

