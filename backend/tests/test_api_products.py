def test_lists_products_with_latest_result(api, seeded):
    body = api.get("/products").json()

    assert [p["source_product_id"] for p in body] == ["111", "222"]
    a, b = body
    assert a["latest"]["lowest_price"] == 48000
    assert a["latest"]["snapshot_id"] == seeded["latest_a"]
    # 가장 최근 결과가 실패면 가격 없이 상태만 보인다
    assert b["latest"]["status"] == "http_error"
    assert b["latest"]["lowest_price"] is None


def test_filters_by_active(api, seeded):
    body = api.get("/products", params={"active": "false"}).json()

    assert [p["source_product_id"] for p in body] == ["222"]


def test_paginates(api, seeded):
    body = api.get("/products", params={"limit": 1, "offset": 1}).json()

    assert [p["source_product_id"] for p in body] == ["222"]


def test_rejects_limit_over_maximum(api, seeded):
    assert api.get("/products", params={"limit": 501}).status_code == 422


def test_product_without_snapshots_has_no_latest(api, session_factory):
    from flowdeck.models import Product

    with session_factory() as session:
        session.add(Product(source="danawa", source_product_id="999", active=True))
        session.commit()

    assert api.get("/products").json()[0]["latest"] is None


def test_gets_one_product(api, seeded):
    body = api.get(f"/products/{seeded['a']}").json()

    assert body["name"] == "상품 A"
    assert body["latest"]["offer_count"] == 11


def test_returns_404_for_unknown_product(api, seeded):
    assert api.get("/products/99999").status_code == 404


def test_times_are_returned_with_utc_offset(api, seeded):
    collected_at = api.get(f"/products/{seeded['a']}").json()["latest"]["collected_at"]

    assert collected_at.startswith("2026-10-24T09:17:00")
    assert collected_at.endswith(("Z", "+00:00"))
