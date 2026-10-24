from pathlib import Path

import httpx
import pytest

from flowdeck.mockshop import discover_products
from flowdeck.mockshop.client import MockShopClient
from flowdeck.mockshop.parser import parse_product_list, parse_product_page
from flowdeck.sources import ListedProduct, ParseError, SellerOffer

# mock-shop이 만든 HTML (uv run mock-shop fixtures). 2026-10-25 14:00 한국 시간 기준
FIXTURES = Path(__file__).parent / "fixtures"
LIST_1 = (FIXTURES / "mockshop_list_1.html").read_text(encoding="utf-8")
LIST_2 = (FIXTURES / "mockshop_list_2.html").read_text(encoding="utf-8")
PRODUCT = (FIXTURES / "mockshop_product.html").read_text(encoding="utf-8")
ROBOTS = "User-agent: *\nDisallow: /admin/\n"


def test_reads_products_and_next_link_from_list():
    first = parse_product_list(LIST_1)
    second = parse_product_list(LIST_2)

    assert [p.product_id for p in first.products] == ["p01", "p02", "p03", "p04", "p05"]
    assert first.products[0] == ListedProduct(product_id="p01", name="무선 이어폰 A100")
    assert first.has_next
    assert [p.product_id for p in second.products] == ["p06", "p07", "p08"]
    assert not second.has_next


def test_empty_list_is_a_parse_error():
    with pytest.raises(ParseError):
        parse_product_list("<html><ul class='product-list'></ul></html>")


def test_reads_offers_including_sold_out():
    page = parse_product_page(PRODUCT)

    assert (page.product_id, page.name) == ("p06", "보조배터리 20000mAh")
    assert page.sellers == (
        SellerOffer(1, "아자쇼핑", "S04", 43300, 0, in_stock=True),
        SellerOffer(2, "다라마켓", "S02", 43500, 3000, in_stock=True),
        SellerOffer(3, "가나몰", "S01", 44700, 0, in_stock=True),
        SellerOffer(4, "바사스토어", "S03", 42000, 2500, in_stock=False),
    )


def test_lowest_price_and_offer_count_skip_sold_out():
    page = parse_product_page(PRODUCT)

    # 품절인 바사스토어(42,000원)가 더 싸지만 최저가는 재고 있는 판매처 기준
    assert page.lowest_price == 43300
    assert page.offer_count == 3


def test_page_without_offers_is_a_parse_error():
    with pytest.raises(ParseError):
        parse_product_page('<h2 class="product-name">상품</h2>')


def make_client(handler):
    http = httpx.Client(transport=httpx.MockTransport(handler))
    return MockShopClient(http=http, delay_seconds=0, sleep=lambda _: None)


def shop(list_status=200):
    requested: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(f"{request.url.path}?{request.url.query.decode()}".rstrip("?"))
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text=ROBOTS)
        if request.url.path == "/products":
            page = request.url.params["page"]
            return httpx.Response(list_status, text=LIST_1 if page == "1" else LIST_2)
        return httpx.Response(200, text=PRODUCT)

    return handler, requested


def test_discover_walks_list_pages_until_no_next_link():
    handler, requested = shop()

    found = discover_products(make_client(handler))

    assert [p.product_id for p in found] == ["p01", "p02", "p03", "p04", "p05", "p06", "p07", "p08"]
    assert requested == ["/robots.txt", "/products?page=1", "/products?page=2"]


def test_discover_fails_on_error_status():
    handler, _ = shop(list_status=500)

    with pytest.raises(ParseError, match="HTTP 500"):
        discover_products(make_client(handler))
