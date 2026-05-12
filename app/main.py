import logging

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.routes import terms

logger = logging.getLogger(__name__)

app = FastAPI(title="Upstage AI Terms Analysis", version="0.1.0")

app.include_router(terms.router)


@app.exception_handler(httpx.HTTPStatusError)
async def upstream_http_error_handler(request: Request, exc: httpx.HTTPStatusError) -> JSONResponse:
    logger.warning("upstream error: %s %s", exc.response.status_code, request.url.path)
    return JSONResponse(
        status_code=502,
        content={"error": "upstream_error", "detail": f"Upstage API returned {exc.response.status_code}"},
    )


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
    logger.warning("validation/parse error: %s", request.url.path)
    return JSONResponse(
        status_code=422,
        content={"error": "validation_error", "detail": str(exc)[:500]},
    )


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
