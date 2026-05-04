from __future__ import annotations

from datetime import date
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

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
from app.services.ted_documents import DocumentDownloadAccessError, TedDocumentService
from app.utils.csrf import get_csrf_token, validate_csrf
from app.utils.time import format_date, format_datetime, parse_ted_date

settings = get_settings()
templates = Jinja2Templates(directory=str(settings.templates_dir))
templates.env.globals["csrf_token"] = get_csrf_token
templates.env.globals["app_name"] = settings.name
templates.env.filters["display_datetime"] = lambda value: format_datetime(value, settings.ui_timezone)
templates.env.filters["display_date"] = format_date

router = APIRouter(tags=["ui"])

RESULT_SORT_OPTIONS = {
    "recommended": "Recommended",
    "highest_score": "Highest score",
    "closing_soon": "Closing soon",
    "newest": "Newest",
    "buyer": "Buyer name",
}


def _static_asset_versions() -> dict[str, int]:
    return {
        "css": int((settings.static_dir / "css" / "app.css").stat().st_mtime),
        "js": int((settings.static_dir / "js" / "app.js").stat().st_mtime),
        "icons": int((settings.static_dir / "icons" / "ui-icons.svg").stat().st_mtime),
    }


templates.env.globals["static_asset_versions"] = _static_asset_versions()


def _base_context(request: Request) -> dict:
    return {
        "request": request,
        "active_path": request.url.path,
        "static_asset_versions": _static_asset_versions(),
    }


def _get_notice_or_404(session: Session, notice_id: str):
    notice = NoticeRepository(session).get_by_id(notice_id)
    if notice is None:
        raise HTTPException(status_code=404, detail="Notice not found.")
    return notice


def _append_feedback(url: str, *, kind: str, message: str) -> str:
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query["feedback_kind"] = kind
    query["feedback_message"] = message
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


