from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.api.routes import router as api_router
from app.config import get_settings
from app.database import create_all_schema
from app.utils.csrf import get_csrf_token
from app.utils.logging import configure_logging
from app.utils.time import format_date, format_datetime


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    configure_logging(settings)
    if settings.auto_create_schema:
        create_all_schema()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.name,
        lifespan=lifespan,
    )
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.secret_key,
        session_cookie=settings.session_cookie_name,
        same_site="lax",
        https_only=settings.session_https_only,
        max_age=settings.session_max_age_seconds,
    )
    app.mount("/static", StaticFiles(directory=settings.static_dir), name="static")
    app.include_router(api_router)

    @app.get("/favicon.ico", include_in_schema=False)
    def favicon() -> RedirectResponse:
        return RedirectResponse(url="/static/favicon.svg", status_code=307)

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        return response

    return app


app = create_app()

