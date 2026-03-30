from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from fastapi import APIRouter, Depends

from app.config import Settings, get_settings
from app.database import get_db_session

router = APIRouter(tags=["health"])


@router.get("/health/live")
def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready")
def ready(
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> dict[str, str]:
    session.execute(text("SELECT 1"))
    return {"status": "ready", "environment": settings.env}

