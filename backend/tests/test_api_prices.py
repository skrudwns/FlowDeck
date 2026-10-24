def test_lists_prices_in_time_order(api, seeded):
    body = api.get(f"/products/{seeded['a']}/prices").json()

    assert [p["lowest_price"] for p in body] == [50000, 48000]
    assert body[0]["collected_at"] < body[1]["collected_at"]


def test_failed_collections_appear_without_price(api, seeded):
    body = api.get(f"/products/{seeded['b']}/prices").json()

    assert [(p["status"], p["lowest_price"]) for p in body] == [
        ("ok", 30000),
        ("http_error", None),
    ]


def test_limit_keeps_most_recent(api, seeded):
    body = api.get(f"/products/{seeded['a']}/prices", params={"limit": 1}).json()

    assert [p["lowest_price"] for p in body] == [48000]


def test_filters_by_time_range(api, seeded):
    params = {"since": "2026-10-24T08:00:00Z", "until": "2026-10-24T09:00:00Z"}

    body = api.get(f"/products/{seeded['a']}/prices", params=params).json()

    assert [p["lowest_price"] for p in body] == [50000]


def test_prices_for_unknown_product_is_404(api, seeded):
    assert api.get("/products/99999/prices").status_code == 404


def test_lists_sellers_of_a_snapshot(api, seeded):
    body = api.get(f"/snapshots/{seeded['latest_a']}/sellers").json()

    assert body == [
        {
            "rank": 1,
            "seller_name": "가나몰",
            "seller_code": "AAA01",
            "price": 48000,
            "delivery_fee": 0,
            "in_stock": True,
        },
        {
            "rank": 2,
            "seller_name": "다라스토어",
            "seller_code": None,
            "price": 49000,
            "delivery_fee": 3000,
            "in_stock": False,
        },
    ]


def test_snapshot_without_sellers_returns_empty_list(api, seeded):
    assert api.get(f"/snapshots/{seeded['failed_b']}/sellers").json() == []


def test_sellers_for_unknown_snapshot_is_404(api, seeded):
    assert api.get("/snapshots/99999/sellers").status_code == 404
