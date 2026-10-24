from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import distinct_on

from flowdeck.api.deps import SessionDep
from flowdeck.api.schemas import LatestResult, ProductOut
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


@router.get("/{product_id}")
def get_product(product_id: int, session: SessionDep) -> ProductOut:
    product = session.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="상품을 찾지 못함")
    return _to_out(product, _latest_results(session, [product.id]).get(product.id))
