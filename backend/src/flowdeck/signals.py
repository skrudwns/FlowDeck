"""가격 분석 신호: 최저가 변화와 판매처별 가격 위치. DB를 모르는 순수 함수만 둔다.

기준값의 근거:
- 최저가 변화: AN-0002. 직전 수준 대비 5% 이상 바뀐 값이 2번 이상(매시 수집이면 2시간)
  이어지면 변화로 본다.
- 판매처 가격 위치: AN-0003, AN-0004. 다른 판매처 가격과 비교한 위치를 주 기준으로, 그 판매처의
  평소 가격과 비교한 값을 보조로 쓴다. 가격만으로는 할인을 절반 정도만 잡으므로 "할인 아님"을
  판정하지 않고, 싸다는 신호만 낸다.

구조와 이유는 docs/adr/0014-price-signals-on-request.md.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from statistics import median

CHANGE_MIN_PCT = 5.0
CHANGE_PERSIST = 2
CHEAPER_MIN_PCT = 5.0
# 다른 판매처 비교는 자기를 뺀 재고 있는 판매처가 이만큼은 있어야 낸다
MIN_OTHERS = 2
USUAL_WINDOW = timedelta(days=7)
# 매시 수집 기준 반나절. 이보다 적으면 평소 가격을 내지 않는다
USUAL_MIN_POINTS = 12
# 다나와 현금가 배지 (#33)
CASH_LABEL = "현금"


@dataclass(frozen=True)
class PriceChange:
    """최저가 수준이 바뀐 시점."""

    at: datetime
    # 직전 수준(마지막 변화 이후 값들의 중앙값)과 새 수준의 첫 값
    before: int
    after: int
    pct: float


def price_changes(
    points: list[tuple[datetime, int]],
    min_pct: float = CHANGE_MIN_PCT,
    persist: int = CHANGE_PERSIST,
) -> list[PriceChange]:
    """시간순 (시각, 가격)에서 수준 변화를 찾는다. analysis/cpd.py의 step_rule과 같은 규칙이다.

    한 번만 튀었다 돌아온 값이나 min_pct 미만의 10원 단위 경쟁은 변화로 보지 않는다.
    """
    values = [price for _, price in points]
    changes: list[PriceChange] = []
    start = 0
    t = 1
    while t + persist <= len(values):
        level = median(values[start:t])
        new = values[t : t + persist]
        threshold = abs(level) * min_pct / 100
        same_side = all(v > level for v in new) or all(v < level for v in new)
        if same_side and all(abs(v - level) >= threshold for v in new):
            changes.append(
                PriceChange(
                    at=points[t][0],
                    before=round(level),
                    after=values[t],
                    pct=(values[t] / level - 1) * 100,
                )
            )
            start = t
            t += persist
        else:
            t += 1
    return changes


@dataclass(frozen=True)
class SellerOffer:
    """한 수집에서 판매처 하나의 가격."""

    key: str
    price: int
    in_stock: bool
    # 다나와 현금가. 카드가와 기준이 달라서 다른 판매처 비교에서 뺀다 (#33, AN-0005)
    cash: bool = False


@dataclass(frozen=True)
class SellerPosition:
    # 다른 판매처(재고 있음, 현금가 제외) 가격 중앙값 대비 %.
    # 비교할 판매처가 모자라거나 현금가면 None
    vs_others_pct: float | None
    others_count: int
    # 이 판매처 지난 가격의 중앙값과 그 대비 %. 기록이 모자라면 None
    usual_price: int | None
    vs_usual_pct: float | None
    usual_points: int

    @property
    def cheaper_than_others(self) -> bool:
        return self.vs_others_pct is not None and self.vs_others_pct <= -CHEAPER_MIN_PCT

    @property
    def cheaper_than_usual(self) -> bool:
        return self.vs_usual_pct is not None and self.vs_usual_pct <= -CHEAPER_MIN_PCT


def seller_key(code: str | None, name: str, cash: bool) -> str:
    """같은 판매처를 수집마다 이어 보기 위한 키. 코드가 있으면 코드, 없으면 이름.
    현금가는 같은 쇼핑몰이라도 따로 본다."""
    return f"{code or name}|{'cash' if cash else 'card'}"


def seller_positions(
    current: list[SellerOffer], history: dict[str, list[int]]
) -> dict[str, SellerPosition | None]:
    """판매처마다 가격 위치. 품절 판매처는 None.

    history는 키별로 이번 수집 이전의 재고 있는 가격들이다 (USUAL_WINDOW 안).
    """
    pool = [o for o in current if o.in_stock and not o.cash]
    result: dict[str, SellerPosition | None] = {}
    for offer in current:
        if not offer.in_stock:
            result[offer.key] = None
            continue
        others = [o.price for o in pool if o.key != offer.key]
        enough = len(others) >= MIN_OTHERS and not offer.cash
        vs_others = (offer.price / median(others) - 1) * 100 if enough else None
        past = history.get(offer.key, [])
        usual = median(past) if len(past) >= USUAL_MIN_POINTS else None
        result[offer.key] = SellerPosition(
            vs_others_pct=vs_others,
            others_count=len(others),
            usual_price=round(usual) if usual is not None else None,
            vs_usual_pct=(offer.price / usual - 1) * 100 if usual is not None else None,
            usual_points=len(past),
        )
    return result
