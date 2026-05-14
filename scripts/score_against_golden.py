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


SEMANTIC_STR_THRESHOLD = 0.5  # SequenceMatcher ratio 0.5 이상이면 의미상 매칭으로 간주


def _str_similar(a: str, b: str) -> float:
    """두 문자열의 유사도 (0-1). difflib SequenceMatcher 사용."""
    from difflib import SequenceMatcher
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a.strip(), b.strip()).ratio()


def _list_str_similar(a, b) -> bool:
    """두 list가 의미상 같은지 — 원소별 fuzzy 매칭. 한국어/영어 혼합 허용."""
    if not isinstance(a, list) or not isinstance(b, list):
        return False
    if len(a) == 0 and len(b) == 0:
        return True
    if abs(len(a) - len(b)) > max(2, len(a) // 2):
        return False
    # 양쪽 모두 같은 원소가 적어도 60% 이상 fuzzy match 되면 OK
    matches = 0
    for x in a:
        if any(_str_similar(str(x), str(y)) >= 0.6 for y in b):
            matches += 1
    return matches >= len(a) * 0.6


def classify(expected, actual, *, semantic: bool = False) -> str:
    """expected vs actual 매칭 결과 분류. semantic=True면 str/list 유사도 매칭."""
    # 사용자 라벨이 "AMBIGUOUS" 문자열인 경우는 bool 비교 불가 → ok_null 취급
    if isinstance(expected, str) and expected.upper() == "AMBIGUOUS":
        return "ok_null"
    e_null, a_null = _is_null(expected), _is_null(actual)
    if e_null and a_null:
        return "ok_null"
    if e_null and not a_null:
        return "over_extracted"
    if not e_null and a_null:
        return "missed"
    if _normalize(expected) == _normalize(actual):
        return "ok"
    # semantic mode: str/list 유사도 매칭
    if semantic:
        if isinstance(expected, str) and isinstance(actual, str):
            if _str_similar(expected, actual) >= SEMANTIC_STR_THRESHOLD:
                return "ok"
        if isinstance(expected, list) and isinstance(actual, list):
            if _list_str_similar(expected, actual):
                return "ok"
    return "wrong"


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = {a for a in sys.argv[1:] if a.startswith("--")}
    semantic = "--semantic" in flags
    result_path = Path(args[0]) if len(args) > 0 else DEFAULT_RESULT
    golden_path = Path(args[1]) if len(args) > 1 else DEFAULT_GOLDEN
    if semantic:
        print(f"[semantic mode: str/list fuzzy matching, threshold={SEMANTIC_STR_THRESHOLD}]")
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
            cls = classify(expected, actual, semantic=semantic)
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
