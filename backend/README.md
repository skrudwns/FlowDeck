# backend

FlowDeck 백엔드. 다나와와 연습 쇼핑몰 가격 수집기, 스케줄러, 포털 API가 들어 있다.

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
uv run flowdeck products add 109680239             # 다나와 수집 대상 추가 (중지된 상품이면 재개)
uv run flowdeck products deactivate 109680239      # 수집 중지 (기록은 남김)
uv run flowdeck products list
uv run flowdeck collect                            # 다나와 한 번 수집
uv run flowdeck collect --source mockshop          # 연습 쇼핑몰 한 번 수집 (쇼핑몰을 먼저 띄운다)
```

- 연습 쇼핑몰은 `mock-shop/`에서 `uv run mock-shop serve --port 8020`으로 띄운다. 다른 주소면 `--mockshop-url`. 상품은 쇼핑몰 목록 페이지에서 찾으므로 대상 목록 파일이 없다 (`docs/adr/0010-mock-shop.md`).

- 다나와 수집 대상은 DB가 기준이다. 포털이나 위 명령으로 바꾸고, 바꾼 내용은 `audit_log`에 남는다. 2026-10-25 전에는 `targets/danawa.txt` 파일이 기준이었다 (`docs/adr/0011-portal-control-and-scheduler.md`).
- `uv run flowdeck plan --trigger schedule`은 DB의 주기와 수동 실행 요청을 보고 이번에 돌 작업을 정한다. 수집 워크플로의 첫 단계다.
- 운영 수집은 GitHub Actions(`.github/workflows/collect.yml`)에서 Neon DB로 돈다. 외부 cron 서비스(cron-job.org)가 매시 17분에 GitHub API로 이 워크플로를 실행하고, 워크플로는 `plan` 결과에 따라 작업을 돌린다. GitHub 예약 실행은 이 저장소에서 돌지 않아서 쓰지 않는다 (`docs/adr/0006-external-cron-trigger.md`).
- 수집이 끝나면 결과를 판정해서 Healthchecks.io에 신호를 보낸다. 문제가 있으면 `/fail`, 신호가 끊기면 Healthchecks.io가 알린다. 신호 주소는 `HEALTHCHECK_URL`이고, 없으면 보내지 않는다 (`docs/adr/0007-collection-monitoring.md`). 워크플로는 다나와에 `HEALTHCHECK_URL`, 연습 쇼핑몰에 `MOCKSHOP_HEALTHCHECK_URL` Secret을 넘긴다.
- 지키는 원칙: 소수 상품, 요청 사이 3초, robots.txt 확인, 403/429를 받으면 멈춤, 가격·판매처·시각만 저장. 자세한 이유는 `docs/adr/0004-real-data-source-alternatives.md`.

## 포털 API

```bash
uv run uvicorn flowdeck.api.app:app --reload   # http://localhost:8000/docs
```

상품 목록과 최근 결과, 가격 이력, 수집 한 번의 판매처 가격, 수집 실행 이력을 준다. 경로와 규칙은 `docs/adr/0008-portal-api-structure.md`.

제어 경로(수동 실행 요청, 주기 변경, 다나와 대상 추가·중지, 변경 이력)는 `docs/adr/0011-portal-control-and-scheduler.md`. 인증이 없으니 로컬에서만 띄운다. `.env`에 `PORTAL_GITHUB_TOKEN`(이 저장소의 Actions 읽기·쓰기만 가진 fine-grained token)이 있으면 수동 실행 요청 때 워크플로를 바로 실행하고, 없으면 요청만 남겨서 다음 정기 호출 때 실행된다.

## 테스트

```bash
uv run pytest
```

수집 실행 테스트는 로컬 Postgres의 `flowdeck_test` DB를 쓴다. DB가 떠 있지 않으면 해당 테스트는 건너뛴다.
