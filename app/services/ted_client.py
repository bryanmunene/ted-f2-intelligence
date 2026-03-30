from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
from dataclasses import dataclass
from typing import Any

import httpx
from cachetools import TTLCache
from pydantic import BaseModel, Field
from tenacity import Retrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.config import Settings
from app.services.query_builder import TED_CANONICAL_FIELDS

logger = logging.getLogger(__name__)


class TedApiError(RuntimeError):
    """Raised when the TED Search API returns an unexpected result."""


class TedSearchRequest(BaseModel):
    query: str
    fields: list[str] = Field(default_factory=lambda: list(TED_CANONICAL_FIELDS))
    page: int = 1
    limit: int = 50
    scope: str = "ACTIVE"
    check_query_syntax: bool = False
    pagination_mode: str = "PAGE_NUMBER"
    iteration_next_token: str | None = None

    def api_payload(self) -> dict[str, Any]:
        payload = {
            "query": self.query,
            "fields": self.fields,
            "page": self.page,
            "limit": self.limit,
            "scope": self.scope,
            "checkQuerySyntax": self.check_query_syntax,
            "paginationMode": self.pagination_mode,
        }
        if self.iteration_next_token:
            payload["iterationNextToken"] = self.iteration_next_token
        return payload


class TedSearchResponse(BaseModel):
    total_count: int
    notices: list[dict[str, Any]]
    next_token: str | None = None
    raw_payload: dict[str, Any]


@dataclass(slots=True)
class TedClientMetrics:
    request_count: int = 0
    rate_limit_events: int = 0
    cache_hits: int = 0


class _RateLimiter:
    def __init__(self, requests_per_minute: int) -> None:
        self.requests_per_minute = max(1, requests_per_minute)
        self.minimum_interval = 60.0 / self.requests_per_minute
        self._last_request_time = 0.0
        self._lock = threading.Lock()
        self.rate_limit_events = 0

    def acquire(self) -> None:
        with self._lock:
            now = time.monotonic()
            sleep_for = self.minimum_interval - (now - self._last_request_time)
            if sleep_for > 0:
                self.rate_limit_events += 1
                time.sleep(sleep_for)
            self._last_request_time = time.monotonic()


class TedApiClient:
    def __init__(self, *, settings: Settings) -> None:
        self.settings = settings
        self._cache: TTLCache[str, TedSearchResponse] = TTLCache(maxsize=256, ttl=settings.ted_cache_ttl_seconds)
        self._cache_lock = threading.Lock()
        self._rate_limiter = _RateLimiter(settings.ted_requests_per_minute)
        self._metrics = TedClientMetrics()
        self._client = httpx.Client(
            base_url=settings.ted_api_base_url,
            timeout=settings.ted_request_timeout_seconds,
            headers={"Accept": "application/json", "User-Agent": "cBrain-TED-F2-Intelligence/0.1"},
        )

    def reset_metrics(self) -> None:
        self._metrics = TedClientMetrics()
        self._rate_limiter.rate_limit_events = 0

    def metrics(self) -> TedClientMetrics:
        return TedClientMetrics(
            request_count=self._metrics.request_count,
            rate_limit_events=self._rate_limiter.rate_limit_events,
            cache_hits=self._metrics.cache_hits,
        )

    def search(self, request: TedSearchRequest) -> TedSearchResponse:
        cache_key = self._cache_key(request)
        with self._cache_lock:
            cached = self._cache.get(cache_key)
        if cached is not None:
            self._metrics.cache_hits += 1
            return cached.model_copy(deep=True)

        payload = request.api_payload()
        self._rate_limiter.acquire()
        response = self._retrying_post(payload)
        with self._cache_lock:
            self._cache[cache_key] = response
        return response.model_copy(deep=True)

    def _retrying_post(self, payload: dict[str, Any]) -> TedSearchResponse:
        retryer = Retrying(
            stop=stop_after_attempt(self.settings.ted_retry_attempts),
            wait=wait_exponential(multiplier=1, min=1, max=8),
            retry=retry_if_exception_type((httpx.HTTPError, TedApiError)),
            reraise=True,
        )
        for attempt in retryer:
            with attempt:
                return self._post_search(payload)
        raise TedApiError("TED Search API retry loop exited unexpectedly.")

    def _post_search(self, payload: dict[str, Any]) -> TedSearchResponse:
        self._metrics.request_count += 1
        response = self._client.post(self.settings.ted_search_path, json=payload)
        if response.status_code >= 500 or response.status_code == 429:
            raise TedApiError(f"TED Search API transient failure: {response.status_code}")
        if response.status_code >= 400:
            detail = response.text.strip()
            if len(detail) > 500:
                detail = detail[:500] + "..."
            raise TedApiError(
                f"TED Search API returned {response.status_code} for payload {payload!r}. Response: {detail}"
            )
        response.raise_for_status()
        body = response.json()
        parsed = self._parse_response(body)
        logger.info(
            "ted_search_request_completed",
            extra={
                "page": payload.get("page"),
                "limit": payload.get("limit"),
                "result_count": len(parsed.notices),
                "total_count": parsed.total_count,
            },
        )
        return parsed

    def _parse_response(self, payload: dict[str, Any]) -> TedSearchResponse:
        total_count = payload.get("totalNoticeCount") or payload.get("total") or payload.get("total_count") or 0
        notices = payload.get("results") or payload.get("notices") or payload.get("items") or []
        next_token = payload.get("iterationNextToken") or payload.get("next_token")
        if not isinstance(notices, list):
            raise TedApiError("TED Search API response did not contain a notice list.")
        return TedSearchResponse(
            total_count=int(total_count),
            notices=notices,
            next_token=next_token,
            raw_payload=payload,
        )

    def _cache_key(self, request: TedSearchRequest) -> str:
        raw = json.dumps(request.api_payload(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()
