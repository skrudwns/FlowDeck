from datetime import UTC, datetime, timedelta

import pytest

from flowdeck.signals import (
    SellerOffer,
    price_changes,
    seller_key,
    seller_positions,
)

T0 = datetime(2026, 11, 2, 0, 0, tzinfo=UTC)


def hourly(*prices: int) -> list[tuple[datetime, int]]:
    return [(T0 + timedelta(hours=i), p) for i, p in enumerate(prices)]


def test_drop_that_lasts_two_collections_is_a_change():
    changes = price_changes(hourly(10000, 10000, 10000, 9000, 9000, 9000))

    assert len(changes) == 1
    change = changes[0]
    assert change.at == T0 + timedelta(hours=3)
    assert (change.before, change.after) == (10000, 9000)
    assert change.pct == pytest.approx(-10)


def test_one_hour_spike_is_ignored():
    assert price_changes(hourly(10000, 10000, 9000, 10000, 10000)) == []


def test_small_moves_are_ignored():
    # 10원 단위 경쟁과 3% 안쪽 변동
    assert price_changes(hourly(10000, 9990, 10010, 9700, 9700, 10200)) == []


def test_drop_and_recovery_are_two_changes():
    changes = price_changes(hourly(10000, 10000, 7500, 7500, 7500, 10000, 10000))

    assert [(c.before, c.after) for c in changes] == [(10000, 7500), (7500, 10000)]


def test_change_needs_enough_points():
    assert price_changes(hourly(10000)) == []
    assert price_changes([]) == []


def offer(name: str, price: int, in_stock: bool = True, cash: bool = False) -> SellerOffer:
    return SellerOffer(key=seller_key(None, name, cash), price=price, in_stock=in_stock, cash=cash)


def test_position_against_other_sellers():
    current = [offer("가", 9000), offer("나", 10000), offer("다", 10400)]

    positions = seller_positions(current, {})

    first = positions[seller_key(None, "가", False)]
    assert first.others_count == 2
    assert first.vs_others_pct == pytest.approx((9000 / 10200 - 1) * 100)
    assert first.cheaper_than_others
    assert not positions[seller_key(None, "나", False)].cheaper_than_others


def test_sold_out_and_cash_prices_are_not_compared():
    current = [
        offer("가", 10000),
        offer("나", 10000),
        offer("다", 5000, in_stock=False),
        offer("라", 8000, cash=True),
        offer("마", 10000),
    ]

    positions = seller_positions(current, {})

    assert positions[seller_key(None, "다", False)] is None
    assert positions[seller_key(None, "가", False)].vs_others_pct == pytest.approx(0)
    # 현금가는 카드가와 기준이 달라 다른 판매처 비교를 내지 않는다
    cash = positions[seller_key(None, "라", True)]
    assert cash.vs_others_pct is None
    assert not cash.cheaper_than_others


def test_no_position_against_others_with_too_few_sellers():
    positions = seller_positions([offer("가", 9000), offer("나", 10000)], {})

    first = positions[seller_key(None, "가", False)]
    assert first.vs_others_pct is None
    assert not first.cheaper_than_others


def test_position_against_usual_price():
    key = seller_key(None, "가", False)
    history = {key: [10000] * 10 + [9000] * 4}

    current = [offer("가", 9000), offer("나", 9000), offer("다", 9000)]

    position = seller_positions(current, history)[key]

    assert position.usual_price == 10000
    assert position.usual_points == 14
    assert position.vs_usual_pct == pytest.approx(-10)
    assert position.cheaper_than_usual


def test_no_usual_price_with_short_history():
    key = seller_key(None, "가", False)

    position = seller_positions([offer("가", 9000)], {key: [10000] * 11})[key]

    assert position.usual_price is None
    assert position.vs_usual_pct is None
    assert not position.cheaper_than_usual


def test_seller_key_prefers_code():
    assert seller_key("TH201", "11번가", False) == seller_key("TH201", "11번가(다른 표기)", False)
    assert seller_key("TH201", "11번가", False) != seller_key("TH201", "11번가", True)
