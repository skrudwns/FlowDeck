"""포털 API와 CLI가 같이 쓰는 제어 동작. 규칙과 이유는 docs/adr/0011.

바꾼 것은 모두 audit_log에 남긴다. 인증이 없어서 누가 했는지는 경로(portal, cli)로만 남긴다.
"""

import logging
from datetime import datetime
from typing import Protocol

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from flowdeck.danawa import SOURCE as DANAWA
from flowdeck.github_dispatch import DispatchError, DispatchResult
from flowdeck.jobs import Job
from flowdeck.models import AuditLog, JobSchedule, Product, RunRequest
from flowdeck.scheduler import (
    INTERVAL_CHOICES,
    Schedule,
    get_schedule,
    has_pending_request,
    hourly_limit_until,
)

# ADR-0004 수집 원칙 1(20개 안팎)이 포털 입력으로 깨지지 않게 하는 상한. 20에 여유를 둔 값
MAX_ACTIVE_DANAWA = 30

log = logging.getLogger(__name__)


class ControlError(Exception):
    """요청을 받을 수 없는 이유. status는 API 응답 코드로 쓴다."""

    def __init__(self, message: str, status: int = 409):
        super().__init__(message)
        self.status = status


class Dispatcher(Protocol):
    def dispatch(self, inputs: dict[str, str]) -> DispatchResult: ...


def _log(
    session: Session, now: datetime, actor: str, action: str, target: str, detail: str | None
) -> None:
    session.add(AuditLog(at=now, actor=actor, action=action, target=target, detail=detail))


def _active_danawa_count(session: Session) -> int:
    return session.scalar(
        select(func.count()).select_from(Product).where(Product.source == DANAWA, Product.active)
    )


def _check_capacity(session: Session) -> None:
    if _active_danawa_count(session) >= MAX_ACTIVE_DANAWA:
        raise ControlError(
            f"다나와 수집 대상은 {MAX_ACTIVE_DANAWA}개까지 (ADR-0004 수집 원칙 1). "
            "다른 상품을 중지한 뒤 추가한다"
        )


def add_danawa_product(session: Session, pcode: str, actor: str, now: datetime) -> Product:
    """없으면 추가하고, 중지된 상품이면 다시 켠다."""
    pcode = pcode.strip()
    if not pcode.isdigit():
        raise ControlError(f"pcode는 숫자여야 함: {pcode!r}", status=422)
    product = session.scalar(
        select(Product).where(Product.source == DANAWA, Product.source_product_id == pcode)
    )
    if product is not None and product.active:
        raise ControlError(f"이미 수집 중인 상품: {pcode}")
    _check_capacity(session)

    if product is None:
        product = Product(source=DANAWA, source_product_id=pcode, active=True)
        session.add(product)
        _log(session, now, actor, "product_added", f"danawa:{pcode}", None)
    else:
        product.active = True
        _log(session, now, actor, "product_reactivated", f"danawa:{pcode}", product.name)
    session.commit()
    return product


def set_product_active(
    session: Session, product: Product, active: bool, actor: str, now: datetime
) -> Product:
    if product.source != DANAWA:
        raise ControlError("연습 쇼핑몰 상품은 쇼핑몰 상품 목록으로 정해진다 (ADR-0010)")
    if product.active == active:
        return product
    if active:
        _check_capacity(session)
    product.active = active
    action = "product_reactivated" if active else "product_deactivated"
    _log(session, now, actor, action, f"danawa:{product.source_product_id}", product.name)
    session.commit()
    return product


def update_schedule(
    session: Session,
    job: Job,
    actor: str,
    now: datetime,
    interval_hours: int | None = None,
    enabled: bool | None = None,
) -> Schedule:
    if interval_hours is not None and interval_hours not in INTERVAL_CHOICES:
        choices = ", ".join(str(c) for c in INTERVAL_CHOICES)
        raise ControlError(f"주기는 {choices}시간 중 하나", status=422)
    before = get_schedule(session, job.id)
    after = Schedule(
        interval_hours=before.interval_hours if interval_hours is None else interval_hours,
        enabled=before.enabled if enabled is None else enabled,
    )
    if after == before:
        return before

    row = session.get(JobSchedule, job.id)
    if row is None:
        row = JobSchedule(job_id=job.id)
        session.add(row)
    row.interval_hours = after.interval_hours
    row.enabled = after.enabled
    row.updated_at = now
    detail = f"{_describe(before)} → {_describe(after)}"
    _log(session, now, actor, "schedule_changed", job.id, detail)
    session.commit()
    return after


def _describe(schedule: Schedule) -> str:
    return schedule.label + ("" if schedule.enabled else ", 꺼짐")


def manual_run_block(session: Session, job: Job, now: datetime) -> str | None:
    """지금 수동 실행 요청을 받을 수 없는 이유. 받을 수 있으면 None."""
    if has_pending_request(session, job):
        return "이미 대기 중인 실행 요청이 있음"
    until = hourly_limit_until(session, job, now)
    if until is not None:
        return f"이번 시에 이미 수집함. 다나와는 한 시에 한 번만 수집 ({until:%H:%M}부터 가능)"
    return None


def request_run(
    session: Session, job: Job, actor: str, now: datetime, dispatcher: Dispatcher | None
) -> RunRequest:
    """요청을 큐에 넣고, dispatcher가 있으면 워크플로를 바로 실행한다.
    바로 실행하지 못해도 요청은 남아서 다음 정기 호출 때 실행된다."""
    reason = manual_run_block(session, job, now)
    if reason is not None:
        raise ControlError(reason)

    request = RunRequest(job_id=job.id, requested_at=now, status="pending")
    session.add(request)
    _log(session, now, actor, "run_requested", job.id, None)
    session.commit()

    if dispatcher is None:
        return request
    try:
        result = dispatcher.dispatch({"trigger": "portal"})
    except DispatchError as e:
        log.warning("워크플로 바로 실행 실패: %s", e)
        request.dispatch_error = str(e)
    else:
        request.dispatched_at = now
        request.workflow_run_url = result.html_url
    session.commit()
    return request
