from pathlib import Path

import pytest

from flowdeck.danawa.parser import parse_product_page
from flowdeck.sources import ParseError, SellerOffer

FIXTURE = (Path(__file__).parent / "fixtures" / "danawa_product.html").read_text(encoding="utf-8")


def test_reads_lowest_price_and_offer_count_from_json_ld():
    page = parse_product_page(FIXTURE)

    assert page.product_id == "1000001"
    assert page.name == "테스트 상품 A"
    assert page.lowest_price == 50000
    assert page.offer_count == 12


def test_reads_seller_list():
    page = parse_product_page(FIXTURE)

    assert page.seller_error is None
    assert page.sellers == (
        SellerOffer(rank=1, name="가나몰", code="AAA01", price=50000, delivery_fee=0),
        SellerOffer(rank=2, name="다라스토어", code="BBB02", price=51200, delivery_fee=3000),
    )


def test_keeps_lowest_price_when_seller_list_is_missing():
    html = FIXTURE.replace("list__mall-price", "list__renamed-by-redesign")

    page = parse_product_page(html)

    assert page.lowest_price == 50000
    assert page.sellers == ()
    assert "list__mall-price" in page.seller_error


def test_reports_seller_item_it_cannot_read():
    html = FIXTURE.replace('<span class="text__num">51,200</span>', "")

    page = parse_product_page(html)

    assert page.sellers == ()
    assert "2번째" in page.seller_error


def test_fails_without_product_json_ld():
    html = FIXTURE.replace('"@type": "Product"', '"@type": "Thing"')

    with pytest.raises(ParseError, match="JSON-LD"):
        parse_product_page(html)


def test_fails_without_lowest_price():
    html = FIXTURE.replace('"lowPrice": "50000",', "")

    with pytest.raises(ParseError, match="lowPrice"):
        parse_product_page(html)
