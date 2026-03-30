from __future__ import annotations

import httpx

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.api.presenters import notice_to_detail_dict, scan_run_to_dict
from app.api.schemas import ScanRequestPayload
from app.config import get_settings
from app.deps import get_actor_context, get_db, get_scan_service, get_search_profiles
from app.models.enums import AuditEventType
from app.repositories.audit import AuditRepository
from app.repositories.notices import NoticeListFilters, NoticeRepository
from app.repositories.scan_runs import ScanRunRepository
from app.repositories.settings import SettingsRepository
from app.repositories.users import UserRepository
from app.services.scan_service import ScanService
from app.services.ted_documents import TedDocumentService
from app.utils.csrf import get_csrf_token, validate_csrf
from app.utils.time import format_date, format_datetime

settings = get_settings()
templates = Jinja2Templates(directory=str(settings.templates_dir))
templates.env.globals["csrf_token"] = get_csrf_token
templates.env.globals["app_name"] = settings.name
templates.env.filters["display_datetime"] = lambda value: format_datetime(value, settings.ui_timezone)
templates.env.filters["display_date"] = format_date

router = APIRouter(tags=["ui"])


def _base_context(request: Request) -> dict:
    return {"request": request, "active_path": request.url.path}


def _get_notice_or_404(session: Session, notice_id: str):
    notice = NoticeRepository(session).get_by_id(notice_id)
    if notice is None:
        raise HTTPException(status_code=404, detail="Notice not found.")
    return notice


@router.get("/")
def dashboard(request: Request, session: Session = Depends(get_db)):
    notice_repo = NoticeRepository(session)
    scan_repo = ScanRunRepository(session)
    metrics = notice_repo.dashboard_metrics()
    top_notices, _ = notice_repo.list(NoticeListFilters(), page=1, page_size=8)
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        _base_context(request)
        | {
            "metrics": metrics,
            "recent_scans": scan_repo.recent(limit=6),
            "top_notices": top_notices,
        },
    )


@router.get("/scan")
def scan_page(request: Request, search_profiles=Depends(get_search_profiles)):
    payload = ScanRequestPayload()
    return templates.TemplateResponse(
        request,
        "scan.html",
        _base_context(request)
        | {
            "profiles": search_profiles.profiles,
            "payload": payload,
        },
    )


@router.post("/scan/run")
def run_scan_page(
    request: Request,
    profile_name: str = Form(...),
    date_from: str | None = Form(default=None),
    date_to: str | None = Form(default=None),
    country: str | None = Form(default=None),
    cpv: str | None = Form(default=None),
    keyword_override: str | None = Form(default=None),
    include_conditional: str | None = Form(default=None),
    exclude_old: str | None = Form(default=None),
    include_soft_locks: str | None = Form(default=None),
    page_size: int = Form(default=50),
    max_pages: int = Form(default=2),
    csrf_token: str = Form(...),
    scan_service: ScanService = Depends(get_scan_service),
):
    validate_csrf(request, csrf_token)
    payload = ScanRequestPayload(
        profile_name=profile_name,
        date_from=date_from or None,
        date_to=date_to or None,
        country=country or None,
        cpv=cpv or None,
        keyword_override=keyword_override or None,
        include_conditional=include_conditional == "on",
        exclude_old=exclude_old == "on",
        include_soft_locks=include_soft_locks == "on",
        page_size=page_size,
        max_pages=max_pages,
    )
    outcome = scan_service.run_manual_scan(payload)
    redirect_url = f"/results?scan_id={outcome.scan_run_id}"
    if not payload.include_conditional:
        redirect_url += "&fit_label=YES"
    return RedirectResponse(url=redirect_url, status_code=303)


@router.get("/results")
def results_page(
    request: Request,
    country: str | None = None,
    fit_label: str | None = None,
    priority_bucket: str | None = None,
    min_score: int | None = Query(default=None, ge=0, le=100),
    hard_lock_only: bool = False,
    deadline_window_days: int | None = Query(default=None, ge=1, le=365),
    include_dismissed: bool = False,
    saved_only: bool = False,
    search: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    scan_id: str | None = None,
    session: Session = Depends(get_db),
):
    notice_repo = NoticeRepository(session)
    scan_repo = ScanRunRepository(session)
    filters = NoticeListFilters(
        country=country,
        fit_label=fit_label,
        priority_bucket=priority_bucket,
        min_score=min_score,
        hard_lock_only=hard_lock_only,
        deadline_window_days=deadline_window_days,
        include_dismissed=include_dismissed,
        saved_only=saved_only,
        search=search,
    )
    notices, total = notice_repo.list(filters, page=page, page_size=page_size)
    scan_run = scan_repo.get_by_id(scan_id) if scan_id else None
    return templates.TemplateResponse(
        request,
        "results.html",
        _base_context(request)
        | {
            "notices": notices,
            "total": total,
            "page": page,
            "page_size": page_size,
            "filters": filters,
            "scan_run": scan_run_to_dict(scan_run) if scan_run else None,
        },
    )


