from datetime import UTC, datetime, timedelta

from mock_shop.catalog import PRODUCTS, SELLERS
from mock_shop.pricing import KST, offer_at, offers_at

# 2026-10-26(월) 0시 한국 시간부터 4주
START = datetime(2026, 10, 26, tzinfo=KST)
HOURS = [START + timedelta(hours=h) for h in range(24 * 28)]


def all_offers():
    for product in PRODUCTS:
        for code in product.base_prices:
            for at in HOURS:
                yield product, SELLERS[code], at, offer_at(product, SELLERS[code], at)


def test_same_time_gives_same_price():
    product = PRODUCTS[0]
    at = datetime(2026, 10, 25, 5, 30, tzinfo=UTC)
    assert offers_at(product, at) == offers_at(product, at)


def test_price_changes_only_on_the_hour():
    product, seller = PRODUCTS[0], SELLERS["S01"]
    at = datetime(2026, 10, 25, 5, 0, tzinfo=UTC)
    assert offer_at(product, seller, at) == offer_at(product, seller, at + timedelta(minutes=59))


def test_prices_are_rounded_to_100_won():
    assert all(o.price % 100 == 0 for *_, o in all_offers())


def test_price_without_rules_stays_within_daily_swing():
    for product, seller, _, offer in all_offers():
        if {"weekend_sale", "flash_sale"} & set(offer.rules):
            continue
        base = product.base_prices[seller.code]
        assert base * 0.97 - 50 <= offer.price <= base * 1.03 + 50


def test_weekend_sale_only_on_weekends_for_that_seller():
    for _, seller, at, offer in all_offers():
        expected = seller.weekend_sale and at.weekday() >= 5
        assert ("weekend_sale" in offer.rules) == expected


def test_anchor_seller_is_never_sold_out():
    for product, seller, _, offer in all_offers():
        if seller.code == product.anchor:
            assert offer.in_stock


def test_every_pattern_shows_up_within_four_weeks():
    rules = [r for *_, o in all_offers() for r in o.rules]
    assert {"weekend_sale", "flash_sale", "sold_out"} <= set(rules)


def test_flash_sale_lasts_three_hours_within_a_day():
    product, seller = PRODUCTS[0], SELLERS["S01"]
    for day in range(28):
        hours = [
            h
            for h in range(24)
            if "flash_sale" in offer_at(product, seller, START + timedelta(days=day, hours=h)).rules
        ]
        assert hours == [] or (len(hours) == 3 and hours == list(range(hours[0], hours[0] + 3)))


def test_offers_are_sorted_in_stock_first_by_price():
    for product in PRODUCTS:
        for at in HOURS[:48]:
            offers = offers_at(product, at)
            in_stock = [o.price for o in offers if o.in_stock]
            assert in_stock == sorted(in_stock)
            stock_flags = [o.in_stock for o in offers]
            assert stock_flags == sorted(stock_flags, reverse=True)
