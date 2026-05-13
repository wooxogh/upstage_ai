# Upstage AI Terms Analysis

OTT/구독 약관 분석 파이프라인. Document Parse → Information Extract → Solar Pro 3 요약 → Groundedness Check.

## Setup

```bash
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"
cp .env.example .env  # UPSTAGE_API_KEY 입력
uvicorn app.main:app --reload
```

## Test

```bash
pytest tests/unit -v
```
