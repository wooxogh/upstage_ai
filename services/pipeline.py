from __future__ import annotations

import logging
import time

from pydantic import BaseModel, Field

from schemas.subscription import SubscriptionTerms
from services.extract import extract_subscription
from services.ground import check_groundedness
from services.parse import parse_document
from services.summarize import KeyClause, summarize_risks
from services.upstage import UpstageClient

logger = logging.getLogger(__name__)


class StageTiming(BaseModel):
    stage: str
    seconds: float


class AnalysisResult(BaseModel):
    terms: SubscriptionTerms
    summary: str
    key_clauses: list[KeyClause]
    ungrounded_clauses: list[KeyClause] = Field(default_factory=list)
    grounded: bool
    timings: list[StageTiming] = Field(default_factory=list)


async def run_pipeline(
    client: UpstageClient,
    *,
    file_bytes: bytes,
    filename: str,
    service_name: str,
    service_provider: str,
) -> AnalysisResult:
    timings: list[StageTiming] = []

    t0 = time.perf_counter()
    parsed = await parse_document(client, file_bytes=file_bytes, filename=filename)
    timings.append(StageTiming(stage="parse", seconds=time.perf_counter() - t0))

    t0 = time.perf_counter()
    terms = await extract_subscription(
        client,
        parsed_markdown=parsed.markdown,
        parsed_elements=parsed.elements,
        service_name=service_name,
        service_provider=service_provider,
    )
    timings.append(StageTiming(stage="extract", seconds=time.perf_counter() - t0))

    t0 = time.perf_counter()
    summary = await summarize_risks(client, terms=terms)
    timings.append(StageTiming(stage="summarize", seconds=time.perf_counter() - t0))

    t0 = time.perf_counter()
    ground = await check_groundedness(client, summary=summary, source_markdown=parsed.markdown)
    timings.append(StageTiming(stage="ground", seconds=time.perf_counter() - t0))

    logger.info(
        "pipeline complete service=%s timings=%s grounded=%s",
        service_name, [(t.stage, round(t.seconds, 2)) for t in timings], ground.overall_grounded,
    )
    return AnalysisResult(
        terms=terms,
        summary=ground.summary,
        key_clauses=ground.grounded_clauses,
        ungrounded_clauses=ground.ungrounded_clauses,
        grounded=ground.overall_grounded,
        timings=timings,
    )
