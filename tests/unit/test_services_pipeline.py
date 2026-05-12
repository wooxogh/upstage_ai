from unittest.mock import AsyncMock

import pytest

from schemas.common import Citation, FieldValue, Uncertainty
from schemas.enums import BillingCycle, ConsentMechanism, NoticeChannel
from schemas.subscription import (
    Cancellation, DataUsage, Disputes, FreeTrial, Liability,
    Pricing, SubscriptionTerms, TermsChanges,
)
from services.ground import GroundednessResult
from services.parse import DocumentParseResult, ParsedElement
from services.pipeline import AnalysisResult, run_pipeline
from services.summarize import KeyClause, KeyClauseCitation, SummaryResult


def _fv(v, page=1, quote="..."):
    return FieldValue(value=v, uncertainty=Uncertainty.CONFIRMED, citation=Citation(page=page, quote=quote))


def _build_terms() -> SubscriptionTerms:
    return SubscriptionTerms(
        service_name="X", service_provider="Y", extraction_date="2026-05-13T00:00:00Z",
        pricing=Pricing(base_price_krw=_fv(9900), billing_cycle=_fv(BillingCycle.MONTHLY),
                         auto_renewal_enabled=_fv(True), auto_renewal_consent=_fv(ConsentMechanism.OPT_OUT_AVAILABLE),
                         price_change_notice_days=_fv(30), price_change_notice_channels=_fv([NoticeChannel.EMAIL])),
        free_trial=FreeTrial(offered=_fv(False), duration_days=_fv(0), auto_convert_to_paid=_fv(False),
                              cancel_required_before_end=_fv(False), payment_method_required_upfront=_fv(False),
                              notice_before_conversion_days=_fv(0)),
        cancellation=Cancellation(method=_fv("online"), method_description=_fv(""), notice_period_days=_fv(0),
                                   penalty_present=_fv(False), penalty_description=_fv(""),
                                   proration_policy=_fv("no_refund"), blackout_periods=_fv([])),
        terms_changes=TermsChanges(notice_channels=_fv([NoticeChannel.EMAIL]), notice_lead_time_days=_fv(30),
                                    user_consent_mechanism=_fv(ConsentMechanism.OPT_OUT_AVAILABLE),
                                    user_right_to_terminate_on_change=_fv(True), silent_acceptance_clause=_fv(False)),
        data_usage=DataUsage(collected_categories=_fv([]), third_party_sharing=_fv(False),
                              third_party_recipients=_fv([]), third_party_purposes=_fv([]),
                              retention_period_months=_fv(0), marketing_use=_fv(False),
                              marketing_consent=_fv(ConsentMechanism.OPT_OUT_AVAILABLE),
                              cross_border_transfer=_fv(False)),
        liability=Liability(service_disruption_compensation=_fv(False), compensation_description=_fv(""),
                             damages_cap_present=_fv(False), damages_cap_description=_fv(""),
                             force_majeure_scope=_fv(""), indirect_damages_excluded=_fv(False)),
        disputes=Disputes(governing_law=_fv(""), jurisdiction_clause=_fv(""),
                           arbitration_required=_fv(False), class_action_waiver=_fv(False)),
    )


async def test_run_pipeline_invokes_each_stage_in_order(monkeypatch):
    """파이프라인이 parse → extract → summarize → ground 순으로 호출되는지 검증."""
    call_order: list[str] = []

    parse_result = DocumentParseResult(
        markdown="# 약관\n...",
        elements=[ParsedElement(id=1, page=1, category="paragraph", text="...", bbox=None)],
    )
    terms = _build_terms()
    summary = SummaryResult(summary="요약", key_clauses=[
        KeyClause(title="t", description="d", risk_level="high", pain_point_id="MID-02",
                  citation=KeyClauseCitation(page=1, quote="...")),
    ])
    ground = GroundednessResult(
        summary="요약", grounded_clauses=summary.key_clauses, ungrounded_clauses=[],
        overall_grounded=True,
    )

    async def fake_parse(client, *, file_bytes, filename):
        call_order.append("parse")
        return parse_result

    async def fake_extract(client, *, parsed_markdown, parsed_elements, service_name, service_provider):
        call_order.append("extract")
        return terms

    async def fake_summarize(client, *, terms):
        call_order.append("summarize")
        return summary

    async def fake_ground(client, *, summary, source_markdown):
        call_order.append("ground")
        return ground

    monkeypatch.setattr("services.pipeline.parse_document", fake_parse)
    monkeypatch.setattr("services.pipeline.extract_subscription", fake_extract)
    monkeypatch.setattr("services.pipeline.summarize_risks", fake_summarize)
    monkeypatch.setattr("services.pipeline.check_groundedness", fake_ground)

    fake_client = AsyncMock()
    result = await run_pipeline(
        fake_client,
        file_bytes=b"...",
        filename="t.pdf",
        service_name="X",
        service_provider="Y",
    )
    assert call_order == ["parse", "extract", "summarize", "ground"]
    assert isinstance(result, AnalysisResult)
    assert result.terms.service_name == "X"
    assert result.summary == "요약"
    assert result.grounded is True
    assert len(result.key_clauses) == 1
