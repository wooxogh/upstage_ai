from fastapi import FastAPI

from app.routes import terms

app = FastAPI(title="Upstage AI Terms Analysis", version="0.1.0")

app.include_router(terms.router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
