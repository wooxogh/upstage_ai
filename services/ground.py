# TODO(groundedness): Upstage 전용 /groundedness-check endpoint가 공식 문서에 추가되면
# CHAT_COMPLETIONS_PATH → 전용 path로 swap, payload를 {context, answer} 단순 형태로 변경.
# 현재는 Solar Pro 3 chat에 verification prompt 보내는 fallback 구현.

from __future__ import annotations

import json

from pydantic import BaseModel, Field

from prompts.groundedness_check import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
from services.summarize import KeyClause, SummaryResult
from services.upstage import UpstageClient

CHAT_COMPLETIONS_PATH = "/chat/completions"
MODEL = "solar-pro3"
MIN_SCORE = 0.7


class GroundednessResult(BaseModel):
    summary: str
    grounded_clauses: list[KeyClause] = Field(default_factory=list)
    ungrounded_clauses: list[KeyClause] = Field(default_factory=list)
    overall_grounded: bool


async def _check_one(
    client: UpstageClient,
    *,
    context: str,
    answer: str,
) -> tuple[bool, float]:
    """Solar Pro 3 chat completions으로 verification (전용 endpoint 미수록 fallback)."""
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": USER_PROMPT_TEMPLATE.format(context=context, answer=answer),
            },
        ],
        "response_format": {"type": "json_object"},
        "reasoning_effort": "low",
    }
    raw = await client.post_json(CHAT_COMPLETIONS_PATH, json=payload)
    content_str = raw["choices"][0]["message"]["content"]
    data = json.loads(content_str)
    # Strict bool 비교 — LLM이 "true"/"false" 문자열을 돌려줘도 ungrounded로 안전하게 처리
    is_grounded = data.get("grounded") is True
    try:
        score = float(data.get("score", 0.0))
    except (TypeError, ValueError):
        score = 0.0
    return is_grounded, score


async def check_groundedness(
    client: UpstageClient,
    *,
    summary: SummaryResult,
    source_markdown: str,
) -> GroundednessResult:
    grounded: list[KeyClause] = []
    ungrounded: list[KeyClause] = []
    for clause in summary.key_clauses:
        answer = f'{clause.title}: {clause.description} (원문 인용: "{clause.citation.quote}")'
        is_grounded, score = await _check_one(client, context=source_markdown, answer=answer)
        if is_grounded and score >= MIN_SCORE:
            grounded.append(clause)
        else:
            ungrounded.append(clause)
    # summary 텍스트도 검증 — clause와 별개로 사용자에게 노출되므로
    summary_is_grounded, summary_score = await _check_one(
        client, context=source_markdown, answer=summary.summary
    )
    summary_grounded = summary_is_grounded and summary_score >= MIN_SCORE
    return GroundednessResult(
        summary=summary.summary,
        grounded_clauses=grounded,
        ungrounded_clauses=ungrounded,
        overall_grounded=(len(ungrounded) == 0 and summary_grounded),
    )
