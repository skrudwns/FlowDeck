"""수집 대상(다나와, 연습 쇼핑몰)이 수집기에 넘기는 것.

수집기는 수집 대상마다 상품 페이지를 받는 방법(fetch_product)과 읽는 방법(parse)만 바꿔 끼운다.
"""

from collections.abc import Callable
from dataclasses import dataclass

from flowdeck.polite_http import Response


class ParseError(Exception):
    pass


@dataclass(frozen=True)
class SellerOffer:
    rank: int
    name: str
    code: str | None
    price: int
    delivery_fee: int | None
    in_stock: bool = True


@dataclass(frozen=True)
class ProductPage:
    product_id: str
    name: str
    # 재고 있는 판매처 기준
    lowest_price: int
    offer_count: int | None
    sellers: tuple[SellerOffer, ...]
    # 판매처 목록을 못 읽었을 때 이유. 읽었으면 None
    seller_error: str | None


@dataclass(frozen=True)
class ListedProduct:
    product_id: str
    name: str


@dataclass(frozen=True)
class Source:
    name: str
    fetch_product: Callable[[str], Response]
    parse: Callable[[str], ProductPage]
    # 사이트의 상품 목록을 돌며 수집할 상품을 찾는 대상(연습 쇼핑몰)만 둔다.
    # 없으면 DB에 등록된 상품을 수집한다 (다나와: 대상 목록 파일)
    discover: Callable[[], list[ListedProduct]] | None = None
