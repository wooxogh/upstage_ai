"""파이프라인 출력을 골든 라벨과 비교해 per-field 정확도 측정.

사용:
    .venv/bin/python scripts/score_against_golden.py [pipeline_result.json] [golden.json]

기본:
    pipeline = /tmp/variance_run_1.json (가장 최근 eval run)
    golden   = data/fixtures/netflix_golden.json

출력:
- per-field 비교표 (정답/오답/null누락/오버추출)
- 섹션별 정확도
- 타입별 정확도 (enum / bool / int / str / list)
- 전체 정확도 요약
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RESULT = Path("/tmp/variance_run_1.json")
DEFAULT_GOLDEN = ROOT / "data" / "fixtures" / "netflix_golden.json"

SECTIONS = (
    "pricing", "free_trial", "cancellation", "terms_changes",
    "data_usage", "liability", "disputes",
)


def _enum_value(v):
    if hasattr(v, "value"):
        return v.value
    return v


def _normalize(v):
    """비교용 정규화: enum→value, list→sorted tuple, str→strip."""
    v = _enum_value(v)
    if isinstance(v, list):
        return tuple(sorted(str(x) for x in v))
    if isinstance(v, str):
        return v.strip()
    return v


def _is_null(v):
    if v is None:
        return True
    if isinstance(v, (list, str)) and len(v) == 0:
        return True
    return False


def classify(expected, actual) -> str:
    """expected vs actual 매칭 결과 분류."""
    e_null, a_null = _is_null(expected), _is_null(actual)
    if e_null and a_null:
        return "ok_null"
    if e_null and not a_null:
        return "over_extracted"  # 정답은 없는데 모델이 채움 (drift)
    if not e_null and a_null:
        return "missed"           # 정답 있는데 못 찾음
    if _normalize(expected) == _normalize(actual):
        return "ok"
    return "wrong"


def main():
    result_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_RESULT
    golden_path = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_GOLDEN
    if not result_path.exists():
        print(f"ERROR: pipeline result {result_path} not found")
        sys.exit(1)
    if not golden_path.exists():
        print(f"ERROR: golden file {golden_path} not found")
        sys.exit(1)

    with open(result_path) as f:
        run = json.load(f)
    with open(golden_path) as f:
        golden = json.load(f)

    # Type hints for each field — for type-level metrics
    type_hints = {
        "int": [
            "pricing.base_price_krw", "pricing.price_change_notice_days",
            "free_trial.duration_days", "free_trial.notice_before_conversion_days",
            "cancellation.notice_period_days",
            "terms_changes.notice_lead_time_days",
            "data_usage.retention_period_months",
        ],
        "bool": [
            "pricing.auto_renewal_enabled",
            "free_trial.offered", "free_trial.auto_convert_to_paid",
            "free_trial.cancel_required_before_end", "free_trial.payment_method_required_upfront",
            "cancellation.penalty_present",
            "terms_changes.user_right_to_terminate_on_change", "terms_changes.silent_acceptance_clause",
            "data_usage.third_party_sharing", "data_usage.marketing_use", "data_usage.cross_border_transfer",
            "liability.service_disruption_compensation", "liability.damages_cap_present",
            "liability.indirect_damages_excluded",
            "disputes.arbitration_required", "disputes.class_action_waiver",
        ],
        "enum": [
            "pricing.billing_cycle", "pricing.auto_renewal_consent",
            "cancellation.method", "cancellation.proration_policy",
            "terms_changes.user_consent_mechanism",
            "data_usage.marketing_consent",
        ],
        "list": [
            "pricing.price_change_notice_channels",
            "cancellation.blackout_periods",
            "terms_changes.notice_channels",
            "data_usage.collected_categories", "data_usage.third_party_recipients", "data_usage.third_party_purposes",
        ],
        "str": [
            "cancellation.method_description", "cancellation.penalty_description",
            "liability.compensation_description", "liability.damages_cap_description", "liability.force_majeure_scope",
            "disputes.governing_law", "disputes.jurisdiction_clause",
        ],
    }
    field_to_type = {}
    for t, fields in type_hints.items():
        for f in fields:
            field_to_type[f] = t

    # Per-field comparison
    print("=" * 110)
    print("PER-FIELD ACCURACY (expected vs actual)")
    print("=" * 110)
    print(f"{'Field':<55} {'Type':<6} {'Expected':<22} {'Actual':<22} {'Result'}")
    print("-" * 110)

    counters: dict[str, int] = {"ok": 0, "ok_null": 0, "wrong": 0, "missed": 0, "over_extracted": 0}
    type_counters: dict[str, dict[str, int]] = {}
    section_counters: dict[str, dict[str, int]] = {}

    for section in SECTIONS:
        for field, fv in run["terms"][section].items():
            key = f"{section}.{field}"
            actual = _enum_value(fv["value"])
            golden_entry = golden.get(key)
            if golden_entry is None:
                continue  # 정답 없음
            expected = golden_entry.get("expected")
            cls = classify(expected, actual)
            counters[cls] += 1
            t = field_to_type.get(key, "?")
            type_counters.setdefault(t, dict.fromkeys(counters, 0))[cls] += 1
            section_counters.setdefault(section, dict.fromkeys(counters, 0))[cls] += 1

            mark = {"ok": "✓", "ok_null": "·", "wrong": "✗", "missed": "—", "over_extracted": "+"}[cls]
            print(f"{key:<55} {t:<6} {str(expected)[:21]:<22} {str(actual)[:21]:<22} {mark} {cls}")

    print()
    total = sum(counters.values())
    correct = counters["ok"] + counters["ok_null"]
    print("=" * 110)
    print(f"OVERALL ({total} fields)")
    print(f"  ✓ ok (correct non-null):    {counters['ok']:>3} ({100 * counters['ok'] // total}%)")
    print(f"  · ok_null (correct null):   {counters['ok_null']:>3} ({100 * counters['ok_null'] // total}%)")
    print(f"  — missed (had answer, model said null): {counters['missed']:>3} ({100 * counters['missed'] // total}%)")
    print(f"  ✗ wrong (different value): {counters['wrong']:>3} ({100 * counters['wrong'] // total}%)")
    print(f"  + over_extracted (no answer, model invented): {counters['over_extracted']:>3} ({100 * counters['over_extracted'] // total}%)")
    print(f"  --- accuracy = (ok + ok_null) / total = {100 * correct // total}% ---")
    print()

    print("BY TYPE")
    for t, c in type_counters.items():
        tot = sum(c.values())
        acc = (c["ok"] + c["ok_null"]) / max(tot, 1) * 100
        print(f"  {t:<6}  n={tot:>2}  acc={acc:>5.1f}%   ok={c['ok']} ok_null={c['ok_null']} wrong={c['wrong']} missed={c['missed']} over={c['over_extracted']}")
    print()
    print("BY SECTION")
    for s, c in section_counters.items():
        tot = sum(c.values())
        acc = (c["ok"] + c["ok_null"]) / max(tot, 1) * 100
        print(f"  {s:<14}  n={tot:>2}  acc={acc:>5.1f}%")
    print()

    # unfair_clause_flags
    gold_flags = set(golden.get("unfair_clause_flags", {}).get("expected") or [])
    actual_flags = set(run["terms"].get("unfair_clause_flags") or [])
    print("unfair_clause_flags:")
    print(f"  expected: {sorted(gold_flags)}")
    print(f"  actual:   {sorted(actual_flags)}")
    print(f"  precision={len(actual_flags & gold_flags)/max(len(actual_flags),1):.2f}  recall={len(actual_flags & gold_flags)/max(len(gold_flags),1):.2f}")


if __name__ == "__main__":
    main()
