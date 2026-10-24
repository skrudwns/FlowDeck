"""다나와 상품 페이지(prod.danawa.com/info/?pcode=...) HTML 파싱.

- 최저가, 판매처 수: schema.org JSON-LD에서 읽는다. 검색엔진용 데이터라 화면 개편에 덜 흔들린다.
- 상위 판매처(관찰한 최대 10곳): 화면 HTML(ul.list__mall-price)에서 읽는다. 더 쉽게 깨질 수 있어서,
  이 부분이 실패해도 최저가는 살리고 실패 이유만 남긴다.
"""

import json
import re
from urllib.parse import parse_qs, urlparse

from selectolax.lexbor import LexborHTMLParser, LexborNode

from flowdeck.sources import ParseError, ProductPage, SellerOffer


def parse_product_page(html: str) -> ProductPage:
    tree = LexborHTMLParser(html)
    product = _find_product_json_ld(tree)

    offers = product.get("offers") or {}
    lowest_price = _to_int(offers.get("lowPrice"))
    if lowest_price is None:
        raise ParseError("JSON-LD에 offers.lowPrice가 없음")

    try:
        sellers = _parse_sellers(tree)
        seller_error = None
    except ParseError as e:
        sellers = ()
        seller_error = str(e)

    return ProductPage(
        product_id=str(product.get("sku", "")),
        name=str(product.get("name", "")),
        lowest_price=lowest_price,
        offer_count=_to_int(offers.get("offerCount")),
        sellers=sellers,
        seller_error=seller_error,
    )


def _find_product_json_ld(tree: LexborHTMLParser) -> dict:
    for script in tree.css('script[type="application/ld+json"]'):
        try:
            data = json.loads(script.text(), strict=False)
        except json.JSONDecodeError:
            continue
        for item in data if isinstance(data, list) else [data]:
            if isinstance(item, dict) and item.get("@type") == "Product":
                return item
    raise ParseError("Product 타입 JSON-LD를 찾지 못함")


def _parse_sellers(tree: LexborHTMLParser) -> tuple[SellerOffer, ...]:
    items = tree.css("ul.list__mall-price > li.list-item")
    if not items:
        raise ParseError("판매처 목록(ul.list__mall-price)을 찾지 못함")

    sellers = []
    for rank, item in enumerate(items, start=1):
        name = _seller_name(item)
        price = _to_int(_text(item.css_first(".sell-price .text__num")))
        if not name or price is None:
            raise ParseError(f"{rank}번째 판매처의 이름이나 가격을 읽지 못함")
        sellers.append(
            SellerOffer(
                rank=rank,
                name=name,
                code=_seller_code(item),
                price=price,
                delivery_fee=_delivery_fee(_text(item.css_first(".box__delivery"))),
            )
        )
    return tuple(sellers)


def _seller_name(item: LexborNode) -> str | None:
    # 로고가 있으면 이미지 alt, 없으면 텍스트 로고 (네이버페이 판매처 등)
    img = item.css_first(".box__logo img")
    if img is not None and img.attributes.get("alt"):
        return img.attributes["alt"].strip()
    return _text(item.css_first(".box__logo .text__logo"))


def _seller_code(item: LexborNode) -> str | None:
    link = item.css_first("a.link__full-cover")
    if link is None:
        return None
    values = parse_qs(urlparse(link.attributes.get("href") or "").query).get("cmpnyc")
    return values[0] if values else None


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


def _to_int(value: object) -> int | None:
    if value is None:
        return None
    digits = re.sub(r"[^\d]", "", str(value))
    return int(digits) if digits else None