@router.get("/results/{notice_id}")
def notice_detail_page(request: Request, notice_id: str, session: Session = Depends(get_db)):
    notice = _get_notice_or_404(session, notice_id)
    return templates.TemplateResponse(
        request,
        "notice_detail.html",
        _base_context(request) | {"notice": notice_to_detail_dict(notice)},
    )


@router.get("/results/{notice_id}/open-ted")
def open_official_ted_notice(notice_id: str, session: Session = Depends(get_db)):
    notice = _get_notice_or_404(session, notice_id)
    document_service = TedDocumentService(settings=settings)
    try:
        official_url = document_service.resolve_notice_page_url(notice)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return RedirectResponse(url=official_url, status_code=307)


@router.get("/results/{notice_id}/download/{artifact}")
def download_notice_artifact(notice_id: str, artifact: str, session: Session = Depends(get_db)):
    notice = _get_notice_or_404(session, notice_id)
    document_service = TedDocumentService(settings=settings)
    try:
        spec = document_service.resolve_download(notice, artifact=artifact)
        payload, media_type = document_service.fetch_download(spec)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Failed to download official TED {artifact.upper()} document.") from exc

    headers = {
        "Content-Disposition": f'attachment; filename="{spec.filename}"',
        "X-Download-Source": "official-ted",
    }
    return Response(content=payload, media_type=media_type, headers=headers)


@router.post("/results/{notice_id}/save")
def save_notice(
    request: Request,
    notice_id: str,
    csrf_token: str = Form(...),
    next_url: str = Form(default="/results"),
    session: Session = Depends(get_db),
    actor=Depends(get_actor_context),
):
    validate_csrf(request, csrf_token)
    notice_repo = NoticeRepository(session)
    user = UserRepository(session).get_or_create(actor.email, actor.display_name, actor.auth_provider)
    notice = notice_repo.set_triage(notice_id, saved=True)
    AuditRepository(session).record(
        event_type=AuditEventType.NOTICE_SAVED,
        entity_type="notice",
        entity_id=notice.id,
        payload_json={"saved": True},
        actor=user,
    )
    session.commit()
    return RedirectResponse(url=next_url, status_code=303)


@router.post("/results/{notice_id}/dismiss")
def dismiss_notice(
    request: Request,
    notice_id: str,
    csrf_token: str = Form(...),
    next_url: str = Form(default="/results"),
    session: Session = Depends(get_db),
    actor=Depends(get_actor_context),
):
    validate_csrf(request, csrf_token)
    notice_repo = NoticeRepository(session)
    user = UserRepository(session).get_or_create(actor.email, actor.display_name, actor.auth_provider)
    notice = notice_repo.set_triage(notice_id, dismissed=True)
    AuditRepository(session).record(
        event_type=AuditEventType.NOTICE_DISMISSED,
        entity_type="notice",
        entity_id=notice.id,
        payload_json={"dismissed": True},
        actor=user,
    )
    session.commit()
    return RedirectResponse(url=next_url, status_code=303)


@router.post("/results/{notice_id}/notes")
def add_note(
    request: Request,
    notice_id: str,
    note_text: str = Form(...),
    csrf_token: str = Form(...),
    next_url: str = Form(default="/results"),
    session: Session = Depends(get_db),
    actor=Depends(get_actor_context),
):
    validate_csrf(request, csrf_token)
    cleaned = note_text.strip()
    if not cleaned:
        raise HTTPException(status_code=400, detail="Note text is required.")
    user = UserRepository(session).get_or_create(actor.email, actor.display_name, actor.auth_provider)
    note = NoticeRepository(session).add_note(notice_id=notice_id, user_id=user.id, note_text=cleaned)
    AuditRepository(session).record(
        event_type=AuditEventType.NOTE_CREATED,
        entity_type="notice",
        entity_id=notice_id,
        payload_json={"note_id": note.id},
        actor=user,
    )
    session.commit()
    return RedirectResponse(url=next_url, status_code=303)


@router.get("/admin")
def admin_page(request: Request, session: Session = Depends(get_db), search_profiles=Depends(get_search_profiles)):
    return templates.TemplateResponse(
        request,
        "admin.html",
        _base_context(request)
        | {
            "profiles": search_profiles.profiles,
            "app_settings": SettingsRepository(session).list_all(),
            "runtime_settings": settings,
        },
    )
