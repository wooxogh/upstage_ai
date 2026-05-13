"""voting.py 단위 테스트 — 필드별 majority voting 로직 검증."""

from __future__ import annotations

import pytest

from schemas.common import Citation, FieldValue, Uncertainty
from schemas.enums import (
    BillingCycle, CancellationMethod, ConsentMechanism, NoticeChannel, ProrationPolicy,
)
from schemas.subscription import (
    Cancellation, DataUsage, Disputes, FreeTrial, Liability,
    Pricing, SubscriptionTerms, TermsChanges,
)
from services.voting import _vote_field, vote_subscription_terms


def _fv(value, page=1, quote="..."):
    return FieldValue(
        value=value,
        uncertainty=Uncertainty.CONFIRMED if value is not None else Uncertainty.NOT_SPECIFIED,
        citation=Citation(page=page, quote=quote) if value is not None else None,
    )


# ============ _vote_field 단위 ============


def test_vote_field_majority_wins():
    fvs = [_fv(True), _fv(True), _fv(False)]
    assert _vote_field(fvs).value is True


def test_vote_field_prefers_non_null_over_null():
    # 같은 빈도라도 non-null 우선
    fvs = [_fv(30), _fv(None), _fv(None)]
    assert _vote_field(fvs).value == 30


def test_vote_field_all_null_returns_first():
    fvs = [_fv(None), _fv(None), _fv(None)]
    assert _vote_field(fvs).value is None


def test_vote_field_enum_values_grouped_correctly():
    fvs = [
        _fv(ConsentMechanism.DEEMED_AGREED),
        _fv(ConsentMechanism.OPT_OUT_AVAILABLE),
        _fv(ConsentMechanism.DEEMED_AGREED),
    ]
    assert _vote_field(fvs).value == ConsentMechanism.DEEMED_AGREED


def test_vote_field_lists_compared_as_sets():
    # 같은 원소 다른 순서는 같은 것으로 카운트
    fvs = [
        _fv(["email", "sms"]),
        _fv(["sms", "email"]),
        _fv(["email"]),
    ]
    voted = _vote_field(fvs)
    # 첫 두 개가 같은 카테고리, 그게 다수
    assert sorted(voted.value) == ["email", "sms"]


def test_vote_field_preserves_citation_from_winning_run():
    fvs = [
        FieldValue(value=True, uncertainty=Uncertainty.CONFIRMED,
                    citation=Citation(page=2, quote="winning citation")),
        FieldValue(value=False, uncertainty=Uncertainty.CONFIRMED,
                    citation=Citation(page=99, quote="losing citation")),
        FieldValue(value=True, uncertainty=Uncertainty.CONFIRMED,
                    citation=Citation(page=2, quote="another winning")),
    ]
    voted = _vote_field(fvs)
    assert voted.value is True
    assert voted.citation is not None
    assert voted.citation.quote == "winning citation"


# ============ vote_subscription_terms 통합 ============


def _build_terms(
    auto_renewal_consent: ConsentMechanism,
    notice_days: int | None,
    flags: list[str] | None = None,
) -> SubscriptionTerms:
    return SubscriptionTerms(
        service_name="Netflix", service_provider="N", extraction_date="2026-05-13",
        pricing=Pricing(
            base_price_krw=_fv(None),
            billing_cycle=_fv(BillingCycle.MONTHLY),
            auto_renewal_enabled=_fv(True),
            auto_renewal_consent=_fv(auto_renewal_consent),
            price_change_notice_days=_fv(notice_days),
            price_change_notice_channels=_fv([NoticeChannel.EMAIL]),
        ),
        free_trial=FreeTrial(offered=_fv(False), duration_days=_fv(0),
                              auto_convert_to_paid=_fv(False), cancel_required_before_end=_fv(False),
                              payment_method_required_upfront=_fv(False),
                              notice_before_conversion_days=_fv(0)),
        cancellation=Cancellation(method=_fv(CancellationMethod.ONLINE),
                                   method_description=_fv(""), notice_period_days=_fv(0),
                                   penalty_present=_fv(False), penalty_description=_fv(""),
                                   proration_policy=_fv(ProrationPolicy.NO_REFUND),
                                   blackout_periods=_fv([])),
        terms_changes=TermsChanges(notice_channels=_fv([NoticeChannel.EMAIL]),
                                    notice_lead_time_days=_fv(30),
                                    user_consent_mechanism=_fv(ConsentMechanism.DEEMED_AGREED),
                                    user_right_to_terminate_on_change=_fv(True),
                                    silent_acceptance_clause=_fv(True)),
        data_usage=DataUsage(collected_categories=_fv([]), third_party_sharing=_fv(False),
                              third_party_recipients=_fv([]), third_party_purposes=_fv([]),
                              retention_period_months=_fv(0), marketing_use=_fv(False),
                              marketing_consent=_fv(ConsentMechanism.OPT_OUT_AVAILABLE),
                              cross_border_transfer=_fv(False)),
        liability=Liability(service_disruption_compensation=_fv(False), compensation_description=_fv(""),
                             damages_cap_present=_fv(False), damages_cap_description=_fv(""),
                             force_majeure_scope=_fv(""), indirect_damages_excluded=_fv(False)),
        disputes=Disputes(governing_law=_fv("대한민국"), jurisdiction_clause=_fv("서울"),
                           arbitration_required=_fv(False), class_action_waiver=_fv(False)),
        unfair_clause_flags=flags or [],
    )


def test_vote_subscription_terms_picks_majority_per_field():
    """3개 runs 중 2개가 OPT_OUT, 1개가 DEEMED → OPT_OUT 이김."""
    runs = [
        _build_terms(ConsentMechanism.OPT_OUT_AVAILABLE, notice_days=30),
        _build_terms(ConsentMechanism.OPT_OUT_AVAILABLE, notice_days=None),
        _build_terms(ConsentMechanism.DEEMED_AGREED, notice_days=None),
    ]
    voted = vote_subscription_terms(runs)
    # auto_renewal_consent: OPT_OUT 2회 > DEEMED 1회
    assert voted.pricing.auto_renewal_consent.value == ConsentMechanism.OPT_OUT_AVAILABLE
    # price_change_notice_days: 30 1회 > None 2회 (non-null 우선)
    assert voted.pricing.price_change_notice_days.value == 30


def test_vote_subscription_terms_unions_unfair_flags():
    """한 번이라도 flag 검출되면 voted 결과에 포함 (union)."""
    runs = [
        _build_terms(ConsentMechanism.OPT_OUT_AVAILABLE, notice_days=30, flags=["의사표시_의제"]),
        _build_terms(ConsentMechanism.OPT_OUT_AVAILABLE, notice_days=30, flags=[]),
        _build_terms(ConsentMechanism.OPT_OUT_AVAILABLE, notice_days=30, flags=["면책/손배_제한"]),
    ]
    voted = vote_subscription_terms(runs)
    assert set(voted.unfair_clause_flags) == {"의사표시_의제", "면책/손배_제한"}


def test_vote_subscription_terms_single_run_returns_input():
    runs = [_build_terms(ConsentMechanism.DEEMED_AGREED, notice_days=30)]
    voted = vote_subscription_terms(runs)
    assert voted.pricing.auto_renewal_consent.value == ConsentMechanism.DEEMED_AGREED


def test_vote_subscription_terms_empty_raises():
    with pytest.raises(ValueError, match="empty"):
        vote_subscription_terms([])
