"""수집 실행 한 번: 활성 상품마다 요청 → 파싱 → 저장.

- 상품 하나가 끝날 때마다 커밋해서, 중간에 멈춰도 그때까지 결과는 남는다.
- 실패도 상태와 원인을 price_snapshots에 남긴다 (#2 완료 기준).
- 차단(403, 429)을 받으면 남은 상품은 요청하지 않고 멈춘다 (ADR-0004 수집 원칙 5).
"""

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Protocol

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from flowdeck.danawa.parser import ParseError, parse_product_page
from flowdeck.models import CollectionRun, PriceSnapshot, Product, SellerPrice
from flowdeck.polite_http import Blocked, DisallowedByRobots, Response

SOURCE = "danawa"

log = logging.getLogger(__name__)


class ProductFetcher(Protocol):
    def fetch_product(self, pcode: str) -> Response: ...


def utc_now() -> datetime:
    return datetime.now(UTC)


def run_collection(
    session_factory: sessionmaker[Session],
    fetcher: ProductFetcher,
    trigger: str = "schedule",
    now: Callable[[], datetime] = utc_now,
) -> CollectionRun:
    with session_factory() as session:
        run = CollectionRun(
            started_at=now(),
            status="running",
            trigger=trigger,
            products_total=0,
            products_succeeded=0,
        )
        session.add(run)
        session.commit()

        try:
            _collect_all(session, run, fetcher, now)
        except Exception as e:
            # 예상 못 한 오류라도 실행 기록이 running으로 남지 않게 닫는다
            session.rollback()
            run.status = "failed"
            run.error_message = f"예상하지 못한 오류: {e!r}"
            run.finished_at = now()
            session.commit()
            raise

        run.finished_at = now()
        session.commit()
        return run


def _collect_all(
    session: Session, run: CollectionRun, fetcher: ProductFetcher, now: Callable[[], datetime]
) -> None:
    products = session.scalars(
        select(Product).where(Product.source == SOURCE, Product.active).order_by(Product.id)
    ).all()
    run.products_total = len(products)
    session.commit()

    if not products:
        run.status = "failed"
        run.error_message = "수집 대상 상품이 없음"
        return

    blocked = False
    for product in products:
        try:
            snapshot = _collect_one(fetcher, product, now)
        except Blocked as e:
            session.add(
                PriceSnapshot(
                    run=run,
                    product=product,
                    collected_at=now(),
                    status="blocked",
                    http_status=e.status_code,
                    error_message=str(e),
                )
            )
            run.error_message = (
                f"pcode {product.source_product_id}에서 {e}. 남은 상품은 수집하지 않음"
            )
            log.warning(run.error_message)
            blocked = True
            session.commit()
            break

        snapshot.run = run
        session.add(snapshot)
        if snapshot.status == "ok":
            run.products_succeeded += 1
        else:
            log.warning(
                "pcode %s: %s %s",
                product.source_product_id,
                snapshot.status,
                snapshot.error_message,
            )
        session.commit()

    if run.products_succeeded == run.products_total and not blocked:
        run.status = "success"
    elif run.products_succeeded == 0:
        run.status = "failed"
    else:
        run.status = "partial"


def _collect_one(
    fetcher: ProductFetcher, product: Product, now: Callable[[], datetime]
) -> PriceSnapshot:
    pcode = product.source_product_id

    def failed(status: str, message: str, http_status: int | None = None) -> PriceSnapshot:
        return PriceSnapshot(
            product=product,
            collected_at=now(),
            status=status,
            http_status=http_status,
            error_message=message,
        )

    try:
        response = fetcher.fetch_product(pcode)
    except DisallowedByRobots as e:
        return failed("disallowed", f"robots.txt가 막은 경로: {e}")
    except httpx.HTTPError as e:
        return failed("http_error", f"요청 실패: {e!r}")

    if response.status_code != 200:
        return failed("http_error", f"HTTP {response.status_code}", response.status_code)

    try:
        page = parse_product_page(response.text)
    except ParseError as e:
        return failed("parse_failed", str(e), response.status_code)

    if not product.name and page.name:
        product.name = page.name

    return PriceSnapshot(
        product=product,
        collected_at=now(),
        status="ok",
        http_status=response.status_code,
        lowest_price=page.lowest_price,
        offer_count=page.offer_count,
        # 판매처 목록만 못 읽은 경우 이유를 남긴다
        error_message=page.seller_error,
        sellers=[
            SellerPrice(
                rank=s.rank,
                seller_name=s.name,
                seller_code=s.code,
                price=s.price,
                delivery_fee=s.delivery_fee,
            )
            for s in page.sellers
        ],
    )
