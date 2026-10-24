"""연습 쇼핑몰 HTML 파싱. 페이지 구조는 mock-shop/src/mock_shop/app.py.

- 목록: li.product-item 링크에서 상품 ID와 이름, a.next로 다음 페이지가 있는지.
- 상품: table.offers의 판매처 행. 품절 행도 읽어서 in_stock=False로 남긴다.
  최저가와 판매처 수는 재고 있는 판매처만으로 계산한다 (ADR-0010).
"""

import re
from dataclasses import dataclass

from selectolax.lexbor import LexborHTMLParser, LexborNode

from flowdeck.sources import ListedProduct, ParseError, ProductPage, SellerOffer


@dataclass(frozen=True)
class ListPage:
    products: tuple[ListedProduct, ...]
    has_next: bool


def parse_product_list(html: str) -> ListPage:
    tree = LexborHTMLParser(html)
    products = []
    for link in tree.css("li.product-item a.product-link"):
        href = link.attributes.get("href") or ""
        match = re.fullmatch(r"/products/([\w-]+)", href)
        name = link.text(strip=True)
        if not match or not name:
            raise ParseError(f"상품 링크를 읽지 못함: {href!r}")
        products.append(ListedProduct(product_id=match.group(1), name=name))
    if not products:
        # 빈 목록을 그대로 받아들이면 모든 상품이 비활성화된다
        raise ParseError("상품 목록(li.product-item)을 찾지 못함")
    return ListPage(products=tuple(products), has_next=tree.css_first("a.next") is not None)


def parse_product_page(html: str) -> ProductPage:
    tree = LexborHTMLParser(html)
    heading = tree.css_first("h2.product-name")
    if heading is None:
        raise ParseError("상품명(h2.product-name)을 찾지 못함")

    rows = tree.css("table.offers tbody tr.offer")
    if not rows:
        raise ParseError("판매처 목록(table.offers)을 찾지 못함")
    sellers = tuple(_offer(rank, row) for rank, row in enumerate(rows, start=1))

    in_stock = [s for s in sellers if s.in_stock]
    if not in_stock:
        raise ParseError("재고 있는 판매처가 없음")

    return ProductPage(
        product_id=heading.attributes.get("data-product-id") or "",
        name=heading.text(strip=True),
        lowest_price=min(s.price for s in in_stock),
        offer_count=len(in_stock),
        sellers=sellers,
        seller_error=None,
    )


def _offer(rank: int, row: LexborNode) -> SellerOffer:
    name = _text(row.css_first("td.seller"))
    price = _to_int(_text(row.css_first("td.price")))
    stock = _text(row.css_first("td.stock"))
    if not name or price is None or stock is None:
        raise ParseError(f"{rank}번째 판매처의 이름, 가격, 재고를 읽지 못함")
    return SellerOffer(
        rank=rank,
        name=name,
        code=row.attributes.get("data-seller"),
        price=price,
        delivery_fee=_delivery_fee(_text(row.css_first("td.delivery"))),
        in_stock=stock != "품절",
    )


def _delivery_fee(text: str | None) -> int | None:
    if not text:
        return None
    if "무료" in text:
        return 0
    return _to_int(text)


def _text(node: LexborNode | None) -> str | None:
    if node is None:
        return None
    return node.text(strip=True) or None


def _to_int(value: str | None) -> int | None:
    if value is None:
        return None
    digits = re.sub(r"[^\d]", "", value)
    return int(digits) if digits else None
