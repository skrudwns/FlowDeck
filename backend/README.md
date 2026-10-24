# backend

FlowDeck 백엔드. 지금은 다나와 가격 수집기가 들어 있다.

## 로컬 실행

```bash
docker compose up -d          # 저장소 루트에서. Postgres 17이 localhost:5433에 뜬다
cp .env.example .env          # backend/에서. DATABASE_URL이 로컬 DB를 가리킨다
uv sync
uv run alembic upgrade head   # 테이블 생성
```

## 수집기

```bash
uv run flowdeck products sync targets/danawa.txt   # 대상 목록 파일을 DB에 반영
uv run flowdeck products list
uv run flowdeck collect                            # 한 번 수집
```

- 수집 대상은 `targets/danawa.txt`에서 관리한다. 파일에서 뺀 상품은 지우지 않고 비활성화한다.
- 운영 수집은 GitHub Actions(`.github/workflows/collect.yml`)에서 Neon DB로 돈다. 외부 cron 서비스(cron-job.org)가 매시 17분에 GitHub API로 이 워크플로를 실행한다. GitHub 예약 실행은 이 저장소에서 돌지 않아서 쓰지 않는다 (`docs/adr/0006-external-cron-trigger.md`).
- 수집이 끝나면 결과를 판정해서 Healthchecks.io에 신호를 보낸다. 문제가 있으면 `/fail`, 신호가 끊기면 Healthchecks.io가 알린다. 신호 주소는 `HEALTHCHECK_URL`이고, 없으면 보내지 않는다 (`docs/adr/0007-collection-monitoring.md`).
- 지키는 원칙: 소수 상품, 요청 사이 3초, robots.txt 확인, 403/429를 받으면 멈춤, 가격·판매처·시각만 저장. 자세한 이유는 `docs/adr/0004-real-data-source-alternatives.md`.

## 포털 API

```bash
uv run uvicorn flowdeck.api.app:app --reload   # http://localhost:8000/docs
```

읽기 전용이다. 상품 목록과 최근 결과, 가격 이력, 수집 한 번의 판매처 가격, 수집 실행 이력을 준다. 경로와 규칙은 `docs/adr/0008-portal-api-structure.md`.

## 테스트

```bash
uv run pytest
```

수집 실행 테스트는 로컬 Postgres의 `flowdeck_test` DB를 쓴다. DB가 떠 있지 않으면 해당 테스트는 건너뛴다.
