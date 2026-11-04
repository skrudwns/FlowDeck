from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import exists, func, select
from sqlalchemy.dialects.postgresql import distinct_on

from flowdeck.api.deps import SessionDep
from flowdeck.api.schemas import (
    CONTROL_ERRORS,
    LatestResult,
    PriceChangeOut,
    PricePoint,
    ProductCreate,
    ProductOut,
    ProductSignals,
    ProductUpdate,
    SellerOut,
    SellerSignalOut,
    SignalRules,
)
from flowdeck.control import add_danawa_product, set_product_active
from flowdeck.models import PriceSnapshot, Product, SellerPrice
from flowdeck.signals import (
    CASH_LABEL,
    CHANGE_MIN_PCT,
    CHANGE_PERSIST,
    CHEAPER_MIN_PCT,
    USUAL_WINDOW,
    SellerOffer,
    price_changes,
    seller_key,
    seller_positions,
)

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


@router.get("/{product_id}/signals")
def get_signals(
    product_id: int,
    session: SessionDep,
    days: Annotated[int, Query(ge=1, le=30)] = 7,
) -> ProductSignals:
    """가격 신호. 저장하지 않고 요청 때 수집 기록에서 계산한다 (ADR-0014).

    - 최저가 변화: 가장 최근 정상 수집부터 지난 days일
    - 판매처 위치: 판매처 목록이 있는 가장 최근 수집. 평소 가격은 그 전 7일
    """
    if session.get(Product, product_id) is None:
        raise HTTPException(status_code=404, detail="상품을 찾지 못함")
    ok = (
        PriceSnapshot.product_id == product_id,
        PriceSnapshot.status == "ok",
    )
    rules = SignalRules(
        change_min_pct=CHANGE_MIN_PCT,
        change_persist=CHANGE_PERSIST,
        cheaper_min_pct=CHEAPER_MIN_PCT,
        usual_days=USUAL_WINDOW.days,
    )

    changes = []
    latest_at = session.scalar(
        select(func.max(PriceSnapshot.collected_at)).where(
            *ok, PriceSnapshot.lowest_price.is_not(None)
        )
    )
    if latest_at is not None:
        rows = session.execute(
            select(PriceSnapshot.collected_at, PriceSnapshot.lowest_price)
            .where(
                *ok,
                PriceSnapshot.lowest_price.is_not(None),
                PriceSnapshot.collected_at >= latest_at - timedelta(days=days),
            )
            .order_by(PriceSnapshot.collected_at, PriceSnapshot.id)
        ).all()
        changes = [
            PriceChangeOut(at=c.at, before=c.before, after=c.after, pct=c.pct)
            for c in price_changes([(r.collected_at, r.lowest_price) for r in rows])
        ]

    snapshot = session.scalars(
        select(PriceSnapshot)
        .where(*ok, exists().where(SellerPrice.snapshot_id == PriceSnapshot.id))
        .order_by(PriceSnapshot.collected_at.desc(), PriceSnapshot.id.desc())
        .limit(1)
    ).first()
    if snapshot is None:
        return ProductSignals(
            rules=rules,
            changes=changes,
            sellers_snapshot_id=None,
            sellers_collected_at=None,
            sellers=[],
        )

    def key(code: str | None, name: str, label: str | None) -> str:
        return seller_key(code, name, label == CASH_LABEL)

    history: dict[str, list[int]] = {}
    past = session.execute(
        select(
            SellerPrice.seller_code,
            SellerPrice.seller_name,
            SellerPrice.price_label,
            SellerPrice.price,
        )
        .join(PriceSnapshot, PriceSnapshot.id == SellerPrice.snapshot_id)
        .where(
            *ok,
            SellerPrice.in_stock,
            PriceSnapshot.collected_at >= snapshot.collected_at - USUAL_WINDOW,
            PriceSnapshot.collected_at < snapshot.collected_at,
        )
    ).all()
    for r in past:
        history.setdefault(key(r.seller_code, r.seller_name, r.price_label), []).append(r.price)

    current = [
        SellerOffer(
            key=key(s.seller_code, s.seller_name, s.price_label),
            price=s.price,
            in_stock=s.in_stock,
            cash=s.price_label == CASH_LABEL,
        )
        for s in snapshot.sellers
    ]
    positions = seller_positions(current, history)
    sellers = []
    for s, o in zip(snapshot.sellers, current, strict=True):
        pos = positions[o.key]
        sellers.append(
            SellerSignalOut(
                **SellerOut.model_validate(s).model_dump(),
                vs_others_pct=pos.vs_others_pct if pos else None,
                others_count=pos.others_count if pos else None,
                usual_price=pos.usual_price if pos else None,
                vs_usual_pct=pos.vs_usual_pct if pos else None,
                usual_points=pos.usual_points if pos else None,
                cheaper_than_others=bool(pos and pos.cheaper_than_others),
                cheaper_than_usual=bool(pos and pos.cheaper_than_usual),
            )
        )
    return ProductSignals(
        rules=rules,
        changes=changes,
        sellers_snapshot_id=snapshot.id,
        sellers_collected_at=snapshot.collected_at,
        sellers=sellers,
    )
