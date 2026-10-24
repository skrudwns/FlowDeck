# mock-shop

FlowDeck 공개 데모용 연습 쇼핑몰 "연습마켓". 상품과 판매처는 지어낸 값이고, 가격은 규칙에 따라 시간마다 바뀐다. 구조와 이유는 `docs/adr/0010-mock-shop.md`.

## 실행

```bash
uv sync
uv run mock-shop serve --port 8020   # http://127.0.0.1:8020/products
```

## 페이지

| 경로 | 내용 |
|---|---|
| `/robots.txt` | `/admin/`만 막는다 |
| `/products?page=N` | 상품 목록, 한 페이지에 5개 |
| `/products/{id}` | 판매처별 가격, 배송비, 재고 |

## 가격 규칙

`src/mock_shop/pricing.py`. 상품, 판매처, 한국 시간 기준 날짜와 시(hour)만으로 정해진다.

- 일별 변동: 기본가의 -3% ~ +3%
- 토·일 10% 할인: 바사스토어
- 급락: 하루 1/7 확률, 3시간 동안 25% 내림
- 품절: 하루 1/10 확률, 6시간. 상품마다 품절되지 않는 판매처가 하나 있다

`offer_at()`이 돌려주는 `rules`에 적용된 규칙이 들어 있다. 분석 결과와 맞춰 볼 정답으로 쓴다.

## 백엔드 테스트용 HTML

백엔드 파서 테스트(`backend/tests/fixtures/mockshop_*.html`)는 이 쇼핑몰이 만든 HTML을 쓴다. 페이지 구조를 바꾸면 다시 만든다. CI가 다시 만들어 보고 다르면 실패한다.

```bash
uv run mock-shop fixtures ../backend/tests/fixtures
```

## 검사

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest
```
