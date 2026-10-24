from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from flowdeck.api.deps import SessionDep
from flowdeck.api.schemas import RunDetail, RunOut, RunProductResult
from flowdeck.models import CollectionRun, PriceSnapshot

router = APIRouter(prefix="/runs", tags=["runs"])


@router.get("")
def list_runs(
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[RunOut]:
    """수집 실행 이력. 최신순."""
    rows = session.scalars(
        select(CollectionRun)
        .order_by(CollectionRun.started_at.desc(), CollectionRun.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return [RunOut.model_validate(r) for r in rows]


@router.get("/{run_id}")
def get_run(run_id: int, session: SessionDep) -> RunDetail:
    """실행 하나와 상품별 결과. 실패한 상품은 원인이 함께 나온다."""
    run = session.scalar(
        select(CollectionRun)
        .where(CollectionRun.id == run_id)
        .options(selectinload(CollectionRun.snapshots).selectinload(PriceSnapshot.product))
    )
    if run is None:
        raise HTTPException(status_code=404, detail="수집 실행을 찾지 못함")
    results = [
        RunProductResult(
            snapshot_id=s.id,
            product_id=s.product_id,
            source_product_id=s.product.source_product_id,
            status=s.status,
            http_status=s.http_status,
            lowest_price=s.lowest_price,
            error_message=s.error_message,
        )
        for s in sorted(run.snapshots, key=lambda s: s.id)
    ]
    return RunDetail(**RunOut.model_validate(run).model_dump(), results=results)
