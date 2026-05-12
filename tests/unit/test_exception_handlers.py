import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app


def test_upstream_http_error_returns_502(monkeypatch):
    """파이프라인에서 httpx.HTTPStatusError 발생 시 502 + 구조화 응답."""

    async def fake_run_pipeline(*args, **kwargs):
        request = httpx.Request("POST", "https://api.upstage.test/v1/chat/completions")
        response = httpx.Response(401, request=request)
        raise httpx.HTTPStatusError("unauthorized", request=request, response=response)

    monkeypatch.setattr("app.routes.terms.run_pipeline", fake_run_pipeline)
    monkeypatch.setenv("UPSTAGE_API_KEY", "test-key")

    client = TestClient(app, raise_server_exceptions=False)
    response = client.post(
        "/v1/terms/analyze",
        files={"file": ("t.pdf", b"%PDF", "application/pdf")},
        data={"service_name": "X", "service_provider": "Y"},
    )
    assert response.status_code == 502
    body = response.json()
    assert body["error"] == "upstream_error"
    assert "401" in body["detail"]


def test_value_error_returns_422(monkeypatch):
    """파이프라인에서 ValueError(검증 실패) 발생 시 422 + 구조화 응답."""

    async def fake_run_pipeline(*args, **kwargs):
        raise ValueError("Extract response validation failed: missing field 'pricing'")

    monkeypatch.setattr("app.routes.terms.run_pipeline", fake_run_pipeline)
    monkeypatch.setenv("UPSTAGE_API_KEY", "test-key")

    client = TestClient(app, raise_server_exceptions=False)
    response = client.post(
        "/v1/terms/analyze",
        files={"file": ("t.pdf", b"%PDF", "application/pdf")},
        data={"service_name": "X", "service_provider": "Y"},
    )
    assert response.status_code == 422
    body = response.json()
    assert body["error"] == "validation_error"
    assert "validation failed" in body["detail"]
