"""판매처와 상품. 이름과 기본가는 지어낸 값이다."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Seller:
    code: str
    name: str
    delivery_fee: int
    # 토·일에 10% 내리는 판매처
    weekend_sale: bool = False


@dataclass(frozen=True)
class Product:
    id: str
    name: str
    # 판매처 코드별 기본가
    base_prices: dict[str, int]
    # 품절되지 않는 판매처. 상품 전체가 품절되는 경우는 다루지 않는다 (ADR-0010)
    anchor: str


SELLERS: dict[str, Seller] = {
    s.code: s
    for s in (
        Seller("S01", "가나몰", delivery_fee=0),
        Seller("S02", "다라마켓", delivery_fee=3000),
        Seller("S03", "바사스토어", delivery_fee=2500, weekend_sale=True),
        Seller("S04", "아자쇼핑", delivery_fee=0),
    )
}

PRODUCTS: tuple[Product, ...] = (
    Product("p01", "무선 이어폰 A100", {"S01": 89000, "S02": 86500, "S03": 91000}, anchor="S01"),
    Product(
        "p02",
        "블루투스 스피커 B20",
        {"S01": 54000, "S02": 52900, "S03": 55500, "S04": 53800},
        anchor="S04",
    ),
    Product(
        "p03", "기계식 키보드 K87", {"S02": 129000, "S03": 132000, "S04": 127500}, anchor="S02"
    ),
    Product("p04", "무선 마우스 M5", {"S01": 32900, "S03": 34000, "S04": 31500}, anchor="S01"),
    Product("p05", "USB-C 충전기 65W", {"S01": 39000, "S02": 37900, "S04": 38500}, anchor="S04"),
    Product(
        "p06",
        "보조배터리 20000mAh",
        {"S01": 45000, "S02": 43500, "S03": 46900, "S04": 44200},
        anchor="S02",
    ),
    Product(
        "p07", "27인치 모니터 Q27", {"S02": 319000, "S03": 309000, "S04": 315000}, anchor="S03"
    ),
    Product("p08", "웹캠 FHD W1", {"S01": 59000, "S03": 61500, "S04": 57900}, anchor="S01"),
)

PRODUCTS_BY_ID: dict[str, Product] = {p.id: p for p in PRODUCTS}
