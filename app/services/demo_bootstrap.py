from __future__ import annotations

from sqlalchemy import func, select

from app.database import create_all_schema, get_session_factory
from app.models import AuditEvent, Notice, ScanRun
from scripts.seed_sample_data import main as seed_sample_data


def ensure_streamlit_storage(*, purge_demo: bool = True) -> dict[str, int]:
    create_all_schema()

    session = get_session_factory()()
    try:
        purged_demo_notices = 0
        purged_demo_scans = 0
        purged_demo_audits = 0

        if purge_demo:
            demo_notices = [
                notice
                for notice in session.scalars(select(Notice)).all()
                if isinstance(notice.raw_payload_json, dict) and notice.raw_payload_json.get("_seed_fixture")
            ]
            purged_demo_notices = len(demo_notices)
            for notice in demo_notices:
                session.delete(notice)

            demo_scans = [
                scan
                for scan in session.scalars(select(ScanRun)).all()
                if isinstance(scan.query_parameters, dict) and scan.query_parameters.get("source") == "fixture"
            ]
            demo_scan_ids = {scan.id for scan in demo_scans}
            purged_demo_scans = len(demo_scans)

            if demo_scan_ids:
                demo_audits = [
                    event
                    for event in session.scalars(select(AuditEvent)).all()
                    if event.entity_id in demo_scan_ids
                    or (isinstance(event.payload_json, dict) and event.payload_json.get("seeded"))
                ]
                purged_demo_audits = len(demo_audits)
                for event in demo_audits:
                    session.delete(event)

            for scan in demo_scans:
                session.delete(scan)

            session.commit()

        notice_count = session.scalar(select(func.count()).select_from(Notice)) or 0
    finally:
        session.close()

    return {
        "notice_count": int(notice_count),
        "purged_demo_notices": purged_demo_notices,
        "purged_demo_scans": purged_demo_scans,
        "purged_demo_audits": purged_demo_audits,
    }


def ensure_streamlit_demo_data() -> bool:
    state = ensure_streamlit_storage(purge_demo=False)
    if state["notice_count"] > 0:
        return False

    seed_sample_data()
    return True
