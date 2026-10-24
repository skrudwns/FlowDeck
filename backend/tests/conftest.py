import os

import pytest
from sqlalchemy.exc import OperationalError

from flowdeck.db import make_engine, make_session_factory
from flowdeck.models import Base

# 개발 DB(flowdeck)와 분리된 테스트 전용 DB. compose.yaml의 Postgres에 만들어 둔다.
DEFAULT_TEST_DATABASE_URL = "postgresql://flowdeck:flowdeck@localhost:5433/flowdeck_test"


@pytest.fixture
def session_factory():
    engine = make_engine(os.environ.get("TEST_DATABASE_URL", DEFAULT_TEST_DATABASE_URL))
    try:
        engine.connect().close()
    except OperationalError:
        # CI에서는 건너뛰면 DB 테스트 없이 통과로 보이므로 실패시킨다
        if os.environ.get("REQUIRE_TEST_DB"):
            raise
        pytest.skip("테스트 DB에 연결할 수 없음 (docker compose up -d 필요)")

    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield make_session_factory(engine)
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def seeded(session_factory):
    """API 테스트용 데이터.

    상품 A(활성), B(비활성). 실행 2번:
    - run1 (08:17 UTC): A 50,000원, B 30,000원
    - run2 (09:17 UTC): A 48,000원(판매처 2곳), B 요청 실패
    """
    from datetime import UTC, datetime

    from flowdeck.models import CollectionRun, PriceSnapshot, Product, SellerPrice

    t1 = datetime(2026, 10, 24, 8, 17, tzinfo=UTC)
    t2 = datetime(2026, 10, 24, 9, 17, tzinfo=UTC)
    with session_factory() as session:
        a = Product(source="danawa", source_product_id="111", name="상품 A", active=True)
        b = Product(source="danawa", source_product_id="222", name="상품 B", active=False)
        run1 = CollectionRun(
            started_at=t1,
            finished_at=t1,
            status="success",
            trigger="schedule",
            products_total=2,
            products_succeeded=2,
        )
        run2 = CollectionRun(
            started_at=t2,
            finished_at=t2,
            status="partial",
            trigger="schedule",
            products_total=2,
            products_succeeded=1,
        )
        session.add_all([a, b, run1, run2])
        session.add_all(
            [
                PriceSnapshot(
                    run=run1,
                    product=a,
                    collected_at=t1,
                    status="ok",
                    http_status=200,
                    lowest_price=50000,
                    offer_count=10,
                ),
                PriceSnapshot(
                    run=run1,
                    product=b,
                    collected_at=t1,
                    status="ok",
                    http_status=200,
                    lowest_price=30000,
                    offer_count=5,
                ),
            ]
        )
        latest_a = PriceSnapshot(
            run=run2,
            product=a,
            collected_at=t2,
            status="ok",
            http_status=200,
            lowest_price=48000,
            offer_count=11,
            sellers=[
                SellerPrice(
                    rank=1, seller_name="가나몰", seller_code="AAA01", price=48000, delivery_fee=0
                ),
                SellerPrice(
                    rank=2,
                    seller_name="다라스토어",
                    seller_code=None,
                    price=49000,
                    delivery_fee=3000,
                ),
            ],
        )
        failed_b = PriceSnapshot(
            run=run2,
            product=b,
            collected_at=t2,
            status="http_error",
            http_status=500,
            error_message="HTTP 500",
        )
        session.add_all([latest_a, failed_b])
        session.commit()
        return {
            "a": a.id,
            "b": b.id,
            "run1": run1.id,
            "run2": run2.id,
            "latest_a": latest_a.id,
            "failed_b": failed_b.id,
        }


@pytest.fixture
def api(session_factory):
    """테스트 DB를 쓰는 API 클라이언트."""
    from fastapi.testclient import TestClient

    from flowdeck.api.app import create_app
    from flowdeck.api.deps import get_session

    app = create_app()

    def test_session():
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = test_session
    with TestClient(app) as client:
        yield client
