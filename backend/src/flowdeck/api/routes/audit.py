from typing import Annotated

from fastapi import APIRouter, Query
from sqlalchemy import select

from flowdeck.api.deps import SessionDep
from flowdeck.api.schemas import AuditLogOut
from flowdeck.models import AuditLog

router = APIRouter(prefix="/audit-log", tags=["audit"])


@router.get("")
def list_audit_log(
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[AuditLogOut]:
    """수집 대상, 주기, 수동 실행 변경 이력. 최신순."""
    rows = session.scalars(
        select(AuditLog)
        .order_by(AuditLog.at.desc(), AuditLog.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return [AuditLogOut.model_validate(r) for r in rows]
