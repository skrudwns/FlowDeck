from pathlib import Path

import pytest
from sqlalchemy import select

from flowdeck.collector import run_collection
from flowdeck.danawa.parser import parse_product_page
from flowdeck.models import CollectionRun, PriceSnapshot, Product, SellerPrice
from flowdeck.polite_http import Blocked, Response
from flowdeck.sources import ListedProduct, Source

PAGE = (Path(__file__).parent / "fixtures" / "danawa_product.html").read_text(encoding="utf-8")


class FakeFetcher:
    """pcode별로 정해 둔 응답을 돌려준다. 값이 예외면 그 예외를 던진다."""

    def __init__(self, responses):
        self.responses = responses
        self.requested: list[str] = []

    def fetch_product(self, pcode):
        self.requested.append(pcode)
        result = self.responses[pcode]
        if isinstance(result, Exception):
            raise result
        return result


def source(fetcher):
    return Source(name="danawa", fetch_product=fetcher.fetch_product, parse=parse_product_page)


def add_products(session_factory, *pcodes, active=True):
    with session_factory() as session:
        for pcode in pcodes:
            session.add(Product(source="danawa", source_product_id=pcode, active=active))
        session.commit()


def snapshots(session_factory):
    with session_factory() as session:
        rows = session.scalars(select(PriceSnapshot).order_by(PriceSnapshot.id)).all()
        return [
            (r.product.source_product_id, r.status, r.lowest_price, len(r.sellers)) for r in rows
        ]


def ok():
    return Response(status_code=200, text=PAGE)


def test_saves_prices_and_sellers(session_factory):
    add_products(session_factory, "1", "2")

    run = run_collection(session_factory, source(FakeFetcher({"1": ok(), "2": ok()})))

    assert (run.status, run.products_total, run.products_succeeded) == ("success", 2, 2)
    assert run.finished_at is not None
    assert snapshots(session_factory) == [("1", "ok", 50000, 2), ("2", "ok", 50000, 2)]


def test_records_source_on_run_and_stock_on_sellers(session_factory):
    add_products(session_factory, "1")

    run = run_collection(session_factory, source(FakeFetcher({"1": ok()})))

    with session_factory() as session:
        assert session.get(CollectionRun, run.id).source == "danawa"
        assert session.scalars(select(SellerPrice.in_stock)).all() == [True, True]


def test_fills_product_name_from_page(session_factory):
    add_products(session_factory, "1")

    run_collection(session_factory, source(FakeFetcher({"1": ok()})))

    with session_factory() as session:
        assert session.scalar(select(Product.name)) == "테스트 상품 A"


def test_skips_inactive_products(session_factory):
    add_products(session_factory, "1")
    add_products(session_factory, "2", active=False)
    fetcher = FakeFetcher({"1": ok()})

    run_collection(session_factory, source(fetcher))

    assert fetcher.requested == ["1"]


def test_records_failures_and_marks_run_partial(session_factory):
    add_products(session_factory, "1", "2", "3")
    fetcher = FakeFetcher(
        {
            "1": ok(),
            "2": Response(status_code=500, text="error"),
            "3": Response(status_code=200, text="<html>구조가 바뀐 페이지</html>"),
        }
    )

    run = run_collection(session_factory, source(fetcher))

    assert run.status == "partial"
    assert snapshots(session_factory) == [
        ("1", "ok", 50000, 2),
        ("2", "http_error", None, 0),
        ("3", "parse_failed", None, 0),
    ]


def test_stops_when_blocked(session_factory):
    add_products(session_factory, "1", "2", "3")
    fetcher = FakeFetcher({"1": ok(), "2": Blocked(429), "3": ok()})

    run = run_collection(session_factory, source(fetcher))

    assert fetcher.requested == ["1", "2"]
    assert run.status == "partial"
    assert "429" in run.error_message
    assert snapshots(session_factory) == [("1", "ok", 50000, 2), ("2", "blocked", None, 0)]


def test_fails_when_there_is_nothing_to_collect(session_factory):
    run = run_collection(session_factory, source(FakeFetcher({})))

    assert run.status == "failed"
    assert run.products_total == 0


def test_closes_run_on_unexpected_error(session_factory):
    add_products(session_factory, "1")

    with pytest.raises(KeyError):
        run_collection(session_factory, source(FakeFetcher({})))

    with session_factory() as session:
        run = session.scalar(select(CollectionRun))
        assert run.status == "failed"
        assert run.finished_at is not None


def listing_source(fetcher, listed):
    """상품 목록을 찾는 수집 대상. listed가 예외면 목록 수집이 그 예외로 실패한다."""

    def discover():
        if isinstance(listed, Exception):
            raise listed
        return [ListedProduct(product_id=i, name=f"상품 {i}") for i in listed]

    return Source(
        name="danawa",
        fetch_product=fetcher.fetch_product,
        parse=parse_product_page,
        discover=discover,
    )


def products(session_factory):
    with session_factory() as session:
        rows = session.scalars(select(Product).order_by(Product.source_product_id)).all()
        return [(p.source_product_id, p.active) for p in rows]


def test_discovered_products_are_added_and_collected(session_factory):
    fetcher = FakeFetcher({"1": ok(), "2": ok()})

    run = run_collection(session_factory, listing_source(fetcher, ["1", "2"]))

    assert run.status == "success"
    assert fetcher.requested == ["1", "2"]
    assert products(session_factory) == [("1", True), ("2", True)]


def test_products_missing_from_listing_are_deactivated(session_factory):
    add_products(session_factory, "1", "2")
    fetcher = FakeFetcher({"1": ok()})

    run_collection(session_factory, listing_source(fetcher, ["1"]))

    assert fetcher.requested == ["1"]
    assert products(session_factory) == [("1", True), ("2", False)]


def test_name_from_listing_is_kept_when_page_has_one(session_factory):
    run_collection(session_factory, listing_source(FakeFetcher({"1": ok()}), ["1"]))

    with session_factory() as session:
        # 목록에서 먼저 이름을 채우고, 상품 페이지 이름으로 덮어쓰지 않는다
        assert session.scalar(select(Product.name)) == "상품 1"


def test_run_fails_when_listing_cannot_be_read(session_factory):
    add_products(session_factory, "1")
    fetcher = FakeFetcher({"1": ok()})

    run = run_collection(session_factory, listing_source(fetcher, Blocked(429)))

    assert run.status == "failed"
    assert run.error_message == "상품 목록 수집 실패: 차단 응답 429"
    assert fetcher.requested == []
    assert products(session_factory) == [("1", True)]
