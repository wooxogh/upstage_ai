"""Netflix 약관 1회 파이프라인 실행 — 골든 템플릿용 베이스라인 생성."""

from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.pipeline import run_pipeline
from services.settings import Settings
from services.upstage import UpstageClient

FIXTURE = Path(__file__).resolve().parent.parent / "data" / "fixtures" / "netflix_terms.pdf"
OUT_PATH = Path("/tmp/variance_run_1.json")


async def main():
    settings = Settings()
    print(f"Running 1 pipeline call against {FIXTURE.name}...", flush=True)
    t0 = time.perf_counter()
    async with UpstageClient(settings) as client:
        result = await run_pipeline(
            client,
            file_bytes=FIXTURE.read_bytes(),
            filename=FIXTURE.name,
            service_name="Netflix",
            service_provider="Netflix, Inc.",
        )
    elapsed = time.perf_counter() - t0
    print(f"\nDone in {elapsed:.1f}s | grounded={result.grounded}", flush=True)
    print(f"Timings: {[(t.stage, round(t.seconds, 2)) for t in result.timings]}", flush=True)
    print(f"Usage: total={sum(u.total_tokens for u in result.usage):,} tokens", flush=True)
    for u in result.usage:
        parts = []
        if u.pages: parts.append(f"pages={u.pages}")
        if u.total_tokens: parts.append(f"tokens={u.total_tokens:,}")
        if u.reasoning_tokens: parts.append(f"reasoning={u.reasoning_tokens:,}")
        print(f"  {u.stage:12s} calls={u.calls} {' '.join(parts)}", flush=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(result.model_dump(), f, ensure_ascii=False)
    print(f"\nWritten to {OUT_PATH}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
