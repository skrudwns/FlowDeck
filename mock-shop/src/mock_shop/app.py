"""연습 쇼핑몰 페이지. 구조와 이유는 docs/adr/0010-mock-shop.md.

페이지 구조는 일부러 다나와와 다르게 만든다. 수집기는 수집 대상마다 파서를 따로 둔다.
"""

from collections.abc import Callable
from datetime import UTC, datetime
from html import escape

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse

from mock_shop.catalog import PRODUCTS, PRODUCTS_BY_ID
from mock_shop.pricing import KST, Offer, offers_at

PAGE_SIZE = 5
ROBOTS_TXT = "User-agent: *\nDisallow: /admin/\n"

STYLE = """
body { font-family: sans-serif; max-width: 720px; margin: 2rem auto; padding: 0 1rem; color: #222; }
a { color: #0369a1; }
table { border-collapse: collapse; width: 100%; }
th, td { border-bottom: 1px solid #ddd; padding: .5rem; text-align: left; }
.sold-out { color: #999; }
.product-list { list-style: none; padding: 0; }
.product-item { display: flex; justify-content: space-between; padding: .5rem 0;
  border-bottom: 1px solid #eee; }
"""


def utc_now() -> datetime:
    return datetime.now(UTC)


def won(value: int) -> str:
    return f"{value:,}원"


def create_app(now: Callable[[], datetime] = utc_now) -> FastAPI:
    app = FastAPI(title="연습마켓", docs_url=None, redoc_url=None, openapi_url=None)

    @app.get("/robots.txt", response_class=PlainTextResponse)
    def robots() -> str:
        return ROBOTS_TXT

    @app.get("/")
    def home() -> RedirectResponse:
        return RedirectResponse("/products")

    @app.get("/products", response_class=HTMLResponse)
    def product_list(page: int = Query(1, ge=1)) -> str:
        start = (page - 1) * PAGE_SIZE
        items = PRODUCTS[start : start + PAGE_SIZE]
        if not items:
            raise HTTPException(status_code=404, detail="없는 페이지")
        at = now()
        rows = []
        for product in items:
            lowest = min(o.price for o in offers_at(product, at) if o.in_stock)
            rows.append(
                f'<li class="product-item">'
                f'<a class="product-link" href="/products/{product.id}">{escape(product.name)}</a>'
                f'<span class="lowest-price">{won(lowest)}부터</span></li>'
            )
        nav = []
        if page > 1:
            nav.append(f'<a class="prev" href="/products?page={page - 1}">이전</a>')
        if start + PAGE_SIZE < len(PRODUCTS):
            nav.append(f'<a class="next" href="/products?page={page + 1}">다음</a>')
        body = (
            f'<ul class="product-list">{"".join(rows)}</ul>'
            f'<nav class="pagination">{" ".join(nav)}</nav>'
        )
        return _page("상품 목록", body, at)

    @app.get("/products/{product_id}", response_class=HTMLResponse)
    def product_detail(product_id: str) -> str:
        product = PRODUCTS_BY_ID.get(product_id)
        if product is None:
            raise HTTPException(status_code=404, detail="없는 상품")
        at = now()
        rows = "".join(_offer_row(o) for o in offers_at(product, at))
        body = (
            f'<p><a href="/products">상품 목록</a></p>'
            f'<h2 class="product-name" data-product-id="{product.id}">{escape(product.name)}</h2>'
            '<table class="offers"><thead><tr><th>판매처</th><th>가격</th><th>배송</th>'
            f"<th>재고</th></tr></thead><tbody>{rows}</tbody></table>"
        )
        return _page(product.name, body, at)

    return app


def _offer_row(offer: Offer) -> str:
    seller = offer.seller
    delivery = "무료배송" if seller.delivery_fee == 0 else f"배송비 {won(seller.delivery_fee)}"
    css = "offer" if offer.in_stock else "offer sold-out"
    stock = "구매 가능" if offer.in_stock else "품절"
    return (
        f'<tr class="{css}" data-seller="{seller.code}">'
        f'<td class="seller">{escape(seller.name)}</td>'
        f'<td class="price">{won(offer.price)}</td>'
        f'<td class="delivery">{delivery}</td>'
        f'<td class="stock">{stock}</td></tr>'
    )


def _page(title: str, body: str, at: datetime) -> str:
    # 가격이 바뀌는 단위(1시간)로 기준 시각을 보여준다
    hour = at.astimezone(KST).strftime("%Y-%m-%d %H:00")
    return (
        '<!doctype html><html lang="ko"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{escape(title)} | 연습마켓</title><style>{STYLE}</style></head><body>"
        '<header><h1><a href="/products">연습마켓</a></h1>'
        "<p>FlowDeck 데모용 연습 쇼핑몰. 상품과 가격은 지어낸 값이다.</p></header>"
        f'<main>{body}</main><footer><p class="price-time">가격 기준: {hour} (한국 시간)</p>'
        "</footer></body></html>"
    )


app = create_app()
