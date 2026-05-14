# Upstage AI Terms Analysis

한국 OTT/구독 약관 분석 파이프라인. PDF/HTML 약관 1건을 입력받아 **42개 필드 구조화 추출 + 위험 조항 요약 + 인용 근거 검증**까지 종단으로 동작.

```
입력 (PDF/HTML)
  ↓ Document Parse (PDF) / 직접 추출 (HTML)
  ↓ Solar Pro 3 × N=2 voting (구조화 추출)
  ↓ Solar Pro 3 요약 (위험 조항 3-5개)
  ↓ Solar Pro 3 groundedness check (근거 검증)
출력 JSON { terms, summary, key_clauses, ungrounded_clauses, grounded, timings, usage }
```

---

## 📊 성능 평가 (7 서비스, 사람 라벨 기준)

7개 서비스의 약관에 대해 **사람이 수동으로 라벨링한 42개 필드 골든 데이터셋**에 대조한 정확도. **default config = BC (N=2 voting + medium reasoning) + prompt #1 (한국 OTT bool 추론 룰)**, 서비스당 2 runs 평균 (병렬 동시성 3, 총 22.2분):

| 서비스 | 형식 | Strict | Semantic | Range | 추출 시간 | 토큰 |
|---|---|---|---|---|---|---|
| **Netflix** | PDF | **72.5%** | **79.5%** | 69-76 | 322s | 81K |
| **Spotify** | HTML | 67.5% | 78.0% | 64-71 | 210s | 89K |
| **Wavve** ¹ | HTML×2 | 62.5% | 71.0% | 61-64 | 153s | 103K |
| **Disney+** ⁴ | HTML | 59.0% | 71.0% | 59-59 | 248s | 108K |
| **TVING** ³ | HTML×2 | 59.0% | 62.5% | 57-61 | 272s | 139K |
| **Watcha** ⁵ | HTML | 53.0% | 59.0% | 52-54 | 195s | 98K |
| **Coupang Play** ² | HTML×2 | 52.0% | 53.0% | 52-52 | 457s | 84K |
| **평균** | — | **60.8%** | **67.7%** | — | **265s** | **100K** |

