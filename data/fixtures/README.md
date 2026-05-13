# Fixtures

E2E 테스트용 실제 약관 PDF/HTML 보관소.

## 필요 파일

- `netflix_terms.pdf` — Netflix 이용약관 (https://help.netflix.com/legal/termsofuse 다운로드)
- `spotify_terms.pdf` — Spotify 이용약관
- `wavve_terms.pdf` — Wavve 이용약관

## 추가 방법

각 서비스 약관 페이지에서 PDF/HTML로 저장 후 위 파일명으로 본 디렉토리에 배치.

## 실행

UPSTAGE_API_KEY가 .env에 설정되어 있어야 함.

    pytest tests/integration -v -m e2e
