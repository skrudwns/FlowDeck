# 기록

작업 규칙은 [conventions.md](conventions.md), 기록 원칙은 [record-principles.md](record-principles.md).

## 개발 일지

- [2026-10-23](devlog/2026-10-23.md) 주제와 작업 규칙 정함
- [2026-10-24](devlog/2026-10-24.md) 데이터 소스를 다나와로 바꾸고 수집기 구현, 로컬 첫 수집

## 기술 결정 (ADR)

- [ADR-0001](adr/0001-tech-stack.md) 기술 스택: Python(FastAPI) 백엔드, Next.js 웹, PostgreSQL
- [ADR-0002](adr/0002-real-data-source.md) 실데이터 소스: 네이버 쇼핑 검색 API (폐기, API 종료)
- [ADR-0003](adr/0003-collector-runtime.md) 수집기 실행 위치: GitHub Actions + Neon (주기 실행 방식은 ADR-0006으로 대체)
- [ADR-0004](adr/0004-real-data-source-alternatives.md) 실데이터 소스: 다나와 직접 수집, 수집 원칙
- [ADR-0005](adr/0005-collector-data-model.md) 다나와 수집 범위와 저장 구조, SQLAlchemy + Alembic
- [ADR-0006](adr/0006-external-cron-trigger.md) 수집 주기 실행: 외부 cron이 workflow_dispatch 호출
- [ADR-0007](adr/0007-collection-monitoring.md) 수집 감시와 알림: Healthchecks.io
- [ADR-0008](adr/0008-portal-api-structure.md) 포털 API 구조: 동기 엔드포인트, 읽기 전용 경로
- [ADR-0009](adr/0009-portal-web-structure.md) 포털 웹 구조: Next.js 서버 컴포넌트, OpenAPI 타입
- [ADR-0010](adr/0010-mock-shop.md) 연습 쇼핑몰: 수집 작업 안에서 띄우고, 규칙으로 정한 가격을 크롤링

## 트러블슈팅

- [TS-0001](troubleshooting/0001-amended-commit-already-pushed.md) push된 커밋을 amend해서 로컬과 원격 브랜치가 갈라짐
- [TS-0002](troubleshooting/0002-setup-uv-major-tag-missing.md) CI가 시작하자마자 실패, setup-uv@v10을 찾지 못함
- [TS-0003](troubleshooting/0003-scheduled-workflow-not-running.md) 수집 워크플로 예약 실행이 돌지 않음
- [TS-0004](troubleshooting/0004-next-route-types-missing-in-ci.md) CI에서만 PageProps, LayoutProps 타입을 못 찾음

## 분석 노트

아직 없음
