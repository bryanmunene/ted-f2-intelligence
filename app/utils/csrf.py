from __future__ import annotations

import secrets

from fastapi import HTTPException, Request, status

CSRF_SESSION_KEY = "csrf_token"


def get_csrf_token(request: Request) -> str:
    token = request.session.get(CSRF_SESSION_KEY)
    if token:
        return token
    token = secrets.token_urlsafe(32)
    request.session[CSRF_SESSION_KEY] = token
    return token


def validate_csrf(request: Request, submitted_token: str | None) -> None:
    expected = request.session.get(CSRF_SESSION_KEY)
    if not expected or not submitted_token or submitted_token != expected:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid CSRF token.",
        )

