from __future__ import annotations

import json
from datetime import datetime, timezone

from pydantic import ValidationError

from prompts.extract_subscription import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
from schemas.common import Citation, FieldValue
from schemas.subscription import SubscriptionTerms
from services.parse import ParsedElement
from services.upstage import UpstageClient

CHAT_COMPLETIONS_PATH = "/chat/completions"
MODEL = "solar-pro3"
SECTION_NAMES = (
    "pricing", "free_trial", "cancellation", "terms_changes",
    "data_usage", "liability", "disputes",
)


def _find_element_for_quote(
    quote: str, page: int, elements: list[ParsedElement]
) -> ParsedElement | None:
    """page를 우선으로, quote가 element.text에 포함되는 첫 element 반환."""
    if not quote:
        return None
    # 같은 페이지부터 검사, 없으면 다른 페이지에서도 검사
    for elem in elements:
        if elem.page == page and quote in elem.text:
            return elem
    for elem in elements:
        if quote in elem.text:
            return elem
    return None


def _enrich_citation(
    citation: Citation | None, elements: list[ParsedElement]
) -> Citation | None:
    if citation is None or citation.bbox is not None:
        return citation
    elem = _find_element_for_quote(citation.quote, citation.page, elements)
    if elem is None:
        return citation
    updates: dict = {"bbox": elem.bbox}
    if citation.section is None:
        updates["section"] = elem.category
    return citation.model_copy(update=updates)


def _enrich_with_bbox(
    terms: SubscriptionTerms, elements: list[ParsedElement]
) -> SubscriptionTerms:
    """각 섹션의 모든 FieldValue에 대해 citation.bbox를 element 매칭으로 채움."""
    for section_name in SECTION_NAMES:
        section = getattr(terms, section_name)
        for field_name in section.__class__.model_fields:
            fv: FieldValue = getattr(section, field_name)
            new_citation = _enrich_citation(fv.citation, elements)
            if new_citation is not fv.citation:
                fv.citation = new_citation
    return terms


async def extract_subscription(
    client: UpstageClient,
    *,
    parsed_markdown: str,
    parsed_elements: list[ParsedElement],
    service_name: str,
    service_provider: str,
) -> SubscriptionTerms:
    """Solar Pro 3 chat completions + json_schema로 SubscriptionTerms 추출.

    Information Extract API는 nested 스키마 미지원이라 chat completions 사용.
    citation.bbox는 Document Parse elements와 quote 매칭으로 후처리에서 채워짐.
    """
    response_format = {
        "type": "json_schema",
        "json_schema": {
            "name": "SubscriptionTerms",
            "schema": SubscriptionTerms.model_json_schema(),
            "strict": True,
        },
    }
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": USER_PROMPT_TEMPLATE.format(
                    service_name=service_name,
                    service_provider=service_provider,
                    parsed_markdown=parsed_markdown,
                ),
            },
        ],
        "response_format": response_format,
        "reasoning_effort": "low",
    }
    raw = await client.post_json(CHAT_COMPLETIONS_PATH, json=payload)
    content_str = raw["choices"][0]["message"]["content"]
    parsed = json.loads(content_str)
    parsed.setdefault("extraction_date", datetime.now(timezone.utc).isoformat())
    parsed.setdefault("service_name", service_name)
    parsed.setdefault("service_provider", service_provider)
    try:
        terms = SubscriptionTerms.model_validate(parsed)
    except ValidationError as e:
        raise ValueError(f"Extract response validation failed: {e}") from e
    return _enrich_with_bbox(terms, parsed_elements)
