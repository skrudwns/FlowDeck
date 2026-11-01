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


# 2026-11-01 pcode 77319515 페이지의 구조를 본뜬 판매처 항목 (#33)
FAST_SHIPPING_ITEM = """
  <li class="list-item">
    <div class="box__logo"><img src="//img.example/CCC_logo.gif" class="image" alt="마바몰"></div>
    <div class="box__price ">
      <div class="sell-price">
        <span class="text__num">52,000</span><span class="text__unit">원</span>
      </div>
    </div>
    <div class="box__delivery">
      <div class="box__fast-notice">
        <span class="icon__fast-shipping"><em class="blind">빠른배송</em></span>
        <div class="layer-prod-pdb1"><div class="box__inner box__inner--top">
          <div class="box__contents">
          낮 3시 이전 주문 시 당일 발송하는 <strong>빠른 배송</strong> 상품입니다.
        </div></div></div>
      </div>
      3,000원
    </div>
    <a class="link__full-cover"
       href="https://prod.danawa.com/bridge/loadingBridge.html?pcode=1000001&cmpnyc=CCC03&r=3"></a>
  </li>
"""

CASH_ITEM = """
  <li class="list-item">
    <div class="box__logo">
      <span class="text__logo" role="img" aria-label="사아몰">사아몰</span>
    </div>
    <div class="box__price ">
      <span class="badge__cash">현금</span>
      <div class="sell-price">
        <span class="text__num">45,000</span><span class="text__unit">원</span>
      </div>
    </div>
    <div class="box__delivery"> 무료배송 </div>
    <a class="link__full-cover"
       href="https://prod.danawa.com/bridge/loadingBridge.html?pcode=1000001&cmpnyc=DDD04&r=4"></a>
  </li>
"""


def with_items(*items):
    return FIXTURE.replace("</ul>", "".join(items) + "</ul>")


def test_delivery_fee_ignores_fast_shipping_notice():
    page = parse_product_page(with_items(FAST_SHIPPING_ITEM))

    # 안내 문구의 "3시"가 붙어 33,000원으로 읽히면 안 된다
    assert page.sellers[2].delivery_fee == 3000


def test_reads_price_label_badge():
    page = parse_product_page(with_items(FAST_SHIPPING_ITEM, CASH_ITEM))

    assert [(s.name, s.price, s.price_label) for s in page.sellers] == [
        ("가나몰", 50000, "최저가"),
        ("다라스토어", 51200, None),
        ("마바몰", 52000, None),
        ("사아몰", 45000, "현금"),
    ]
