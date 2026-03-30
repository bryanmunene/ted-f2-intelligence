from __future__ import annotations

from functools import lru_cache
from typing import Generator

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.auth import ActorContext
from app.config import KeywordPack, SearchProfileRegistry, Settings, get_settings, load_keyword_pack, load_search_profiles
from app.database import get_db_session
from app.services.scan_service import ScanService
from app.services.ted_client import TedApiClient


@lru_cache(maxsize=1)
def get_keyword_pack_cached() -> KeywordPack:
    settings = get_settings()
    return load_keyword_pack(settings.resolved_keyword_pack_path)


@lru_cache(maxsize=1)
def get_search_profiles_cached() -> SearchProfileRegistry:
    settings = get_settings()
    return load_search_profiles(settings.resolved_search_profiles_path)


@lru_cache(maxsize=1)
def get_ted_client_cached() -> TedApiClient:
    return TedApiClient(settings=get_settings())


def get_keyword_pack() -> KeywordPack:
    return get_keyword_pack_cached()


def get_search_profiles() -> SearchProfileRegistry:
    return get_search_profiles_cached()


def get_db() -> Generator[Session, None, None]:
    yield from get_db_session()


def get_actor_context(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> ActorContext:
    if settings.auth_enabled:
        email = request.headers.get(settings.header_auth_email_header)
        display_name = request.headers.get(settings.header_auth_name_header, email or "")
        if not email:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authenticated user headers are required.",
            )
        return ActorContext(email=email, display_name=display_name or email, auth_provider="reverse-proxy")
    return ActorContext(
        email=settings.default_user_email,
        display_name=settings.default_user_name,
        auth_provider="internal-default",
    )


def get_scan_service(
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    keyword_pack: KeywordPack = Depends(get_keyword_pack),
    search_profiles: SearchProfileRegistry = Depends(get_search_profiles),
    actor: ActorContext = Depends(get_actor_context),
) -> ScanService:
    return ScanService(
        session=session,
        settings=settings,
        ted_client=get_ted_client_cached(),
        keyword_pack=keyword_pack,
        search_profiles=search_profiles,
        actor=actor,
    )
