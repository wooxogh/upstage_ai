# 실험 종합 분석 — 2026-05-14

**Total: 15 runs across 8 configs**
**Fixture**: Netflix terms (data/fixtures/netflix_golden.json)
**Total wall clock for experiments**: ~66분 (round 1: 27분 + round 2: 39분)

## Config 집계 (모든 round 합산)

| Config | Runs | Acc 평균 | 범위 | Sec 평균 | Tokens 평균 | Grounded% | 비용/정확도 |
|---|---|---|---|---|---|---|---|
| **C: N=3 medium** | 5 | **65.8%** | 57–71 | 308s | 92K | 60% | 4.7K tok/% |
| **G: N=2 medium** | 2 | **68.5%** | 66–71 | 149s | 63K | 0% | 0.9K tok/% |
| B: N=1 high | 2 | 63.5% | 61–66 | 97s | 49K | 50% | 0.8K tok/% |
| D: N=1 medium | 1 | 64.0% | 64 | 84s | 44K | 100% | 0.7K tok/% |
| A: N=3 high | 2 | 61.5% | 59–64 | 313s | 85K | 100% | 1.4K tok/% |
| F: N=5 medium | 1 | 66.0% | 66 | 419s | 131K | 100% | 2.0K tok/% |
| E: N=3 low | 2 | 45.0% | 40–50 | 116s | 58K | 0% | 1.3K tok/% |

## 핵심 발견

### 1. reasoning_effort: **medium ≫ high ≫ low**
- low: 45% (망함)
- high: 61.5% (예상보다 낮음 — voting과 충돌)
- medium: 65.8% (최선)
- 가설: high는 reasoning path가 너무 다양해 voting이 합의 못 찾음; medium은 일관성 있어 voting이 noise 평균화

### 2. voting (N): **N=2 ≈ N=3 ≥ N=5 ≫ N=1**
- N=1: 63-64%
- N=2: 68.5%
- N=3: 65.8%
- N=5: 66% (diminishing returns)
- N=2가 가성비 정점 — N=3 대비 절반 시간/토큰으로 비슷한 정확도

### 3. **C는 변동성 큼 (5 sample: 57–71%, std ~5.5%p)**
- 단일 sample로 config 비교는 noise level. N=10+ 필요
- 95% CI 추정: C [60-72%], G [60-77%] — 겹침. G>C 단정 불가.

### 4. grounded rate variance
- 같은 config 안에서도 run마다 True/False 다름
- summary text 자체가 약관 paraphrase라 검증 불안정

## 비용/정확도 정리

| Config | $-equivalent (토큰 기준) | 정확도 |
|---|---|---|
| D: N=1 medium | 44K tokens | 64% |
| G: N=2 medium | 63K tokens | 68.5% |
| C: N=3 medium | 92K tokens | 65.8% |
| F: N=5 medium | 131K tokens | 66% |

**G (N=2 medium)이 sweet spot 후보**. 비용 -32% vs C, 정확도 +2.7%p.
다만 N=2 sample이 2개뿐 — 변동성 미확정.

## 타입별 가장 잘 잡는 config

| Type | 최고 config | 정확도 |
|---|---|---|
| int | F (N=5 medium) | 100% |
| enum | C / F | 83.3% |
| **bool** | G (N=2 medium) | **68.8%** |
| **list** | F | **83.3%** |
| **str** | G | **57.1%** |

G가 bool/list/str 3개 타입에서 1위. F가 int/list에서 1위지만 토큰 2배.

## 운영 권고

### Option α: **G (N=2 medium)** — 신중 채택
- 정확도: 68.5% (2 sample only — 더 측정 필요)
- 토큰: 63K (현재 C 대비 -32%)
- 시간: 149s (현재 C 대비 -39%)
- 위험: N=2 sample 부족, 변동성 확인 안 됨

### Option β: **C (N=3 medium)** — 현재 default 유지
- 정확도: 65.8% (5 sample 확정)
- 토큰: 92K
- 시간: 308s
- 안정성: 측정 sample 가장 많음

### Option γ: **N=1 medium (D)** — minimal viable
- 정확도: 64% (1 sample only)
- 토큰: 44K (-52%)
- 시간: 84s (-73%)
- 위험: variance 미측정

## 다음 측정 우선순위
1. **G config × 5+ runs** — N=2 medium 진짜 mean 확인 (~20분 소요)
2. **D config × 5+ runs** — N=1 minimal baseline 확인 (~10분)
3. **F config × 3+ runs** — N=5 진짜 효과 vs cost

## 핵심 교훈 (vibe coding 학습)

1. **prompt를 더 길게 ≠ 더 정확**. Codex 제안한 11개 규칙 추가했더니 57%로 폭락. 짧고 명확한 prompt가 모델 attention 분산을 막음.
2. **reasoning_effort=high가 항상 좋은 게 아님**. voting과 결합하면 오히려 손해. medium이 sweet spot.
3. **변동성을 측정하지 않은 실험은 의미가 작음**. 단일 sample로 prompt/config 비교 = noise 보고 결정.
4. **자유 텍스트 paraphrase는 voting/prompt로 못 잡음** — str 정확도가 모든 config에서 가장 낮음. semantic similarity 기반 채점이나 schema 변경이 필요.
5. **사용자 라벨링 의지가 진짜 baseline 확립의 결정적 요소**. 골든 라벨 없었으면 위 모든 비교 불가.

## 데이터 위치

- `data/experiments/experiments_20260514_032524.{json,md}` — Round 1 (A, B, C, D 첫 측정)
- `data/experiments/experiments_20260514_040020.{json,md}` — Round 2 (C 변동성, G/E/F 추가)
- `data/fixtures/netflix_golden.json` — 사용자 라벨링 v0.2 (50 fields)
