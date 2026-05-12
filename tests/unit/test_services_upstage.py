import httpx
import pytest

from services.settings import Settings
from services.upstage import UpstageClient


@pytest.fixture
def settings(sample_api_key, sample_base_url) -> Settings:
    return Settings(upstage_api_key=sample_api_key, upstage_base_url=sample_base_url)


async def test_client_sends_bearer_token(httpx_mock, settings):
    httpx_mock.add_response(
        url=f"{settings.upstage_base_url}/test",
        json={"ok": True},
    )
    async with UpstageClient(settings) as client:
        r = await client.post_json("/test", json={"x": 1})
    assert r["ok"] is True
    request = httpx_mock.get_request()
    assert request.headers["authorization"] == f"Bearer {settings.upstage_api_key}"


async def test_client_retries_on_5xx(httpx_mock, settings):
    httpx_mock.add_response(status_code=503, url=f"{settings.upstage_base_url}/r")
    httpx_mock.add_response(status_code=503, url=f"{settings.upstage_base_url}/r")
    httpx_mock.add_response(json={"ok": True}, url=f"{settings.upstage_base_url}/r")
    async with UpstageClient(settings) as client:
        r = await client.post_json("/r", json={})
    assert r["ok"] is True
    assert len(httpx_mock.get_requests()) == 3


async def test_client_raises_on_4xx(httpx_mock, settings):
    httpx_mock.add_response(
        status_code=400,
        url=f"{settings.upstage_base_url}/bad",
        json={"error": "invalid"},
    )
    async with UpstageClient(settings) as client:
        with pytest.raises(httpx.HTTPStatusError):
            await client.post_json("/bad", json={})
