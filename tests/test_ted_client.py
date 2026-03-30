from __future__ import annotations

import httpx
import respx

from app.config import Settings
from app.services.ted_client import TedApiClient, TedSearchRequest


@respx.mock
def test_ted_client_maps_response_and_caches(ted_fixture_payload: dict) -> None:
    route = respx.post("https://api.ted.europa.eu/v3/notices/search").mock(
        return_value=httpx.Response(200, json=ted_fixture_payload)
    )
    settings = Settings(
        database_url="sqlite+pysqlite:///ignored.db",
        ted_api_base_url="https://api.ted.europa.eu",
        ted_search_path="/v3/notices/search",
        ted_retry_attempts=2,
    )
    client = TedApiClient(settings=settings)
    request = TedSearchRequest(query="\"case management\"", limit=10)

    first = client.search(request)
    second = client.search(request)

    assert first.total_count == 2
    assert len(first.notices) == 2
    assert second.total_count == 2
    assert route.call_count == 1
    assert client.metrics().cache_hits == 1

