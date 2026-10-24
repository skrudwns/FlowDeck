"""연습 쇼핑몰 수집. 구조와 이유는 docs/adr/0010-mock-shop.md."""

from flowdeck.mockshop.client import MockShopClient
from flowdeck.mockshop.parser import parse_product_list, parse_product_page
from flowdeck.sources import ListedProduct, ParseError, Source

SOURCE = "mockshop"
# 목록 페이지 링크가 잘못돼 끝없이 도는 일을 막는다. 지금 목록은 2쪽
MAX_LIST_PAGES = 50


def discover_products(client: MockShopClient) -> list[ListedProduct]:
    """목록 페이지를 다음 페이지가 없을 때까지 돈다."""
    found: list[ListedProduct] = []
    for page in range(1, MAX_LIST_PAGES + 1):
        response = client.fetch_list(page)
        if response.status_code != 200:
            raise ParseError(f"상품 목록 {page}쪽: HTTP {response.status_code}")
        listing = parse_product_list(response.text)
        found.extend(p for p in listing.products if p not in found)
        if not listing.has_next:
            return found
    raise ParseError(f"상품 목록이 {MAX_LIST_PAGES}쪽을 넘음")


def mockshop_source(client: MockShopClient) -> Source:
    return Source(
        name=SOURCE,
        fetch_product=client.fetch_product,
        parse=parse_product_page,
        discover=lambda: discover_products(client),
    )
