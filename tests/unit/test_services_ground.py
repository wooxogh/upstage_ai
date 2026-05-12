import json

import pytest

from services.ground import GroundednessResult, check_groundedness
from services.settings import Settings
from services.summarize import KeyClause, KeyClauseCitation, SummaryResult
from services.upstage import UpstageClient


@pytest.fixture
def settings(sample_api_key, sample_base_url):
    return Settings(upstage_api_key=sample_api_key, upstage_base_url=sample_base_url)


@pytest.fixture
def sample_summary():
    return SummaryResult(
        summary="자동결제와 의사표시 의제 조항이 있습니다.",
        key_clauses=[
            KeyClause(
                title="자동 갱신",
                description="이의 없으면 동의로 간주됩니다.",
                risk_level="high",
                pain_point_id="MID-02",
                citation=KeyClauseCitation(page=2, quote="이의 없으면 동의로 간주"),
            ),
            KeyClause(
                title="가공의 조항",
                description="실제 약관에 없는 가짜 조항입니다.",
                risk_level="medium",
                pain_point_id="PRE-04",
                citation=KeyClauseCitation(page=99, quote="이런 문구는 원문에 없음"),
            ),
        ],
    )


async def test_check_groundedness_filters_ungrounded(httpx_mock, settings, sample_summary):
    # 첫 호출: grounded
    httpx_mock.add_response(
        url=f"{settings.upstage_base_url}/chat/completions",
        json={"choices": [{"message": {"content": json.dumps({"grounded": True, "score": 0.95})}}]},
    )
    # 두 번째 호출: not grounded
    httpx_mock.add_response(
        url=f"{settings.upstage_base_url}/chat/completions",
        json={"choices": [{"message": {"content": json.dumps({"grounded": False, "score": 0.12})}}]},
    )
    async with UpstageClient(settings) as client:
        result = await check_groundedness(
            client,
            summary=sample_summary,
            source_markdown="...이의 없으면 동의로 간주합니다...",
        )
    assert isinstance(result, GroundednessResult)
    assert len(result.grounded_clauses) == 1
    assert result.grounded_clauses[0].title == "자동 갱신"
    assert len(result.ungrounded_clauses) == 1
    assert result.ungrounded_clauses[0].title == "가공의 조항"
    assert result.overall_grounded is False
