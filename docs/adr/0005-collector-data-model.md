# ADR-0005: 다나와 수집 범위와 저장 구조

- 날짜: 2026-10-24
- 상태: 채택
- 관련: #2, ADR-0003, ADR-0004

## 상황

다나와 상품 페이지(`https://prod.danawa.com/info/?pcode=...`)에서 무엇을 가져올 수 있는지 2026-10-24에 두 상품(pcode 109680239, 122644105)으로 확인했다. 요청은 curl로 상품마다 한 번씩, 몇 초 간격을 두고 보냈다.

처음 받는 HTML에 들어 있는 것:

- schema.org JSON-LD (`<script type="application/ld+json">`): 상품명, `sku`(= pcode), `offers.lowPrice`(최저가), `offers.offerCount`(판매처 수).

  ```json
  "offers": {"@type": "AggregateOffer", "offerCount": "15", "lowPrice": "899000", ...}
  ```

- `<ul class="list__mall-price">`: 판매처 최대 5곳. 판매처 이름(로고 `alt` 또는 텍스트), 가격, 배송비, 다나와 업체 코드(링크의 `cmpnyc` 값, 예: `TH201` = 11번가).

판매처 전체 목록은 페이지가 뜬 뒤 `./ajax/getAllPriceCompareMallList.ajax.php`, 즉 `/info/ajax/` 경로로 불러온다. robots.txt가 `Disallow: /info/ajax/`로 막고 있어서 쓰지 않는다 (ADR-0004 수집 원칙 4).

## 수집 범위

- 상품 하나당 1시간에 요청 1번. 상품 페이지 HTML만 받는다.
- 저장: 최저가, 판매처 수, 상위 판매처(최대 5곳)의 이름·업체 코드·가격·배송비.
- 최저가와 판매처 수는 JSON-LD에서 읽는다. 화면 구조가 바뀌어도 검색엔진용 표준 데이터라 덜 깨질 것으로 본다. 상위 판매처 목록은 화면 HTML을 파싱하므로 더 잘 깨질 수 있다. 둘을 따로 처리해서, 판매처 목록 파싱이 실패해도 최저가는 저장한다.

## 테이블

```
products           수집 대상 상품
  id, source('danawa'), source_product_id(pcode), name, active, created_at
  (source, source_product_id) 유일

collection_runs    수집 실행 한 번
  id, started_at, finished_at, status(success / partial / failed),
  products_total, products_succeeded, trigger(schedule / manual)

price_snapshots    실행마다 상품별 결과
  id, run_id, product_id, collected_at,
  lowest_price, offer_count,
  status(ok / parse_failed / http_error / blocked), http_status, error_message

seller_prices      스냅샷의 상위 판매처
  snapshot_id, rank(1~5), seller_name, seller_code, price, delivery_fee
```

- 가격이 바뀌지 않아도 매번 저장한다. 수집이 실제로 돌았다는 기록이 되고, GitHub Actions 예약 실행이 빠진 시간대를 나중에 확인할 수 있다 (ADR-0003).
- 실패도 `price_snapshots`에 상태와 함께 남긴다. "실패한 실행은 실패 원인과 함께 기록된다"는 #2 완료 기준.
- 용량 추정: 상품 20개면 하루 스냅샷 480행, 판매처 2,400행. 행 크기와 인덱스를 넉넉히 잡아도 Neon 무료 0.5GB 안에서 1년 이상 쓸 수 있을 것으로 본다. 실제 크기는 1주일 쌓은 뒤 재서 여기에 적는다.

## DB 접근 방식

### A. SQLAlchemy 2.0 + Alembic

- 좋은 점: 테이블 정의를 코드로 관리하고, Alembic으로 스키마 변경 이력이 마이그레이션 파일로 남는다. 나중에 FastAPI와 같은 모델을 쓸 수 있다.
- 걸리는 점: 테이블 4개짜리 수집기에는 설정할 것이 많다.

### B. psycopg + SQL 파일

- 좋은 점: 의존성이 적고 SQL이 그대로 보인다.
- 걸리는 점: 스키마 변경 이력과 적용 여부를 직접 관리해야 한다. 포털 단계에서 결국 ORM이나 마이그레이션 도구를 다시 고민하게 된다.

결정: A. 포털에서 같은 테이블을 계속 쓸 것이고, 스키마가 바뀐 이력이 마이그레이션 파일로 남는 것도 기록으로 의미가 있다.

## 정할 것

- 수집 대상 상품 20개 고르기. 분석에 쓸 수 있게 가격 변동이 있을 만한 상품(판매처가 많은 상품)이 좋다.

## 돌아보기

<나중에 추가>
