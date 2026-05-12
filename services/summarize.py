from __future__ import annotations

import json

from pydantic import BaseModel, Field

from prompts.summarize_subscription import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
from schemas.subscription import SubscriptionTerms
from services.upstage import UpstageClient

CHAT_COMPLETIONS_PATH = "/chat/completions"
MODEL = "solar-pro3"  # Upstage 공식 alias


class KeyClauseCitation(BaseModel):
    page: int
    quote: str


class KeyClause(BaseModel):
    title: str
    description: str
    risk_level: str  # "high" | "medium" | "low"
    pain_point_id: str
    citation: KeyClauseCitation


class SummaryResult(BaseModel):
    summary: str
    key_clauses: list[KeyClause] = Field(default_factory=list)


async def summarize_risks(client: UpstageClient, *, terms: SubscriptionTerms) -> SummaryResult:
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": USER_PROMPT_TEMPLATE.format(terms_json=terms.model_dump_json(indent=2)),
            },
        ],
        "response_format": {"type": "json_object"},
    }
    raw = await client.post_json(CHAT_COMPLETIONS_PATH, json=payload)
    content_str = raw["choices"][0]["message"]["content"]
    data = json.loads(content_str)
    return SummaryResult.model_validate(data)
