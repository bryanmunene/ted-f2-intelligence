from __future__ import annotations

from sqlalchemy import func, select

from app.database import create_all_schema, get_session_factory
from app.models import Notice
from scripts.seed_sample_data import main as seed_sample_data


def ensure_streamlit_demo_data() -> bool:
    create_all_schema()

    session = get_session_factory()()
    try:
        notice_count = session.scalar(select(func.count()).select_from(Notice)) or 0
    finally:
        session.close()

    if notice_count > 0:
        return False

    seed_sample_data()
    return True
