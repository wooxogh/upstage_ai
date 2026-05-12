from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from services.settings import Settings

logger = logging.getLogger(__name__)


class UpstageClient:
    """Thin async wrapper around Upstage HTTP APIs with auth + retry."""

    MAX_RETRIES = 3
    RETRY_BACKOFF_S = 0.5

    def __init__(self, settings: Settings, timeout_s: float = 60.0):
        self.settings = settings
        self._client = httpx.AsyncClient(
            base_url=settings.upstage_base_url,
            headers={"Authorization": f"Bearer {settings.upstage_api_key}"},
            timeout=timeout_s,
        )

    async def __aenter__(self) -> "UpstageClient":
        return self

    async def __aexit__(self, *exc) -> None:
        await self._client.aclose()

    async def post_json(self, path: str, *, json: dict[str, Any]) -> dict[str, Any]:
        return await self._request("POST", path, json=json)

    async def post_multipart(
        self,
        path: str,
        *,
        files: dict[str, Any],
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return await self._request("POST", path, files=files, data=data)

    async def _request(self, method: str, path: str, **kwargs) -> dict[str, Any]:
        last_exc: Exception | None = None
        for attempt in range(self.MAX_RETRIES):
            try:
                resp = await self._client.request(method, path, **kwargs)
                if resp.status_code >= 500:
                    last_exc = httpx.HTTPStatusError(
                        f"server {resp.status_code}", request=resp.request, response=resp
                    )
                    await asyncio.sleep(self.RETRY_BACKOFF_S * (2**attempt))
                    continue
                resp.raise_for_status()
                logger.info("upstage %s %s -> %s", method, path, resp.status_code)
                return resp.json()
            except httpx.TransportError as e:
                last_exc = e
                await asyncio.sleep(self.RETRY_BACKOFF_S * (2**attempt))
        assert last_exc is not None
        raise last_exc
