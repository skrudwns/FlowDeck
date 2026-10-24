from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from flowdeck.api.deps import SessionDep
from flowdeck.api.schemas import SellerOut
from flowdeck.models import PriceSnapshot, SellerPrice

router = APIRouter(prefix="/snapshots", tags=["snapshots"])


@router.get("/{snapshot_id}/sellers")
def list_sellers(snapshot_id: int, session: SessionDep) -> list[SellerOut]:
    """수집 한 번의 상위 판매처. 판매처 목록을 못 읽은 수집이면 빈 목록이다."""
    if session.get(PriceSnapshot, snapshot_id) is None:
        raise HTTPException(status_code=404, detail="수집 결과를 찾지 못함")
    rows = session.scalars(
        select(SellerPrice).where(SellerPrice.snapshot_id == snapshot_id).order_by(SellerPrice.rank)
    ).all()
    return [SellerOut.model_validate(r) for r in rows]
