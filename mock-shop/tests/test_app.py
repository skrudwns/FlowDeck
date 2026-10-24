from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from mock_shop.app import create_app
from mock_shop.catalog import PRODUCTS

AT = datetime(2026, 10, 25, 5, 0, tzinfo=UTC)


@pytest.fixture
def client():
    with TestClient(create_app(now=lambda: AT)) as c:
        yield c


def test_robots_txt_blocks_only_admin(client):
    response = client.get("/robots.txt")
    assert response.status_code == 200
    assert response.text == "User-agent: *\nDisallow: /admin/\n"


def test_product_list_is_paginated(client):
    first = client.get("/products").text
    second = client.get("/products?page=2").text

    assert first.count('class="product-item"') == 5
    assert 'href="/products?page=2"' in first
    assert second.count('class="product-item"') == len(PRODUCTS) - 5
    assert 'class="next"' not in second


def test_page_past_the_end_is_404(client):
    assert client.get("/products?page=3").status_code == 404


def test_product_page_lists_offers(client):
    html = client.get("/products/p01").text

    assert "무선 이어폰 A100" in html
    assert html.count('<tr class="offer') == len(PRODUCTS[0].base_prices)
    assert "가격 기준: 2026-10-25 14:00 (한국 시간)" in html


def test_unknown_product_is_404(client):
    assert client.get("/products/p99").status_code == 404
