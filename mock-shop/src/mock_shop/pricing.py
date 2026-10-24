"""가격 규칙. 규칙과 확률을 정한 이유는 docs/adr/0010-mock-shop.md.

가격은 상품, 판매처, 한국 시간 기준 날짜와 시(hour)만으로 정해진다. 난수 대신 sha256 값을 써서
서버를 언제 다시 띄워도 같은 시각이면 같은 가격이 나온다.

적용한 규칙은 Offer.rules에 남긴다. 분석 노트에서 정답으로 쓴다. HTTP로는 내보내지 않는다.
"""

import hashlib
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from mock_shop.catalog import SELLERS, Product, Seller

KST = ZoneInfo("Asia/Seoul")

DAILY_SWING = 0.03
WEEKEND_DISCOUNT = 0.10
FLASH_PROBABILITY = 1 / 7
FLASH_HOURS = 3
FLASH_DISCOUNT = 0.25
SOLD_OUT_PROBABILITY = 1 / 10
SOLD_OUT_HOURS = 6


@dataclass(frozen=True)
class Offer:
    seller: Seller
    price: int
    in_stock: bool
    # 기본가와 일별 변동 말고 적용된 규칙: weekend_sale, flash_sale, sold_out
    rules: tuple[str, ...]


def _unit(*parts: str) -> float:
    """parts로 정해지는 [0, 1) 값."""
    digest = hashlib.sha256("|".join(parts).encode()).digest()
    return int.from_bytes(digest[:8]) / 2**64


def _window(key: tuple[str, ...], probability: float, hours: int, hour: int) -> bool:
    """그날 probability 확률로 hours시간짜리 구간이 생기고, hour가 그 안에 있으면 True.
    구간은 자정을 넘지 않는다."""
    if _unit(*key, "on") >= probability:
        return False
    start = int(_unit(*key, "start") * (24 - hours + 1))
    return start <= hour < start + hours


def offer_at(product: Product, seller: Seller, at: datetime) -> Offer:
    local = at.astimezone(KST)
    day = local.date().isoformat()
    key = (product.id, seller.code, day)
    rules = []

    price = product.base_prices[seller.code] * (1 + (_unit(*key, "daily") * 2 - 1) * DAILY_SWING)
    if seller.weekend_sale and local.weekday() >= 5:
        price *= 1 - WEEKEND_DISCOUNT
        rules.append("weekend_sale")
    if _window((*key, "flash"), FLASH_PROBABILITY, FLASH_HOURS, local.hour):
        price *= 1 - FLASH_DISCOUNT
        rules.append("flash_sale")

    in_stock = True
    if seller.code != product.anchor and _window(
        (*key, "sold_out"), SOLD_OUT_PROBABILITY, SOLD_OUT_HOURS, local.hour
    ):
        in_stock = False
        rules.append("sold_out")

    return Offer(seller=seller, price=int(round(price, -2)), in_stock=in_stock, rules=tuple(rules))


def offers_at(product: Product, at: datetime) -> list[Offer]:
    """페이지에 보이는 순서: 재고 있는 판매처를 가격순으로, 품절은 뒤에."""
    offers = [offer_at(product, SELLERS[code], at) for code in product.base_prices]
    return sorted(offers, key=lambda o: (not o.in_stock, o.price, o.seller.code))