@router.get("/")
def dashboard(request: Request, session: Session = Depends(get_db)):
    notice_repo = NoticeRepository(session)
    scan_repo = ScanRunRepository(session)
    metrics = notice_repo.dashboard_metrics()
    recent_scans = scan_repo.recent(limit=6)
    top_notices, _ = notice_repo.list(NoticeListFilters(), page=1, page_size=8)
    total_notices = max(1, metrics["total_notices"])
    queue_mix = [
        {
            "label": "Strong matches",
            "value": metrics["high_fit"],
            "tone": "high",
            "percent": round((metrics["high_fit"] / total_notices) * 100),
            "hint": "Open these first when building a shortlist.",
        },
        {
            "label": "Needs checking",
            "value": metrics["conditional"],
            "tone": "conditional",
            "percent": round((metrics["conditional"] / total_notices) * 100),
            "hint": "Promising notices with qualification or timing risk.",
        },
        {
            "label": "Closing soon",
            "value": metrics["expiring_soon"],
            "tone": "warning",
            "percent": round((metrics["expiring_soon"] / total_notices) * 100),
            "hint": "Deadlines approaching inside the next seven days.",
        },
        {
            "label": "Saved notices",
            "value": metrics["saved_count"],
            "tone": "saved",
            "percent": round((metrics["saved_count"] / total_notices) * 100),
            "hint": "Items already kept for follow-up or internal review.",
        },
    ]
    recent_scan_max = max((scan.total_notices_ingested or 0) for scan in recent_scans) if recent_scans else 1
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        _base_context(request)
        | {
            "metrics": metrics,
            "recent_scans": recent_scans,
            "queue_mix": queue_mix,
            "recent_scan_max": max(1, recent_scan_max),
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
    parsed_date_from = parse_ted_date(date_from) if date_from else None
    parsed_date_to = parse_ted_date(date_to) if date_to else None
    payload = ScanRequestPayload(
        profile_name=profile_name,
        date_from=parsed_date_from,
        date_to=parsed_date_to,
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
    redirect_url = _append_feedback(
        redirect_url,
        kind="success",
        message="Search complete. Review the shortlist below and open the strongest matches first.",
    )
    return RedirectResponse(url=redirect_url, status_code=303)


@router.get("/results")
def results_page(
    request: Request,
    country: str | None = None,
    fit_label: str | None = None,
    priority_bucket: str | None = None,
    min_score: int | None = Query(default=None, ge=0, le=100),
    max_score: int | None = Query(default=None, ge=0, le=100),
    confidence_indicator: str | None = None,
    hard_lock_only: bool = False,
    publication_date_from: date | None = None,
    publication_date_to: date | None = None,
    deadline_from: date | None = None,
    deadline_to: date | None = None,
    deadline_window_days: int | None = Query(default=None, ge=1, le=365),
    include_dismissed: bool = False,
    saved_only: bool = False,
    search: str | None = None,
    sort_by: str = Query(default="recommended"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    scan_id: str | None = None,
    feedback_kind: str | None = None,
    feedback_message: str | None = None,
    session: Session = Depends(get_db),
):
    notice_repo = NoticeRepository(session)
    scan_repo = ScanRunRepository(session)
    filters = NoticeListFilters(
        country=country,
        fit_label=fit_label,
        priority_bucket=priority_bucket,
        min_score=min_score,
        max_score=max_score,
        confidence_indicator=confidence_indicator,
        hard_lock_only=hard_lock_only,
        publication_date_from=publication_date_from,
        publication_date_to=publication_date_to,
        deadline_from=deadline_from,
        deadline_to=deadline_to,
        deadline_window_days=deadline_window_days,
        include_dismissed=include_dismissed,
        saved_only=saved_only,
        search=search,
    )
    selected_sort = sort_by if sort_by in RESULT_SORT_OPTIONS else "recommended"
    notices, total = notice_repo.list(filters, page=page, page_size=page_size, sort_by=selected_sort)
    scan_run = scan_repo.get_by_id(scan_id) if scan_id else None
    total_pages = max(1, (total + page_size - 1) // page_size)
    return templates.TemplateResponse(
        request,
        "results.html",
        _base_context(request)
        | {
            "notices": notices,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
            "filters": filters,
            "sort_by": selected_sort,
            "sort_options": RESULT_SORT_OPTIONS,
            "scan_run": scan_run_to_dict(scan_run) if scan_run else None,
            "feedback_kind": feedback_kind,
            "feedback_message": feedback_message,
        },
    )


@router.get("/results/{notice_id}")
def notice_detail_page(
    request: Request,
    notice_id: str,
    feedback_kind: str | None = None,
    feedback_message: str | None = None,
    session: Session = Depends(get_db),
):
    notice = _get_notice_or_404(session, notice_id)
    document_service = TedDocumentService(settings=settings)
    tender_documents = [
        {
            "index": index,
            "filename": spec.filename,
            "url": f"/results/{notice.id}/download/tender/{index}",
        }
        for index, spec in enumerate(document_service.list_tender_documents(notice))
    ]
    return templates.TemplateResponse(
        request,
        "notice_detail.html",
        _base_context(request)
        | {
            "notice": notice_to_detail_dict(notice),
            "tender_documents": tender_documents,
            "feedback_kind": feedback_kind,
            "feedback_message": feedback_message,
        },
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
    except DocumentDownloadAccessError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Failed to download official TED {artifact.upper()} document.") from exc

    headers = {
        "Content-Disposition": f'attachment; filename="{spec.filename}"',
        "X-Download-Source": "official-ted",
    }
    return Response(content=payload, media_type=media_type, headers=headers)


@router.get("/results/{notice_id}/download/tender/{document_index}")
def download_tender_document(notice_id: str, document_index: int, session: Session = Depends(get_db)):
    notice = _get_notice_or_404(session, notice_id)
    document_service = TedDocumentService(settings=settings)
    try:
        spec = document_service.resolve_tender_document_download(notice, document_index=document_index)
        payload, media_type = document_service.fetch_download(spec)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except DocumentDownloadAccessError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="Failed to download tender document.") from exc

    headers = {
        "Content-Disposition": f'attachment; filename="{spec.filename}"',
        "X-Download-Source": "tender-document",
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
    return RedirectResponse(
        url=_append_feedback(next_url, kind="success", message="Notice saved to your shortlist."),
        status_code=303,
    )


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
    return RedirectResponse(
        url=_append_feedback(next_url, kind="success", message="Notice removed from the active shortlist."),
        status_code=303,
    )


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
    return RedirectResponse(
        url=_append_feedback(next_url, kind="success", message="Analyst note saved."),
        status_code=303,
    )


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
