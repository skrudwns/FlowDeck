from datetime import UTC, datetime, timedelta

import pytest

from flowdeck.models import CollectionRun, PriceSnapshot, Product, SellerPrice

T0 = datetime(2026, 11, 1, 0, 17, tzinfo=UTC)


@pytest.fixture
def hourly(session_factory):
    """상품 하나를 20시간 매시 수집.

    - 0~16시: 가나몰 10,000 / 다라마켓 10,200 / 바사몰 10,400, 현금가 마바샵 9,000
    - 17~19시: 가나몰 9,000으로 내림. 최저가 10,000 → 9,000
    - 19시 수집은 판매처 목록 없이 최저가만 (다나와 새 페이지 실패 같은 경우)
    - 20시 수집은 실패
    """
    with session_factory() as session:
        product = Product(source="danawa", source_product_id="333", name="상품 C")
        run = CollectionRun(source="danawa", started_at=T0, status="success", trigger="schedule")
        session.add_all([product, run])
        for hour in range(20):
            first = 9000 if hour >= 17 else 10000
            sellers = []
            if hour < 19:
                sellers = [
                    SellerPrice(rank=1, seller_name="가나몰", seller_code="A1", price=first),
                    SellerPrice(rank=2, seller_name="다라마켓", seller_code="B2", price=10200),
                    SellerPrice(rank=3, seller_name="바사몰", seller_code="C3", price=10400),
                    SellerPrice(
                        rank=4,
                        seller_name="마바샵",
                        seller_code="D4",
                        price=9000,
                        price_label="현금",
                    ),
                ]
            session.add(
                PriceSnapshot(
                    run=run,
                    product=product,
                    collected_at=T0 + timedelta(hours=hour),
                    status="ok",
                    lowest_price=first,
                    offer_count=3,
                    sellers=sellers,
                )
            )
        session.add(
            PriceSnapshot(
                run=run,
                product=product,
                collected_at=T0 + timedelta(hours=20),
                status="http_error",
            )
        )
        session.commit()
        return product.id


def test_reports_lowest_price_change(api, hourly):
    body = api.get(f"/products/{hourly}/signals").json()

    assert body["rules"] == {
        "change_min_pct": 5.0,
        "change_persist": 2,
        "cheaper_min_pct": 5.0,
        "usual_days": 7,
    }
    [change] = body["changes"]
    assert change["at"].startswith("2026-11-01T17:17")
    assert (change["before"], change["after"]) == (10000, 9000)
    assert change["pct"] == pytest.approx(-10)


def test_seller_positions_use_latest_snapshot_with_sellers(api, hourly):
    body = api.get(f"/products/{hourly}/signals").json()

    assert body["sellers_collected_at"].startswith("2026-11-01T18:17")
    by_name = {s["seller_name"]: s for s in body["sellers"]}
    first = by_name["가나몰"]
    assert first["price"] == 9000
    assert first["vs_others_pct"] == pytest.approx((9000 / 10300 - 1) * 100)
    assert first["cheaper_than_others"]
    # 18시 전 7일의 가격 18개: 10,000 17개, 9,000 1개
    assert first["usual_points"] == 18
    assert first["usual_price"] == 10000
    assert first["cheaper_than_usual"]

    middle = by_name["다라마켓"]
    assert not middle["cheaper_than_others"]
    assert middle["vs_usual_pct"] == pytest.approx(0)

    cash = by_name["마바샵"]
    assert cash["price_label"] == "현금"
    assert cash["vs_others_pct"] is None
    assert not cash["cheaper_than_others"]


def test_days_limits_change_window(api, hourly):
    # 마지막 정상 수집(19시) 기준 1일이면 0시부터라 그대로 잡히고, 범위 밖 값은 거부
    assert len(api.get(f"/products/{hourly}/signals", params={"days": 1}).json()["changes"]) == 1
    assert api.get(f"/products/{hourly}/signals", params={"days": 31}).status_code == 422


def test_product_without_data_has_empty_signals(api, session_factory):
    with session_factory() as session:
        product = Product(source="danawa", source_product_id="444")
        session.add(product)
        session.commit()
        product_id = product.id

    body = api.get(f"/products/{product_id}/signals").json()

    assert body["changes"] == []
    assert body["sellers"] == []
    assert body["sellers_snapshot_id"] is None


def test_signals_for_unknown_product_is_404(api, hourly):
    assert api.get("/products/99999/signals").status_code == 404
