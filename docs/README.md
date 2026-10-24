# 기록

작업 규칙은 [conventions.md](conventions.md), 기록 원칙은 [record-principles.md](record-principles.md).

## 개발 일지

- [2026-10-23](devlog/2026-10-23.md) 주제와 작업 규칙 정함
- [2026-10-24](devlog/2026-10-24.md) 데이터 소스를 다나와로 바꾸고 수집기 구현, 로컬 첫 수집

## 기술 결정 (ADR)

- [ADR-0001](adr/0001-tech-stack.md) 기술 스택: Python(FastAPI) 백엔드, Next.js 웹, PostgreSQL
- [ADR-0002](adr/0002-real-data-source.md) 실데이터 소스: 네이버 쇼핑 검색 API (폐기, API 종료)
- [ADR-0003](adr/0003-collector-runtime.md) 수집기 실행 위치: GitHub Actions + Neon
- [ADR-0004](adr/0004-real-data-source-alternatives.md) 실데이터 소스: 다나와 직접 수집, 수집 원칙
- [ADR-0005](adr/0005-collector-data-model.md) 다나와 수집 범위와 저장 구조, SQLAlchemy + Alembic

## 트러블슈팅

- [TS-0001](troubleshooting/0001-amended-commit-already-pushed.md) push된 커밋을 amend해서 로컬과 원격 브랜치가 갈라짐
- [TS-0002](troubleshooting/0002-setup-uv-major-tag-missing.md) CI가 시작하자마자 실패, setup-uv@v10을 찾지 못함

## 분석 노트

아직 없음
