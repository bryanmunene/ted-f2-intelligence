from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AppSetting


class SettingsRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_all(self) -> list[AppSetting]:
        return list(self.session.scalars(select(AppSetting).order_by(AppSetting.key)).all())