이전 single-run 베이스라인 대비 **strict +1.4%p / semantic +4.7%p** 평균 개선 — Round 5(BC config)와 Round 6(prompt #1) 누적 효과. 가장 큰 개선은 Watcha(+8/+12%p), TVING(+12/+10.5%p), Disney+(+2/+10%p)로 한국 OTT bool 추론 룰이 적용된 서비스들. Spotify는 동의 메커니즘 일부 흔들림으로 strict 회귀(-5.5%p)했지만 semantic은 동일 유지.

¹ Wavve는 약관이 `서비스` + `유료상품` 두 문서로 분리. 두 문서 결합 후 측정. 단일 문서로는 57%(strict)에 그침 — pricing 섹션 5/6 missed가 `유료상품` 문서에 있었음.

² Coupang Play도 `이용 기준` + `유료서비스 이용 약관` 두 문서. `coupangplay.com`은 Akamai 차단으로 직접 접근 불가 — React가 띄우는 iframe 원본(`web.coupangstreaming.com/tnc/`)을 직접 받아서 처리. 결합 fixture에서 over_extraction이 두드러져 strict 52%로 가장 낮음 — `unfair_clause_flags` precision 회복이 핵심.

³ TVING은 SPA(JS 렌더링 필수) — `m.tving.com/guide/term.tving` 을 Playwright + 모바일 UA로 hydration 대기 후 `유료이용약관` 탭 클릭으로 두 문서 모두 캡처. 다른 서비스 대비 over_extracted=7개(16%)가 두드러짐 — 두 약관을 한 문서에 결합해 cross-doc 추론 오류 가능성.

⁴ Disney+는 SSR로 한국·영문 약관이 한 페이지에 둘 다 노출 — 한글 헤딩(`[이전]디즈니+ 이용 약관(대한민국)`) 마커로 한글 섹션만 추출. prompt #1 적용 후 semantic 61→71%로 가장 큰 점프 (한국 OTT bool 추론 룰의 직접 수혜).

⁵ Watcha는 SSR이지만 free_trial 50%, liability 33%, str 필드 14%로 평균 하회. prompt #1 적용 전 bool '명시적 부재' 8개 missed였으나 N=2 voting + 한국 OTT 룰 결합으로 +8/+12%p 회복 — 가장 명확한 prompt#1 ROI.

**비교 기준**: Upstage Solar Pro 3 한국어 MCQ 벤치마크 ~80%.  
**현재 갭**: BC + prompt#1 평균 -12 ~ -19%p (semantic 67.7% vs 벤치마크 80%). Netflix·Spotify·Wavve·Disney+ 의 semantic은 71-80%로 벤치마크 근접권. Coupang Play / Watcha 가 평균을 끌어내림.

### 필드 타입별 정확도 (3 서비스 기준 — Spotify · Netflix PDF · Wavve)

| Type | 정확도 | 비고 |
|---|---|---|
| int | **85.7%** | 30일, 7일 등 명시적 숫자 강함 |
| enum | 61.1% | 도메인 enum (BillingCycle, ConsentMechanism 등) |
| bool | 72.9% | 명시적 부재(False) vs 침묵(null) 구분이 핵심 |
| list | 88.9% | (semantic 기준) — 한/영 표기 차이 해소됨 |
| str | 47.6% | (semantic 기준) — 자유 텍스트 paraphrase variance |

### 서비스별 흥미로운 발견

**Spotify (스웨덴 본사, 한국 서비스)**
- 🚨 `arbitration_required: True` — 의무적 개별 중재 조항 (USA-style)
- 🚨 `class_action_waiver: True` — 집단소송 권리 포기
- `user_consent_mechanism: deemed_agreed` — "계속 사용 = 동의 간주"
- `governing_law: Sweden` (default) / `대한민국 법률` (한국 사용자 예외)

**Netflix (한국)**
- `governing_law: 대한민국 법률` (한국 사용자에게 한국 법 명시)
- `auto_renewal_consent: opt_out_available` (소비자 친화적 해지 통로)
- `price_change_notice_days: 30` (충분한 사전 통지)
- `arbitration/class_action_waiver`에 대한 명시적 부재 (소비자에 유리)

**Wavve (한국)**
- `terms_changes.notice_lead_time_days: 7` — Netflix 30일 대비 **4배 짧음** ⚠️
- `marketing_consent: opt_out_available` — 마케팅 활용 거부 가능
- `force_majeure_scope`: "천재지변 또는 이에 준하는 불가항력" (전통적 한국 약관 표현)

**Coupang Play (한국, 쿠팡 자회사)**
- `data_usage` 섹션 **100% 정확** (한국 서비스 중 최고) — 개인정보 항목이 모회사 쿠팡 표준 약관 패턴을 따라 구조화 명확
- str 필드 5/7 wrong — `cancellation.method_description` 등 자유 텍스트가 모회사 약관 인용 형식이라 paraphrase 갭 큼
- `unfair_clause_flags` 8개 중 1개만 검출 (recall 0.12) — `환불 거부 (시청 시 청약철회 권리 소멸)` 같은 다크패턴 미포착

**TVING (한국, CJ ENM 자회사)**
- 두 약관(서비스+유료) 한 fixture 결합 → **over_extracted=7개**가 두드러짐. 모델이 cross-doc 추론을 시도해 골든에 없는 답을 만들어냄
- `liability` 33%, `data_usage` 37.5% — 다른 한국 서비스 평균 대비 낮음
- `unfair_clause_flags` 5개 중 1개만 검출 — `다크패턴 — 해지 절차 복잡화`, `약관 일방 변경권` 등 핵심 항목 누락

**Disney+ (글로벌, 한국 별도 약관)**
- 🚨 `damages_cap_present: True` + 한도 **100만원** — 글로벌 OTT 최저 수준 손배 한도 (Netflix 무한도 대비)
- `governing_law: 대한민국 법률` + `jurisdiction_clause: 서울` — Spotify와 달리 한국법 친화적 (월트디즈니컴퍼니코리아 법인 운영)
- `auto_renewal_consent` 추출이 한국 서비스 패턴(opt_in)과 글로벌 패턴(opt_out) 사이에서 혼동 — 가입 동의/취소 통로가 서로 다른 단계에 있어서 모델 해석에 흔들림
- terms_changes **100%**: "30일 사전 통지 + 명시적 동의" 명시가 매우 명확

**Watcha (한국, 가장 명확한 약관 구조)**
- 🚨 `cancellation.penalty_description`: 중도 해지 시 결제금액 **10% 위약금 명시** (한국 OTT 중 유일하게 계산식까지 노출)
- 🚨 `marketing_consent: opt_in_required` — Netflix/Wavve의 opt_out_available 대비 사용자 권리 더 명확
- 추출 한계: `disputes` 25%·`liability` 33%·str 14% — 결국 같은 패턴 (자유 텍스트 paraphrase + bool 명시적 부재 식별 한계)

이러한 cross-service 비교는 소비자가 가입 전 검토 시 즉시 보이는 차별점을 드러냄.

---

## 🔬 실험 결과 정리 (30+ runs, Round 1-6)

### Round 1-4: config matrix (Netflix PDF 기준, 23 runs)

| Config | Runs | Acc 평균 | 범위 | Std | Sec | Tokens |
|---|---|---|---|---|---|---|
| E (N=3, low) | 2 | 45.0% | 40-50 | 5.0 | 116 | 58K |
| D (N=1, medium) | 4 | 59.8% | 45-69 | 9.4 | 144 | 47K |
| A (N=3, high) | 2 | 61.5% | 59-64 | 2.5 | 313 | 85K |
| B (N=1, high) | 2 | 63.5% | 61-66 | 2.5 | 97 | 49K |
| C (N=3, medium) | 5 | 65.8% | 57-71 | 5.5 | 308 | 92K |
| F (N=5, medium) | 1 | 66.0% | — | — | 419 | 131K |
| **G (N=2, medium)** ⭐ | **7** | **71.6%** | 66-80 | 4.9 | 222 | 70K |

→ **Winner: G (N=2 majority voting + medium reasoning)**. C(N=3) 대비 시간 -28%, 토큰 -24%, 정확도 +5.8%p.

### Round 5: per-stage reasoning_effort 튜닝 (BC config, 5 runs/config)

`extract` 외 단계 reasoning_effort 영향 측정:

| Config | extract | summarize | ground | Acc 평균 | Sec | 비고 |
|---|---|---|---|---|---|---|
| baseline | medium | minimal | low | 71.6% | 222 | Round 1-4 G config |
| B only | medium | high | low | 73.2% | 263 | summarize ↑ |
| C only | medium | minimal | medium | 72.8% | 251 | ground ↑ |
| **B+C** ⭐ | **medium** | **high** | **medium** | **74.7%** | 268 | **둘 다 ↑** |

→ B+C 채택 — summarize/ground 모두 reasoning_effort ↑가 추출 단계와 무관하게 종합 정확도 향상.

### Round 6: prompt #1 (한국 OTT bool 추론 룰)

`prompts/extract_subscription.py` 에 "한국 OTT 약관에서 arbitration / class_action_waiver / damages_cap_present 등은 한국 강행규정에 의해 적용되지 않으므로 명시 부재 시 `False, inferred`" 룰 추가:

| Config | Service | Acc 평균 | 비고 |
|---|---|---|---|
| BC | Netflix PDF | 74.7% | baseline |
| **BC + prompt #1** ⭐ | **Netflix PDF** | **79.7%** (peak 83%) | **+5%p** |

→ 한국 OTT 6/7 fixtures에서 bool '명시적 부재' missed가 4-8개 → 0-3개로 회복.

### 발견된 counter-intuitive 패턴

1. **`reasoning_effort: medium > high` (extract 단계)** — high가 reasoning path 다양해서 voting과 충돌. medium이 일관성 ↑로 voting 효과 극대화.
2. **`reasoning_effort: high` (summarize/ground 단계)** — 단일 호출 단계는 voting 보호가 없어 reasoning 깊이가 직접 정확도 견인. extract와 정반대 처방.
3. **N=2 voting ≈ N=3 voting**: 추가 voting의 diminishing returns. N=5는 효과 미미.
4. **temperature=0인데도 ±5%p 변동성**: Solar API의 비-결정성 잔존. 최소 N=2 sample 평균 권장.
5. **prompt 도메인 사전 지식 > config 튜닝**: BC config로 +3.1%p 얻은 후 prompt #1으로 +5%p 추가. 모델에게 *한국 약관 컨텍스트*를 명시하는 효과가 reasoning_effort/voting의 generic 튜닝보다 컸음.

---

## 🧪 Pipeline 핵심 설계 결정

### 1. **N=2 majority voting** (services/voting.py)
한 번의 추출 호출은 ±5%p 변동성. 2회 호출 후 필드별 다수결로 합성. 충돌 시 non-null 우선, 같은 의미의 list/enum은 정규화 후 비교.

### 2. **명시적 부재 vs 침묵 구분** (prompts/extract_subscription.py)
약관이 "X는 없습니다" / "부담하지 않습니다"라고 명시하면 → `value=False, confirmed`. 단순 침묵일 때만 `not_specified`.

### 3. **별도 정책 참조 우회 처리**
"개인정보처리방침은 별도로 따른다" 같은 외부 위임 → `not_specified` (False로 추측 금지).  
mini-fix 적용 후 over-extraction이 5건 → 0건 (Spotify 기준).

### 4. **HTML bypass** (services/parse.py)
HTML 입력은 Upstage Document Parse(415 Unsupported)를 우회하고 stdlib `HTMLParser`로 직접 텍스트 추출. PDF는 Document Parse `mode=enhanced` (VLM 기반).

### 5. **bbox 후처리** (services/extract.py:_enrich_with_bbox)
PDF의 경우 Solar Pro 3가 page+quote만 반환. Document Parse의 element 좌표와 quote substring 매칭으로 bbox 자동 채움 → UI 하이라이트용.

### 6. **Groundedness Check fallback** (services/ground.py)
Upstage 전용 `/groundedness-check` endpoint가 공식 docs에 없어 Solar chat completions로 verification prompt 보내는 fallback 구현. clause + summary 둘 다 검증.

---

## 🏗️ Architecture

```
app/
├── main.py              # FastAPI 앱 + exception handlers
└── routes/terms.py      # POST /v1/terms/analyze (multipart)

services/
├── upstage.py           # httpx async client + retry + 토큰 사용량 캡처
├── parse.py             # Document Parse 어댑터 + HTML 우회
├── extract.py           # Solar + json_schema 추출 + N=2 voting
├── voting.py            # 필드별 majority voting (enum/list/citation 정규화)
├── summarize.py         # Solar 위험 조항 요약
├── ground.py            # Solar verification (fallback)
└── pipeline.py          # 4단계 직렬 + 단계별 timing/usage 집계

schemas/
├── common.py            # FieldValue[T] (value, uncertainty, citation)
├── enums.py             # 5개 도메인 enum
├── pain_points.py       # 11개 pain point taxonomy
└── subscription.py      # 7 섹션 + Root

prompts/
├── extract_subscription.py    # 추출 + ConsentMechanism 결정 흐름 + 4개 판정 사례
├── summarize_subscription.py  # 위험 조항 식별 룰
└── groundedness_check.py      # 검증 verifier
```

전체 파이프라인은 단일 `POST /v1/terms/analyze` 엔드포인트로 노출. JSON 응답에 `terms`, `summary`, `key_clauses`, `ungrounded_clauses`, `grounded`, `timings`, `usage` 포함.

---

## 🛠 Setup

```bash
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"
cp .env.example .env  # UPSTAGE_API_KEY 입력
uvicorn app.main:app --reload
```

### 단일 약관 분석 (CLI)

```bash
# Netflix 약관 PDF 사용
.venv/bin/python scripts/single_run.py netflix

# Spotify 약관 (HTML 자동 추출)
.venv/bin/python scripts/fetch_public_terms.py spotify
.venv/bin/python scripts/single_run.py spotify

# 결과 채점 (사용자 라벨 필요)
.venv/bin/python scripts/score_against_golden.py \
  /tmp/variance_run_1.json data/fixtures/spotify_golden.json --semantic
```

### 실험 매트릭스

```bash
# scripts/run_experiments.py 의 CONFIGS 수정 후
.venv/bin/python scripts/run_experiments.py
# → data/experiments/experiments_<timestamp>.{json,md}
```

### 7 서비스 일괄 측정

```bash
# 모든 fixture × N runs (병렬 동시성 3) → aggregate report
.venv/bin/python scripts/run_all_fixtures.py 2 3
# → data/experiments/all_fixtures_<timestamp>.{json,md}
```

다중 API 키 (`UPSTAGE_API_KEY_2..4`)를 `.env`에 추가하면 자동으로 라운드로빈 분배 — 키 K개면 동시 fixture 수 ~K× 증가.

### 환경 변수
- `UPSTAGE_API_KEY` — Upstage 인증 (필수)
- `UPSTAGE_API_KEY_2..4` — 선택, run_all_fixtures.py 가 자동 분배
- `EXTRACT_ENSEMBLE_N` — voting N (default 2)
- `EXTRACT_REASONING_EFFORT` — high/medium/low (default medium)
- `SUMMARIZE_REASONING_EFFORT` — high/medium/low (default high) — Round 5 결과
- `GROUND_REASONING_EFFORT` — high/medium/low (default medium) — Round 5 결과

---

## 📁 산출물 (재현 가능)

| 위치 | 내용 |
|---|---|
| `data/fixtures/*_golden.json` | 사람 라벨된 정답 데이터 (Netflix v0.2 50필드, Spotify v1, Wavve v1, Coupang Play v0.2, TVING v0.2, Watcha v0.2, Disney+ v0.2) |
| `data/fixtures/*_terms.html` | 약관 원본 HTML (Spotify · Wavve · Coupang Play · TVING · Netflix · Watcha · Disney+) — gitignored, [data/fixtures/README.md](data/fixtures/README.md) 참고 |
| `data/fixtures/*_run_baseline.json` | 단일 호출 추출 결과 |
| `data/experiments/experiments_*.{json,md}` | 23회 실험 raw 데이터 + 자동 리포트 (Round 1-4) |
| `data/experiments/all_fixtures_*.{json,md}` | 7 fixture × N runs 일괄 측정 raw + 자동 리포트 (Round 5-6) |
| `data/experiments/aggregate_summary.md` | Round 1-6 종합 분석 |
| `docs/superpowers/specs/2026-05-13-ie-schema-subscription-design.md` | IE 스키마 설계 스펙 |
| `docs/superpowers/plans/2026-05-13-ie-pipeline-implementation.md` | 13-task 구현 계획 |
| `scripts/eval_variance.py` | N회 호출 변동성 측정 |
| `scripts/run_experiments.py` | config matrix runner |
| `scripts/analyze_errors.py` | 필드별 오류 패턴 집계 |

---

## 🚧 한계 및 다음 단계

### 알려진 한계

1. **단일 fixture variance 큼**: 같은 약관 5회 호출에서 ±5%p (G 기준 57-80%). 진짜 mean 수렴엔 N≥10 sample 필요.
2. **자유 텍스트 paraphrase 한계**: str 필드 strict 정확도 29%, semantic 47% — 본질적 paraphrase variance.
3. **글로벌 vs 한국 사용자 viewpoint**: Spotify처럼 region-specific 조항이 있을 때 모델은 default 채택, 사용자는 한국 사용자 기준 라벨 → 약관 해석 철학 차이.
4. **`silent_acceptance`, `continued_use_deemed`**: 사용자가 라벨링 중 신규 enum value 필요성 발견. 현 schema는 3개 (opt_in_explicit / opt_out_available / deemed_agreed)로 한정.
5. **`unfair_clause_flags` controlled vocab**: 사용자 라벨이 `POST-01`, `면책/손배 제한`, `약관 일방 변경권` 등 혼합 표기 → 모델 출력과 매칭 precision 1.0이지만 recall 25-33%.
6. **다중 문서 약관 (Wavve case)**: Wavve는 `서비스 이용약관` + `유료상품 이용약관` 두 문서로 분리. 초기에 service만 처리해 pricing 5/6 missed(=17%). 두 문서 결합 후 pricing 50%로 회복(+33%p). Tving·Watcha 등도 동일 구조 가능 → fixture 추가 시 다중 문서 확인 필요.

### 7 서비스 누적 데이터에서 보이는 개선 기회 (우선순위 순)

7개 서비스 × 42 필드 = 294 sample 누적 후 드러난 *반복 발생* 패턴. 단일 fixture에서는 안 보이는 시스템적 갭이라 prompt/scoring 양쪽 개입이 필요.

1. **bool '명시적 부재' → False 강제 (가장 영향 큰 단일 fix 예상, +5~8%p 추정)**
   - **증상**: `disputes.arbitration_required`, `class_action_waiver`, `liability.damages_cap_present` 등의 bool이 7개 서비스 중 **6개**에서 `missed` (모델이 null 반환). 한국 OTT 6개는 중재/집단소송 자체를 약관에서 다루지 않음 → 정답은 `False`인데 모델은 침묵을 null로 해석.
   - **현상 진단**: `prompts/extract_subscription.py:88` 의 "명시적 부재 vs 침묵" 가이던스가 *국제 분쟁 절차*는 한국 약관 컨텍스트에서 *항상* 부재라는 사전 지식을 모델에 주지 못함.
   - **수정 방향**: disputes/liability 섹션 프롬프트에 "한국 사업자 약관에 arbitration/class_action 조항이 없으면 `False, confirmed`" 룰 명시. 평균 4 missed × 7 서비스 = 28 missed 중 20개 회복 가능.

2. **`unfair_clause_flags` controlled vocab 매칭 (Disney+ precision 0의 근본 원인)**
   - **증상**: Disney+의 모델 출력 `면책/손배 제한`이 골든 `면책/손배 제한 (100만원 한도)`과 strict 매칭 실패로 precision=0. 의미는 동일.
   - **수정 방향**:
     - 단기: `scripts/score_against_golden.py:226` 의 flags 비교에 *괄호 제거 + 토큰 정규화* 후 set 비교 적용. precision/recall 둘 다 즉시 회복.
     - 중기: `prompts/extract_subscription.py` 의 flag 가이드를 닫힌 vocabulary 표로 고정 (`POST-01` ~ `POST-05` + 5개 한글 표준명) — 모델 출력 정규화.

3. **`data_usage.third_party_recipients` / `purposes` 리스트 missed**
   - **증상**: Watcha (3 missed), Disney+ (2 missed), Netflix HTML (4 missed) — 약관 본문에 명시된 list가 모델이 *문장 단위로만* 보고 list 항목으로 못 묶음. Disney+에서 "월트디즈니 계열사", "법집행기관" 등 명백히 적힌 리스트.
   - **수정 방향**: `prompts/extract_subscription.py` 의 `data_usage` 섹션에 *list 추출 예시* 추가 ("...에게 제공할 수 있습니다. ① X ② Y ③ Z" → `[X, Y, Z]`). 추출 변환 패턴 1개 추가로 7개 서비스 모두 영향.

4. **str semantic threshold 0.5 → 0.4 (또는 embedding 기반)**
   - **증상**: Disney+ `jurisdiction_clause`: 골든 `대한민국 서울의 관할법원` vs 모델 `서울, 대한민국` — 의미 동일, SequenceMatcher 0.32. semantic 기준에서도 `wrong`.
   - **수정 방향**:
     - 단기: `scripts/score_against_golden.py:57` 의 `SEMANTIC_STR_THRESHOLD = 0.5` → `0.4`. 검증: 거짓 정답 증가 여부 sample 5개로 확인.
     - 중기: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` 임베딩으로 cosine ≥ 0.7 매칭. 한국어 paraphrase에 robust.
   - **기대 효과**: str 필드 14-43% → 50%+ (across-the-board).

5. **`auto_renewal_consent` enum 일관성 (한국 vs 글로벌 패턴 충돌)**
   - **증상**: Watcha와 Disney+ 모두 골든 `opt_out_available` vs 모델 `opt_in_explicit`. 가입 시 *동의 체크박스*가 있다고 해서 `opt_in_explicit`로 해석하면 한국 약관 표준 (자동갱신=기본, 해지로 opt-out)이 무너짐.
   - **수정 방향**: `prompts/extract_subscription.py` 의 ConsentMechanism 결정 흐름에 룰 추가: "가입 시 동의 ≠ 자동갱신 opt_in. 자동갱신은 *갱신 직전 별도 동의 요구* 여부로 판정". 예시 보강.

6. **다중 문서 결합 시 over_extraction (TVING 사례)**
   - **증상**: TVING fixture (서비스+유료 결합) → over_extracted 7개. 모델이 두 문서 사이 cross-doc 추론으로 골든에 없는 답 생성.
   - **수정 방향**: 결합 fixture에 *문서 경계 마커* 명시 (`<hr><h1>... 유료이용약관</h1>`) — 이미 fixture 빌더에 있음. extract 프롬프트에 "각 마커 이하 본문에서만 인용" 룰 추가.

### 그 외 다음 우선순위

1. **Schema 확장**: ConsentMechanism enum + jurisdiction multi-region 구조 + Codex 추천 신규 필드 (`app_store_billing_dependency`, `dormant_account_policy` 등)
2. **BC + prompt#1 × 5+ runs**: 현재 7 서비스 평균 60.8% strict / 67.7% semantic 의 신뢰구간 확정 (현재는 N=2 평균이라 ±5%p variance 잔존)
3. **다른 fixture 추가**: ~~Tving~~ / ~~쿠팡플레이~~ / ~~Watcha~~ / ~~Disney+~~ (완료) / Apple TV+ / Laftel / Twip 등
4. **str semantic 임계값 튜닝**: 현재 SequenceMatcher 0.4 — embedding 기반 의미 비교 (multilingual-MiniLM)로 업그레이드 가능
5. **disputes 섹션 prompt 보강**: region-specific 조항 추출하도록 (Spotify의 USA-style 중재 조항 캐치)

---

## 📚 관련 문서

- [전체 종합 분석](data/experiments/aggregate_summary.md) — Round 1-6 / 7 configs / 7 services
- [7 fixture 일괄 결과](data/experiments/all_fixtures_20260515_014511.md) — BC + prompt#1 default 14 runs
- [IE 스키마 설계 스펙](docs/superpowers/specs/2026-05-13-ie-schema-subscription-design.md)
- [구현 계획](docs/superpowers/plans/2026-05-13-ie-pipeline-implementation.md)

---

## 🧪 Tests

```bash
PYTHONUNBUFFERED=1 pytest tests/unit -v       # 59 unit tests
pytest tests/integration -m e2e               # opt-in E2E (UPSTAGE_API_KEY + fixture 필요)
```
