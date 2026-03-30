from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User


class UserRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_or_create(self, email: str, display_name: str, auth_provider: str) -> User:
        existing = self.session.scalar(select(User).where(User.email == email))
        if existing:
            existing.display_name = display_name
            existing.auth_provider = auth_provider
            return existing

        user = User(email=email, display_name=display_name, auth_provider=auth_provider)
        self.session.add(user)
        self.session.flush()
        return user

