from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import distinct_on

from flowdeck.api.deps import SessionDep
from flowdeck.api.schemas import (
    CONTROL_ERRORS,
    LatestResult,
    PricePoint,
    ProductCreate,
    ProductOut,
    ProductUpdate,
)
from flowdeck.control import add_danawa_product, set_product_active
from flowdeck.models import PriceSnapshot, Product

router = APIRouter(prefix="/products", tags=["products"])


def _latest_results(session, product_ids: list[int]) -> dict[int, LatestResult]:
    """상품마다 가장 최근 스냅샷 하나. Postgres DISTINCT ON을 쓴다."""
    if not product_ids:
        return {}
    rows = session.scalars(
        select(PriceSnapshot)
        .where(PriceSnapshot.product_id.in_(product_ids))
        .ext(distinct_on(PriceSnapshot.product_id))
        .order_by(
            PriceSnapshot.product_id,
            PriceSnapshot.collected_at.desc(),
            PriceSnapshot.id.desc(),
        )
    ).all()
    return {
        s.product_id: LatestResult(
            snapshot_id=s.id,
            collected_at=s.collected_at,
            status=s.status,
            lowest_price=s.lowest_price,
            offer_count=s.offer_count,
        )
        for s in rows
    }


def _to_out(product: Product, latest: LatestResult | None) -> ProductOut:
    out = ProductOut.model_validate(product)
    out.latest = latest
    return out


@router.get("")
def list_products(
    session: SessionDep,
    active: bool | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[ProductOut]:
    query = select(Product).order_by(Product.id).limit(limit).offset(offset)
    if active is not None:
        query = query.where(Product.active == active)
    products = session.scalars(query).all()
    latest = _latest_results(session, [p.id for p in products])
    return [_to_out(p, latest.get(p.id)) for p in products]


@router.post("", status_code=201, responses=CONTROL_ERRORS)
def create_product(body: ProductCreate, session: SessionDep) -> ProductOut:
    """다나와 pcode로 수집 대상 추가. 중지된 상품이면 다시 켠다. 활성 30개까지."""
    product = add_danawa_product(session, body.source_product_id, "portal", datetime.now(UTC))
    return _to_out(product, _latest_results(session, [product.id]).get(product.id))


@router.patch("/{product_id}", responses=CONTROL_ERRORS)
def update_product(product_id: int, body: ProductUpdate, session: SessionDep) -> ProductOut:
    """수집 중지·재개. 지우지 않아서 가격 기록은 남는다."""
    product = session.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="상품을 찾지 못함")
    set_product_active(session, product, body.active, "portal", datetime.now(UTC))
    return _to_out(product, _latest_results(session, [product.id]).get(product.id))


@router.get("/{product_id}")
def get_product(product_id: int, session: SessionDep) -> ProductOut:
    product = session.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="상품을 찾지 못함")
    return _to_out(product, _latest_results(session, [product.id]).get(product.id))


@router.get("/{product_id}/prices")
def list_prices(
    product_id: int,
    session: SessionDep,
    since: datetime | None = None,
    until: datetime | None = None,
    # 매시 수집이면 한 달에 약 720개. 차트 한 화면에 충분하도록 잡았다
    limit: Annotated[int, Query(ge=1, le=2000)] = 500,
) -> list[PricePoint]:
    """가격 이력. 시간 오름차순이고, limit을 넘으면 가장 최근 것부터 자른다."""
    if session.get(Product, product_id) is None:
        raise HTTPException(status_code=404, detail="상품을 찾지 못함")
    query = select(PriceSnapshot).where(PriceSnapshot.product_id == product_id)
    if since is not None:
        query = query.where(PriceSnapshot.collected_at >= since)
    if until is not None:
        query = query.where(PriceSnapshot.collected_at < until)
    rows = session.scalars(
        query.order_by(PriceSnapshot.collected_at.desc(), PriceSnapshot.id.desc()).limit(limit)
    ).all()
    return [
        PricePoint(
            snapshot_id=s.id,
            collected_at=s.collected_at,
            status=s.status,
            lowest_price=s.lowest_price,
            offer_count=s.offer_count,
        )
        for s in reversed(rows)
    ]
