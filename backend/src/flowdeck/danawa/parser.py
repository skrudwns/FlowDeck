"""다나와 상품 페이지(prod.danawa.com/info/?pcode=...) HTML 파싱.

- 최저가, 판매처 수: schema.org JSON-LD에서 읽는다. 검색엔진용 데이터라 화면 개편에 덜 흔들린다.
- 상위 판매처(관찰한 최대 10곳): 화면 HTML(ul.list__mall-price)에서 읽는다. 목록에는 "현금" 같은
  배지가 붙은 가격이 섞여 있고 가격순이 아니어서 배지를 같이 남긴다. 더 쉽게 깨질 수 있어서,
  이 부분이 실패해도 최저가는 살리고 실패 이유만 남긴다.
- 2026-11-03부터 다나와가 Next.js로 바꾼 페이지를 옛 페이지와 섞어 내보낸다 (#46, TS-0005).
  새 페이지에는 판매처 HTML 목록이 없고, 페이지 데이터(self.__next_f)의 priceCompareTab에
  섹션별(오픈마켓, 종합몰, 전문몰 등) 판매처가 들어 있다. 옛 목록과 같은 기준으로 골라 낸다.
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
        if tree.css_first("ul.list__mall-price") is None and "self.__next_f" in html:
            sellers = _parse_next_sellers(html)
        else:
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
                delivery_fee=_delivery_fee(item.css_first(".box__delivery")),
                price_label=_text(item.css_first('.box__price [class^="badge__"]')),
            )
        )
    return tuple(sellers)


# 옛 페이지의 상위 판매처 목록을 새 페이지 섹션과 맞춰 본 결과 (TS-0005).
# 오픈마켓·종합몰은 쇼핑몰별 최저가 4곳씩, 나머지 섹션은 1곳씩이었다
_NEXT_SECTION_LIMIT = {"openMarket": 4, "affiliate": 4}
_NEXT_PUSH = re.compile(r"self\.__next_f\.push\((\[.*?\])\)</script>", re.S)


def _parse_next_sellers(html: str) -> tuple[SellerOffer, ...]:
    sections = _next_price_compare_sections(html)

    def order(item: dict) -> tuple[int, int, str]:
        return item["rawPrice"], item.get("deliveryPrice") or 0, str(item.get("companyCode"))

    picked = []
    for section in sections:
        per_shop: dict[str, dict] = {}
        for item in section.get("items") or []:
            if not isinstance(item.get("rawPrice"), int) or not item.get("shop"):
                raise ParseError(f"{section.get('sectionType')} 판매처의 이름이나 가격을 읽지 못함")
            code = str(item.get("companyCode"))
            if code not in per_shop or order(item) < order(per_shop[code]):
                per_shop[code] = item
        limit = _NEXT_SECTION_LIMIT.get(section.get("sectionType"), 1)
        picked += sorted(per_shop.values(), key=order)[:limit]
    if not picked:
        raise ParseError("priceCompareTab에 판매처가 없음")

    # 옛 목록처럼 가격순으로 세우고 현금가는 뒤에 둔다
    picked = sorted((i for i in picked if not i.get("isCash")), key=order) + sorted(
        (i for i in picked if i.get("isCash")), key=order
    )
    sellers = []
    for rank, item in enumerate(picked, start=1):
        if item.get("isCash"):
            label = "현금"
        elif rank == 1 and item.get("isLowest"):
            label = "최저가"
        else:
            label = None
        sellers.append(
            SellerOffer(
                rank=rank,
                name=item["shop"],
                code=item.get("companyCode"),
                price=item["rawPrice"],
                delivery_fee=item.get("deliveryPrice"),
                price_label=label,
            )
        )
    return tuple(sellers)


def _next_price_compare_sections(html: str) -> list[dict]:
    """self.__next_f.push로 나뉘어 들어온 문자열을 이어 붙이고,
    React Query dehydrated state 중 priceCompareTab 질의의 data.sections를 꺼낸다."""
    payload = ""
    for chunk in _NEXT_PUSH.findall(html):
        try:
            parts = json.loads(chunk)
        except json.JSONDecodeError:
            continue
        if len(parts) > 1 and isinstance(parts[1], str):
            payload += parts[1]

    at = payload.find('"queryKey":["productInfo","priceCompareTab"')
    start = payload.rfind('{"dehydratedAt"', 0, at) if at >= 0 else -1
    if start < 0:
        raise ParseError("판매처 목록(priceCompareTab)을 찾지 못함")
    try:
        query, _ = json.JSONDecoder().raw_decode(payload, start)
        sections = query["state"]["data"]["sections"]
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        raise ParseError(f"priceCompareTab을 읽지 못함: {e}") from e
    if not isinstance(sections, list):
        raise ParseError("priceCompareTab에 sections가 없음")
    return sections


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


def _delivery_fee(node: LexborNode | None) -> int | None:
    if node is None:
        return None
    # 빠른배송 판매처는 배송비 칸 안에 안내 레이어("낮 3시 이전 주문 시…")가 있다.
    # 그 숫자까지 이어 붙이면 3,000원이 33,000원이 된다 (#33)
    for notice in node.css(".box__fast-notice"):
        notice.decompose()
    text = node.text(strip=True)
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
